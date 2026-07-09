"""Lektor plugin to add YAML databag support."""

from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from lektor.context import get_ctx
from lektor.databags import Databags
from lektor.pluginsystem import Plugin
from markupsafe import Markup

if TYPE_CHECKING:
    from lektor.environment import Environment

YAML_EXTENSIONS = (".yaml", ".yml")

# Match <h1>...</h1> through <h5>...</h5> with any attributes.
# Used by the shift_headings filter to demote body-markdown headings
# so they never compete with the template-level page <h1>.
_HEADING_RE = re.compile(r"<(/?)(h[1-5])([^>]*)>", re.IGNORECASE)


def shift_headings(html: object, by: int = 1) -> Markup:
    """Demote all <h1>..<h5> tags in an HTML fragment by `by` levels.

    Default `by=1` turns h1 -> h2, h2 -> h3, ..., h5 -> h6 (capped at h6).
    Used in templates that render Markdown body content alongside a
    template-emitted <h1>, so author-written # headings in content
    files do not break the heading hierarchy.

    Accepts plain strings or any object exposing __html__ (Lektor's
    Markdown field, Markup, etc.). Always returns Markup so Jinja's
    autoescape leaves the HTML alone.

    Args:
        html: HTML fragment or Markdown-rendering object
        by: number of levels to shift down (1..4)

    Returns:
        Markup-wrapped HTML with shifted heading levels
    """
    if html is None:
        return Markup("")
    # Lektor's Markdown / Markup objects expose __html__()
    text = html.__html__() if hasattr(html, "__html__") else str(html)
    if not text:
        return Markup("")
    if by < 1:
        return Markup(text)
    cap = 6  # h6 is the deepest level; anything past stays h6

    def _sub(match: "re.Match[str]") -> str:
        closing, tag, attrs = match.group(1), match.group(2).lower(), match.group(3)
        level = int(tag[1])
        new_level = min(level + by, cap)
        return f"<{closing}h{new_level}{attrs}>"

    return Markup(_HEADING_RE.sub(_sub, text))


# Patterns used by the `social_url` filter to recognise pre-normalised forms.
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
# Mastodon webfinger handle: @user@server.tld (or user@server.tld without the @)
_MASTODON_WEBFINGER_RE = re.compile(r"^@?([\w.-]+)@([\w.-]+\.[a-z]{2,})$", re.IGNORECASE)
# `server.tld/@user` shape some users paste in
_MASTODON_PATH_RE = re.compile(r"^([\w.-]+\.[a-z]{2,})/@([\w.-]+)$", re.IGNORECASE)
# Bluesky bare handle (e.g. user.bsky.social)
_BLUESKY_HANDLE_RE = re.compile(r"^@?([\w.-]+\.bsky\.social)$", re.IGNORECASE)
# Plain identifier (alpha/num/_/-/.)
_BARE_HANDLE_RE = re.compile(r"^@?([A-Za-z0-9_.-]+)$")


