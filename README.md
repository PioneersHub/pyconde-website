# PyCon DE Website

[![Fetch submissions](https://github.com/PioneersHub/pyconde-website/actions/workflows/fetch_submissions.yml/badge.svg)](https://github.com/PioneersHub/pyconde-website/actions/workflows/fetch_submissions.yml)
[![Upload website](https://github.com/PioneersHub/pyconde-website/actions/workflows/main.yml/badge.svg)](https://github.com/PioneersHub/pyconde-website/actions/workflows/main.yml)
[![Upload staging website](https://github.com/PioneersHub/pyconde-website/actions/workflows/development.yml/badge.svg)](https://github.com/PioneersHub/pyconde-website/actions/workflows/development.yml)

PyCon DE &amp; PyData conference website.

> **Important Note for Speakers**  
> All speaker and session information is sourced from Pretalx.  
**To update your bio or session description, please make the changes directly in Pretalx.**  
> The website updates periodically, at least once per day, to reflect changes from Pretalx.

## Workflows

1. Add a blog post [details](./docs/blog_post.md)
2. Add a sponsor [details](./docs/sponsors_partners.md)
3. Add a community partner [details](./docs/sponsors_partners.md)
4. Manage pre-conference and post-conference landing pages [details](./docs/landing_pages.md)
5. Add a subsite [details](./docs/subsites.md)
6. Manage sessions (talks, tutorials,…) [details](./docs/pretalx.md)
7. Manage speaker-information [details](./docs/pretalx.md)
8. Update the coding [details](./docs/coding.md)
9. Deploy the website [details](./docs/deployment.md)

---

## Development Setup

Following steps are required to develop and run the website locally:

### Setup

There are two options for local development. Both option are valid.

#### Conventional Setup

1. Select the right Python version, the one used and tested is stored in `./.python-version`, however, most relatively current versions
   should work. Use whatever Python version manager you prefer, for example `pyenv`.
2. Create a virtual environment and activate it, so that the dependencies for this project won't clash with other, locally installed
   libraries:`python -m venv ./venv && source venv/bin/activate`.
3. Install the dependencies: `pip install -r requirements.txt`.

#### Setup with uv

```shell
uv venv
```

#### Devcontainer Setup

After having cloned this repository:

1. Make sure to have a local installation of Docker and VS Code running.
2. Open VS Code and make sure to have the Dev Containers Extension from Microsoft installed.
3. Open the cloned project in VS Code and from the bottom right corner confirm to open the project to be opened within the Devcontainer.

If you miss any dependencies check out the devcontainer.json within the .devcontainer folder. The correct python version and all python
dependencies are already installed.

### Run locally

Lektor requires local plugins to be installed. This will take care of all of it.

``bash
make run
``

---

## License & Notice

- **[MIT License](LICENSE)**
- **[Notice - Logos & Trademarks Excluded](NOTICE.md)**
