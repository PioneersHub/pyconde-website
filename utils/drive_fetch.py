"""Fetch a sponsor's material from its Google Drive folder.

Confirmed sponsors deliver a logo and a document (website, social links,
description) in a folder under "Sponsors 2027". This saves the folder's logo
files into the sponsor logo directory and prints each Google Doc as plain
text, ready to be turned into an entry in databags/sponsors.yaml.

Authentication reuses the Google OAuth client configured for pytanis
(~/.pytanis/config.toml, or the file named by $PYTANIS_CONFIG) but keeps a
separate, read-only Drive token, so the pytanis token is never touched:

    [Google]
    client_secret_json = "client_secret.json"
    drive_token_json = "drive_token.json"

Relative paths are resolved against the config file's folder, as in pytanis.
The first run opens a browser for consent and writes the token file.

Usage:
    uv run --extra drive python utils/drive_fetch.py <folder-url-or-id>
"""

import argparse
import io
import re
import sys
import tomllib
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from pytanis.config import get_cfg_file

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
REPO = Path(__file__).parents[1]
LOGO_DIR = REPO / "assets/static/media/sponsors"
LOGO_TYPES = {"image/svg+xml", "image/png", "image/jpeg"}
GOOGLE_DOC = "application/vnd.google-apps.document"

FOLDER_URL = re.compile(r"/folders/([\w-]+)")
DRIVE_ID = re.compile(r"^[\w-]{20,}$")
# An SVG is served from our own origin, so anything that can run script is refused.
UNSAFE_SVG = re.compile(
    rb"<script|\son[a-z]+\s*=|javascript:|<foreignObject", re.IGNORECASE
)


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def folder_id(folder):
    """Accept a Drive folder link or a bare folder id."""
    if match := FOLDER_URL.search(folder):
        return match.group(1)
    if DRIVE_ID.match(folder):
        return folder
    fail(f"'{folder}' is neither a Drive folder link nor a folder id")


def oauth_files():
    """Client secret and Drive token paths from the pytanis config."""
    cfg_path = get_cfg_file()
    if not cfg_path.is_file():
        fail(f"pytanis config {cfg_path} not found; it holds the Google OAuth client")
    with cfg_path.open("rb") as fh:
        google = tomllib.load(fh).get("Google", {})
    missing = [
        key for key in ("client_secret_json", "drive_token_json") if not google.get(key)
    ]
    if missing:
        fail(
            f"[Google] in {cfg_path} needs {' and '.join(missing)} (see utils/drive_fetch.py)"
        )
    secret, token = (
        cfg_path.parent / google[key]
        for key in ("client_secret_json", "drive_token_json")
    )
    if not secret.is_file():
        fail(f"client secret {secret} not found")
    return secret, token


def credentials(secret, token):
    """Read-only Drive credentials; asks for consent once, then refreshes."""
    creds = (
        Credentials.from_authorized_user_file(token, SCOPES)
        if token.is_file()
        else None
    )
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        # Redirect to the literal IPv4 loopback the listener binds to; with
        # "localhost" a browser may try IPv6 first and never reach it.
        # The consent page opens in $BROWSER if set, else the default browser.
        creds = InstalledAppFlow.from_client_secrets_file(
            secret, SCOPES
        ).run_local_server(host="127.0.0.1", port=0)
    token.write_text(creds.to_json())
    return creds


def list_folder(drive, folder):
    files, page = [], None
    while True:
        result = (
            drive.files()
            .list(
                q=f"'{folder}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page,
            )
            .execute()
        )
        files += result.get("files", [])
        if not (page := result.get("nextPageToken")):
            return files


def download(request):
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def save_logo(drive, item):
    target = LOGO_DIR / item["name"]
    if target.exists():
        fail(f"{target} already exists; remove it first to replace it")
    content = download(
        drive.files().get_media(fileId=item["id"], supportsAllDrives=True)
    )
    if item["mimeType"] == "image/svg+xml" and UNSAFE_SVG.search(content):
        fail(
            f"{item['name']} contains script or event handlers; ask the sponsor for a clean SVG"
        )
    target.write_bytes(content)
    print(f"Saved logo: {target.relative_to(REPO)} ({len(content):,} bytes)")


def print_doc(drive, item):
    text = download(
        drive.files().export_media(fileId=item["id"], mimeType="text/plain")
    )
    print(f"\n----- {item['name']} -----\n{text.decode('utf-8-sig').strip()}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", help="Drive folder link or id")
    args = parser.parse_args()
    try:
        fetch(folder_id(args.folder))
    except HttpError as error:
        # Google's message names the fix, e.g. the link to enable the Drive API.
        fail(f"Google Drive API {error.status_code}: {error.reason}")


def fetch(folder):
    drive = build("drive", "v3", credentials=credentials(*oauth_files()))
    files = list_folder(drive, folder)
    if not files:
        fail("the folder is empty or not shared with this Google account")

    for item in files:
        if item["mimeType"] in LOGO_TYPES:
            save_logo(drive, item)
        elif item["mimeType"] == GOOGLE_DOC:
            print_doc(drive, item)
        else:
            print(f"Skipped: {item['name']} ({item['mimeType']})")


if __name__ == "__main__":
    main()
