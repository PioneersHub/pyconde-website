"""
Yaml is more convenient for editing than JSON, but the JSON file is the source of truth.
"""

import json
from pathlib import Path

import yaml

yaml.representer.SafeRepresenter.ignore_aliases = lambda *args: True


def fill_missing(template, actual):
    """Recursively merge template with actual data, filling missing keys with null."""
    if isinstance(template, dict):
        result = {}
        for key, value in template.items():
            if key in actual:
                result[key] = fill_missing(value, actual[key])
            else:
                result[key] = (
                    None
                    if not isinstance(value, (dict, list))
                    else fill_missing(value, {})
                )
        return result
    elif isinstance(template, list):
        # If the actual value is a list, apply the template to each item
        if isinstance(actual, list):
            return [
                fill_missing(template[0], item) if isinstance(item, dict) else item
                for item in actual
            ]
        else:
            return []
    else:
        return actual


def json_to_yaml(json_path: Path, yaml_path: Path, template_path: Path):
    with template_path.open() as f:
        template = yaml.load(f.read(), Loader=yaml.FullLoader)
    with json_path.open() as f:
        data = json.load(f)

    merged = fill_missing(template, data)

    with yaml_path.open("w") as f:
        yaml.dump(
            merged,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            indent=2,
            width=80,
            explicit_start=True,
        )


def yaml_to_json(yaml_path: Path, json_path: Path):
    with yaml_path.open() as f:
        data = yaml.load(f.read(), Loader=yaml.FullLoader)

    with json_path.open("w") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )


if __name__ == "__main__":
    template_file = Path(__file__).parents[1] / "databags/sponsors_template.yaml"
    json_file = Path(__file__).parents[1] / "databags/sponsors.json"
    yaml_file = json_file.with_suffix(".yaml")

    # json_to_yaml(json_file, yaml_file, template_file)
    yaml_to_json(yaml_file, json_file)

    print(f"Converted {json_file} to {yaml_file}")
