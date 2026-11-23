# Adding a Blog Post

1. Create a new branch
2. Create a folder for the new blog post under `content/blog/<blogpost-title>/`
3. Create a `contents.lr` file in this folder.

This file contains the blog post content (in Markdown) and metadata. Example:

```text
title: Something exciting just happened!
---
pub_date: 2025-05-07
---
body:

# The air is thrumming with excitement

Something unbelievable just happened in the **Python** world. Let me tell you all about it:
```

The `title` field is a simple string.

The `pub_date` field is the date, formatted as `YYYY-MM-DD`.

The `body` field contains the blog post content in Markdown format.

4. Run `make page-cards` to draw the post's social card. It shows the title beside a python, on a background colour picked for the post,
   is saved as `content/blog/<blogpost-title>/social_card.png` and linked from the post.
   To use your own image instead, see [Hand-made cards are never replaced](social_cards.md#hand-made-cards-are-never-replaced).
5. Commit the changes to your new branch
6. Push the changes
7. Open a pull request
8. Merge the pull request once approved

The new blog post will be deployed automatically after merging.

> **Note:** Due to CDN caching and deployment pipeline processing, changes may take up to an hour to appear on the website.
