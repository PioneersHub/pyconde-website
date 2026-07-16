"""
One-off importer for the two pre-Pretalx editions: PyCon DE 2016 (Munich)
and PyCon DE 2017 (Karlsruhe).

These editions predate the Pretalx era, so there is no API. Data is sourced
from the web and transformed into the same archive structure used by the
2018-2025 editions:

  content/archive/{year}/contents.lr               archive-edition
  content/archive/{year}/talks/contents.lr         _model: talks
  content/archive/{year}/talks/{slug}/contents.lr  one per talk
  content/archive/{year}/speakers/contents.lr      _model: speakers
  content/archive/{year}/speakers/{slug}/contents.lr  one per speaker

Sources:
  2016: LMU cast JSON API  (title + presenter + LMU video URL per clip)
        /tmp/pycon2016-clips.json
  2017: 2017.pycon.de talk/tutorial/keynote pages, pre-parsed to
        /tmp/pycon2017-parsed.json

Speakers are keyed by a slug of their name (no Pretalx code exists). Talks
reference speakers exactly as the live archive does: the speaker's `talks`
field lists the talk-folder slugs, and the talk template resolves speakers
by intersecting that list with the talk's own folder name.

Idempotent: wipes and rewrites content/archive/{2016,2017}/ on each run.
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTENT = REPO / "content" / "archive"

CLIPS_2016 = Path("/tmp/pycon2016-clips.json")
PARSED_2017 = Path("/tmp/pycon2017-parsed.json")
LMU_CLIP_URL = "https://cast.itunes.uni-muenchen.de/clips/{id}/vod/online.html"


# ── helpers ──────────────────────────────────────────────────────────────

def slugify(s: str, maxlen: int = 80) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:maxlen].rstrip("-") or "untitled"


def lr(fields: list[tuple[str, str]]) -> str:
    """Render an ordered list of (name, value) into Lektor .lr text."""
    out = []
    for i, (name, value) in enumerate(fields):
        if i:
            out.append("---")
        value = "" if value is None else str(value)
        if "\n" in value:
            out.append(f"{name}:")
            out.append("")
            out.append(value)
        else:
            out.append(f"{name}: {value}" if value != "" else f"{name}:")
    return "\n".join(out) + "\n"


def uniq_slug(base: str, used: set[str]) -> str:
    slug = base
    n = 2
    while slug in used:
        slug = f"{base}-{n}"
        n += 1
    used.add(slug)
    return slug


# ── speaker accumulator (dedupe per edition) ─────────────────────────────

class Speakers:
    def __init__(self) -> None:
        self.by_key: dict[str, dict] = {}
        self.used_slugs: set[str] = set()

    def add(self, name: str, *, bio: str = "", twitter: str = "",
            homepage: str = "", github: str = "", company: str = "",
            job_title: str = "") -> str:
        name = name.strip()
        key = slugify(name)
        if key in self.by_key:
            sp = self.by_key[key]
            # enrich missing fields from later talks
            for f, v in (("bio", bio), ("twitter", twitter), ("homepage", homepage),
                         ("github", github), ("company", company), ("job_title", job_title)):
                if v and not sp[f]:
                    sp[f] = v
            return sp["slug"]
        slug = uniq_slug(key, self.used_slugs)
        self.by_key[key] = dict(name=name, slug=slug, bio=bio, twitter=twitter,
                                homepage=homepage, github=github, company=company,
                                job_title=job_title, talks=[])
        return slug


# ── 2017 ─────────────────────────────────────────────────────────────────

# Keynote pages are irregular (speaker title prefix, no Abstract/Description
# headings, trailing link rows). There are only three, so they are encoded
# verbatim here from the source pages rather than parsed heuristically.
KEYNOTES_2017 = [
    dict(
        slug="matthew-rocklin", name="Matthew Rocklin",
        title="Dask: Next Steps in Parallel Python",
        homepage="http://matthewrocklin.com",
        bio=("Matthew is an open source software developer focusing on efficient "
             "computation and parallel computing, primarily within the Python "
             "ecosystem. He has contributed to many of the PyData libraries and "
             "today works on Dask a framework for parallel computing. Matthew holds "
             "a PhD in computer science from the University of Chicago where he "
             "focused on numerical linear algebra, task scheduling, and computer "
             "algebra.\n\nMatthew lives in Brooklyn, NY and is employed by Anaconda Inc."),
        abstract="",
    ),
    dict(
        slug="michael-feindt", name="Prof. Dr. Michael Feindt",
        title="Artificial Intelligence: Differentiating Hype and Real Value",
        homepage="https://www.blue-yonder.com",
        bio=("Prof. Dr. Michael Feindt is the brain behind Blue Yonder GmbH. His "
             "NeuroBayes algorithm was developed during his many years of scientific "
             "research at CERN. Michael is also a professor at the Karlsruhe Institute "
             "of Technology (KIT), Germany, and a lecturer at the Data Science Academy."),
        abstract=("Starting from the evolution of biological and artificial life and "
                  "intelligence examples of already existing superhuman performance of "
                  "\"narrow\" AI are presented. The history of artificial neural networks "
                  "nicely shows how wrong human experts can be. Conditions for and "
                  "principles of predictive and prescriptive analytics, two important "
                  "working horses of AI, are presented. It is explained why superhuman "
                  "performance is especially possible in mass decisions under uncertainty. "
                  "Their value is proven with examples from largely improved and automated "
                  "public scientific research as well as decision making in enterprises. A "
                  "personal view about the role of python and some selected topics that will "
                  "gain much more attention like causality extraction from historic data and "
                  "discrimination-free algorithms are given, before concluding on how we "
                  "should face the challenges but especially the chances of AI to create a "
                  "better world."),
    ),
    dict(
        slug="susanne-mertens", name="Prof. Dr. Susanne Mertens",
        title="Neutrinos: who are you and if yes how many?",
        homepage="https://www.ph.tum.de/about/people/vcard/8C819C16F9AF3575/?language=en",
        bio=("Since 2008 Susanne Mertens is working on the experimental investigation of "
             "the elusive elementary particle, the Neutrino. With the two large-scale "
             "experiments, KATRIN and LEGEND, she explores their mass and the question of "
             "whether the neutrino is its own anti-particle. Beyond that, the group of "
             "Susanne Mertens is developing a novel detector system, to search for a new "
             "type of neutrino, the so-called sterile neutrino, which could make up a large "
             "part of the dark matter of our universe."),
        abstract=("The neutrino is a strange particle: it it extremely light and flies "
                  "through matter without leaving a trace. Nevertheless --due to its vast "
                  "abundance-- it plays a key role as cosmological architect in the formation "
                  "of galaxies in our universe. One of the missing puzzle pieces for the exact "
                  "understanding of the evolution of the universe is the mass of the neutrino. "
                  "The discovery of neutrino oscillations, awarded with the Nobel prize in 2015, "
                  "proofs that neutrinos are not massless, but does not reveal its actual value. "
                  "The Karlsruhe Tritium Neutrino (KATRIN) experiment aims at directly measuring "
                  "the neutrino mass by investigating the radioactive decay of tritium with "
                  "unprecedented precision. The talk will report on the mysterious neutrinos, how "
                  "KATRIN will track down their mass, and which role computational methods play in "
                  "the realization of such a large-scale experiment."),
    ),
]
KEYNOTES_BY_SLUG = {k["slug"]: k for k in KEYNOTES_2017}

# Three multi-speaker talks: the parser captured "Name1,Name2" plus one
# shared twitter. The source pages differ in how the bio is laid out, so
# each speaker's bio is specified explicitly (SHARED = use the single bio
# paragraph the page shows for both; a literal string = that speaker's own
# paragraph; "" = the page shows no bio for that speaker). This was caught
# by an independent re-fetch verification pass.
SHARED = object()
_MARTIN_FOERTSCH_BIO = (
    "Martin Förtsch is an IT-consultant of TNG Technology Consulting GmbH "
    "(https://tngtech.com) based in Unterföhring near Munich who studied "
    "computer sciences. Workwise his focus areas are Agile Development (mainly) "
    "in Java, Search Engine Technologies, Information Retrieval and Databases. As "
    "an Intel Software Innovator and Intel Black Belt Software Developer he is "
    "strongly involved in the development of open-source software for gesture "
    "control with 3D-cameras like e.g. Intel RealSense and has built an Augmented "
    "Reality wearable prototype device with his team based on this technology. "
    "Furthermore, he gives many talks on national and international conferences "
    "about Internet of Things, 3D-camera technologies, Augmented Reality and Test "
    "Driven Development as well. He was awarded with the JavaOne Rockstar award and "
    "is an author for the technical blog ParrotsOnJava.com."
)
_THOMAS_REIFENBERGER_BIO = (
    "Thomas Reifenberger works as an IT Consultant for the Munich based consulting "
    "company TNG Technology Consulting GmbH. Before joining the company in 2012 "
    "studied physics at the Technical University of Munich. Since then he worked for "
    "various customers in different sectors – with his technical focus areas being "
    "Java, Perl, Groovy & Python. Besides that he is involved in the company's "
    "hardware hacking team, where he is mainly working with IoT projects. Besides "
    "other tasks, he is involved in deployment automation, Linux administration and "
    "networking for the team."
)
MULTI_2017 = {
    # Live page shows the same shared bio under both names.
    "data-science-project-for-beginners": [
        ("Natalie Speiser", "natalie_lavrio", SHARED),
        ("Jens Beyer", "", SHARED),
    ],
    # Live page shows a bio only for Jens Nie; Peer Wagner has none.
    "empowered-by-python-a-success-story": [
        ("Jens Nie", "jneines", SHARED),
        ("Peer Wagner", "", ""),
    ],
    # Live page shows two distinct per-speaker bios.
    "project-avatar-telepresence-robotics-with-nao-and-kinect": [
        ("Thomas Reifenberger", "reifenbt", _THOMAS_REIFENBERGER_BIO),
        ("Martin Foertsch", "", _MARTIN_FOERTSCH_BIO),
    ],
}


# 2017 talk slug -> (youtube_id, ISO-8601 duration). Matched from the official
# 2017 PyCon DE YouTube playlist (PLHd2BPBhxqRI_HtgmPJcm3LPAlhdX6J9v) by
# fuzzy title match and 100% eyeball-verified. 56 of 63 talks have a recording;
# the 7 without are tutorials/workshops that were not recorded, plus the three
# lightning-talk compilation videos which have no individual session page.
YT_2017 = {
    'an-admin-s-cornucopia-python-is-more-than-just-a-better-bash': ('CQ3qwmld5V8', 'PT29M42S'),
    'an-introduction-to-pymc3': ('FKhivuCLIT0', 'PT43M32S'),
    'and-now-to-something-else-real-time-data-processing-billiger-de': ('en7XcpYxLU4', 'PT32M41S'),
    'automated-testing-with-400tb-memory': ('Lro5wC_HxhE', 'PT32M39S'),
    'building-your-own-sdn-with-debian-linux-salt-stack-and-python': ('yH_0hptXL94', 'PT37M8S'),
    'connecting-pydata-to-other-big-data-landscapes-using-arrow-and-parquet': ('-IvLScEcoO8', 'PT31M43S'),
    'data-plumbing-101-etl-pipelines-for-everyday-projects': ('D7fYa0NrCuE', 'PT27M56S'),
    'data-science-best-practices-from-proof-of-concepts-to-production': ('OPw0VrZdLdo', 'PT28M33S'),
    'data-science-project-for-beginners': ('4BBCqCgVDLI', 'PT30M48S'),
    'deep-learning-for-computer-vision': ('X4Q6C915sUY', 'PT41M30S'),
    'effective-data-analysis-with-pandas-indexes': ('-E2VTtdwT9U', 'PT30M52S'),
    'empowered-by-python-a-success-story': ('2Ku3tV3QQ3M', 'PT29M50S'),
    'flow-is-in-the-air-best-practices-of-building-analytical-data-pipelines-with-apa': ('Ea3smcbnGxE', 'PT47M46S'),
    'from-0-to-continuous-delivery-in-30-minutes': ('yqpOrB0JDto', 'PT30M51S'),
    'from-java-to-python-migrating-search-functionality-at-billiger-de': ('2fuW9ITUXrU', 'PT29M18S'),
    'getting-scikit-learn-to-run-on-top-of-pandas': ('boXOVvu43ZI', 'PT28M59S'),
    'graphql-in-the-python-world': ('FpQpF0BTrJU', 'PT25M3S'),
    'hacking-the-python-ast': ('kaxAF542Cic', 'PT36M6S'),
    'high-performance-ingestion-with-python-and-swarm64db': ('L4EdHKLB_08', 'PT40M59S'),
    'integrating-jupyter-notebooks-into-your-infrastructure': ('xplmuHEFqCg', 'PT32M49S'),
    'keeping-the-grip-on-decoupled-code-using-clis': ('F20vrgQCFMs', 'PT20M57S'),
    'large-scale-machine-learning-pipelines-using-luigi-pyspark-and-scikit-learn': ('VFB0rcfFCbg', 'PT32M28S'),
    'lift-your-speed-limits-with-cython': ('nTKQkm8U0zE', 'PT42M1S'),
    'master-2-5-gb-of-unstructured-specification-documents-with-ease': ('g277gRcG84I', 'PT30M25S'),
    'matthew-rocklin': ('rZlshXJydgQ', 'PT1H2M52S'),
    'michael-feindt': ('Ndi4hqSdBi4', 'PT1H11M52S'),
    'migrating-existing-codebases-to-using-type-annotations': ('JKvtrb2GWMY', 'PT37M32S'),
    'modern-etl-ing-with-python-and-airflow-and-spark': ('tcJhSaowzUI', 'PT26M36S'),
    'no-compromise-use-ansible-properly-or-stick-to-your-scripts': ('7qipNlReXYg', 'PT28M12S'),
    'observing-your-applications-with-sentry-and-prometheus': ('f3WO4bpLySs', 'PT22M54S'),
    'platform-intrusion-detection-with-deep-learning': ('dXqBuZi7JOE', 'PT43M32S'),
    'plugin-ecosystems-for-python-web-applications': ('5NxRdzLTFik', 'PT26M50S'),
    'programming-the-web-of-things-with-python-and-micropython': ('JtsLlYvcRJI', 'PT46M23S'),
    'project-avatar-telepresence-robotics-with-nao-and-kinect': ('SGpdc-9QAWE', 'PT37M32S'),
    'python-in-space-the-n-body-problem': ('E1nx4ReTgps', 'PT41M4S'),
    'python-is-weird': ('zz9yLOXo2Qk', 'PT26M35S'),
    'python-on-bare-metal-beginners-tutorial-with-micropython-on-the-pyboard': ('MpRXnyFeEwg', 'PT40M24S'),
    'python-with-apache-openwhisk': ('E9Yj4g9LuJc', 'PT30M5S'),
    'rasa-open-source-conversational-ai-to-build-next-generation-chatbots': ('LEFF7-_uh3M', 'PT30M32S'),
    'really-deep-neural-networks-with-pytorch': ('ZUHhNuw9Tlc', 'PT40M39S'),
    'simple-data-engineering-in-python-3-5-with-bonobo': ('3agWJTRn2cc', 'PT32M26S'),
    'sport-analysis-with-python': ('Fl6YFdf37IE', 'PT23M29S'),
    'susanne-mertens': ('3h-6GBBF4Hg', 'PT57M23S'),
    'synthetic-data-for-machine-learning-applications': ('riT9KTkBj0E', 'PT45M10S'),
    'technical-lessons-learned-from-pythonic-refactoring': ('Yq9-b2JKUyU', 'PT31M3S'),
    'the-borgbackup-project': ('oLFMsP1GMa0', 'PT30M20S'),
    'the-eye-of-the-python-an-eye-tracking-system-from-zero-to-what-eye-learned': ('JckAPb-HpME', 'PT39M54S'),
    'the-mustache-movement': ('9lVbpzd1hWk', 'PT28M34S'),
    'the-python-ecosystem-for-data-science-a-guided-tour': ('BIWcciNeMm0', 'PT37M24S'),
    'the-snake-in-the-tar-pit-complex-systems-with-python': ('pee-e01DiyI', 'PT41M11S'),
    'theoretical-physics-with-sympy': ('Ax0et1ZOOTc', 'PT33M1S'),
    'time-series-feature-extraction-with-tsfresh-get-rich-or-die-overfitting': ('Fm8zcOMJ-9E', 'PT27M11S'),
    'turbodbc-turbocharged-database-access-for-data-scientists': ('B-uj8EDcjLY', 'PT32M33S'),
    'verified-fakes-with-openapi': ('NZqovz37Qcw', 'PT7M16S'),
    'vim-your-python-python-your-vim': ('prnndyNV60w', 'PT29M31S'),
    'why-python-has-taken-over-finance': ('aXh7K6cFA8g', 'PT32M49S'),
}


def speaker_line_links(links: list[str]) -> tuple[str, str]:
    """From the speaker-line [LINK]s, return (homepage, github).

    Skip twitter links and internal/relative schedule links.
    """
    homepage = github = ""
    for l in links:
        if not l.startswith("http"):
            continue
        if "twitter.com" in l:
            continue
        if "2017.pycon.de" in l or "/schedule/" in l:
            continue
        if "github.com" in l and not github:
            github = l
        elif not homepage:
            homepage = l
    return homepage, github


def build_2017(speakers: Speakers) -> list[dict]:
    recs = json.load(open(PARSED_2017, encoding="utf-8"))
    talks = []
    used_talk_slugs: set[str] = set()
    for r in recs:
        kind = r["kind"]
        slug = uniq_slug(slugify(r["slug"]), used_talk_slugs)
        title = r["title"].strip()
        abstract = r["abstract"].strip()
        description = (r.get("description") or "").strip()

        # keynotes: use the verbatim hand-encoded record
        if kind == "keynote":
            k = KEYNOTES_BY_SLUG[r["slug"]]
            sp_slug = speakers.add(k["name"], bio=k["bio"], homepage=k["homepage"])
            speakers.by_key[slugify(k["name"])]["talks"].append(slug)
            talks.append(dict(
                slug=slug, title=k["title"], abstract=k["abstract"], description="",
                tags=[], speaker_names=k["name"],
                speakers_block=f"### {k['name']}\n\n{k['bio']}",
                is_keynote=True, submission_type="keynote", submission_type_label="Keynote",
            ))
            continue

        # resolve speakers
        talk_speaker_slugs = []
        speaker_blocks = []
        if r["slug"] in MULTI_2017:
            shared_bio = r.get("bio", "").strip()
            hp, gh = speaker_line_links(r["speakers"][0].get("links", []))
            for name, tw, bio_spec in MULTI_2017[r["slug"]]:
                bio = shared_bio if bio_spec is SHARED else bio_spec
                sp_slug = speakers.add(name, bio=bio, twitter=tw,
                                       homepage=hp, github=gh)
                speakers.by_key[slugify(name)]["talks"].append(slug)
                talk_speaker_slugs.append(name)
                if bio:  # omit the per-talk block for speakers with no bio
                    speaker_blocks.append(f"### {name}\n\n{bio}")
        else:
            sp = r["speakers"][0] if r["speakers"] else {"name": "", "bio": ""}
            name = sp["name"].strip()
            bio = (r.get("bio") or sp.get("bio") or "").strip()
            tw = sp.get("handle", "")
            hp, gh = speaker_line_links(sp.get("links", []))
            if name:
                sp_slug = speakers.add(name, bio=bio, twitter=tw, homepage=hp, github=gh)
                speakers.by_key[slugify(name)]["talks"].append(slug)
                talk_speaker_slugs.append(name)
                if bio:
                    speaker_blocks.append(f"### {name}\n\n{bio}")

        talks.append(dict(
            slug=slug, title=title, abstract=abstract, description=description,
            tags=r.get("tags", []), speaker_names=", ".join(talk_speaker_slugs),
            speakers_block="\n\n".join(speaker_blocks),
            is_keynote=(kind == "keynote"),
            submission_type={"talk": "talk", "tutorial": "tutorial", "keynote": "keynote"}[kind],
            submission_type_label={"talk": "Talk", "tutorial": "Tutorial", "keynote": "Keynote"}[kind],
        ))

    # Attach YouTube recordings (matched from the 2017 playlist).
    for t in talks:
        yt = YT_2017.get(t["slug"])
        if yt:
            vid, dur = yt
            t["youtube_id"] = vid
            t["video_link"] = f"https://www.youtube.com/watch?v={vid}"
            t["video_thumbnail"] = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
            t["video_duration_iso"] = dur
    return talks


# ── 2016 ─────────────────────────────────────────────────────────────────

# presenter strings that need manual speaker splitting
PRESENTER_OVERRIDE_2016 = {
    "Gökçen Eraslan & Martin Preusse - Institute of Computational Biology (HelmholtzZentrum München)":
        [("Gökçen Eraslan", "Institute of Computational Biology (Helmholtz Zentrum München)"),
         ("Martin Preusse", "Institute of Computational Biology (Helmholtz Zentrum München)")],
    "Anton Caceres, Freelance Code Poet | Uliana Andriieshyna, web developer":
        [("Anton Caceres", "Freelance Code Poet"),
         ("Uliana Andriieshyna", "web developer")],
}
LIGHTNING_PRESENTERS = {"diverses", "diverse"}


def parse_presenter_2016(presenter: str) -> list[tuple[str, str]]:
    presenter = (presenter or "").strip()
    if presenter in PRESENTER_OVERRIDE_2016:
        return PRESENTER_OVERRIDE_2016[presenter]
    if presenter.lower() in LIGHTNING_PRESENTERS:
        return []
    # "Name, affiliation"
    if "," in presenter:
        name, aff = presenter.split(",", 1)
        return [(name.strip(), aff.strip())]
    return [(presenter, "")]


def build_2016(speakers: Speakers) -> list[dict]:
    clips = json.load(open(CLIPS_2016, encoding="utf-8"))
    clips.sort(key=lambda c: c.get("position", 0))
    talks = []
    used_talk_slugs: set[str] = set()
    for c in clips:
        title = (c.get("title") or "").strip()
        slug = uniq_slug(slugify(title), used_talk_slugs)
        clip_id = c["id"]
        video = LMU_CLIP_URL.format(id=clip_id)
        date = (c.get("date") or "")[:10]

        pairs = parse_presenter_2016(c.get("presenter", ""))
        talk_speaker_names = []
        speaker_blocks = []
        for name, aff in pairs:
            # The 2016 source only gives a one-line affiliation per speaker;
            # use it as the (verbatim) biography. No separate job_title to
            # avoid duplicating the same string in two fields.
            bio = aff
            sp_slug = speakers.add(name, bio=bio)
            speakers.by_key[slugify(name)]["talks"].append(slug)
            talk_speaker_names.append(name)
            if bio:
                speaker_blocks.append(f"### {name}\n\n{bio}")

        talks.append(dict(
            slug=slug, title=title, abstract="", description="",
            tags=[], speaker_names=", ".join(talk_speaker_names),
            speakers_block="\n\n".join(speaker_blocks),
            is_keynote=False, submission_type="talk", submission_type_label="Talk",
            video_link=video, video_clip_id=clip_id, slot_date=date,
        ))
    return talks


# ── writers ──────────────────────────────────────────────────────────────

def write_talk(year: int, t: dict, created: str) -> None:
    d = CONTENT / str(year) / "talks" / t["slug"]
    d.mkdir(parents=True, exist_ok=True)
    desc = t["abstract"][:155] if t["abstract"] else t["title"]
    fields = [
        ("title", t["title"]),
        ("description", desc),
        ("created", created),
        ("code", t["slug"]),
        ("slug", t["slug"]),
        ("speaker_names", t["speaker_names"]),
        ("speakers", t["speakers_block"]),
        ("abstract", t["abstract"]),
        ("full_description", t["description"]),
        ("room", ""),
        ("day", ""),
        ("slot_date", t.get("slot_date", "")),
        ("start_time", ""),
        ("end_time", ""),
        ("slot_id", ""),
        ("track", ""),
        # Tags on the 2017 source were a flat space-separated list that can't
        # be safely re-split (multi-word tags like "machine learning"); the
        # live archive leaves this empty, so we do too.
        ("tags", ""),
        ("submission_type", t["submission_type"]),
        ("submission_type_label", t["submission_type_label"]),
        ("submission_type_id", ""),
        ("is_keynote", "yes" if t["is_keynote"] else "no"),
        ("do_not_record", "no"),
        ("python_skill", ""),
        ("domain_expertise", ""),
        ("supporting_material_url", ""),
        ("slides_link", ""),
        ("social_card_image", ""),
        ("youtube_id", t.get("youtube_id", "")),
        ("video_link", t.get("video_link", "")),
        ("video_published_at", ""),
        ("video_duration_iso", t.get("video_duration_iso", "")),
        ("video_thumbnail", t.get("video_thumbnail", "")),
        ("recording_available", "yes" if (t.get("video_link") or t.get("youtube_id")) else "no"),
    ]
    (d / "contents.lr").write_text(lr(fields), encoding="utf-8")


def write_speaker(year: int, sp: dict) -> None:
    d = CONTENT / str(year) / "speakers" / sp["slug"]
    d.mkdir(parents=True, exist_ok=True)
    fields = [
        ("_model", "speaker"),
        ("code", sp["slug"]),
        ("name", sp["name"]),
        ("slug", sp["slug"]),
        ("avatar", ""),
        ("pronouns", ""),
        ("country", ""),
        ("city", ""),
        ("company", sp.get("company", "")),
        ("job_title", sp.get("job_title", "")),
        ("homepage", sp.get("homepage", "")),
        ("linkedin", ""),
        ("github", sp.get("github", "")),
        ("mastodon", ""),
        ("threads", ""),
        ("bluesky", ""),
        ("twitter", sp.get("twitter", "")),
        ("is_first_time_speaker", "no"),
        ("talks", "\n".join(sp["talks"])),
        ("inactive_reason", ""),
        ("biography", sp.get("bio", "")),
    ]
    (d / "contents.lr").write_text(lr(fields), encoding="utf-8")


def write_edition(year: int, title: str, date_from: str, date_to: str,
                  location: str, body: str, n_talks: int, n_rec: int,
                  talks_title: str, speakers_title: str) -> None:
    base = CONTENT / str(year)
    base.mkdir(parents=True, exist_ok=True)
    (base / "contents.lr").write_text(lr([
        ("_model", "archive-edition"),
        ("title", title),
        ("year", str(year)),
        ("date_from", date_from),
        ("date_to", date_to),
        ("location", location),
        ("pretalx_slug", ""),
        ("talk_count", str(n_talks)),
        ("recording_count", str(n_rec)),
        ("body", "\n" + body),
    ]), encoding="utf-8")
    (base / "talks" / "contents.lr").write_text(lr([
        ("_model", "talks"), ("title", talks_title)]), encoding="utf-8")
    (base / "speakers" / "contents.lr").write_text(lr([
        ("_model", "speakers"), ("title", speakers_title)]), encoding="utf-8")


# ── main ─────────────────────────────────────────────────────────────────

def main() -> None:
    for year in (2016, 2017):
        shutil.rmtree(CONTENT / str(year), ignore_errors=True)

    # 2017
    sp17 = Speakers()
    talks17 = build_2017(sp17)
    for t in talks17:
        write_talk(2017, t, created="2017-10-25")
    for sp in sp17.by_key.values():
        write_speaker(2017, sp)
    n_rec17 = sum(1 for t in talks17 if t.get("youtube_id"))
    write_edition(
        2017, "PyCon.DE 2017 & PyData Karlsruhe",
        "2017-10-25", "2017-10-27", "ZKM | Center for Art and Media, Karlsruhe",
        "The 2017 edition of PyCon.DE & PyData Karlsruhe took place 25–27 October 2017 "
        "at the ZKM in Karlsruhe. Browse the [archived talks](talks/) and [speakers](speakers/) "
        "below, or revisit the [original conference site](https://2017.pycon.de/).",
        len(talks17), n_rec17,
        "PyCon.DE 2017 & PyData Karlsruhe — Talks",
        "PyCon.DE 2017 & PyData Karlsruhe — Speakers")
    print(f"2017: {len(talks17)} talks, {len(sp17.by_key)} speakers, {n_rec17} recordings")

    # 2016
    sp16 = Speakers()
    talks16 = build_2016(sp16)
    for t in talks16:
        write_talk(2016, t, created="2016-10-28")
    for sp in sp16.by_key.values():
        write_speaker(2016, sp)
    n_rec16 = sum(1 for t in talks16 if t.get("video_link"))
    write_edition(
        2016, "PyCon.DE 2016 Munich",
        "2016-10-28", "2016-10-30", "Ludwig-Maximilians-Universität, Munich",
        "The 2016 edition of PyCon.DE took place 28–30 October 2016 in Munich. "
        "Browse the [archived talks](talks/) and [speakers](speakers/) below — every "
        "session was recorded and is hosted by LMU Munich.",
        len(talks16), n_rec16,
        "PyCon.DE 2016 Munich — Talks",
        "PyCon.DE 2016 Munich — Speakers")
    print(f"2016: {len(talks16)} talks, {len(sp16.by_key)} speakers, {n_rec16} recordings")


if __name__ == "__main__":
    main()
