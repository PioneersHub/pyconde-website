"""Pretalx -> Lektor importer for confirmed talks.

Refactored for the SEO-overhaul Phase 1 to be entirely YAML-driven —
all per-edition Pretalx field IDs live in `databags/pretalx.yaml`
(question_ids[year], submission_type_ids[year]). The importer never
hardcodes IDs.

The importer pulls the current event's submissions in a single
`?expand=` request via pytanis (PretalxClient already chains the
expand params for the full set of related objects we need), then
maps each submission to a Lektor talk node.
"""

from __future__ import annotations

import calendar
import json
import os
import re
import shutil
import textwrap
from collections import defaultdict
from pathlib import Path
from string import Template

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel
from pytanis import PretalxClient

REPO_ROOT = Path(__file__).resolve().parent.parent
PRETALX_CONFIG = REPO_ROOT / "databags" / "pretalx.yaml"
CONTENT_DIR = REPO_ROOT / "content"
CURRENT_TALKS_JSON_PATH = REPO_ROOT / "databags" / "talks.json"


def talks_dir_for(year: str, current_year: str) -> Path:
    """Resolve the on-disk talks folder for a given edition year.

    Current edition lives at /talks/ (top-level routing); historical
    editions live under /archive/{year}/talks/.
    """
    if year == current_year:
        return CONTENT_DIR / "talks"
    return CONTENT_DIR / "archive" / year / "talks"


def talks_json_for(year: str, current_year: str) -> Path:
    """Where to write the JSON bag of talks for this edition."""
    if year == current_year:
        return CURRENT_TALKS_JSON_PATH
    return REPO_ROOT / "databags" / f"talks-{year}.json"

META_DESCRIPTION_MAX = 155
TRACK_PREFIX_PATTERN = re.compile(r"(?i)(pycon|pydata|general):\s*")

# ── Bio → third-person conversion ─────────────────────────────────────
#
# Speakers regularly submit bios in the first person ("Hi, I'm X. I work
# at Y."). Conference pages read more consistently when every bio is in
# third person. The transformation here is conservative:
#   * known greeting + self-intro openers are stripped (the speaker name
#     is shown in the heading already)
#   * "I am/I'm/I've/I have/I had/I'll/etc." are mapped to "{first} is/has/…"
#     and a curated list of present-tense verbs get an -s suffix
#   * possessive / object / reflexive pronouns shift to a configurable
#     pronoun set (default singular they)
#   * leftover bare "I" → first name on first occurrence, then subject
#     pronoun afterwards
# Output is left as-is when no pattern matches, so the function is
# idempotent on bios that are already in the third person.
# ──────────────────────────────────────────────────────────────────────

_PAST_VERBS = {
    "was", "did", "got", "joined", "started", "graduated", "moved", "founded",
    "wrote", "built", "earned", "completed", "finished", "left", "received",
    "served", "worked", "studied", "launched", "grew", "spent", "led",
    "managed", "created", "developed", "designed", "taught", "researched",
    "co-founded", "co-authored", "published", "decided", "moved", "spoke",
    "gave", "took", "saw", "made", "ran", "wrote", "lived", "shared",
    "presented", "contributed", "co-organized", "organized",
}


def _conjugate_3s(verb: str) -> str:
    """Return the 3rd-person singular form of a base-form verb."""
    if verb == "have":
        return "has"
    if verb == "do":
        return "does"
    if verb == "be":
        return "is"
    if verb == "go":
        return "goes"
    if verb.endswith("y") and not verb.endswith(("ay", "ey", "oy", "uy")):
        return verb[:-1] + "ies"
    if verb.endswith(("s", "ss", "sh", "ch", "x", "z", "o")):
        return verb + "es"
    return verb + "s"


# All "I (+verb)" / "I'm" / "I've" / etc. patterns rolled into one regex so
# we can rewrite each occurrence as a unit and switch between speaker-name
# and pronoun in a single pass.
_I_PATTERN = re.compile(
    r"""\bI
    (?:
        (?P<contr>['’](?:m|ve|ll|d|re))
        |\s+(?P<aux>am|have|had|will|can|could|would|should|might|must|do|does|did|was|were|been)\b
        |\s+(?P<verb>[a-zA-Z][a-zA-Z'’-]*)\b
        |\b(?P<bare>(?=[.,!?;:]|$))
    )""",
    re.VERBOSE,
)


