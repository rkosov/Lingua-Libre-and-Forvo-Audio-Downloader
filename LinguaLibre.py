import datetime
import json
import time
import os
import re
import random
import sparql
import requests
import datetime
import unicodedata
import json
import random
import sparql
import cfscrape

from aqt import mw, gui_hooks
import os
from tempfile import gettempdir

database_file = str()
max_date = str()
ll_database = dict()
locations = dict()
restrict_to_places = list()
prefer_locations = frozenset()
prefer_speakers = frozenset()
exclude_speakers = frozenset()
checked = list()
language = list()
garbage = dict()
batch = bool()
error_number = 0
error_strings = []
headers = {'User-Agent': 'Lingua Libre Anki Addon'}

ENDPOINT = "https://lingualibre.org/bigdata/namespace/wdq/sparql"
API = "https://lingualibre.org/api.php"
BASEQUERY = """
SELECT DISTINCT
    ?record ?file ?transcription ?recorded
    ?languageIso ?residence ?languageLevel
    ?speaker ?linkeduser
WHERE {
  ?record prop:P2 entity:Q2 .
  ?record prop:P3 ?file .
  ?record prop:P4 ?language .
  ?record prop:P5 ?speaker .
  ?record prop:P7 ?transcription .
  ?language prop:P13 ?languageIso.
  ?speakerLanguagesStatement llq:P16 ?languageLevel .
  ?speaker prop:P11 ?linkeduser .
  ?speaker prop:P14 ?residence .
  ?speaker llp:P4 ?speakerLanguagesStatement .
  ?speakerLanguagesStatement llv:P4 ?speakerLanguages .
  FILTER( ?speakerLanguages = ?language) .
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}"""


def fetch_ll_database():
    global ll_database
    raw_records = sparql.request(ENDPOINT, BASEQUERY.replace("#filters", ""))
    for record in raw_records:
        current_term = sparql.format_value(record, "transcription")
        speaker = sparql.format_value(record, "linkeduser")
        #print(current_term)
        if sparql.format_value(record, "languageLevel") != "Q15":
            continue

        if current_term not in ll_database:
            ll_database[current_term] = {}
        ll_database[current_term][speaker] = {"file": sparql.format_value(record, "file"),
                                              "language": sparql.format_value(record, "languageIso"),
                                              "recorded": sparql.format_value(record, "recorded"),
                                              "residence": sparql.format_value(record, "residence")}

    with open('LinguaLibre.json', 'w') as outfile:
        json.dump(ll_database, outfile, indent=4)


def load_ll_database():
    global ll_database, locations
    try:
        today = datetime.datetime.today()
        modified_date = datetime.datetime.fromtimestamp(os.path.getmtime('LinguaLibre.json'))
        duration = today - modified_date
        if bool(ll_database):
            return
        elif duration.days < max_date:
            try:
                with open('LinguaLibre.json', 'r') as f:
                    ll_database = json.load(f)
            except FileNotFoundError:
                fetch_ll_database()
            try:
                with open('Locations.json', 'r') as f:
                    locations = json.load(f)
            except FileNotFoundError:
                return
        else:
            fetch_ll_database()
            try:
                with open('Locations.json', 'r') as f:
                    locations = json.load(f)
            except FileNotFoundError:
                return
    except FileNotFoundError:
        fetch_ll_database()


def get_ll_results(terms):
    global error_number, error_strings
    filenames = []

    for index, term in enumerate(ll_database):
        filename = ""
        speaker = ""
        selection = ""
        entry = dict()
        results = ll_database.get(term)
        #print(results)
        available_speakers = []
        # Only continue if there are pronunciations for the given term
        if results:

            # Create a reduced dictionary of acceptable pronunciations of the term
            for si, speaker in enumerate(results):

                # Gets the city, country corresponding to the Wikidata item
                place = results[speaker]['residence']
                if speaker not in checked:
                    get_location_labels(place, speaker)

    return filenames


def get_location_labels(qid, speaker):
    global locations, checked

    if qid is None:
        checked.append(speaker)
        print([speaker, qid])
        return

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
        checked.append(speaker)
    except IndexError:
        checked.append(speaker)
        print([speaker, qid])
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
            download_filename = f"{filename.replace('?', '')}.mp3"
        else:
            print(f"No mp3 file found for {filename}")
            return False
    else:
        common_url = re.search(
            r'<div class="fullMedia"><p><a href="(https://upload.wikimedia.org/[\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])"',
            content)
        if common_url:
            download_url = common_url.groups()[0]
            download_filename = f"{filename.replace('?', '')}"
        else:
            print(f"No download link found for found for {filename}")
            return False

    # Common files are generally safe for downloading, but ? need to be removed
    try:
        audio = requests.get(download_url, headers=headers)
    except:
        return False

    return audio


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


def save_audio(audio, filename):
    save_name = os.path.join(gettempdir(), filename)
    try:
        with open(save_name, 'wb') as audio_file:
            for chunk in audio.iter_content(512):
                audio_file.write(chunk)

        '''if batch:
            mw.col.media.addFile(save_name)'''

        return save_name
    except OSError:
        pass


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
        elif not batch:
            return [[], [], []]
        elif not batch:

            continue
        else:
            continue

        # Since the username can be found in either the second or third position, we need to check both of them
        for a, b, c in pronunciations:
            user = b or c
            if user not in results:
                results[user] = [a]
                continue
            results[user].append(a)

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
                if False:
                    return
                else:
                    return [audio_file_paths, speakers, term_filenames]

    return filenames


def sort_results(results, exclude_field, sort_field):
    # Remove the unwanted entries from the list of results
    sorted_results = {k: v for k, v in results.items() if k not in exclude_field}

    # sort the results according to the sort_field
    index_map = {v: i for i, v in enumerate(sort_field)}
    sorted_results = sorted(sorted_results.items(), key=lambda pair: index_map[pair[0]]
                                if pair[0] in sort_field else 999)

    return sorted_results


# sets the audio string used in the file name and audio field
def set_forvo_audio_string(speaker, audio):
    if accent:
        audio_string = slugify(f"Forvo_{language[0]}_{accent}_{speaker}_{audio}") + ".mp3"
    else:
        audio_string = slugify(f"Forvo_{language[0]}_{speaker}_{audio}") + ".mp3"

    return audio_string


def test_text(term):
    ll = [f"LL {x}" for x in term]
    print(ll)


accent = ""
disable_Forvo  = False
batch = False
language = ["fr", "fra"]
#restrict_to_places = ['France']
exclude_speakers = ["0x010C", "Adélaïde Calais WMFr", "Julien Baley"]
#prefer_users = ["GrandCelinien", "Pamputt"]
#prefer_locations = ["Paris", "Cornimont"]
max_date = 1
load_ll_database()

a = get_ll_results(["chien", "chat"])

#test_text(["cat", "dog"])
print(garbage)
with open('Locations.json', 'w') as outfile:
    json.dump(locations, outfile, indent=4)
