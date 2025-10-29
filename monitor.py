#!/usr/bin/env python3
"""Main monitoring script that polls SEC APIs and resolves markets.

Now supports CLI input for CIK, estimate, and tags. Examples:

  uv run monitor.py --cik 0000320193 --estimate 125000000000 --tags RevenueFromContractWithCustomerExcludingAssessedTax,SalesRevenueNet,Revenues

If no args are passed, you'll be prompted interactively.
"""

import time
import signal
import sys
import argparse
from resolver import MarketResolver

try:
    from resolvers.sec.config import (  # type: ignore
        POLL_INTERVAL_SEC,
        DEFAULT_REVENUE_TAGS,
        DEFAULT_NET_INCOME_TAGS,
    )
except ImportError:
    from config import (  # type: ignore
        POLL_INTERVAL_SEC,
        DEFAULT_REVENUE_TAGS,
        DEFAULT_NET_INCOME_TAGS,
    )


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n\nShutting down monitor...")
    sys.exit(0)


def parse_args():
    parser = argparse.ArgumentParser(description="SEC metric monitor")
    parser.add_argument("--cik", help="Company CIK (10-digit, leading zeros)")
    parser.add_argument("--estimate", type=float, help="Threshold estimate in USD")
    parser.add_argument("--tags", help="Comma-separated list of XBRL tags to try in order")
    parser.add_argument("--preset", choices=["revenue", "netincome"], help="Use preset tags for revenue or net income")
    return parser.parse_args()


def prompt_if_missing(value, prompt_text):
    if value is None:
        return input(prompt_text).strip()
    return value


def main():
    """Main monitoring loop."""
    args = parse_args()
    
    # Collect inputs (prompt if not provided)
    cik = prompt_if_missing(args.cik, "Enter CIK (10 digits, e.g., 0000320193): ")
    estimate_str = prompt_if_missing(str(args.estimate) if args.estimate is not None else None, "Enter estimate in USD (e.g., 125000000000): ")
    
    # Determine tags from preset or manual input
    if args.preset == "revenue":
        tags = DEFAULT_REVENUE_TAGS
    elif args.preset == "netincome":
        tags = DEFAULT_NET_INCOME_TAGS
    else:
        tags_input = prompt_if_missing(args.tags, "Enter comma-separated XBRL tags (priority order): ")
        tags = [t.strip() for t in tags_input.split(",") if t.strip()]
    
    try:
        estimate = float(estimate_str)
    except ValueError:
        print("Estimate must be a number (USD). Exiting.")
        sys.exit(1)
    
    print("="*60)
    print("🚀 SEC Metric Monitor Started")
    print("="*60)
    print(f"CIK:              {cik}")
    print(f"Estimate:         ${estimate:,.0f}")
    print(f"Tags:             {', '.join(tags)}")
    print(f"Poll Interval:    {POLL_INTERVAL_SEC}s ({POLL_INTERVAL_SEC//60} minutes)")
    print(f"Target Forms:     10-Q, 10-K")
    print("="*60)
    print("\nMonitoring for new filings...\n")
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    resolver = MarketResolver(cik=cik, tags=tags, estimate=estimate)
    
    while True:
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Checking for new filings...")
            
            resolution = resolver.check_for_resolution()
            
            if resolution:
                resolver.print_resolution(resolution)
                print("\n✅ Market resolved! Monitor will continue checking for new filings...")
            else:
                print("  → No new filings detected")
            
            print(f"  → Next check in {POLL_INTERVAL_SEC}s\n")
            time.sleep(POLL_INTERVAL_SEC)
            
        except Exception as e:
            print(f"❌ Error in monitoring loop: {e}")
            print(f"  → Retrying in {POLL_INTERVAL_SEC}s\n")
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()

