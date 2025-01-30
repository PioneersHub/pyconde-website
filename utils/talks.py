from pytanis import PretalxClient
import json
import os
import re
import shutil
from string import Template
from pydantic import BaseModel
import calendar
from collections import defaultdict

PYTHON_SKILL_ID = 4400
DOMAIN_EXPERTISE_ID = 4399


def submission_to_talk(sub):
    t = defaultdict(lambda: "")
    t["title"] = sub.title
    t["abstract"] = sub.abstract
    t["full_description"] = sub.description
    t["code"] = sub.code
    t["state"] = sub.state.value
    t["created"] = sub.created.strftime("%Y-%m-%d")
    t["speaker_names"] = ", ".join([speaker.name for speaker in sub.speakers])

    for speaker in sub.speakers:
        t["speakers"] += speaker_to_markdown(speaker)

    for answer in sub.answers:
        if answer["question"]["id"] == PYTHON_SKILL_ID:
            t["python_skill"] = answer["answer"]
        if answer["question"]["id"] == DOMAIN_EXPERTISE_ID:
            t["domain_expertise"] = answer["answer"]

    if sub.track is not None:
        t["track"] = re.sub(r'(?i)(pycon|pydata|general): ', "", sub.track.en)
    if sub.slot is not None:
        t["room"] = sub.slot.room.en
        t["start_time"] = sub.slot.start.strftime("%H:%M")
        t["day"] = calendar.day_name[sub.slot.start.weekday()]

    return t


def speaker_to_markdown(speaker):
    s = {"name": speaker.name}
    s["biography"] = speaker.biography if speaker.biography is not None else ""
    s["avatar"] = speaker.avatar
    tmpl = Template('''
### $name

$biography
''')
    return tmpl.substitute(s)


def submission_to_lektor(sub):
    tmpl = Template('''title: $title
---
created: $created
---
code: $code
---
speaker_names: $speaker_names
---
speakers:

$speakers
---
abstract:

$abstract
---
full_description:

$full_description
---
room: $room
---
day: $day
---
start_time: $start_time
---
track: $track
---
python_skill: $python_skill
---
domain_expertise: $domain_expertise

''')

    talk = submission_to_talk(sub)
    return tmpl.substitute(talk)


def remove_old_talks():
    """
    Removes old talks before regenerating them to avoid having previously on
    Pretalx removed talks still hanging around on the website. Crude but simple
    """
    talk_dirs = [f.path for f in os.scandir("content/talks") if f.is_dir()]
    for dir in talk_dirs:
        shutil.rmtree(dir)


def submission_to_lektor_file(sub):
    new_dir = f"content/talks/{sub.code}"
    if not os.path.isdir(new_dir):
        os.mkdir(new_dir)

    sub = submission_to_lektor(sub)
    with open(new_dir+"/contents.lr", "w") as f:
        f.write(sub)


def submissions_to_json_file(submissions):
    with open("databags/talks.json", "w") as f:
        talks = [submission_to_talk(sub) for sub in submissions]
        f.write(json.dumps({'talks': talks}, default=str))


def configure_pretalx_client():
    pretalx_api_key = os.environ.get('PRETALX_API_KEY')

    class PretalxBasicModel(BaseModel):
        api_token: str | None = None

    class PytanisBasicConfigModel(BaseModel):
        Pretalx: PretalxBasicModel

    cfg = PytanisBasicConfigModel.model_validate({
        'Pretalx': {
            'api_token': pretalx_api_key
        }
    })
    return PretalxClient(config=cfg)


def main():
    event_name = os.environ.get('PRETALX_EVENT_NAME')
    client = configure_pretalx_client()
    _, submissions = client.submissions(
        event_name, params={"state": ["accepted", "confirmed"]})
    submissions = list(submissions)
    remove_old_talks()
    for sub in submissions:
        submission_to_lektor_file(sub)

    submissions_to_json_file(submissions)


if __name__ == "__main__":
    main()
