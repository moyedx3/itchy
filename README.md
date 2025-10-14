# SEC Metric Monitor — Pool Staking MVP

Minimal backend that monitors SEC `10-Q`/`10-K` filings, reads a chosen XBRL metric (e.g., Revenue or Net Income), and resolves a YES/NO pool against a threshold.

---

## Quick Start

Requirements:
- Python 3.10+
- `uv` recommended (auto-manages env): `curl -LsSf https://astral.sh/uv/install.sh | sh`

Install and run:
```bash
uv sync

# Option A: presets
uv run monitor.py --preset revenue   --cik 0000320193 --estimate 125000000000
uv run monitor.py --preset netincome --cik 0001065280 --estimate 2000000000

# Option B: custom tags (comma-separated, priority order)
uv run monitor.py --cik 0001318605 --estimate 25000000000 \
  --tags RevenueFromContractWithCustomerExcludingAssessedTax,SalesRevenueNet,Revenues
```

Environment:
```bash
# .env (required by SEC)
SEC_USER_AGENT="RevenueBetPrototype you@domain.com"
POLL_INTERVAL_SEC=600
```

---

## Usage

Interactive mode (prompts):
```bash
uv run monitor.py
# Enter CIK (10 digits)
# Enter estimate in USD
# Enter tags (e.g., RevenueFromContractWithCustomerExcludingAssessedTax,SalesRevenueNet)
```

CLI flags:
```bash
uv run monitor.py --cik <CIK> --estimate <USD> --tags <Tag1,Tag2,...>
uv run monitor.py --preset <revenue|netincome> --cik <CIK> --estimate <USD>
```

Output includes company, filing, metric tag, value, comparison to estimate, and outcome.

---

## Two Ready-to-Run Tests

1) Apple — Revenue
```bash
uv run monitor.py --cik 0000320193 --estimate 125000000000 \
  --tags RevenueFromContractWithCustomerExcludingAssessedTax,SalesRevenueNet,Revenues
```

2) Netflix — Net Income
```bash
uv run monitor.py --cik 0001065280 --estimate 2000000000 \
  --tags NetIncomeLoss,ProfitLoss
```

Tip: Use `--preset revenue` or `--preset netincome` to avoid remembering tags.

---

## Example Output

```text
============================================================
🎯 MARKET RESOLVED
============================================================
Company:      Apple Inc.
Filing:       10-Q (2025-08-01)
Accession:    0000320193-25-000073

Metric Tag:   RevenueFromContractWithCustomerExcludingAssessedTax
Period End:   2025-06-28 (Q3 2025)

Actual:       $313,695,000,000
Estimate:     $125,000,000,000

🟢 YES - Actual > Estimate

Outcome:      YES POOL WINS
============================================================

Resolved at:  2025-10-14T16:56:05Z

Full data:
{
  "cik": "0000320193",
  "company": "Apple Inc.",
  "filing": {
    "form": "10-Q",
    "accession": "0000320193-25-000073",
    "filing_date": "2025-08-01"
  },
  "metric": {
    "tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "value": 313695000000.0,
    "period_end": "2025-06-28",
    "fiscal_year": 2025,
    "fiscal_period": "Q3"
  },
  "estimate": 125000000000.0,
  "outcome": "YES",
  "resolved_at": "2025-10-14T16:56:05Z"
}
```

---

## Finding Valid XBRL Tags

Browse a company’s facts to see all available US-GAAP tags and units (USD):
- Company Facts API: `https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json`
  - Apple example: `https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json`

Common tags:
- Revenue: `RevenueFromContractWithCustomerExcludingAssessedTax`, `SalesRevenueNet`, `Revenues`
- Net income: `NetIncomeLoss` (positive = income, negative = loss), fallback `ProfitLoss`
- Others: `Assets`, `ResearchAndDevelopmentExpense`, `CostOfRevenue`

Note: SEC requires a valid `User-Agent` header (set via `.env`). Rate limit ≤ 10 req/s.

---

## What’s Next

- Add DB and staking ledger (markets, positions, payouts)
- Web UI to create/view markets and stake

License: MIT

