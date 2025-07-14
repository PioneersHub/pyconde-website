# Dynamic Landing Page

> DO NOT CHANGE THE CONTENT of the home page: `content/contents.lr`. This file will be overwritten.

The landing page should change, based on if the conference is currently running (or soon to be running) or if the conference is over. There are two landing page versions:

## 1. Landing Page (announced, forthcoming and running conference)

Inform about the forthcoming conference and provide information during the running conference (CTAs, tickets, registration, etc.).

## 2. Landing Page (after the conference, until the next conference is announced)

When the conference is over the landing page should show a summary of the event and some preparation for the next event. The forthcoming
conference is not set up yet, and we want to present highlights to make an appetite for the next conference.

## Managing index page contents

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

## Adding images for the "inactive" landing page

Add images to the correct folders in `./assets/static/landing-page` then run `make landing-page` to update the databag.
