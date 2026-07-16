"""Atomically flip ticket pricing between Early-Bird and Late-Bird.

`make flip-pricing` (or `make flip-pricing PERIOD=late`) rewrites both
the schema source (`databags/tickets.yaml`) and the UI CTA
(`databags/frontpage/sections/tickets.yaml`) from the tier list so the
AggregateOffer JSON-LD and the on-page price line never drift:

  - tickets.yaml: toggles `active_period`, rewrites `aggregate`
    (low/high/offer_count from the on-sale tiers only) and
    `price_valid_until` (early -> late_bird_from - 1 day; late ->
    valid_through).
  - frontpage/sections/tickets.yaml: rewrites `period`, `price_label` (from the
    3-day standard tier of the active period) and `strike_price`
    (early period: the future late 3-day price, loss-framing; late
    period: empty — the regret anchor is dropped).

Comment-preserving: edits are line-targeted, not a full YAML round
trip, so the helpful docs in both files survive the flip. Roll back
with `make flip-pricing PERIOD=early`.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
TICKETS = REPO / "databags" / "tickets.yaml"
TICKETS_CTA = REPO / "databags" / "frontpage" / "sections" / "tickets.yaml"


def period_of(tier: dict) -> str:
    return (tier.get("period") or "").lower()


def set_line(text: str, key: str, value: str) -> str:
    """Replace a top-level `key: ...` line (regex, multiline)."""
    pattern = re.compile(rf"(?m)^{re.escape(key)}: .*$")
    if not pattern.search(text):
        raise SystemExit(f"Field `{key}` not found in {TICKETS.name}")
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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--period",
        choices=("early", "late"),
        help="Target period; default toggles from the current active_period.",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    cfg = yaml.safe_load(TICKETS.read_text(encoding="utf-8"))
    current = (cfg.get("active_period") or "early").lower()
    target = args.period or ("late" if current == "early" else "early")
    if target == current:
        print(f"active_period is already {target}; nothing to do.")
        return 0

    tiers = cfg.get("tiers") or []
    public = [t for t in tiers if (t.get("kind") == "public")]
    on_sale = [t for t in public if target in period_of(t)]
    if not on_sale:
        raise SystemExit(f"No public tiers match period '{target}' in tickets.yaml.")

    low = min(t["price"] for t in on_sale)
    high = max(t["price"] for t in on_sale)
    offer_count = len(on_sale)

    def three_day_price(period: str) -> int | None:
        for t in public:
            if (t.get("id") or "").startswith("3day-standard-") and period in period_of(t):
                return t["price"]
        # Fallback: first on-sale tier of that period.
        for t in public:
            if period in period_of(t):
                return t["price"]
        return None

    target_3day = three_day_price(target)
    opposite_3day = three_day_price("late" if target == "early" else "early")
    if target_3day is None:
        raise SystemExit("Could not resolve a 3-day standard price for the target period.")

    valid_through = cfg.get("valid_through")
    late_bird_from = cfg.get("late_bird_from")
    # Compute price_valid_until: early -> day before late-bird opens; late -> sale close.
    if target == "early":
        price_valid_until = fmt(parse_date(late_bird_from) - timedelta(days=1))
    else:
        price_valid_until = fmt(parse_date(valid_through))

    # --- tickets.yaml (schema source) ---
    tx = TICKETS.read_text(encoding="utf-8")
    tx = set_line(tx, "active_period", target)
    tx = set_line(tx, "price_valid_until", price_valid_until)
    tx = set_indented_line(tx, "low_price", str(low))
    tx = set_indented_line(tx, "high_price", str(high))
    tx = set_indented_line(tx, "offer_count", str(offer_count))

    # --- frontpage/sections/tickets.yaml (UI copy) ---
    price_label = f'"from €{target_3day}"'
    strike_price = f'"€{opposite_3day}"' if (target == "early" and opposite_3day is not None) else '""'
    cx = TICKETS_CTA.read_text(encoding="utf-8")
    cx = set_line(cx, "period", target)
    cx = set_line(cx, "price_label", price_label)
    cx = set_line(cx, "strike_price", strike_price)

    print(f"Flipping pricing: {current} -> {target}")
    print(f"  aggregate: low={low} high={high} offer_count={offer_count}")
    print(f"  price_valid_until: {price_valid_until}")
    print(f"  UI: price_label={price_label} strike_price={strike_price}")

    if args.dry_run:
        print("Dry run — no files written.")
        return 0

    TICKETS.write_text(tx, encoding="utf-8")
    TICKETS_CTA.write_text(cx, encoding="utf-8")
    print("Wrote databags/tickets.yaml + databags/frontpage/sections/tickets.yaml. Rebuild to publish.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
