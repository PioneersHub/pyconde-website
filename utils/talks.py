from pytanis import PretalxClient
import json

def normalize_talk(talk):
    talk = talk.model_dump()
    talk['state'] = talk['state'].value
    talk['speaker_names'] = ", ".join([speaker['name'] for speaker in talk['speakers']])
    return talk

def main():
    event_name = "pyconde-pydata-2025"
    client = PretalxClient()
    _, talks = client.submissions(event_name)
    talks = list(talks)
    with open("databags/talks.json", "w") as f:
        f.write(json.dumps({'talks': [normalize_talk(talk) for talk in talks]}, default=str))

if __name__ == "__main__":
    main()
