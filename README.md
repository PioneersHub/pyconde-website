# PyCon DE Website

[![Fetch submissions](https://github.com/PioneersHub/pyconde-website/actions/workflows/fetch_submissions.yml/badge.svg)](https://github.com/PioneersHub/pyconde-website/actions/workflows/fetch_submissions.yml) [![Upload website](https://github.com/PioneersHub/pyconde-website/actions/workflows/main.yml/badge.svg)](https://github.com/PioneersHub/pyconde-website/actions/workflows/main.yml)[![Upload staging website](https://github.com/PioneersHub/pyconde-website/actions/workflows/development.yml/badge.svg)](https://github.com/PioneersHub/pyconde-website/actions/workflows/development.yml)

PyCon DE &amp; PyData website for 2025 conference.

> **Important Note for Speakers**  
> All speaker and session information is sourced from Pretalx.  
**To update your bio or session description, please make the changes directly in Pretalx.**  
> The website updates periodically, at least once per day, to reflect changes from Pretalx.

## Workflows

### Adding a Blog Post

1. Create a new branch
2. Add a folder for the new blog post under `./content/blog/<blogpost-title>`
3. Add a `contents.lr` file to this folder.

This file will contain the blog post (as markdown) and some additional metadata. Here is an example on how this could look like:

```
title: Something exciting just happened!
---
pub_date: 2025-05-07
---
body:

# The air is thrumming with excitement

Something unbelievable just happened in the **Python** world. Let me tell you all about it:
```

The `title` field is a simple string.

The `pub_date` field is the date, formatted like this: YYYY-mm-dd.

the `body` is the blog post as markdown.

4. Commit the changes to your new branch
5. Push the changes
6. Open a PR
7. Merge the PR, once it has been approved

The new blog post will automatically be deployed, once it has been merged. Note: Due to some technicalities it can take up to an hour for
the changes to be visible on the website.

### Adding Sponsors and Partners

To add a new sponsor or community partner, you need to do two things:

1. Copy the svg logo to `./assets/static/media/sponsors/`
2. Add the information for the sponsor to `./databags/sponsors.json`
3. Run `make sponsor-pages`. This will generate the individual sponsor page, based on the data in the databag.


### Dynamic Landing Page

> DO NOT CHANGE THE CONTENT of the home page: `content/contents.lr`. This file will be overwritten.

The landing page should change, based on if the conference is currently running (or soon to be running) or if the conference is over. There are two landing page versions:

#### 1. Landing Page (announced, forthcoming and running conference)

Inform about the forthcoming conference and provide information during the running conference (CTAs, tickets, registration, etc.).

#### 2. Landing Page (after the conference, until the next conference is announced)

When the conference is over the landing page should show a summary of the event and some preparation for the next event. The forthcoming
conference is not set up yet, and we want to present highlights to make an appetite for the next conference.

#### Managing index page contents

The contents for the landing pages is located in the following files:

Landing Page (active, this is the content for the running conference)

`content/landing-page-active/contents.lr`

Landing Page (inactive, this is the content for when the conference is over)

`content/landing-page-inactive/contents.lr`

If you for example want to change the content for the landing page of the running conference, change it in
`content/landing-page-active/contents.lr`.

Afterward you need to run `make` to copy the correct landing page to the location that Lektor expects:

Set the active landing page (when the conference is running) as the current one:
`make activate-conference`

Set the active landing page (when the conference is over) as the current one:
`make disable-conference`

#### Adding images for the "inactive" landing page

Add images to the correct folders in `./assets/static/landing-page` then run `make landing-page` to update the databag.


#### Adding a subsite

Adding a subsite involves changes in /models, /databags, and /content structure.

#### Adding or changing talks

You should not try to change or add talks in this repository since they will be automatically updated via a script and would be pverwritten
or deleted.

You can change/add or remove talks in Pretalx and it will automatically be updated on the website via the previously mentioned update
process. See the GitHub actions in `./.github/workflows/main.yml` for details.

### Updating website code

 TODO

---

## Dev Setup

Following steps are required to develop and run the website locally:

### Setup

There are two options for local development. Both option are valid.

#### Conventional Setup

1. Select the right Python version, the one used and tested is stored in `./.python-version`, however, most relatively current versions
   should work. Use whatever Python version manager you prefer, for example `pyenv`.
2. Create a virtual environment and activate it, so that the dependencies for this project won't clash with other, locally installed
   libraries: `python -m venv ./venv && source venv/bin/activate`.
3. Install the dependencies: `pip install -r requirements.txt`.

#### Devcontainer Setup

After having cloned this repository:

1. Make sure to have a local installation of Docker and VS Code running.
2. Open VS Code and make sure to have the Dev Containers Extension from Microsoft installed.
3. Open the cloned project in VS Code and from the bottom right corner confirm to open the project to be opened within the Devcontainer.

If you miss any dependencies check out the devcontainer.json within the .devcontainer folder. The correct python version and all python
dependencies are already installed.

### Run locally

`make run`

### Pull newest content

## Content Source

All the content is provided via Pretalx.

--- 

## Deployment/Hosting

The site is hosted as a static site on AWS/S3.

To (re-)create the S3 bucket setup in the eu-central-1 region, run the following:

Prerequisites:

- aws-cli
- aws credentials that allow you to create and manage S3 buckets

Create the bucket:

```bash
aws s3api create-bucket --bucket <bucket-name> --region eu-central-1 --create-bucket-configuration LocationConstraint=eu-central-1
```

Allow policies to set public access:

```bash
aws s3api put-public-access-block --bucket <bucket-name> --public-access-block-configuration "BlockPublicPolicy=false"
```

Check that the settings are correct:

```bash
aws s3api get-bucket-ownership-controls --bucket <bucket-name>
```

Allow public read through policy.

```bash
aws s3api put-bucket-policy --bucket <bucket-name> --policy '{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::'<bucket-name>'/*"
 
            ]
        }
    ]
}'
```

Copy website to s3:

```bash
aws s3 cp tmp s3://<bucket-name>/ --recursive
```

Set index:

```bash
aws s3 website s3://<bucket-name> --index-document index.html
```

Confirm the results:

```bash
curl <bucket-name>.s3-website.eu-central-1.amazonaws.com
```

AWS provides in-depth guides on how to setup SSL and your domain, check it out on the buckets' page:
https://eu-central-1.console.aws.amazon.com/s3/buckets/<bucket-name>?region=eu-central-1&bucketType=general&tab=properties

### Automation

A github action workflow is provided and will take care of building and deployment. Check out `./.github/workflows/main.yml` for details.

Don't forget to set the following secrets in the github project:

- AWS_S3_BUCKET
- AWS_REGION
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY

### Manual Deployment

You should probably not do that and rely on the github action for this. Otherwise you might have a local version deployed that is not
reflected upstream.
But there will be the possibility for an emergency situation where you will need to quickly upload a hotpatch and can't wait for the github
action. We have all been there:

```bash
make build
aws s3 cp tmp s3://<bucket-name>/ --recursive
```

## License & Notice

- 📜 **[MIT License](LICENSE)**
- ⚠️ **[Notice - Logos & Trademarks Excluded](NOTICE.md)**
