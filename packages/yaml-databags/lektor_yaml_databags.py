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

if TYPE_CHECKING:
    from lektor.environment import Environment

YAML_EXTENSIONS = (".yaml", ".yml")


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
        Note: YAML folded scalars (>) convert blank lines to single newlines,
        so we split on lines ending with double spaces followed by newline.

    Returns:
        HTML with each paragraph wrapped in <p> tags
    """
    if not text or (isinstance(text, str) and text.strip().startswith('<')):
        # Already HTML or empty
        return text

    # YAML folded scalars (>) preserve blank lines as lines ending with "  \n"
    # Split on this pattern to get paragraphs
    # First try double newlines (literal scalars)
    if '\n\n' in text:
        paragraphs = text.split('\n\n')
    else:
        # For folded scalars, split on "  \n" (two trailing spaces + newline)
        paragraphs = re.split(r'  \n', text)

    # Process each paragraph
    result = []
    for para in paragraphs:
        para = para.strip()
        if para:  # Skip empty paragraphs
            # Apply markdown inline formatting
            para = markdown_inline(para)
            # Replace remaining single newlines within paragraph with spaces
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
    """Discover all YAML databag files in the databags directory.

    Args:
        root_path: Path to the databags directory

    Returns:
        Dictionary mapping bag names to empty lists
    """
    if not root_path.exists():
        return {}

    yaml_bags = {}
    for filepath in root_path.iterdir():
        if filepath.suffix in YAML_EXTENSIONS:
            bag_name = filepath.stem
            yaml_bags[bag_name] = []

    return yaml_bags


class YAMLDatabagPlugin(Plugin):
    """Extends Lektor's databag system to support YAML files.

    This plugin monkey-patches the Databags class to recognize and load
    .yaml and .yml files in addition to the default .json and .ini formats.
    """

    name = "YAML Databags"
    description = "Adds support for .yaml and .yml databag files"

    def on_setup_env(self, **extra: Any) -> None:
        """Register Jinja filters when environment is set up."""
        # Register markdown filters for Jinja templates
        self.env.jinja_env.filters['markdown_inline'] = markdown_inline
        self.env.jinja_env.filters['paragraphize'] = paragraphize

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
