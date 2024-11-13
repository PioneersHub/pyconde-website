# PyCon DE Website

PyCon DE &amp; PyData website for 2025 conference.

## Covered Workflows

### Changing content

### Updating website code

## Dev Setup

Following steps are required to develop and run the website locally:

### Setup

1. Select the right Python version, the one used and tested is stored in `./.python-version`, however, most relatively current versions should work. Use whatever Python version manager you prefer, for example `pyenv`.
2. Create a virtual environment and activate it, so that the dependencies for this project won't clash with other, locally installed libraries: `python -m venv`.
3. Create a virtual environment and activate it, so that the dependencies for this project won't clash with other, locally installed libraries: `python -m venv ./venv && source venv/bin/activate`.
4. Install the dependencies: `pip install -r requirements.txt`.

### Run locally

`make run`

### Pull newest content

## Content Source

All the content is provided via Pretalx.

## Deployment/Hosting

The site is hosted as a static site on AWS/S3.

### Automation

### Manual Deployment
