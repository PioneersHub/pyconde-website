"""Lektor plugin to add YAML databag support."""

from __future__ import annotations

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

    def on_setup_env(self, **_extra: Any) -> None:
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
