# (c) 2022 Rodion Kosovsky released under the GPL v3

from aqt import mw, gui_hooks
from aqt.utils import showInfo
from anki.collection import Collection
from aqt.operations import QueryOp
from aqt.qt import *
from anki.utils import stripHTML
from .selector import SelectDialog
from .dialog import SoundDialog
import unicodedata
import re

#Lingua Libre Specific
import sparql
import requests
import datetime
import json
import random

# Used to save the audio
import os
from tempfile import gettempdir

# Used to get the audio from Forvo
import cfscrape

# Create global variable for the configuration settings.
separator = str()
prefixes = str()
suffixes = str()
find_and_replace = dict()
tag_missing = str()
text_field = str()
note_type = str()
deck_name = str()
audio_field = str()
language = list()
accent = str()
field_names = dict()
prefer_speakers = frozenset()
exclude_speakers = frozenset()
add_tag = str()
error_number = 0
error_strings = []
batch = bool
recheck_tag = str()
restrict_to_places = list()
prefer_locations = frozenset()


#Lingua Libre specific
# Header to use to download from Wiki Commons.
headers = {'User-Agent': 'Lingua Libre Anki Addon'}
database_file = str()
max_date = 1
ll_database = dict()
ll_database_json = os.path.join(os.path.dirname(__file__), "LinguaLibre.json")
locations = dict()
ll_locations_json = os.path.join(os.path.dirname(__file__), "Locations.json")
disable_Lingua_Libre = False
disable_Forvo = False

# Query for Lingua Libre
ENDPOINT = "https://lingualibre.org/bigdata/namespace/wdq/sparql"
API = "https://lingualibre.org/api.php"
BASEQUERY = """
SELECT DISTINCT
    ?record ?file ?transcription
    ?languageIso ?residence ?languageLevel
    ?speaker ?linkeduser
WHERE {
  ?record prop:P2 entity:Q2 .
  ?record prop:P3 ?file .
  ?record prop:P4 ?language .
  ?record prop:P5 ?speaker .
  ?record prop:P7 ?transcription .
  ?language prop:P13 ?languageIso.
  ?speaker prop:P11 ?linkeduser .
  ?speaker prop:P14 ?residence .
  ?speaker llp:P4 ?speakerLanguagesStatement .
  ?speakerLanguagesStatement llq:P16 ?languageLevel .
  ?speakerLanguagesStatement llv:P4 ?speakerLanguages .
  FILTER( ?speakerLanguages = ?language) .
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}"""


# Read the setting for the chosen configuration and make them global
def get_config_batch():

    # Grab the entire configuration file
    config = mw.addonManager.getConfig(__name__)

    test = list(config.keys())
    select_dialog = SelectDialog(mw, test)
    res = select_dialog.wait_for_result()
    if res == QDialog.Accepted:
        selected_config = test[select_dialog.selected]
        desired_config = config[selected_config]
        process_config(desired_config)
        return True
    else:
        return False


def get_config_note():
    # Grab the entire configuration file
    config = mw.addonManager.getConfig(__name__)
    keys = config.keys()

    for k in keys:
        if "note type" in config[k].keys() and config[k]['note type'] == note_type:
            process_config(config[k])
            return True

    return False


