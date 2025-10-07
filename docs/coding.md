# Development with Lektor

## Pretalx Integration

Session and speaker data is automatically synchronized from Pretalx via GitHub Actions. See `.github/workflows/fetch_submissions.yml` for the automated process. Never edit session data directly in this repository.

## Development Setup

### Using Pixi (Recommended)

```bash
pixi install
pixi shell
```

### Using uv

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Using Devcontainer

Open the project in VS Code with the Dev Containers extension installed. The container includes all dependencies.

## Lektor Commands

```bash
# Start development server
lektor server

# Start with admin interface
lektor server --with-admin

# Build static site
lektor build -O site/
```

## Creating Content

### Pages

```bash
lektor new-page --path <path> --title "<Title>"
```

### Blog Posts

See `docs/blog_post.md`

### Subsites

See `docs/subsites.md`

## Project Structure

- `content/` - Page content and structure
- `models/` - Content type definitions
- `templates/` - Jinja2 templates
- `databags/` - YAML/JSON data files
- `assets/` - Static files (CSS, JS, images)
- `flowblocks/` - Reusable content components