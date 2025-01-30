from pytanis import PretalxClient
import json
import os
import shutil
from string import Template
from pydantic import BaseModel
import calendar
from collections import defaultdict

PYTHON_SKILL_ID = 4400
DOMAIN_EXPERTISE_ID = 4399


def submission_to_talk_dict(talk):
    t = defaultdict(lambda: "")
    t["title"] = talk.title
    t["abstract"] = talk.abstract
    t["full_description"] = talk.description
    t["code"] = talk.code
    t["state"] = talk.state.value
    t["created"] = talk.created.strftime("%Y-%m-%d")
    t["speaker_names"] = ", ".join([speaker.name for speaker in talk.speakers])

    for answer in talk.answers:
        if answer["question"]["id"] == PYTHON_SKILL_ID:
            t["python_skill"] = answer["answer"]
        if answer["question"]["id"] == DOMAIN_EXPERTISE_ID:
            t["domain_expertise"] = answer["answer"]

    if talk.track is not None:
        t["track"] = talk.track.en
    if talk.slot is not None:
        t["room"] = talk.slot.room.en
        t["start_time"] = talk.slot.start.strftime("%H:%M")
        t["day"] = calendar.day_name[talk.slot.start.weekday()]

    return t


def speaker_to_markdown(speaker):
    pass


def talk_to_lektor(talk):
    """
    Converts the object into a persisted lektor entry,
    defined as per the talk model.
    """
    tmpl = Template('''title: $title
---
created: $created
---
code: $code
---
speaker_names: $speaker_names
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

    talk_dict = submission_to_talk_dict(talk)
    return tmpl.substitute(talk_dict)


def remove_old_talks():
    """
    Removes old talks before regenerating them to avoid having previously on
    Pretalx removed talks still hanging around on the website. Crude but simple
    """
    talk_dirs = [f.path for f in os.scandir("content/talks") if f.is_dir()]
    for dir in talk_dirs:
        shutil.rmtree(dir)


def talk_to_lektor_file(talk):
    new_dir = f"content/talks/{talk.code}"
    if not os.path.isdir(new_dir):
        os.mkdir(new_dir)

    talk = talk_to_lektor(talk)
    with open(new_dir+"/contents.lr", "w") as f:
        f.write(talk)


def talks_to_json_file(talks):
    with open("databags/talks.json", "w") as f:
        talks = [submission_to_talk_dict(talk) for talk in talks]
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
    client = PretalxClient(config=cfg)
    return client


def main():
    event_name = os.environ.get('PRETALX_EVENT_NAME')
    client = configure_pretalx_client()
    _, talks = client.submissions(
        event_name, params={"state": ["accepted", "confirmed"]})
    talks = list(talks)
    remove_old_talks()
    for talk in talks:
        talk_to_lektor_file(talk)

    talks_to_json_file(talks)


if __name__ == "__main__":
    main()