def process_config(config):
    global note_type, field_names, language
    global separator, prefixes, suffixes, find_and_replace
    global accent, prefer_speakers, exclude_speakers, tag_missing, deck_name, add_tag, recheck_tag
    global restrict_to_places, prefer_locations, max_date, disable_Forvo, disable_Lingua_Libre
    config_fields = []

    # reset all config variables
    separator = prefixes = suffixes = tag_missing = note_type = deck_name = language = accent = add_tag = str()
    find_and_replace = field_names = dict()
    prefer_speakers = exclude_speakers = list()
    recheck_tag = ""

    keys = [*config]

    # These are required
    if "note type" and "language" and "fields" in keys:
        note_type = config['note type']
        field_names = config['fields']
        language = config['language']
    else:
        showInfo("Missing Required Field")
        return

    # These are used for textual manipulation
    if "separator" in keys:
        separator = config['separator']
    if "prefixes" in keys:
        prefixes = config['prefixes']
    if "suffixes" in keys:
        suffixes = config['suffixes']
    if "find_and_replace" in keys:
        find_and_replace = config['find_and_replace']
    if "remove" in keys:
        # First convert the replacement values to a dictionary, then merge it with find_and_replace dictionary
        replace = dict.fromkeys(config['remove'], "")
        find_and_replace = find_and_replace | replace

    # Optional parameters
    if "deck" in keys:
        deck_name = config['deck']
    if "accent" in keys:
        accent = config['accent']
    if "prefer_speakers" in keys:
        prefer_speakers = config['prefer_speakers']
    if "exclude_speakers" in keys:
        exclude_speakers = config['exclude_speakers']
    if "tag_missing" in keys:
        tag_missing = config['tag_missing']
    if "add_tag" in keys:
        add_tag = config['add_tag']
    if "recheck_tag" in keys:
        recheck_tag = config['recheck_tag']
    if "restrict_to_places" in keys:
        restrict_to_places = config['restrict_to_places']
    if "prefer_locations" in keys:
        prefer_locations = config['prefer_locations']
    if "max_date" in keys:
        max_date = config['max_date']
    if "disable_Forvo" in keys:
        disable_Forvo = config['disable_Forvo']
    if "disable_Lingua_Libre" in keys:
        disable_Lingua_Libre = config['disable_Lingua_Libre']

    # check to make sure that the provided field names are valid
    for k, v in field_names.items():
        config_fields.extend([k, v])

    if check_fields(config_fields):
        return True
    else:
        return False


# Perform all the textual manipulation
def process_text(text):
    # start by removing any html tags
    text = stripHTML(text).strip()

    # either split the text or put the text into a list
    if separator:
        text_strings = text.split(separator)
    else:
        text_strings = [text]

    for i in range(len(text_strings)):
        # strip any remaining whitespace
        text_strings[i] = text_strings[i].strip()

        # Remove prefixes
        for prefix in prefixes:
            if text_strings[i].startswith(prefix):
                text_strings[i] = text_strings[i].removeprefix(prefix)
                break

        # Remove suffixes
        for suffix in suffixes:
            if text_strings[i].endswith(suffix):
                text_strings[i] = text_strings[i].removesuffix(suffix)
                break

        # Perform all replacement.
        for k, v in find_and_replace.items():
            text_strings[i] = text_strings[i].replace(k, v)

        # strip any remaining whitespace
        text_strings[i] = text_strings[i].strip()

    return text_strings


def slugify(value):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    value = unicodedata.normalize('NFKC', value)
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


def fetch_ll_database():
    global ll_database

    # Run the sparql query to fetch the results
    raw_records = sparql.request(ENDPOINT, BASEQUERY.replace("#filters", ""))

    # Loop through the records returned by the sparql query and move them into a dictionary.
    for record in raw_records:

        # Write the transcription and the speaker because they get used several times.
        current_term = sparql.format_value(record, "transcription")
        speaker = sparql.format_value(record, "linkeduser")

        # If the speaker is not a native speaker, move to the next record.
        if sparql.format_value(record, "languageLevel") != "Q15":
            continue

        # If the term is not in the dictionary, then add it to the dictionary.
        if current_term not in ll_database:
            ll_database[current_term] = {}

        # Store the record for the speaker as a nested dictionary under the current_term key
        ll_database[current_term][speaker] = {"file": sparql.format_value(record, "file"),
                                              "language": sparql.format_value(record, "languageIso"),
                                              "residence": sparql.format_value(record, "residence")}

    # Save the dictionary as utf-8 json file to speed up the next operation.
    with open(ll_database_json, 'w', encoding='utf8') as outfile:
        json.dump(ll_database, outfile, indent=4, ensure_ascii=False)


