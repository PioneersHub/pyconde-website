import json

from app.config import submissions_path, submissions_raw_path, speakers_raw_path, speakers_path


def save_submissions_to_file(submissions):
    with submissions_path.open("w") as f:
        json.dump(submissions, f, indent=4)


def save_submissions_raw_to_file(submissions):
    with submissions_raw_path.open("w") as f:
        json.dump(submissions, f, indent=4)


def load_submissions_raw_from_file():
    with submissions_raw_path.open() as f:
        submissions = json.load(f)
    return submissions


def load_submissions_from_file():
    with submissions_path.open() as f:
        submissions = json.load(f)
    return submissions


def save_speakers_raw_to_file(speakers):
    with speakers_raw_path.open("w") as f:
        json.dump(speakers, f, indent=4)


def load_speakers_raw_from_file():
    with speakers_raw_path.open() as f:
        speakers = json.load(f)
    return speakers


def load_speakers_from_file():
    with speakers_path.open() as f:
        speakers = json.load(f)
    return speakers