def parse_pronouns(raw: str | None) -> dict[str, str]:
    """Map a Pretalx "How should we address you?" answer into pronoun forms.

    Defaults to singular they when no pronouns are recorded.
    """
    s = (raw or "").lower().strip()
    if "she" in s or "her" in s:
        return {"subj": "she", "obj": "her", "poss": "her", "refl": "herself"}
    if "he/" in s or "/him" in s or "him/" in s or s.startswith("he") and "she" not in s:
        return {"subj": "he", "obj": "him", "poss": "his", "refl": "himself"}
    return {"subj": "they", "obj": "them", "poss": "their", "refl": "themself"}


def to_third_person(bio: str, name: str, pronouns: dict[str, str] | None = None) -> str:
    """Best-effort first-person → third-person conversion.

    Args:
        bio: speaker biography (markdown / plain text).
        name: full name from Pretalx; the first token is used in subject
            position so the bio reads as a natural rewrite.
        pronouns: optional dict {subj, obj, poss, refl}; default they/them.
    """
    if not bio:
        return bio
    p = pronouns or {"subj": "they", "obj": "them", "poss": "their", "refl": "themself"}
    first = name.split()[0] if name else p["subj"].capitalize()

    text = bio

    # Strip greeting + self-intro at the start ("Hi, I'm X.", "My name is X and",
    # "I'm X!" etc.). The ### heading already shows the name.
    intro_pattern = (
        rf"^\s*(?:(?:Hi|Hello|Hey|Hiya|Greetings)[,!\.\s]+)?"
        rf"(?:(?:my name is|I\'m|I am|I’m)\s+{re.escape(first)}[,!\.\s]+(?:and\s+)?)?"
    )
    m = re.match(intro_pattern, text, flags=re.IGNORECASE)
    if m and m.end() > 0:
        text = text[m.end():].lstrip()
        if text and text[0].islower():
            text = text[0].upper() + text[1:]

    # Single-pass substitution. Each occurrence of "I (+verb)" chooses the
    # right subject + verb conjugation in one step. The counter switches the
    # subject from the speaker's name to the pronoun after the first hit so
    # the bio doesn't repeat the name in every sentence.
    is_singular_3rd = p["subj"] in {"he", "she"}
    counter = [0]

    def replace(match: "re.Match[str]") -> str:
        counter[0] += 1
        use_name = counter[0] == 1
        subj = first if use_name else p["subj"]
        # Pick the verb form: 3rd-singular for name (always) and for he/she;
        # plural for singular "they" (which takes plural verb forms).
        use_3s = use_name or is_singular_3rd

        contr_raw = match.group("contr") or ""
        contr = contr_raw.replace("'", "").replace("’", "")
        aux = match.group("aux") or ""
        verb = match.group("verb") or ""

        # Contractions
        if contr == "m":
            return f"{subj} {'is' if use_3s else 'are'}"
        if contr == "ve":
            return f"{subj} {'has' if use_3s else 'have'}"
        if contr == "ll":
            return f"{subj} will"
        if contr == "d":
            return f"{subj} would"  # heuristic: could also be "had"
        if contr == "re":
            return f"{subj} are"

        # Auxiliaries & irregulars
        if aux == "am":
            return f"{subj} {'is' if use_3s else 'are'}"
        if aux == "have":
            return f"{subj} {'has' if use_3s else 'have'}"
        if aux == "had":
            return f"{subj} had"
        if aux == "was":
            return f"{subj} {'was' if use_3s else 'were'}"
        if aux == "were":
            return f"{subj} were"
        if aux == "do":
            return f"{subj} {'does' if use_3s else 'do'}"
        if aux == "does":
            return f"{subj} does"
        if aux == "did":
            return f"{subj} did"
        if aux == "been":
            return f"{subj} been"  # rare standalone; usually after have/has
        if aux in {"will", "can", "could", "would", "should", "might", "must"}:
            return f"{subj} {aux}"

        # Generic verb
        if verb:
            if verb in _PAST_VERBS:
                v = verb
            elif use_3s:
                v = _conjugate_3s(verb)
            else:
                v = verb
            return f"{subj} {v}"

        # Bare "I" followed by punctuation
        return subj

    text = _I_PATTERN.sub(replace, text)

    # Possessive / object / reflexive pronouns (no alternation).
    text = re.sub(r"\bMy\b", p["poss"].capitalize(), text)
    text = re.sub(r"\bmy\b", p["poss"], text)
    text = re.sub(r"\bme\b", p["obj"], text)
    text = re.sub(r"\bmyself\b", p["refl"], text)

    # Capitalize the subject pronoun if it now sits at the start of a sentence.
    text = re.sub(
        rf"(^|[.!?]\s+)({re.escape(p['subj'])})\b",
        lambda m: f"{m.group(1)}{m.group(2).capitalize()}",
        text,
    )

    return text.strip()