def load_ll_database():
    global ll_database, locations

    '''
    1) First get the date from the existing database. If to local database exist, fetch a new one
    2) If the existing database is younger than the max_date, load it. If the loading fails, fetch a new one.
    3) If the existing database is corrupt, fetch a new one.
    '''
    try:
        today = datetime.datetime.today()
        modified_date = datetime.datetime.fromtimestamp(os.path.getmtime(ll_database_json))
        duration = today - modified_date
        if duration.days < max_date:
            try:
                with open(ll_database_json, 'r', encoding='utf8') as f:
                    ll_database = json.load(f)
            except (FileNotFoundError, ValueError) as exception:
                fetch_ll_database()
        else:
            fetch_ll_database()
    except FileNotFoundError:
        fetch_ll_database()

    # Load the existing locations json file to speed up operations
    try:
        with open(ll_locations_json, 'r', encoding='utf8') as f:
            locations = json.load(f)
    except (FileNotFoundError, ValueError) as exception:
        return


def get_ll_results(terms):
    # Store the number of errors and the terms that produced the errors as global variable
    global error_number, error_strings

    # The filenames will contain a list of audio filenames to add to the note later.
    filenames = []

    # Since the terms variable is a list, loop through it and check each term individually
    for index, term in enumerate(terms):

        # Reset all the variable to avoid any problems
        filename = ""
        speaker = ""
        selection = ""
        entry = dict()
        available_speakers = []

        # Fetch the key in the Lingua Lingua dictionary.
        results = ll_database.get(term)

        # Only continue if there are pronunciations for the given term
        if results:

            # Create a reduced dictionary of acceptable pronunciations of the term
            for si, speaker in enumerate(results):

                # Gets the city, country corresponding to the Wikidata item
                place = results[speaker]['residence']
                if place not in locations:
                    get_location_labels(place)

                city = locations[place]['city']
                country = locations[place]['country']

                # Filters the results based on the user's criteria
                if ((city or country) in restrict_to_places or restrict_to_places == []) \
                        and speaker not in exclude_speakers\
                        and language[1] == results[speaker]['language']:
                    entry[speaker] = {"term": term, "speaker": speaker, "filename": results[speaker]['file'],
                                      "city": city, "country": country,
                                      "language": results[speaker]['language']}
                    available_speakers.append(speaker)
            '''
            Handles what to do with the acceptable pronunciations
            1) If its a batch operation and LL has acceptable pronunciations. 
                a) First check to see if there are pronunciations by the user's preferred speakers
                b) Then check if there are pronunciations in the user's preferred places
                c) Otherwise grab a random pronunciation
            2) If Lingua Libre does not have acceptable pronunciations, check Forvo and continue to the next term.
            '''
            # Only execute the following code if acceptable entries exists and this is a batch operation
            if entry and batch:

                # Checking if the results contain a pronunciation by a preferred speaker
                intersection = [x for x in prefer_speakers if x in available_speakers]

                # Since the prefer_speakers is a frozen set, the first entry will contain the user's top choice.
                if intersection:
                    speaker = intersection[0]
                # If not, check for a user's preferred places
                else:
                    places = [val['city'] for key, val in entry.items() if 'city' in val]

                    intersection = [x for x in prefer_locations if x in places]
                    '''
                    a) Since the prefer_speakers is a frozen set, the first entry will contain the user's top choice.
                    b) Since multiple pronunciations can exist, grab a random one.
                    '''
                    if intersection:
                        available_pronunciations = [key for key, val in entry.items() if val['city'] == intersection[0]]
                        speaker = random.choice(available_pronunciations)
                    # Otherwise, select a random pronunciation
                    else:
                        speaker = random.choice(available_speakers)

                # Now that the speaker is known, pull their information.
                selection = entry[speaker]

                # Use the speaker information to set the filename
                filename = set_ll_audio_string(selection)

                # Download the audio from commons using the filename on commons.
                audio = download_ll_audio(selection["filename"])

                # If the audio did not download, record the error and continue to the next term.
                if not audio:
                    error_number = error_number + 1
                    error_strings.append(f"LL: {term}")
                    continue

                # Save the audio to the anki media file
                save_audio(audio, filename)

                # Save the filename in the list of filenames that the function will return
                filenames.append(filename)

            # If no audio on Lingua Libre meets the user's criteria and this is a batch operation, check Forvo
            elif not disable_Forvo and batch:
                forvo = get_forvo_results([term])
                filenames.extend(forvo)

        # If Lingua Libre does not contain audio and this is a batch operation, check Forvo
        elif not disable_Forvo and batch:
            forvo = get_forvo_results([term])
            filenames.extend(forvo)

        # If the user presses the button to fetch an individual audio, a different logic applies.
        if not batch:
            # reset the variables
            term_filenames = []
            term_filename = ""
            audio_file_paths = []
            speakers = []

            '''
            To enable the playback of the audio, several things need to be done:
            1) Set the filename for each speaker and save it in a list
            2) Download the audio for each speaker and save it in a list
            3) Save the audio paths in a list as well
            4) Save the speaker name in a list'''
            for speaker in available_speakers:
                selection = entry[speaker]
                term_filename = set_ll_audio_string(selection)
                term_filenames.append(term_filename)
                audio = download_ll_audio(selection["filename"])
                if not audio:
                    error_number = error_number + 1
                    error_strings.append(f"LL: {term}")
                    continue

                audio_file_path = save_audio(audio, term_filename)
                audio_file_paths.append(audio_file_path)

            speakers = [f"Lingua Libre: {x}" for x in available_speakers]

            # If the user also wants to check Forvo,
            if not disable_Forvo:
                forvo_results = get_forvo_results([term])
                audio_file_paths.extend(forvo_results[0])
                speakers.extend([f"Forvo: {x}" for x in forvo_results[1]])
                term_filenames.extend(forvo_results[2])

            # Only show the speakers if there are available pronunciations
            if speakers:
                # Send the paths to the audio and the speaker names to the QT dialog
                sound_dialog = SoundDialog(mw, audio_file_paths, speakers)
                # Wait for a selection.
                res = sound_dialog.wait_for_result()

                """
                If the user made a selection, use the row number
                to move the appropriate audio to the anki media folder and 
                add the filename to the list  of filenames to add the audio field
                 """
                if res == QDialog.Accepted:
                    index = sound_dialog.selected
                    filenames.append(term_filenames[index])
                    mw.col.media.addFile(audio_file_paths[index])
            # If no audio is found, then let the user know.
            else:
                showInfo(f"No pronunciation found for {term}.")

    # Return the list of filenames to add to audio field.
    return filenames


