"""This will eventually replace ./update.py

ToDo:
    - implement load_schedule using pretalx api using the submission endpoint and making use of Slot
    - implement update_schedule_from_sheet() using pretalx
"""
import logging
import sys
import pickle
import calendar
from typing import List
from pathlib import Path
import shutil
import subprocess
import re
from unicodedata import normalize
from datetime import datetime
import tempfile

import typer
from pytanis import PretalxClient
from pytanis.pretalx.types import Speaker, Submission
from IPython.core import ultratb
from pydantic import BaseModel

# Since the package structure is all fucked up, I cannot easily import `app.config`.
# So rather duplicate instead of going down that rabbit hole of fixing this mess.
EVENT_SLUG = "pyconde-pydata-2025"
project_root = Path(__file__).resolve().parents[1]
# Have I yet complained about the package structure? Another necessary hack to be able to import `schedule
import os
sys.path.append(os.getcwd())
from twitter.twitter_helpers import cleanhandle
from process_sessions.session_template import session_template
from social_cards import make_store_social_cards

app = typer.Typer(name="process-sessions", add_completion=False, help="This processes the sessions.", pretty_exceptions_enable=False)


def slugify(text, delim="-"):
    """Generates a slightly worse ASCII-only slug."""

    _punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.:]+')
    _regex = re.compile("[^a-z0-9]")
    # First parameter is the replacement, second parameter is your input string

    result = []
    for word in _punct_re.split(text.lower()):
        word = normalize("NFKD", word).encode("ascii", "ignore")
        word = word.decode("ascii")
        word = _regex.sub("", word)
        if word:
            result.append(word)
    slug = delim.join(result)
    return str(slug)


def get_speakers(client: PretalxClient, event_slug: str, use_cache: bool) -> List[Speaker]:
    """Retrieve speakers from Pretalx"""
    file_name = 'speakers.pickle'

    if use_cache:
        with open(file_name, 'rb') as fh:
            speakers = pickle.load(fh)
    else:
        count, speakers = client.speakers(event_slug, params={"questions": "all"})
        speakers = list(speakers)  # resolve iterator
        with open(file_name, 'wb') as fh:
            pickle.dump(speakers, fh)
    return speakers


def get_submissions(client: PretalxClient, event_slug: str, use_cache: bool) -> List[Submission]:
    """Retrieve submissions from Pretalx"""
    file_name = 'submissions.pickle'

    if use_cache:
        with open(file_name, 'rb') as fh:
            submissions = pickle.load(fh)
    else:
        count, submissions = client.submissions(event_slug, params={"questions": "all"})
        submissions = list(submissions)  # resolve iterator
        with open(file_name, 'wb') as fh:
            pickle.dump(submissions, fh)
    return submissions


def process_speakers(speakers):
    """Code minimally changed

    ToDo: Clean it up, using the types Pytanis provides. Also the hard-coded pretalx message ids should be reworked.
    """
    qa_map = {
        3012: "affiliation",  # changed for 2024
        3013: "position",  # changed for 2024
        3015: "@twitter",  # changed for 2024
        3026: "residence",  # changed for 2024 (Country of Residence)
        3018: "homepage",  # changed for 2024
        3016: "github",  # changed for 2024
    }

    the_speakers = []
    for s in speakers:
        speaker = {k: s[k] for k in ["name", "biography", "email", "code"]}
        for qa in s["answers"]:
            _id = qa.get("question", {}).get("id")
            if _id not in qa_map:
                continue
            speaker[qa_map[_id]] = qa.get("answer")
            # normalize twitter

            if _id == 1308:
                speaker["@twitter"] = ""
                handle = qa.get("answer").split("/")[-1].replace("@", "").strip()
                speaker[qa_map[_id]] = handle
                if handle:
                    speaker["@twitter"] = f"https://twitter.com/{speaker[qa_map[_id]]}"
                else:
                    pass

            if _id == 1309:
                if qa.get("answer").strip() and "github.com" not in qa.get(
                    "answer", ""
                ):
                    speaker["github"] = f"https://github.com/{qa.get('answer').strip()}"

            if _id == 1307:
                if qa.get("answer").strip() and "http" not in qa.get("answer", ""):
                    speaker["homepage"] = f"http://{qa.get('answer').strip()}"

            if _id == 1319:
                speaker["remote-only"] = False
                if "in-person" not in qa.get("answer", "").casefold():
                    speaker["remote-only"] = True

        the_speakers.append(speaker)
    return the_speakers


