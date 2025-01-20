from pytanis import PretalxClient
import json

def normalize_submission(submission):
    submission = submission.model_dump()
    submission['state'] = submission['state'].value
    return submission

def main():
    event_name = "pyconde-pydata-2025"
    client = PretalxClient()
    _, subs = client.submissions(event_name)
    subs = list(subs)
    with open("databags/submissions.json", "w") as f:
        f.write(json.dumps({'submissions': [normalize_submission(sub) for sub in subs]}, default=str))

if __name__ == "__main__":
    main()
