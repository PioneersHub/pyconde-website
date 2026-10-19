"""Atomically flip ticket pricing to the next ticket edition.

Tickets are sold in editions (e.g. Early -> Blind -> Wise -> Late Bird),
listed in sale order under `editions` in `databags/tickets.yaml`.
`make flip-pricing` advances to the next edition; `make flip-pricing
PERIOD=<edition id>` jumps to (or rolls back to) a specific one.
`make sync-pricing` (`--by-date`, run by CI) picks the edition whose
`opens` date is the latest one reached today in the configured time
zone, and never moves back to an earlier edition — so a manual early
flip (e.g. Edition I sold out before its date) survives the next
build. Both the schema source and the UI CTA are rewritten from the
tier list so the AggregateOffer JSON-LD and the on-page price line
never drift:

  - tickets.yaml: sets `active_period`, rewrites `aggregate`
    (low/high/offer_count from the on-sale tiers only) and
    `price_valid_until` (the day before the next edition opens; the
    last edition runs to `valid_through`).
  - frontpage/sections/tickets.yaml: rewrites `period`, `price_label`
    (from the 3-day standard tier of the active edition) and
    `strike_price` (the next edition's 3-day standard price,
    loss-framing; empty for the last edition).

Comment-preserving: edits are line-targeted, not a full YAML round
trip, so the helpful docs in both files survive the flip.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

REPO = Path(__file__).resolve().parent.parent
TICKETS = REPO / "databags" / "tickets.yaml"
TICKETS_CTA = REPO / "databags" / "frontpage" / "sections" / "tickets.yaml"


def set_line(text: str, key: str, value: str, source: Path) -> str:
    """Replace a top-level `key: ...` line (regex, multiline)."""
    pattern = re.compile(rf"(?m)^{re.escape(key)}: .*$")
    if not pattern.search(text):
        raise SystemExit(f"Field `{key}` not found in {source.name}")
    return pattern.sub(f"{key}: {value}", text, count=1)


def set_indented_line(text: str, key: str, value: str) -> str:
    """Replace a 2-space-indented `  key: ...` line under aggregate."""
    pattern = re.compile(rf"(?m)^  {re.escape(key)}: .*$")
    if not pattern.search(text):
        raise SystemExit(f"Field `  {key}` not found in {TICKETS.name}")
    return pattern.sub(f"  {key}: {value}", text, count=1)


def parse_date(s: str) -> date:
    return datetime.strptime(s.strip('"'), "%Y-%m-%d").date()


def fmt(d: date) -> str:
    return f'"{d.isoformat()}"'


def three_day_standard_price(tiers: list[dict], edition: str) -> int:
    """The headline price of an edition: its 3-day standard tier."""
    for t in tiers:
        if t.get("id") == f"3day-standard-{edition}":
            return t["price"]
    raise SystemExit(f"No tier `3day-standard-{edition}` in {TICKETS.name}.")


def edition_by_date(cfg: dict, ids: list[str], current: str, today: date) -> str:
    """The latest edition whose `opens` date has been reached, never earlier than `current`.

    Before the first edition opens, the first edition's prices stand.
    """
    reached = [e["id"] for e in cfg["editions"] if parse_date(e["opens"]) <= today]
    by_date = reached[-1] if reached else ids[0]
    return max(by_date, current, key=ids.index)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--period",
        help="Target edition id; default advances to the next edition.",
    )
    mode.add_argument(
        "--by-date",
        action="store_true",
        help="Select the edition from today's date (used by CI).",
    )
    p.add_argument(
        "--today",
        help="Override today's date (YYYY-MM-DD) for --by-date, e.g. to preview a switch.",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.today and not args.by_date:
        p.error("--today only applies with --by-date")
    return args


def select_target(
    cfg: dict, ids: list[str], current: str, args: argparse.Namespace
) -> str:
    """Resolve the edition to switch to from the command-line mode."""
    if args.by_date:
        if args.today:
            today = parse_date(args.today)
        else:
            tz = cfg.get("timezone")
            if not tz:
                raise SystemExit(f"--by-date needs `timezone` in {TICKETS.name}.")
            today = datetime.now(ZoneInfo(tz)).date()
        target = edition_by_date(cfg, ids, current, today)
        print(f"Edition by date ({today.isoformat()}): {target}")
        return target
    if args.period:
        if args.period not in ids:
            raise SystemExit(f"Unknown edition `{args.period}`; choose one of {ids}.")
        return args.period
    position = ids.index(current)
    if position == len(ids) - 1:
        raise SystemExit(
            f"`{current}` is the last edition; pass PERIOD=<edition id> to roll back."
        )
    return ids[position + 1]


def flip(cfg: dict, current: str, target: str, dry_run: bool) -> None:
    """Rewrite tickets.yaml and the UI CTA for the `target` edition."""
    editions = cfg["editions"]
    public = [t for t in cfg.get("tiers") or [] if t.get("kind") == "public"]
    on_sale = [t for t in public if t.get("period") == target]
    if not on_sale:
        raise SystemExit(f"No public tiers for edition `{target}` in {TICKETS.name}.")

    low = min(t["price"] for t in on_sale)
    high = max(t["price"] for t in on_sale)
    offer_count = len(on_sale)

    position = [e["id"] for e in editions].index(target)
    next_edition = editions[position + 1] if position + 1 < len(editions) else None
    if next_edition:
        price_valid_until = fmt(parse_date(next_edition["opens"]) - timedelta(days=1))
    else:
        price_valid_until = fmt(parse_date(cfg["valid_through"]))

    target_price = three_day_standard_price(public, target)
    next_price = (
        three_day_standard_price(public, next_edition["id"]) if next_edition else None
    )

    # --- tickets.yaml (schema source) ---
    tx = TICKETS.read_text(encoding="utf-8")
    tx = set_line(tx, "active_period", target, TICKETS)
    tx = set_line(tx, "price_valid_until", price_valid_until, TICKETS)
    tx = set_indented_line(tx, "low_price", str(low))
    tx = set_indented_line(tx, "high_price", str(high))
    tx = set_indented_line(tx, "offer_count", str(offer_count))

    # --- frontpage/sections/tickets.yaml (UI copy) ---
    price_label = f'"from €{target_price}"'
    strike_price = f'"€{next_price}"' if next_price is not None else '""'
    cx = TICKETS_CTA.read_text(encoding="utf-8")
    cx = set_line(cx, "period", target, TICKETS_CTA)
    cx = set_line(cx, "price_label", price_label, TICKETS_CTA)
    cx = set_line(cx, "strike_price", strike_price, TICKETS_CTA)

    print(f"Flipping pricing: {current} -> {target}")
    print(f"  aggregate: low={low} high={high} offer_count={offer_count}")
    print(f"  price_valid_until: {price_valid_until}")
    print(f"  UI: price_label={price_label} strike_price={strike_price}")

    if dry_run:
        print("Dry run — no files written.")
        return

    TICKETS.write_text(tx, encoding="utf-8")
    TICKETS_CTA.write_text(cx, encoding="utf-8")
    print(
        "Wrote databags/tickets.yaml + databags/frontpage/sections/tickets.yaml. Rebuild to publish."
    )


def main() -> int:
    args = parse_args()
    cfg = yaml.safe_load(TICKETS.read_text(encoding="utf-8"))
    ids = [e["id"] for e in cfg.get("editions") or []]
    if not ids:
        raise SystemExit(f"No `editions` listed in {TICKETS.name}.")

    current = cfg.get("active_period")
    if current not in ids:
        raise SystemExit(f"active_period `{current}` is not one of the editions {ids}.")

    target = select_target(cfg, ids, current, args)
    if target == current:
        print(f"active_period is already {target}; nothing to do.")
        return 0

    flip(cfg, current, target, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
