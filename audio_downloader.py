# (c) 2022 Rodion Kosovsky released under the GPL v3

from aqt import mw, gui_hooks
from aqt.utils import showInfo, qconnect
from anki.collection import Collection
from aqt.operations import QueryOp
from aqt.qt import *
from anki.utils import stripHTML
from .selector import SelectDialog
from .dialog import SoundDialog
import unicodedata
import re

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
language = str()
accent = str()
field_names = dict()
prefer_users = list()
exclude_users = list()
add_tag = str()
error_number = 0
error_strings = []
batch = bool
recheck_tag = str()


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
    global accent, prefer_users, exclude_users, tag_missing, deck_name, add_tag, recheck_tag
    config_fields = []

    # reset all config variables
    separator = prefixes = suffixes = tag_missing = note_type = deck_name = language = accent = add_tag = str()
    find_and_replace = field_names = dict()
    prefer_users = exclude_users = list()
    recheck_tag = ""

    keys = config.keys()

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
    if "prefer_users" in keys:
        prefer_users = config['prefer_users']
    if "exclude_users" in keys:
        exclude_users = config['exclude_users']
    if "tag_missing" in keys:
        tag_missing = config['tag_missing']
    if "add_tag" in keys:
        add_tag = config['add_tag']
    if "recheck_tag" in keys:
        recheck_tag = config['recheck_tag']

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


# sets the audio string used in the file name and audio field
def set_audio_string(speaker, audio):
    if accent:
        audio_string = slugify(f"{language}_{accent}_{speaker}_{audio}") + ".mp3"
    else:
        audio_string = slugify(f"{language}_{speaker}_{audio}") + ".mp3"

    return audio_string


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


def sort_results(results):
    # Remove the unwanted users from the list of results
    sorted_results = {k: v for k, v in results.items() if k not in exclude_users}

    # sort the results according to the preferred user setting
    index_map = {v: i for i, v in enumerate(prefer_users)}
    sorted_results = sorted(sorted_results.items(), key=lambda pair: index_map[pair[0]]
                                if pair[0] in prefer_users else 999)

    return sorted_results


# Used to get the results from Forvo, can be used as either a batch or stand alone
def get_forvo_results(term):
    global error_number, error_strings
    filenames = []

    for i in range(len(term)):
        audio_files = []
        filename = ""
        results = dict()

        # This constructs the url to retry and replaces ? with %253F as Forvo does.
        url = "https://forvo.com/word/" + term[i].replace("?", "%253F")
        scraper = cfscrape.CloudflareScraper()
        try:
            html = scraper.get(url).text
        except:
            error_number = error_number + 1
            error_strings.append(f"Connection Error: {term[i]}")
            continue

        if accent:
            accent_string = f"{language}_{accent}"
            match = re.search(
                rf'<div id=\"language-container-{language}\"[^>]*?>.*?<ul class=\"show-all-pronunciations\"[^>]*?.*?<header class=\"accent {accent_string}\"[^>]*?(.*?)</ul>',
                html, re.DOTALL | re.MULTILINE)
        else:
            match = re.search(
                rf'<div id=\"language-container-{language}\"[^>]*?>.*?<ul class=\"show-all-pronunciations\"[^>]*?(.*?)</ul>',
                html, re.DOTALL | re.MULTILINE)

        if match:
            pronunciations = re.findall(
                r'onclick=\"Play\([^,]+,\'([^\']+).*?Pronunciation by\s*?(?:<span class=\"ofLink\"[^>]*?>([^<]+?)</span>|(\b\w+\b))',
                match.groups()[0], re.DOTALL | re.MULTILINE)
        elif not batch:
            showInfo(f"No pronunciation found for {term[i]}.")
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
        results = sort_results(results)
        speakers = list()

        if not results:
            # raise ValueError(f"No results for {term[i]}")
            continue

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
                    error_strings.append(f"No Audio: {term[i]}")
                    continue
            if player_result.headers['Content-Disposition']:
                mp3 = player_result.headers['Content-Disposition'] \
                    .split('=')[1].replace('"', '')
                try:
                    audio = scraper.get(mp3)
                except:
                    error_number = error_number + 1
                    error_strings.append(f"Connection Error: {term[i]}")
                    continue

                speakers.append(results[k][0])
                # Set the filename and save the audio to the disk
                filename = set_audio_string(results[k][0], term[i])
                term_filenames.append(filename)
                audio_files.append(save_audio(audio, filename))
                save_audio(audio, filename)
        if filename:
            # If this is a batch operation, there is only one possible filename to append
            # Otherwise, ask the user which one they want to save
            if batch:
                filenames.append(filename)
            else:
                sound_dialog = SoundDialog(mw, audio_files, speakers)
                res = sound_dialog.wait_for_result()
                if res == QDialog.Accepted:
                    index = sound_dialog.selected
                    filenames.append(term_filenames[index])
                    mw.col.media.addFile(audio_files[index])

    return create_audio_field_string(filenames)


# Used to return all the notes missing audio
def find_missing_audio():
    # Create the search string
    if not deck_name:
        search = f'"note:{note_type}" {audio_field}: OR "note:{note_type}" tag:{recheck_tag}'
    else:
        search = f'"note:{note_type}" "deck:{deck_name}" {audio_field}: ' \
                 f'OR note:{note_type}" "deck:{deck_name}" tag:{recheck_tag}'
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
            result = get_forvo_results(term)
            # Only update the card if we actually found audio
            if result:
                if result.count(separator) < len(term) - 1 and not note.hasTag(tag_missing):
                    note.addTag(tag_missing)
                if add_tag:
                    note.addTag(add_tag)
                if recheck_tag:
                    note.removeTag(recheck_tag)
                success = success + 1
                note[audio_field] = result
                note.flush()

            else:
                fail += 1

            if mw.progress.want_cancel():
                return [success, fail]

    return [success, fail]


def on_success(count: tuple) -> None:
    showInfo(f"{count[0]} Meanings Added.\n {count[1]} not found.\n {error_number} errors")
    if error_number != 0:
        label = "\n".join(error_strings)
        showInfo(f"Errors occurred with the following terms: {label}\n"
                 f" If this continue to occur, please check the terms on Forvo.")


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
    op.with_progress(label="Fetching Audio").run_in_background()


def button_pressed(self):
    global batch, note_type
    batch = False
    note_type = str()

    note = self.note
    note_type = note.note_type()['name']
    get_config_note()

    for k, v in field_names.items():
        text_field = k
        audio_field = v
        check_fields([k, v])

        term = process_text(note[text_field])
        # Download the audio and update the audio field
        result = get_forvo_results(term)

        # Only update the card if we actually found audio
        if result:
            if result.count(separator) < len(term) - 1 and not note.hasTag(tag_missing):
                note.addTag(tag_missing)
            if add_tag:
                note.addTag(add_tag)
            note[audio_field] = result
            self.loadNoteKeepingFocus()
    return


def add_audio_button(buttons, editor):
    # Add a button to the edit bar to enable manual download of a sound
    buttons.append(
        editor.addButton(icon=os.path.join(os.path.dirname(__file__), "icon/volume-up-fill.svg"),
                         cmd="add_forvo",
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