def get_location_labels(qid):
    global locations
    url = 'https://query.wikidata.org/sparql'
    query = f'''
            SELECT DISTINCT ?city ?country ?countryLabel  WHERE {{
            wd:{qid} rdfs:label ?city.
            wd:{qid} wdt:P17 ?country.
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
            FILTER (LANG(?city) = "en")
            }}
                '''
    r = requests.get(url, headers=headers, params={'format': 'json', 'query': query})
    try:
        data = r.json()
    except:
        get_location_labels(qid)

    try:
        city = data['results']['bindings'][0]['city']['value']
        country = data['results']['bindings'][0]['countryLabel']['value']
        locations[qid] = {"city": city, "country": country}
    except IndexError:
        locations[qid] = {"city": "", "country": ""}


# sets the audio string used in the file name and audio field
def set_ll_audio_string(entry):

    city = entry['city']
    country = entry['country']

    #Creates the code for the place
    if city == country:
        place = f"{city}_"
    elif city:
        place = f"{city}, {country}_"
    else:
        place = ""

    audio_string = slugify(f"Lingua Libre_{entry['language']}_{entry['speaker']}_{place}{entry['term']}") + ".mp3"

    return audio_string


def download_ll_audio(filename):

    # In the url replace ? with %3F as Commons does.
    url = f"https://commons.wikimedia.org/wiki/File:{filename.replace('?', '%3F')}"


    # Download the HTML for the file
    content = requests.get(url, headers=headers).text

    '''
    Find the download link to the file in the HTML using a regex.
    If the file is not transcoded, then it has the same location in the html. 
    Otherwise, the specific transcoding requires finding.
    '''
    if filename.endswith("wav"):
        mp3_url = re.search(
            r'<source src="(https://upload.wikimedia.org/[\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])" '
            r'type="audio/mpeg" data-title="MP3" data-shorttitle="MP3" data-transcodekey="mp3"'
            r' data-width="0" data-height="0" data-bandwidth="\d*"/>', content)
        if mp3_url:
            download_url = mp3_url.groups()[0]
    else:
        common_url = re.search(
            r'<div class="fullMedia"><p><a href="(https://upload.wikimedia.org/[\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])"',
            content)
        if common_url:
            download_url = common_url.groups()[0]
        else:
            return False

    # Fetch the audio file from Common
    try:
        audio = requests.get(download_url, headers=headers)
    except:
        return False

    return audio


