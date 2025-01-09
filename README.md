# PyCon DE Website

PyCon DE &amp; PyData website for 2025 conference.

## Covered Workflows

### Changing content

#### Adding a sponsor

To add a new sponsor, you need to do two things:

1. Copy the svg logo to `./assets/static/media/sponsors/`
2. Add the information for the sponsor to `./databags/sponsors.json`

#### Adding a blog post

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

The new blog post will automatically be deployed, once it has been merged. Note: Due to some technicalities it can take up to an hour for the changes to be visible on the website.

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

You should probably not do that and rely on the github action for this. Otherwise you might have a local version deployed that is not reflected upstream.
But there will be the possibility for an emergency situation where you will need to quickly upload a hotpatch and can't wait for the github action. We have all been there:

```bash
make build
aws s3 cp tmp s3://<bucket-name>/ --recursive
```