_FP_DETECTOR = re.compile(
    r"\b(I am |I\'m |I’m |I\'ve |I’ve |I have |I had |I\'ll |I will |I do |I work|I run|I love)\b"
)


def looks_first_person(bio: str) -> bool:
    """Return True if the bio still appears to be in first person."""
    return bool(_FP_DETECTOR.search(bio or ""))


def load_pretalx_config() -> dict:
    """Load and validate the year-keyed Pretalx mapping from YAML."""
    with PRETALX_CONFIG.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def event_for(cfg: dict, year_override: str | None = None) -> tuple[str, str]:
    """Resolve which event slug and year to import.

    Order of precedence: explicit --year argument > env PRETALX_EVENT_NAME
    matched against archive entries > current event from YAML.
    """
    current_slug = cfg["events"]["current"]["slug"]
    current_year = str(cfg["events"]["current"]["year"])

    if year_override:
        if year_override == current_year:
            return current_slug, current_year
        for entry in cfg["events"].get("archive", []):
            if str(entry["year"]) == year_override:
                return entry["slug"], str(entry["year"])
        raise SystemExit(f"No event configured for year {year_override}")

    env_slug = os.environ.get("PRETALX_EVENT_NAME")
    if env_slug and env_slug != current_slug:
        # Allow env override but resolve year from YAML for consistency.
        for entry in [cfg["events"]["current"]] + cfg["events"].get("archive", []):
            if entry["slug"] == env_slug:
                return entry["slug"], str(entry["year"])
        # Unknown slug: import it anyway but warn (year unknown -> empty).
        return env_slug, ""

    return current_slug, current_year


def make_meta_description(abstract: str | None) -> str:
    """Compress an abstract into a clean ~155-char plain-text snippet.

    Strips line breaks, collapses whitespace, truncates on word boundary.
    """
    if not abstract:
        return ""
    text = re.sub(r"\s+", " ", abstract.strip())
    if len(text) <= META_DESCRIPTION_MAX:
        return text
    return textwrap.shorten(text, width=META_DESCRIPTION_MAX, placeholder="…")


def answer_for(sub_answers, question_id: int | None) -> str:
    """Return the .answer for the question with the given ID, or empty."""
    if question_id is None:
        return ""
    for ans in sub_answers or []:
        # pytanis exposes either AnswerQuestion (only id+text) or expanded form.
        q = ans.question
        q_id = getattr(q, "id", None) if not isinstance(q, int) else q
        if q_id == question_id:
            return ans.answer or ""
    return ""


def submission_type_slug(sub_type_id: int | None, type_map: dict) -> str:
    """Reverse-lookup the slug for a Pretalx submission_type_id within a year."""
    if sub_type_id is None:
        return ""
    for slug, mapped_id in type_map.items():
        if mapped_id == sub_type_id:
            return slug
    return ""