# Creates the text string for the audio field
def create_audio_field_string(filenames):
    audio_string = ""
    for i in range(len(filenames)):
        if 0 < i < len(filenames):
            audio_string = f"{audio_string}, "

        audio_string = f"{audio_string}[sound:{filenames[i]}]"

    return audio_string


def save_audio(audio, filename):
    save_name = os.path.join(gettempdir(), filename)
    try:
        with open(save_name, 'wb') as audio_file:
            for chunk in audio.iter_content(512):
                audio_file.write(chunk)

        if batch:
            mw.col.media.addFile(save_name)

        return save_name
    except OSError:
        pass


def sort_results(results, exclude_field, sort_field):
    # Remove the unwanted entries from the list of results
    sorted_results = {k: v for k, v in results.items() if k not in exclude_field}

    # sort the results according to the sort_field
    index_map = {v: i for i, v in enumerate(sort_field)}
    sorted_results = sorted(sorted_results.items(), key=lambda pair: index_map[pair[0]]
                                if pair[0] in sort_field else 999)

    return sorted_results


# Used to get the results from Forvo, can be used as either a batch or stand alone
def get_forvo_results(terms):
    global error_number, error_strings
    filenames = []

    for index, term in enumerate(terms):
        audio_file_paths = []
        filename = ""
        results = dict()

        # This constructs the url to retry and replaces ? with %253F as Forvo does.
        url = "https://forvo.com/word/" + term.replace("?", "%253F")
        scraper = cfscrape.CloudflareScraper()
        try:
            html = scraper.get(url).text
        except:
            error_number = error_number + 1
            error_strings.append(f"Forvo: {term}")
            continue

        if accent:
            accent_string = f"{language[0]}_{accent}"
            match = re.search(
                rf'<div id=\"language-container-{language[0]}\"[^>]*?>.*?<ul class=\"show-all-pronunciations\"[^>]*?.*?<header class=\"accent {accent_string}\"[^>]*?(.*?)</ul>',
                html, re.DOTALL | re.MULTILINE)
        else:
            match = re.search(
                rf'<div id=\"language-container-{language[0]}\"[^>]*?>.*?<ul class=\"show-all-pronunciations\"[^>]*?(.*?)</ul>',
                html, re.DOTALL | re.MULTILINE)

        if match:
            pronunciations = re.findall(
                r'onclick=\"Play\([^,]+,\'([^\']+).*?Pronunciation by\s*?(?:<span class=\"ofLink\"[^>]*?>([^<]+?)</span>|(\b\w+\b))',
                match.groups()[0], re.DOTALL | re.MULTILINE)
        elif not batch and not disable_Lingua_Libre:
            return [[], [], []]
        elif not batch:
            showInfo(f"No pronunciation found for {term}.")
            continue
        else:
            continue

        # Since the username can be found in either the second or third position, we need to check both of them
        for a, b, c in pronunciations:
            user = b or c
            if user not in results:
                results[user] = a
                continue

        # Now remove the unwanted users and reorder the results based on preferred users
        results = sort_results(results, exclude_speakers, prefer_speakers)
        speakers = list()

        if not results and batch:
            continue
        elif not results and not batch:
            return [[], [], []]

        # Either download the first result if this is batch operation
        # Or download all the available audio if this is run on an individual card
        if batch:
            j = 1
        else:
            j = len(results)
        term_filenames = []
        for k in range(j):
            # Find the path to the mp3 and download it
            player_url = "https://forvo.com/player-mp3Handler.php?path={id}" \
                .format(id=results[k][1])
            player_result = scraper.get(player_url)
            if 'Content-Disposition' not in player_result.headers:
                if j < len(results):
                    j += 1
                    continue
                else:
                    error_number = error_number + 1
                    error_strings.append(f"Forvo: {term}")
                    continue
            if player_result.headers['Content-Disposition']:
                mp3 = player_result.headers['Content-Disposition'] \
                    .split('=')[1].replace('"', '')
                try:
                    audio = scraper.get(mp3)
                except:
                    error_number = error_number + 1
                    error_strings.append(f"Forvo: {term}")
                    continue

                speakers.append(results[k][0])
                # Set the filename and save the audio to the disk
                filename = set_forvo_audio_string(results[k][0], term)
                term_filenames.append(filename)
                audio_file_path = save_audio(audio, filename)
                audio_file_paths.append(audio_file_path)

        if filename:
            # If this is a batch operation, there is only one possible filename to append
            # Otherwise, ask the user which one they want to save
            if batch:
                filenames.append(filename)
            else:
                if disable_Lingua_Libre:
                    sound_dialog = SoundDialog(mw, audio_file_paths, speakers)
                    res = sound_dialog.wait_for_result()
                    if res == QDialog.Accepted:
                        index = sound_dialog.selected
                        filenames.append(term_filenames[index])
                        mw.col.media.addFile(audio_file_paths[index])
                else:
                    return [audio_file_paths, speakers, term_filenames]

    return filenames


