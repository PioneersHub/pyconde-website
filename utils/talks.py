from pytanis import PretalxClient
import json
import os
from string import Template
from pydantic import BaseModel


def normalize_talk(talk):
    talk = talk.model_dump()
    talk['state'] = talk['state'].value
    talk['created'] = talk['created'].strftime("%Y-%m-%d")
    talk['speaker_names'] = ", ".join(
        [speaker['name'] for speaker in talk['speakers']])
    return talk


def convert_to_lektor_content(talk):
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
abstract: $abstract
''')

    normalized = normalize_talk(talk)
    return tmpl.substitute(normalized)


def create_lektor_content(talk):
    new_dir = f"content/talks/{talk.code}"
    if not os.path.isdir(new_dir):
        os.mkdir(new_dir)

    talk = convert_to_lektor_content(talk)
    with open(new_dir+"/contents.lr", "w") as f:
        f.write(talk)


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
    event_name = "pyconde-pydata-2025"
    client = configure_pretalx_client()
    _, talks = client.submissions(event_name)
    talks = list(talks)
    # persist each talk as talk model content
    for talk in talks:
        create_lektor_content(talk)

    # persist talks as json
    with open("databags/talks.json", "w") as f:
        f.write(json.dumps(
            {'talks': [normalize_talk(talk) for talk in talks]}, default=str))


if __name__ == "__main__":
    main()