def submission_to_talk(sub, cfg: dict, year: str, audit: list | None = None) -> dict:
    """Map a pytanis Submission to the flat dict used in talks.json / .lr files."""
    questions = cfg["question_ids"].get(year, {})
    type_map = cfg["submission_type_ids"].get(year, {})
    type_labels = cfg["submission_type_labels"]

    t: dict[str, object] = defaultdict(lambda: "")
    t["title"] = sub.title
    t["abstract"] = sub.abstract or ""
    t["full_description"] = sub.description or ""
    t["description"] = make_meta_description(sub.abstract)
    t["code"] = sub.code
    t["state"] = sub.state.value
    t["created"] = sub.created.strftime("%Y-%m-%d") if sub.created else ""
    t["social_card_image"] = f"/static/media/social/talks/{sub.code}.png"
    t["speaker_names"] = ", ".join(speaker.name for speaker in sub.speakers)

    # Submission-type slug + display label resolved via YAML map.
    sub_type_id = sub.submission_type_id
    t["submission_type_id"] = str(sub_type_id) if sub_type_id is not None else ""
    type_slug = submission_type_slug(sub_type_id, type_map)
    t["submission_type"] = type_slug
    t["submission_type_label"] = type_labels.get(type_slug, "")
    t["is_keynote"] = type_slug == "keynote"

    # Speaker rendering. Pretalx pronouns aren't on SubmissionSpeaker — they
    # live on the Speaker object via a separate fetch. Default to singular
    # they so the conversion stays grammatically safe.
    for speaker in sub.speakers:
        t["speakers"] += speaker_to_markdown(speaker, audit=audit)

    # Submission-level answers driven by year-keyed question IDs.
    answers = sub.answers or []
    t["python_skill"] = answer_for(answers, questions.get("python_skill"))
    t["domain_expertise"] = answer_for(answers, questions.get("domain_expertise"))
    t["supporting_material_url"] = answer_for(answers, questions.get("supporting_material"))
    t["slides_link"] = answer_for(answers, questions.get("slides_link"))

    # Governance booleans (Pretalx returns "true"/"false" strings or "Yes"/"No").
    t["streaming_consent"] = _to_bool(answer_for(answers, questions.get("streaming_consent")))
    t["already_recorded"] = _to_bool(answer_for(answers, questions.get("already_recorded")))
    t["do_not_record"] = bool(getattr(sub, "do_not_record", False))

    # Tags (Pretalx may return empty list for editions that don't use them).
    tags = getattr(sub, "tags", None) or []
    t["tags"] = ", ".join(_tag_name(tag) for tag in tags if _tag_name(tag))

    # Track + label cleanup.
    if sub.track is not None:
        track_name = sub.track.name.en if hasattr(sub.track, "name") else ""
        t["track"] = TRACK_PREFIX_PATTERN.sub("", track_name or "")

    if sub.slot_count != 1:
        raise ValueError(
            f"Talk {sub.title} ({sub.code}) has {sub.slot_count} slots instead of 1!"
        )
    if sub.slots:
        slot = sub.slots[0]
        room_name = slot.room.en if slot.room else ""
        t["room"] = room_name or ""
        if slot.start:
            t["start_time"] = slot.start.strftime("%H:%M")
            t["slot_date"] = slot.start.strftime("%Y-%m-%d")
            t["day"] = calendar.day_name[slot.start.weekday()]
        if slot.end:
            t["end_time"] = slot.end.strftime("%H:%M")
        t["slot_id"] = str(getattr(slot, "id", "") or "")

    return t


def _to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1", "ja"}


def _tag_name(tag: object) -> str:
    if tag is None:
        return ""
    if isinstance(tag, str):
        return tag
    name = getattr(tag, "tag", None) or getattr(tag, "name", None)
    if hasattr(name, "en"):
        return name.en or ""
    return str(name) if name else ""


def speaker_to_markdown(speaker, pronouns: dict | None = None, audit: list | None = None) -> str:
    raw = speaker.biography or ""
    bio = to_third_person(raw, speaker.name, pronouns)
    if audit is not None and raw and looks_first_person(bio):
        audit.append((speaker.code, speaker.name, bio[:140]))
    tmpl = Template("""
### $name

$biography
""")
    return tmpl.substitute(name=speaker.name, biography=bio)


LR_TEMPLATE = Template(
    """title: $title
---
description: $description
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
slot_date: $slot_date
---
start_time: $start_time
---
end_time: $end_time
---
slot_id: $slot_id
---
track: $track
---
tags: $tags
---
submission_type: $submission_type
---
submission_type_label: $submission_type_label
---
submission_type_id: $submission_type_id
---
is_keynote: $is_keynote
---
do_not_record: $do_not_record
---
streaming_consent: $streaming_consent
---
already_recorded: $already_recorded
---
python_skill: $python_skill
---
domain_expertise: $domain_expertise
---
supporting_material_url: $supporting_material_url
---
slides_link: $slides_link
---
social_card_image: $social_card_image
"""
)