# sets the audio string used in the file name and audio field
def set_forvo_audio_string(speaker, audio):
    if accent:
        audio_string = slugify(f"Forvo_{language[0]}_{accent}_{speaker}_{audio}") + ".mp3"
    else:
        audio_string = slugify(f"Forvo_{language[0]}_{speaker}_{audio}") + ".mp3"

    return audio_string


# Used to return all the notes missing audio
def find_missing_audio():
    # Create the search string
    if not deck_name:
        search = f'"note:{note_type}" {audio_field}: OR "note:{note_type}" tag:{recheck_tag}'
    else:
        search = f'"note:{note_type}" "deck:{deck_name}" {audio_field}: OR "note:{note_type}" "deck:{deck_name}" tag:{recheck_tag}'
    # Find all notes with a given note type with a blank audio field
    notes = mw.col.findNotes(search)

    return notes


# Returns the index of a field name in the note type
def check_fields(config_fields):
    # Get all the fieldnames for the selected note type
    model = mw.col.models.by_name(note_type)
    fields = mw.col.models.fieldNames(model)

    # Check to see if the provided field name is in the note type
    if set(config_fields).issubset(fields):
        return True
    else:
        missing_fields = list(set(config_fields) - set(fields))
        if len(missing_fields) == 1:
            showInfo(f"Configuration error:\nThe field {missing_fields} does not exist in the note.")
        else:
            showInfo(f"Configuration error:\nThe fields {missing_fields} do not exist in the note.")
        return False