def short_type(long: str):
    if "tutorial" in long.casefold():
        return "TU"
    if "sponsored" in long.casefold():
        return "ST"
    if "45" in long.casefold():
        return "T45"
    if "30" in long.casefold():
        return "T30"
    if "keynote" in long.casefold():
        return "KN"
    if "panel" in long.casefold():
        return "P"
    if "open space" in long.casefold():
        return "OS"
    return "???"


def preprocess_submissions(submissions, speakers):
    """Code minimally changed

    ToDo: Clean it up, using the types Pytanis provides
    """
    # add custom data
    _speakers_dict = {x["code"]: x for x in speakers}

    for submission in submissions:
        spkrs = " ".join([x.get("name") for x in submission["speakers"]])
        try:
            slug = slugify(
                f"{submission.get('track', {}).get('en', 'pycon-pydata')}-{submission['code']}-{submission['title']}-{spkrs}"
            )
        except AttributeError as e:
            slug = slugify(
                f"'pycon-pydata'-{submission['code']}-{submission['title']}-{spkrs}"
            )

        submission["plan_remote"] = any(
            [
                _speakers_dict.get(y, {}).get("remote-only", False)
                for y in [x["code"] for x in submission["speakers"]]
            ]
        )

        submission["speakers_names"] = spkrs
        submission["type"] = short_type(submission["submission_type"]["en"])
        if submission["type"] == "ST":
            dur = submission.get("duration")
            submission["type"] = "ST30"
            if dur and dur == 45:
                submission["type"] = "ST45"
        submission["slug"] = slug
    return submissions


def update_session_pages(submissions, speakers, publish_states=None, pending_ok=False):
    """Code minimally changed, id_answer changed to this year, domains (tags) removed

    ToDo: Clean it up, using the types Pytanis provides

    Refactored for 2023 setup
    - mangle submission data from API
    - make available in databags
    """
    if not publish_states:
        publish_states = []
    speakers = {s["code"]: s for s in speakers}
    # TODO: add custom sessions as Open Space
    # take on only required attributes

    eq_attr = [
        "abstract",
        "answers",
        "code",
        "do_not_record",
        "description",
        "duration",
        "is_featured",
        "speakers",
        "state",
        "submission_type",
        "title",
        "track",
        "slug",
        "youtube_id",
        "video_link",
    ]
    id_answers = {
        4401: "short_description",  # changed for 2024 to "Abstract as a tweet"
        4400: "python_skill",  # Changed for 2025
        4399: "domain_expertise",  # Changed for 2025
    }
    cleaned_submissions = []
    for s in submissions:
        pending_state = s['pending_state'].value if s['pending_state'] is not None else ""
        state = s['state'].value if s['state'] is not None else ""
        if not ((pending_ok and pending_state in publish_states) or state in publish_states):
            continue

        cs = {k: s[k] for k in s if k in eq_attr}
        cs["submission_type"] = cs["submission_type"]["en"]
        cs["track"] = cs["track"]["en"] if cs['track'] is not None else ""
        cs["room"] = s["slot"]["room"]["en"] if s["slot"] is not None else ""
        cs["start_time"] = s["slot"]["start"].strftime("%H:%M") if s["slot"] is not None else ""
        cs["day"] = calendar.day_name[s["slot"]["start"].weekday()] if s["slot"] is not None else ""
        cs["submission_type"] = cs["submission_type"].replace("Talk-", "Talk -")
        for answer in [a for a in cs["answers"] if a["question"]["id"] in id_answers]:
            val = answer["answer"]
            if answer["id"] == 119:
                val = val.split(", ")
            cs[id_answers[answer["question"]["id"]]] = val
        del cs["answers"]
        # add speaker info
        enriched_speakers = []
        for x in cs["speakers"]:
            take_on = [
                "affiliation",
                "homepage",
                "@twitter",
                "twitter",
                "github",
                "biography",
            ]
            try:
                _add = {
                    k: speakers[x["code"]].get(k, "")
                    for k in take_on
                    if speakers[x["code"]].get(k, "")
                }
                x.update(_add)
                enriched_speakers.append(x)
            except KeyError:
                continue
        cs["speakers"] = enriched_speakers
        cleaned_submissions.append(cs)

    return cleaned_submissions


def create_redirect(redir_dirname, program_route):
    redir_dirname.mkdir(exist_ok=True)
    with open(redir_dirname / "contents.lr", "w") as f:
        f.write(
            f"""_model: redirect
---
target: /program/{program_route}
---
_discoverable: no"""
        )


