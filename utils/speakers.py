"""Pretalx → Lektor importer for speaker profiles.

Pulls confirmed speakers + their answers in a single throttled call per
edition, writes one Lektor page per speaker (current edition under
/speakers/{code}/, archive editions under /archive/{year}/speakers/{code}/),
and downloads each Pretalx avatar to the static-media tree.

Speaker bios are preserved verbatim. When a bio is written in the first
person the importer prepends one italic framing line so the voice reads
as a quoted statement — same convention as `utils/talks.py`.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import time
import urllib.parse
from pathlib import Path
from string import Template
from typing import Any

import httpx
import yaml
from dotenv import load_dotenv

# Re-use the bio-detection helper from talks.py so the two importers stay
# consistent (looks_first_person + framing convention).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from talks import looks_first_person  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
PRETALX_CONFIG = REPO_ROOT / "databags" / "pretalx.yaml"
CONTENT_DIR = REPO_ROOT / "content"
AVATAR_DIR = REPO_ROOT / "assets" / "static" / "media" / "speakers"
PRETALX_API = "https://pretalx.com/api/events"
REQUEST_DELAY_S = 0.6  # Stay well below Pretalx's burst threshold.
PAGE_LIMIT = 100


def load_pretalx_config() -> dict:
    with PRETALX_CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def event_for(cfg: dict, year_override: str | None) -> tuple[str, str]:
    """Resolve which event slug + year to import."""
    current = cfg["events"]["current"]
    archive = cfg["events"].get("archive", []) or []
    candidates = [current, *archive]
    if year_override:
        for entry in candidates:
            if str(entry["year"]) == year_override:
                return entry["slug"], str(entry["year"])
        raise SystemExit(f"No event configured for year {year_override}")
    return current["slug"], str(current["year"])


def speakers_dir_for(year: str, current_year: str) -> Path:
    """Where speaker pages live on disk for this edition."""
    if year == current_year:
        return CONTENT_DIR / "speakers"
    return CONTENT_DIR / "archive" / year / "speakers"


def confirmed_talk_codes(year: str, current_year: str) -> set[str]:
    """Set of pretalx codes whose .lr files exist for this edition.

    Used to filter the Pretalx speakers endpoint (which also returns
    speakers whose proposals were rejected or never confirmed).
    """
    if year == current_year:
        talks_dir = CONTENT_DIR / "talks"
    else:
        talks_dir = CONTENT_DIR / "archive" / year / "talks"
    if not talks_dir.exists():
        return set()
    return {p.name for p in talks_dir.iterdir() if p.is_dir() and (p / "contents.lr").exists()}


def slug_from_name(name: str) -> str:
    """Stable URL slug from a name. Idempotent."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s.strip("-") or "speaker"


def fetch_token() -> str:
    load_dotenv(REPO_ROOT / ".env", override=False)
    token = os.environ.get("PRETALX_API_KEY")
    if not token:
        raise SystemExit("PRETALX_API_KEY is not set (check .env or environment)")
    return token


def iter_speakers(slug: str, token: str) -> list[dict]:
    """Walk the paginated Pretalx speakers endpoint for one event.

    `?expand=answers` inlines each speaker's answers so we only need one
    request per page.
    """
    out: list[dict] = []
    url: str | None = f"{PRETALX_API}/{slug}/speakers/?expand=answers&limit={PAGE_LIMIT}"
    headers = {"Authorization": f"Token {token}", "Accept": "application/json"}
    page = 1
    while url:
        print(f"  Fetching speakers page {page} …", flush=True)
        r = httpx.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("results", []))
        url = data.get("next")
        page += 1
        time.sleep(REQUEST_DELAY_S)
    return out


def answer_for(answers: list[dict] | None, question_id: int | None) -> str:
    if question_id is None or not answers:
        return ""
    for a in answers:
        q = a.get("question")
        q_id = q.get("id") if isinstance(q, dict) else q
        if q_id == question_id:
            return (a.get("answer") or "").strip()
    return ""


def download_avatar(url: str, code: str) -> str:
    """Download avatar to assets/static/media/speakers/{code}.{ext}.

    Idempotent: if the file already exists, the URL is returned as-is.
    Returns the public path (relative to site root) or "" on failure.
    """
    if not url:
        return ""
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    # Pretalx URLs look like .../avatars/{code}_xxxxxxx.webp — keep extension.
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower() or ".webp"
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}:
        ext = ".webp"
    target = AVATAR_DIR / f"{code}{ext}"
    public = f"/static/media/speakers/{code}{ext}"
    if target.exists():
        return public
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True)
        r.raise_for_status()
        target.write_bytes(r.content)
        return public
    except Exception as e:
        print(f"  ⚠️  avatar download failed for {code}: {e}")
        return ""


def split_csv(raw: str) -> list[str]:
    return [t.strip() for t in (raw or "").split(",") if t.strip()]


LR_TEMPLATE = Template("""_model: speaker
---
code: $code
---
name: $name
---
slug: $slug
---
avatar: $avatar
---
pronouns: $pronouns
---
country: $country
---
city: $city
---
company: $company
---
job_title: $job_title
---
homepage: $homepage
---
linkedin: $linkedin
---
github: $github
---
mastodon: $mastodon
---
threads: $threads
---
bluesky: $bluesky
---
twitter: $twitter
---
is_first_time_speaker: $is_first_time_speaker
---
talks:

$talks
---
inactive_reason: $inactive_reason
---
biography:

$biography
""")


