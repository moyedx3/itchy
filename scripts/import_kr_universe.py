#!/usr/bin/env python3
"""Bulk-import Korean listed stocks from kr_universe.json into itchy markets.

Usage:
    python scripts/import_kr_universe.py                  # import all 111 stocks (revenue preset)
    python scripts/import_kr_universe.py --preset netincome --estimate 50000000000
    python scripts/import_kr_universe.py --sector SEMICONDUCTOR
    python scripts/import_kr_universe.py --dry-run        # preview without writing to DB
"""

import argparse
import json
import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, create_market
from resolvers.dart.config import (
    DEFAULT_KR_REVENUE_TAGS,
    DEFAULT_KR_OPERATING_INCOME_TAGS,
    DEFAULT_KR_NET_INCOME_TAGS,
)

PRESET_MAP = {
    "revenue": DEFAULT_KR_REVENUE_TAGS,
    "operating_income": DEFAULT_KR_OPERATING_INCOME_TAGS,
    "netincome": DEFAULT_KR_NET_INCOME_TAGS,
}

UNIVERSE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kr_universe.json")


def load_universe(sector_filter: str = None) -> list[dict]:
    with open(UNIVERSE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    if sector_filter:
        data = [d for d in data if d["sector"].upper() == sector_filter.upper()]
    return data


def main():
    parser = argparse.ArgumentParser(description="Import Korean stocks into itchy markets")
    parser.add_argument("--preset", default="revenue", choices=list(PRESET_MAP.keys()),
                        help="Metric preset (default: revenue)")
    parser.add_argument("--estimate", type=float, default=0,
                        help="Estimate threshold in KRW (default: 0, meaning just track)")
    parser.add_argument("--sector", default=None,
                        help="Filter by sector (e.g. SEMICONDUCTOR, SKINCARE)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without writing to database")
    args = parser.parse_args()

    stocks = load_universe(args.sector)
    if not stocks:
        print("No stocks found matching criteria.")
        return

    tags = PRESET_MAP[args.preset]

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Importing {len(stocks)} stocks")
    print(f"  Preset: {args.preset} → {tags}")
    print(f"  Estimate: ₩{args.estimate:,.0f}")
    if args.sector:
        print(f"  Sector: {args.sector}")
    print()

    if not args.dry_run:
        init_db()

    for stock in stocks:
        name = stock["name_kr"]
        code = stock["stock_code"]
        sector = stock["sector"]

        if args.dry_run:
            print(f"  [SKIP] {name} ({code}) — {sector}")
        else:
            market = create_market(
                tags=tags,
                estimate=args.estimate,
                preset=args.preset,
                source="dart",
                corp_name=name,
                stock_code=code,
                currency="krw",
            )
            print(f"  [OK] #{market['id']} {name} ({code}) — {sector}")

    print(f"\n{'Would import' if args.dry_run else 'Imported'} {len(stocks)} markets.")


if __name__ == "__main__":
    main()