def generate_session_pages(cleaned_submissions, social_banner_path):
    """Code minimally changed

    ToDo: Clean it up, using the types Pytanis provides
    """
    # book keeping
    session_path = project_root / "content/program/"
    session_path.mkdir(exist_ok=True)

    in_place_submissions = [x.name for x in session_path.glob("*") if x.name[0] != "."]
    lr_file = "contents.lr"
    if lr_file in in_place_submissions:
        in_place_submissions.remove(lr_file)  # only dirs

    all_categories = {}  # collect categories automatically add newly discovered ones
    redirects = (
        {}
    )  # simple url with talk code redirecting to full url, used for auto urls from other systems

    for submission in cleaned_submissions:

        biography = []
        for x in submission["speakers"]:
            biography.append(f"#### {x.get('name')}")
            if x.get("affiliation"):
                biography.append(f'Affiliation: {x["affiliation"]}')
            biography.append(f"")
            biography.append(f"{x['biography'] if x['biography'] else ''}")
            social = []
            if x.get("twitter"):
                social.append(f"[Twitter]({x['twitter']})")
            if x.get("github"):
                social.append(f"[Github]({x['github']})")
            if x.get("homepage"):
                social.append(f"[Homepage]({x['homepage']})")
            if social:
                biography.append("visit the speaker at: " + " • ".join(social))
        biography = "\n\n".join(biography)

        speakers = ", ".join([x["name"] for x in submission["speakers"]])
        speaker_twitters = " ".join(
            [
                f"@{cleanhandle(x.get('@twitter'))}"
                for x in submission["speakers"]
                if x.get("@twitter")
            ]
        )
        meta_title = f"{submission['title']} {speakers.replace(',', '')} PyConDE & PyDataBerlin 2024 conference "
        meta_twitter_title = f"{submission['title']} {speaker_twitters} #PyConDE #PyDataBerlin #PyData".replace(
            "@@", "@"
        )

        # easier to handle on website as full text
        python_skill = f"Python Skill Level {submission['python_skill']}"
        domain_expertise = f"Domain Expertise {submission['domain_expertise']}"

        video_link = (
            f"https://www.youtube.com/embed/{submission['youtube_id']}"
            if submission.get("youtube_id")
            else ""
        )
        youtube_id = submission["youtube_id"] if submission.get("youtube_id") else ""

        categories = (
                [python_skill, domain_expertise]
                + [submission["submission_type"].split(" ")[0]]
                + [x.strip() for x in submission["track"].split(":")]
        )

        categories = categories + [slugify(submission["track"])]
        slugified_categories = [slugify(x) for x in categories]
        categories_list = ", ".join(slugified_categories)
        all_categories.update(
            {slugify(x).replace("---", "-").replace("--", "-"): x for x in categories}
        )

        redirects[submission["slug"]] = submission["code"]
        redir_dirname = session_path / submission["slug"]
        if submission["slug"] in in_place_submissions:
            in_place_submissions.remove(submission["slug"])
        create_redirect(redir_dirname, submission["code"])

        dirname = session_path / submission["code"]
        if dirname.name in in_place_submissions:
            # print("slug hasn't changed")
            in_place_submissions.remove(dirname.name)

        dirname.mkdir(exist_ok=True)

        twitter_banner = (
                project_root
                / f"assets/static/media/twitter/{submission['code']}.png"
        )

        src = Path(social_banner_path) / Path(f"{submission['code']}.png")

        if src.exists():
            shutil.copy(src, twitter_banner)
        else:
            logging.warning(f"Social banner for {submission['code']} not found!")
            shutil.copy(project_root / Path('process_sessions/1x1-transparent.png'), twitter_banner)

        contents = session_template.format(
            title=submission["title"],
            short_description=submission["short_description"],
            short_description_html=submission["short_description"],
            code=submission["code"],
            body=submission["abstract"], # changed from submission["description"]
            track=slugify(submission["track"]),
            submission_type=submission["submission_type"].split(" ")[0],
            speakers=speakers,
            biography=biography,
            affiliation=", ".join(
                [
                    x["affiliation"]
                    for x in submission["speakers"]
                    if x.get("affiliation")
                ]
            ),
            twitter_image=f"/static/media/twitter/{submission['code']}.png",
            meta_title=meta_title,
            meta_twitter_title=meta_twitter_title,
            categories=categories,
            categories_list=categories_list,
            python_skill=python_skill,
            domain_expertise=domain_expertise,
            start_time=submission['start_time'],
            room=submission['room'],
            day=submission['day'],
            video_link=video_link,
            youtube_id=youtube_id,
        )
        with open(dirname / "contents.lr", "w") as f:
            f.write(contents)
        cpath = (
                project_root
                / Path("website/content/program-categories")
                / slugify(submission["track"])
        )
        if not cpath.exists():
            cpath.mkdir(parents=True, exist_ok=True)
            with open(cpath / "contents.lr", "w") as f:
                f.write(
                    """name: {0}

            ---
            title: {0} Session List
            ---
            description: All {0} sessions at the PyConDE & Pydata Berlin 2024 conference
            ---""".format(
                        submission["track"]
                    )
                )

    if in_place_submissions:  # leftover dirs
        for zombie in in_place_submissions:
            if len(zombie) != 6 or "-" in zombie:
                # #ignore slug changed, keep redirect to code
                continue
            zpath = project_root / Path("website/content/program/") / zombie
            try:
                code = zombie.split("-")[1].upper()
                if redirects.get(code):
                    create_redirect(zpath, slug=redirects.get(code))
            except Exception as e:
                shutil.rmtree(zpath)

    for category in all_categories:
        cpath = (
                project_root
                / Path("website/content/program-categories")
                / slugify(category)
        )
        if not cpath.exists():
            cpath.mkdir(parents=True, exist_ok=True)
            with open(cpath / "contents.lr", "w") as f:
                f.write(
                    """name: {0}

---
title: {0} Session List
---
description: All {0} sessions at the PyConDE & Pydata Berlin 2024 conference
---""".format(
                        all_categories[category]
                    )
                )