def speaker_to_lektor(speaker: dict, year: str, questions: dict[str, int | None]) -> tuple[str, dict]:
    """Build the .lr text for one speaker and return (rendered, meta) for audit."""
    code = speaker["code"]
    name = speaker.get("name", "").strip() or "Unknown Speaker"
    answers = speaker.get("answers") or []

    # Stammdaten
    raw_bio = (speaker.get("biography") or "").strip()
    if raw_bio and looks_first_person(raw_bio):
        first = name.split()[0]
        bio = f"_This is what {first} says:_\n\n{raw_bio}"
    else:
        bio = raw_bio

    # Pretalx social / identity answers — null-safe per question_ids YAML.
    avatar_url = (speaker.get("avatar_url") or "").strip()
    avatar_public = download_avatar(avatar_url, code) if avatar_url else ""

    submissions = speaker.get("submissions") or []

    # Inactive flag: skeleton page with neither bio nor avatar gets noindex.
    inactive_reason = "insufficient_data" if not (bio or avatar_public) else ""

    fields = {
        "code": code,
        "name": name,
        "slug": slug_from_name(name),
        "avatar": avatar_public,
        "pronouns": answer_for(answers, questions.get("pronouns")),
        "country": answer_for(answers, questions.get("country")),
        "city": answer_for(answers, questions.get("city")),
        "company": answer_for(answers, questions.get("company")),
        "job_title": answer_for(answers, questions.get("job_title")),
        "homepage": answer_for(answers, questions.get("homepage")),
        "linkedin": answer_for(answers, questions.get("linkedin")),
        "github": answer_for(answers, questions.get("github")),
        "mastodon": answer_for(answers, questions.get("mastodon")),
        "threads": answer_for(answers, questions.get("threads")),
        "bluesky": answer_for(answers, questions.get("bluesky")),
        "twitter": answer_for(answers, questions.get("twitter")),
        "is_first_time_speaker": "yes" if answer_for(answers, questions.get("first_time_speaker")).lower() in {"true", "yes", "1", "ja"} else "no",
        "talks": "\n".join(submissions),
        "inactive_reason": inactive_reason,
        "biography": bio,
    }
    rendered = LR_TEMPLATE.substitute(fields)
    return rendered, fields


def write_speaker_file(rendered: str, code: str, speakers_dir: Path) -> None:
    target = speakers_dir / code
    target.mkdir(parents=True, exist_ok=True)
    (target / "contents.lr").write_text(rendered, encoding="utf-8")


def write_speakers_index(speakers_dir: Path, edition_title: str) -> None:
    """Idempotently create the speakers listing-page node if missing."""
    contents = speakers_dir / "contents.lr"
    if contents.exists():
        return
    speakers_dir.mkdir(parents=True, exist_ok=True)
    contents.write_text(
        f"_model: speakers\n---\ntitle: {edition_title} — Speakers\n",
        encoding="utf-8",
    )


def remove_old_speakers(speakers_dir: Path) -> None:
    if not speakers_dir.exists():
        return
    for entry in speakers_dir.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import speakers from Pretalx into Lektor.")
    parser.add_argument("--year", help="Edition year to import. Defaults to events.current.")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Skip the wipe of speaker dirs before re-import (allows partial reimport).",
    )
    args = parser.parse_args()

    cfg = load_pretalx_config()
    slug, year = event_for(cfg, args.year)
    current_year = str(cfg["events"]["current"]["year"])
    speakers_dir = speakers_dir_for(year, current_year)
    questions = cfg["question_ids"].get(year, {}) or {}

    is_archive = year != current_year
    target_label = "archive" if is_archive else "current"
    print(f"Importing speakers from '{slug}' (year={year}, target={target_label})")
    print(f"  Speakers dir: {speakers_dir}")

    # Only speakers who actually presented a confirmed talk in this edition.
    # Pretalx exposes everyone who submitted (incl. rejected); the site should
    # only list real speakers.
    confirmed = confirmed_talk_codes(year, current_year)
    if not confirmed:
        raise SystemExit(
            f"No confirmed talks found for {year}. Run utils/talks.py --year {year} first."
        )

    token = fetch_token()
    all_speakers = iter_speakers(slug, token)
    speakers = [
        sp for sp in all_speakers
        if set(sp.get("submissions") or []) & confirmed
    ]
    print(f"Fetched {len(all_speakers)} speakers from Pretalx; {len(speakers)} matched confirmed talks.")

    edition_title = f"PyCon DE & PyData {year}"
    if not args.keep_existing:
        remove_old_speakers(speakers_dir)
    write_speakers_index(speakers_dir, edition_title)

    framed = 0
    stubs = 0
    for sp in speakers:
        # Restrict the talks: array to confirmed codes only — keeps cross-links clean.
        kept = [c for c in (sp.get("submissions") or []) if c in confirmed]
        sp["submissions"] = kept
        rendered, fields = speaker_to_lektor(sp, year, questions)
        write_speaker_file(rendered, sp["code"], speakers_dir)
        if "_This is what " in fields["biography"]:
            framed += 1
        if fields["inactive_reason"]:
            stubs += 1

    print(f"Wrote {len(speakers)} speaker pages.")
    print(f"  {framed} bios framed (first-person voice preserved with intro line).")
    if stubs:
        print(f"  {stubs} speakers stubbed (no bio + no avatar → noindex).")


if __name__ == "__main__":
    main()