def social_url(value: object, kind: str) -> str:
    """Normalise a stored social-media value to a canonical full URL.

    Speaker contents.lr files were imported over multiple years with
    inconsistent shapes — bare handles ("hendorf"), at-prefixed handles
    ("@hendorf"), full URLs ("https://twitter.com/hendorf"), mastodon
    webfinger handles ("@hendorf@fosstodon.org"), and path-style entries
    ("fosstodon.org/@hendorf"). This filter turns every recognised form
    into the same outbound URL so templates (the visible links, the
    JSON-LD `sameAs[]`, and the OpenGraph tags) all agree.

    Returns the canonical URL on success, or an empty string when the
    value is blank / a placeholder / unparseable. Templates should
    treat the empty string as "no profile".

    Recognised `kind` values: twitter, x, mastodon, bluesky, threads,
    github, linkedin, homepage.

    Args:
        value: stored field value (Lektor `Url` types pass through
            `str()` cleanly)
        kind: profile type so we know which canonical host to use

    Returns:
        Canonical URL or empty string
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s or s in {"-", "—", "n/a", "N/A", "none", "None"}:
        return ""

    kind = (kind or "").lower()

    # Already a full URL — return verbatim (don't try to rewrite the host).
    if _URL_RE.match(s):
        return s

    # Schemeless host with a path, like "twitter.com/hendorf" or
    # "www.linkedin.com/in/foo/". Prepend https://.
    if "/" in s and "." in s.split("/", 1)[0]:
        return "https://" + s.lstrip("/")

    # Bare host like "adrin.info" (used as homepage for some speakers).
    if kind == "homepage" and "." in s and " " not in s:
        return "https://" + s

    if kind in {"twitter", "x"}:
        m = _BARE_HANDLE_RE.match(s)
        if m:
            return f"https://x.com/{m.group(1)}"
        return ""

    if kind == "mastodon":
        m = _MASTODON_WEBFINGER_RE.match(s)
        if m:
            user, server = m.group(1), m.group(2)
            return f"https://{server}/@{user}"
        m = _MASTODON_PATH_RE.match(s)
        if m:
            server, user = m.group(1), m.group(2)
            return f"https://{server}/@{user}"
        return ""

    if kind == "bluesky":
        m = _BLUESKY_HANDLE_RE.match(s)
        if m:
            return f"https://bsky.app/profile/{m.group(1)}"
        m = _BARE_HANDLE_RE.match(s)
        if m:
            # Assume bsky.social if user didn't include the server suffix
            handle = m.group(1)
            if "." not in handle:
                handle = f"{handle}.bsky.social"
            return f"https://bsky.app/profile/{handle}"
        return ""

    if kind == "github":
        m = _BARE_HANDLE_RE.match(s)
        if m:
            return f"https://github.com/{m.group(1)}"
        return ""

    if kind == "linkedin":
        m = _BARE_HANDLE_RE.match(s)
        if m:
            # LinkedIn doesn't allow inferring vanity vs. company URLs
            # from a bare handle. Assume personal (`/in/`).
            return f"https://www.linkedin.com/in/{m.group(1)}/"
        return ""

    if kind == "threads":
        m = _BARE_HANDLE_RE.match(s)
        if m:
            user = m.group(1).lstrip("@")
            return f"https://www.threads.net/@{user}"
        return ""

    return ""


def social_label(value: object, kind: str) -> str:
    """Return a short, screen-friendly display label for a social URL.

    Strips scheme, www., and obvious path noise so screen-reader and
    visible captions don't render the entire URL. Falls back to the
    raw value if no shortening applies.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    s = re.sub(r"^https?://", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^www\.", "", s, flags=re.IGNORECASE)
    s = s.rstrip("/")
    if kind in {"twitter", "x"} and s.startswith(("x.com/", "twitter.com/")):
        return "@" + s.split("/", 1)[1]
    if kind == "github" and s.startswith("github.com/"):
        return "@" + s.split("/", 1)[1]
    if kind == "linkedin" and "linkedin.com/in/" in s:
        return s.split("linkedin.com/in/", 1)[1].rstrip("/")
    if kind == "bluesky" and "bsky.app/profile/" in s:
        return "@" + s.split("bsky.app/profile/", 1)[1]
    if kind == "mastodon" and "/@" in s:
        server, _, user = s.partition("/@")
        return f"@{user}@{server}"
    return s


def markdown_inline(text: str) -> str:
    """Convert inline markdown syntax to HTML.

    Args:
        text: Text possibly containing markdown syntax

    Returns:
        Text with markdown converted to HTML
    """
    if not text or (isinstance(text, str) and text.strip().startswith('<')):
        return text

    # Convert **bold** to <strong>bold</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    return text


def paragraphize(text: str) -> str:
    """Convert text with blank lines into proper HTML paragraphs.

    Args:
        text: Text with paragraphs separated by blank lines
        Note: YAML folded scalars (>) indicate paragraph breaks by:
        - Lines ending with "  " (two spaces) before a newline
        - Actual blank lines in literal scalars (\n\n)

    Returns:
        HTML with each paragraph wrapped in <p> tags
    """
    if not text or (isinstance(text, str) and text.strip().startswith('<')):
        # Already HTML or empty
        return text

    # Handle literal scalars with \n\n first
    if '\n\n' in text:
        # Literal scalar (|) - split on double newlines
        paragraph_texts = text.split('\n\n')
    else:
        # Folded scalar (>) - split on lines ending with "  \n"
        # This preserves the YAML convention for hard line breaks
        paragraph_texts = re.split(r'  \n', text)

    # Process each paragraph
    result = []
    for para in paragraph_texts:
        para = para.strip()
        if para:  # Skip empty paragraphs
            # Apply markdown inline formatting
            para = markdown_inline(para)
            # Replace any remaining single newlines with spaces
            para = re.sub(r'\s*\n\s*', ' ', para)
            result.append(f'<p>{para}</p>')

    return '\n'.join(result)


def _load_yaml_databag(yaml_path: Path) -> OrderedDict | Any:
    """Load YAML databag file and return its contents.

    Args:
        yaml_path: Path to the YAML file to load

    Returns:
        OrderedDict if data is a dict, otherwise returns data as-is
    """
    ctx = get_ctx()
    if ctx is not None:
        ctx.record_dependency(str(yaml_path))

    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return OrderedDict(data) if isinstance(data, dict) else data


def _discover_yaml_bags(root_path: Path) -> dict[str, list]:
    """Discover all YAML databag files, including in subdirectories.

    Bag names mirror the file path relative to databags/ without the
    suffix, e.g. ``frontpage/sections/intro.yaml`` becomes the bag
    ``frontpage/sections/intro`` — templates access it via
    ``bag('frontpage/sections/intro')``.

    Args:
        root_path: Path to the databags directory

    Returns:
        Dictionary mapping bag names to empty lists
    """
    if not root_path.exists():
        return {}

    yaml_bags = {}
    for filepath in sorted(root_path.rglob("*")):
        if filepath.suffix in YAML_EXTENSIONS:
            bag_name = filepath.relative_to(root_path).with_suffix("").as_posix()
            yaml_bags[bag_name] = []

    return yaml_bags


class YAMLDatabagPlugin(Plugin):
    """Extends Lektor's databag system to support YAML files.

    This plugin monkey-patches the Databags class to recognize and load
    .yaml and .yml files in addition to the default .json and .ini formats.
    YAML bags may live in subdirectories; the bag name is the relative
    path without suffix (e.g. ``bag('frontpage/config')`` reads
    ``databags/frontpage/config.yaml``).
    """

    name = "YAML Databags"
    description = "Adds support for .yaml and .yml databag files"

    def on_setup_env(self, **extra: Any) -> None:
        """Register Jinja filters when environment is set up."""
        # Register markdown filters for Jinja templates
        self.env.jinja_env.filters['markdown_inline'] = markdown_inline
        self.env.jinja_env.filters['paragraphize'] = paragraphize
        # Demote body-markdown headings so they never collide with the
        # template-level <h1>. Used in talk/blog/markdown body templates.
        self.env.jinja_env.filters['shift_headings'] = shift_headings
        # Normalise social-media handles / URLs to canonical full URLs and
        # short display labels — handles the mixed shapes ("hendorf",
        # "@hendorf", "https://twitter.com/hendorf") in speaker contents.lr.
        self.env.jinja_env.filters['social_url'] = social_url
        self.env.jinja_env.filters['social_label'] = social_label

        # Call the databag setup
        self._setup_databags()

    def _setup_databags(self) -> None:
        """Patch databag loading to support YAML files.

        This hook is called during environment setup and patches both the
        get_bag and __init__ methods of the Databags class.
        """
        original_get_bag = Databags.get_bag
        original_init = Databags.__init__

        def patched_get_bag(self: Databags, name: str) -> Any:
            """Get databag by name, checking YAML files if JSON/INI not found.

            Args:
                name: Name of the databag to retrieve

            Returns:
                Databag contents as dict or other data structure

            Raises:
                KeyError: If databag is not found in any supported format
            """
            # Try original formats (JSON/INI) first
            try:
                result = original_get_bag(self, name)
                if result is not None:
                    return result
            except (KeyError, FileNotFoundError):
                pass

            # Try YAML files
            root = Path(self.root_path)
            for ext in YAML_EXTENSIONS:
                yaml_path = root / f"{name}{ext}"
                if yaml_path.exists():
                    return _load_yaml_databag(yaml_path)

            raise KeyError(f"Databag '{name}' not found")

        def patched_init(self: Databags, env: Environment) -> None:
            """Initialize Databags and discover YAML files.

            Args:
                env: Lektor environment instance
            """
            original_init(self, env)

            # Register YAML databags in the known bags registry
            yaml_bags = _discover_yaml_bags(Path(self.root_path))
            for bag_name, bag_files in yaml_bags.items():
                self._known_bags.setdefault(bag_name, bag_files)

        # Apply monkey patches
        Databags.get_bag = patched_get_bag
        Databags.__init__ = patched_init
