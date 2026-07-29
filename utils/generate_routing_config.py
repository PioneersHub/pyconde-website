"""Generate hosting-layer redirect config from databags/routing.yaml.

The site has three redirect layers (see the header of databags/routing.yaml).
This script owns the third: prefix rewrites that the *host* applies as real
HTTP 301s, covering every URL beneath a prefix.

Why not reuse the existing generators: databags/redirects.yaml is exact-path
only and renders HTML meta-refresh pages, which cannot express "/latest/* ->
/archive/2026/*" and are weaker for crawlers. Those generators also emit
nginx/Caddy snippets into site-config/, but that directory is gitignored and
no workflow consumes it — nothing there reaches production.

One YAML source, three renderings, so the rule is never written twice:

    site-config/s3-website-routing.json   applied by routing-config.yml
    site-config/routing.nginx.conf        if the site ever moves behind nginx
    site-config/Caddyfile.routing         same, for Caddy

The S3 document is the one in use. `aws s3api put-bucket-website` replaces
the entire website configuration, so IndexDocument and ErrorDocument have to
be part of it — omitting them would break the whole site. Pass `--merge` with
the bucket's current configuration and those values are carried over rather
than guessed; databags/routing.yaml only supplies the fallback.

    python utils/generate_routing_config.py
    python utils/generate_routing_config.py --merge current-website.json

Note: S3 routing rules only fire on the bucket's *website* endpoint. If a CDN
sits in front with the REST endpoint as its origin, the rules never run and
the alias needs an edge function instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ROUTING_CONFIG = REPO_ROOT / "databags" / "routing.yaml"
SITE_STATE_CONFIG = REPO_ROOT / "databags" / "site_state.yaml"
OUT_DIR = REPO_ROOT / "site-config"

S3_JSON = OUT_DIR / "s3-website-routing.json"
NGINX_OUT = OUT_DIR / "routing.nginx.conf"
CADDY_OUT = OUT_DIR / "Caddyfile.routing"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Missing required config: {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_placeholders(value: str, site_state: dict) -> str:
    """Substitute {featured_edition} from databags/site_state.yaml.

    Fails loudly rather than emitting a rule with a literal placeholder in it,
    which would silently redirect visitors to a 404.
    """
    if "{featured_edition}" not in value:
        return value
    year = ((site_state.get("featured_edition") or {}).get("year") or "")
    if not year:
        raise SystemExit(
            "routing.yaml uses {featured_edition} but site_state.yaml has no "
            "featured_edition.year. Set it, or drop the placeholder."
        )
    return value.replace("{featured_edition}", str(year))


def load_rules() -> list[dict]:
    cfg = load_yaml(ROUTING_CONFIG)
    site_state = load_yaml(SITE_STATE_CONFIG)
    rules = []
    for raw in cfg.get("prefix_redirects") or []:
        src = raw["from"].strip()
        dst = resolve_placeholders(raw["to"].strip(), site_state)
        if not src.startswith("/") or not src.endswith("/"):
            raise SystemExit(f"prefix_redirects 'from' must start and end with '/': {src!r}")
        if not dst.startswith("/") or not dst.endswith("/"):
            raise SystemExit(f"prefix_redirects 'to' must start and end with '/': {dst!r}")
        rules.append(
            {
                "from": src,
                "to": dst,
                "status": str(raw.get("status", 301)),
                "note": (raw.get("note") or "").strip(),
            }
        )
    if not rules:
        raise SystemExit("No prefix_redirects defined in databags/routing.yaml.")
    return rules


def build_website_config(rules: list[dict], current: dict | None) -> dict:
    """Assemble the full S3 website configuration.

    Anything the bucket already declares wins over the databag fallback, so
    applying this never silently changes settings we did not intend to touch.
    """
    cfg = load_yaml(ROUTING_CONFIG).get("website") or {}
    current = current or {}

    index = (current.get("IndexDocument") or {}).get("Suffix") or cfg.get("index_document")
    if not index:
        raise SystemExit("No IndexDocument: set website.index_document in routing.yaml.")

    out: dict = {"IndexDocument": {"Suffix": index}}

    error = (current.get("ErrorDocument") or {}).get("Key") or cfg.get("error_document")
    if error:
        out["ErrorDocument"] = {"Key": error}

    out["RoutingRules"] = [
        {
            "Condition": {"KeyPrefixEquals": r["from"].lstrip("/")},
            "Redirect": {
                "ReplaceKeyPrefixWith": r["to"].lstrip("/"),
                "HttpRedirectCode": r["status"],
            },
        }
        for r in rules
    ]
    return out


def write_server_snippets(rules: list[dict]) -> None:
    nginx = [
        "# Generated by utils/generate_routing_config.py — DO NOT EDIT.",
        "# Source: databags/routing.yaml. Emitted so the routing rules stay",
        "# portable if the site ever moves off S3 website hosting.",
        "",
    ]
    caddy = list(nginx)
    for i, r in enumerate(rules):
        if r["note"]:
            nginx.append(f"# {r['note']}")
            caddy.append(f"# {r['note']}")
        # Both need a capture group to carry the rest of the path across.
        # nginx: a prefix `location` has no captures, so this must be a
        # rewrite. `permanent` is 301; `redirect` would be 302.
        verb = "permanent" if r["status"] == "301" else "redirect"
        src = r["from"].rstrip("/")
        nginx.append(f"rewrite ^{src}/(.*)$ {r['to']}$1 {verb};")
        # Caddy v2: capture groups come from a *named* path_regexp matcher and
        # are referenced as {re.<name>.<n>} — a bare `redir /latest/*` cannot
        # reference the remainder of the path.
        name = f"prefix{i}"
        caddy.append(f"@{name} path_regexp {name} ^{src}/(.*)$")
        caddy.append(f"redir @{name} {r['to']}{{re.{name}.1}} {r['status']}")
    NGINX_OUT.write_text("\n".join(nginx) + "\n", encoding="utf-8")
    CADDY_OUT.write_text("\n".join(caddy) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--merge",
        type=Path,
        help="Existing bucket website configuration (aws s3api get-bucket-website output) "
        "whose IndexDocument/ErrorDocument should be preserved.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print, do not write.")
    args = parser.parse_args()

    rules = load_rules()

    current = None
    if args.merge:
        if not args.merge.exists():
            raise SystemExit(f"--merge file not found: {args.merge}")
        text = args.merge.read_text(encoding="utf-8").strip()
        current = json.loads(text) if text else {}

    website = build_website_config(rules, current)
    payload = json.dumps(website, indent=2) + "\n"

    for r in rules:
        print(f"  {r['status']}  {r['from']}*  ->  {r['to']}*")

    if args.dry_run:
        print(payload)
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    S3_JSON.write_text(payload, encoding="utf-8")
    write_server_snippets(rules)
    print(f"  wrote {S3_JSON.relative_to(REPO_ROOT)}")
    print(f"  wrote {NGINX_OUT.relative_to(REPO_ROOT)}, {CADDY_OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