def submission_to_lektor(sub, cfg: dict, year: str, audit: list | None = None) -> str:
    talk = submission_to_talk(sub, cfg, year, audit=audit)
    # string.Template requires all keys present; defaultdict('') already covers it,
    # but normalize booleans to "yes"/"no" so Lektor reads them correctly.
    talk["is_keynote"] = "yes" if talk["is_keynote"] else "no"
    talk["do_not_record"] = "yes" if talk["do_not_record"] else "no"
    talk["streaming_consent"] = "yes" if talk["streaming_consent"] else "no"
    talk["already_recorded"] = "yes" if talk["already_recorded"] else "no"
    return LR_TEMPLATE.substitute(talk)


def submission_to_lektor_file(sub, cfg: dict, year: str, talks_dir: Path, audit: list | None = None) -> None:
    new_dir = talks_dir / sub.code
    new_dir.mkdir(parents=True, exist_ok=True)
    rendered = submission_to_lektor(sub, cfg, year, audit=audit)
    (new_dir / "contents.lr").write_text(rendered, encoding="utf-8")


def remove_old_talks(talks_dir: Path) -> None:
    """Wipe the given talks dir so removed Pretalx submissions disappear."""
    if not talks_dir.exists():
        return
    for entry in talks_dir.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)


def submissions_to_json_file(submissions, cfg: dict, year: str, json_path: Path) -> None:
    talks = [submission_to_talk(sub, cfg, year) for sub in submissions]
    json_path.write_text(json.dumps({"talks": talks}, default=str), encoding="utf-8")


def configure_pretalx_client() -> PretalxClient:
    load_dotenv(REPO_ROOT / ".env", override=False)
    api_key = os.environ.get("PRETALX_API_KEY")
    if not api_key:
        raise SystemExit("PRETALX_API_KEY is not set (check .env or environment)")

    class PretalxBasicModel(BaseModel):
        api_token: str | None = None
        api_version: str | None = None
        api_base_url: str | None = None
        timeout: float | None = None

    class PytanisBasicConfigModel(BaseModel):
        Pretalx: PretalxBasicModel

    cfg = PytanisBasicConfigModel.model_validate(
        {
            "Pretalx": {
                "api_token": api_key,
                "api_version": "",
                "api_base_url": "https://pretalx.com",
            }
        }
    )
    return PretalxClient(config=cfg)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Import confirmed Pretalx talks into Lektor content tree."
    )
    parser.add_argument(
        "--year",
        help="Override the edition year (e.g. 2025). Defaults to events.current in databags/pretalx.yaml.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Skip the wipe of content/talks/* before re-import. Useful for partial reimports.",
    )
    args = parser.parse_args()

    cfg = load_pretalx_config()
    slug, year = event_for(cfg, args.year)
    current_year = str(cfg["events"]["current"]["year"])
    talks_dir = talks_dir_for(year, current_year)
    json_path = talks_json_for(year, current_year)
    is_archive = year != current_year

    label = "archive" if is_archive else "current"
    print(f"Importing from Pretalx event '{slug}' (year={year or 'unknown'}, target={label})")
    print(f"  Talks dir: {talks_dir}")
    print(f"  JSON bag:  {json_path}")

    client = configure_pretalx_client()
    _, submissions = client.submissions(slug, params={"state": ["confirmed"]})
    submissions = list(submissions)
    print(f"Fetched {len(submissions)} confirmed submissions")

    if not args.keep_existing:
        remove_old_talks(talks_dir)

    talks_dir.mkdir(parents=True, exist_ok=True)
    audit: list[tuple[str, str, str]] = []
    for sub in submissions:
        submission_to_lektor_file(sub, cfg, year, talks_dir, audit=audit)
    submissions_to_json_file(submissions, cfg, year, json_path)
    print(f"Wrote {len(submissions)} talks to {talks_dir} and {json_path}")

    if audit:
        print()
        print(f"⚠️  {len(audit)} bios still look first-person after rewrite — manual review needed:")
        for code, name, snippet in audit:
            print(f"   - {code} · {name}: {snippet}…")
    else:
        print("All bios converted cleanly to third person.")


if __name__ == "__main__":
    main()
