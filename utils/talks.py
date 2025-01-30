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


def submission_to_talk_dict(sub):
    t = defaultdict(lambda: "")
    t["title"] = sub.title
    t["abstract"] = sub.abstract
    t["full_description"] = sub.description
    t["code"] = sub.code
    t["state"] = sub.state.value
    t["created"] = sub.created.strftime("%Y-%m-%d")
    t["speaker_names"] = ", ".join([speaker.name for speaker in sub.speakers])

    for answer in sub.answers:
        if answer["question"]["id"] == PYTHON_SKILL_ID:
            t["python_skill"] = answer["answer"]
        if answer["question"]["id"] == DOMAIN_EXPERTISE_ID:
            t["domain_expertise"] = answer["answer"]

    if sub.track is not None:
        t["track"] = sub.track.en
    if sub.slot is not None:
        t["room"] = sub.slot.room.en
        t["start_time"] = sub.slot.start.strftime("%H:%M")
        t["day"] = calendar.day_name[sub.slot.start.weekday()]

    return t


def speaker_to_markdown(speaker):
    pass


def talk_to_lektor(talk):
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
    return PretalxClient(config=cfg)


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