def run_lekor_update():
    command = (
        f"cd {project_root.absolute()}/website && lektor build --output-path ../www"
    )
    process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    proc_stdout = process.communicate()[0].strip()
    for line in proc_stdout.decode("utf-8").split("\n"):
        print(line)


def exec_command(commands):
    for command in commands:
        print("command:", command)
        process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        proc_stdout, proc_error = process.communicate()
        if proc_error:
            raise RuntimeError(f"git did return an error {proc_error}: {proc_stdout}")
        for line in proc_stdout.decode("utf-8").split("\n"):
            print(line)


def git_push_as_branch():
    new_branch = f"program_update-{datetime.utcnow().strftime('%y%m%d_%H%M%S')}"
    commands = [
        f"cd {project_root.absolute()}",
        f"git checkout -b {new_branch}",
        "git add --all",
        "git commit -am " "website-auto-update",
        f"git push --set-upstream origin {new_branch}",
    ]
    exec_command(commands)


@app.command()
def process(use_cache: bool = False, git_push: bool = False, pending_ok: bool = False, pipeline_mode: bool = False):
    # For easy debugging, can be removed later on
    sys.excepthook = ultratb.FormattedTB(mode='Verbose', color_scheme='Linux', call_pdb=True)

    # check, if started as part of Github Action and create config object accordingly 
    pretalx_api_key = None
    if pipeline_mode:
        pretalx_api_key = os.environ.get('PRETALX_API_KEY')
    
    if pretalx_api_key is None:
        raise('Execution in pipeline mode requiring pretalx API key as environment variable.')

    class PretalxBasicModel(BaseModel):
        api_token: str | None = None
    class PytanisBasicConfigModel(BaseModel):
        Pretalx: PretalxBasicModel

    cfg = PytanisBasicConfigModel.model_validate({
        'Pretalx': {
            'api_token': pretalx_api_key
        }
    })

    client = None
    if pipeline_mode:
        client = PretalxClient(config=cfg, blocking=True)
    else:
        client = PretalxClient(blocking=True)

    """pending_ok = True only for testing"""
    print("Retrieving speakers...")
    speakers = get_speakers(client, EVENT_SLUG, use_cache)
    print("Retrieving submissions...")
    submissions = get_submissions(client, EVENT_SLUG, use_cache)

    # Add this point we convert everything to JSON instead of using types to circumvent rewriting everything
    speakers_dict = [speaker.model_dump() for speaker in speakers]
    submissions_dict = [submission.model_dump() for submission in submissions]

    speakers_dict = process_speakers(speakers_dict)
    submissions_dict = preprocess_submissions(submissions_dict, speakers_dict)

    with tempfile.TemporaryDirectory() as social_banners_path:
        print("Creating social cards...")
        make_store_social_cards(speakers, submissions, social_banners_path)

        print("Prepare generating session pages...")
        # updates submissions, allows filtering by status
        states = ["confirmed"]
        cleaned_submissions = update_session_pages(submissions_dict, speakers_dict, publish_states=states, pending_ok=pending_ok)
        
        print("Generating", len(cleaned_submissions), "session pages ...")
        generate_session_pages(cleaned_submissions, social_banners_path)

    print("Running Lektor update...")
    run_lekor_update()
    if git_push:
        git_push_as_branch()


if __name__ == "__main__":
    app()