# Runs a batch operation to download audio from Forvo
def batch_get_audio(col: Collection):
    global error_strings, error_number, text_field, audio_field

    count = 0
    total = 25
    if not disable_Lingua_Libre:
        # Load the Lingua Libre database
        load_ll_database()

    success = 0
    error_strings = []
    error_number = 0

    for k, v in field_names.items():
        count = 0
        fail = 0
        percentage = 0

        text_field = k
        audio_field = v

        notes = find_missing_audio()

        total = len(notes)
        for note_id in notes:
            count += 1
            note = col.get_note(note_id)
            term = process_text(note[text_field])

            # This constructs the part of label that displays the search term(s) in the progress bar.
            term_length = len(term)
            for i in range(term_length):
                if term_length == 1:
                    label = f"Search Term: {term[i]}\n"
                elif i == 0:
                    label = f"Search Terms:\n{term[i]}\n"
                else:
                    label += f"{term[i]}\n"

            # Calculates the percentage of notes checked for the label.
            percentage = round((count/total) * 100, 2)
            mw.taskman.run_on_main(
                lambda: mw.progress.update(
                    label=f"{label}\n{percentage}% of {total} notes",
                    value=count,
                    max=total,
                ))

            # Download the audio and update the audio field
            if not disable_Lingua_Libre:
                audio_files = get_ll_results(term)
            elif not disable_Forvo:
                audio_files = get_forvo_results(term)
            else:
                break

            # Create the string for the audio field
            result = create_audio_field_string(audio_files)

            # Only update the card if we actually found audio
            if result:
                if add_tag:
                    note.addTag(add_tag)
                if recheck_tag:
                    note.removeTag(recheck_tag)
                if len(audio_files) != term_length:
                    note.addTag(tag_missing)
                success = success + 1
                note[audio_field] = result
                note.flush()

            else:
                fail += 1

            if mw.progress.want_cancel():
                return [success, fail]

    with open(ll_locations_json, 'w', encoding='utf8') as outfile:
        json.dump(locations, outfile, indent=4, ensure_ascii=False)

    return [success, fail]


def on_success(count: tuple) -> None:
    showInfo(f"{count[0]} Meanings Added.\n {count[1]} not found.\n {error_number} errors")
    if error_number != 0:
        label = "\n".join(error_strings)
        showInfo(f"Errors occurred with the following terms:\n{label}\n"
                 f" Please run again. If this continues to occur, please check the terms on Forvo.")


def batch_download() -> None:
    global batch
    batch = True

    if not get_config_batch():
        return

    op = QueryOp(
        parent=mw,
        op=lambda col: batch_get_audio(col),
        success=on_success,
    )

    # Show a progress window
    op.with_progress(label="Downloading Lingua Libre database.\n Please wait. This will take several minutes.").run_in_background()


def button_pressed(self):
    global batch, note_type

    batch = False
    note_type = str()

    note = self.note
    note_type = note.note_type()['name']
    get_config_note()

    load_ll_database()

    for k, v in field_names.items():
        text_field = k
        audio_field = v
        check_fields([k, v])

        term = process_text(note[text_field])

        # Download the audio and update the audio field
        if not disable_Lingua_Libre:
            audio_files = get_ll_results(term)
        elif not disable_Forvo:
            audio_files = get_forvo_results(term)
        else:
            break


        # Create the string for the audio field
        result = create_audio_field_string(audio_files)

        # Only update the card if we actually found audio
        if result:
            if add_tag:
                note.addTag(add_tag)
            if recheck_tag:
                note.removeTag(recheck_tag)
            if len(audio_files) != len(term):
                note.addTag(tag_missing)

            note[audio_field] = result
            self.loadNoteKeepingFocus()
    return


def add_audio_button(buttons, editor):
    # Add a button to the edit bar to enable manual download of a sound
    buttons.append(
        editor.addButton(icon=os.path.join(os.path.dirname(__file__), "icon/volume-up-fill.svg"),
                         cmd="Download Audio",
                         func=button_pressed),
    )
    return buttons


# Add the Item to the Menu
action = QAction("Download Audio", mw)
# set it to call testFunction when it's clicked
qconnect(action.triggered, batch_download)
# and add it to the tools menu
mw.form.menuTools.addAction(action)

gui_hooks.editor_did_init_buttons.append(add_audio_button)

