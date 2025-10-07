# Lektor YAML Databags Plugin

A minimal local plugin that adds YAML support to Lektor's databag system.

## Overview

By default, Lektor only supports `.json` and `.ini` files for databags. This plugin extends Lektor to also recognize and load `.yaml` and `.yml` files from the `databags/` directory.

## Features

- Loads YAML databag files (`.yaml` and `.yml` extensions)
- Maintains compatibility with existing JSON and INI databags
- Preserves file ordering (uses OrderedDict)
- Properly integrates with Lektor's dependency tracking system

## Installation

This plugin is automatically activated when placed in the `packages/` directory of your Lektor project. No additional configuration is needed.

## Usage

Simply place your YAML files in the `databags/` directory, and access them using the standard `bag()` function in templates:

```jinja
{{ bag('links')['pages'] }}
{{ bag('sponsors', 'keystone') }}
```

## Implementation

The plugin works by monkey-patching Lektor's `Databags` class to:
1. Check for YAML files when a databag is requested
2. Discover YAML files during initialization
3. Load YAML files with proper dependency tracking

## Dependencies

- `pyyaml>=6.0`
