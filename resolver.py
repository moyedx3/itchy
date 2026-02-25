"""Market resolution logic based on SEC and DART data."""

from typing import Optional, Dict, Any
import json
from datetime import datetime

try:
    from resolvers.sec.sec_client import SECClient  # type: ignore
    from resolvers.sec.config import TARGET_FORMS  # type: ignore
except ImportError:
    from sec_client import SECClient  # type: ignore
    from config import TARGET_FORMS  # type: ignore

try:
    from resolvers.dart.dart_client import OpenDartClient  # type: ignore
    from resolvers.dart.config import DART_API_KEY  # type: ignore
except ImportError:
    try:
        from dart_client import OpenDartClient  # type: ignore
        from config import DART_API_KEY  # type: ignore
    except ImportError:
        OpenDartClient = None  # type: ignore
        DART_API_KEY = None  # type: ignore


class MarketResolver:
    """Resolves markets based on SEC filing data."""
    
    def __init__(self, cik: str, tags: list[str], estimate: float):
        self.client = SECClient(cik)
        self.tags = tags
        self.estimate = estimate
        self.last_checked_accession = None

    @staticmethod
    def _format_amount(value: float, currency: str) -> str:
        """Format numeric values with currency-aware symbols."""
        currency_code = (currency or "").lower()
        symbol_map = {
            "usd": "$",
            "krw": "₩",
        }
        symbol = symbol_map.get(currency_code, "")
        if symbol:
            return f"{symbol}{value:,.0f}"
        suffix = currency_code.upper() if currency_code else ""
        return f"{value:,.0f}{(' ' + suffix) if suffix else ''}"
    
    def check_for_resolution(self) -> Optional[Dict[str, Any]]:
        """Check if a new filing allows market resolution.
        
        Returns:
            Resolution result dict if market can be resolved, None otherwise
        """
        # Get recent filings
        filings = self.client.get_recent_filings(TARGET_FORMS)
        
        if not filings:
            print("No recent filings found")
            return None
        
        # Get the most recent 10-Q or 10-K
        latest_filing = filings[0]
        
        # Skip if we've already processed this filing
        if latest_filing["accession"] == self.last_checked_accession:
            return None
        
        print(f"\nNew filing detected: {latest_filing['form']} - {latest_filing['accession']}")
        print(f"Filed: {latest_filing['filing_date']}")
        
        # Fetch company facts to get revenue
        facts = self.client.get_company_facts()
        if not facts:
            print("Could not fetch company facts")
            return None
        
        # Extract latest revenue
        metric_data = self.client.get_latest_metric(facts, self.tags)
        if not metric_data:
            print("Could not extract requested metric from company facts")
            return None
        
        # Resolve market
        actual_value = float(metric_data["value"])
        outcome = "YES" if actual_value > self.estimate else "NO"
        metric_currency = metric_data.get("currency", "usd").lower()
        metric_formatted = self._format_amount(actual_value, metric_currency)
        estimate_formatted = self._format_amount(self.estimate, metric_currency)
        
        resolution = {
            "cik": self.client.cik,
            "company": facts.get("entityName", "Unknown"),
            "currency": metric_currency,
            "filing": {
                "form": latest_filing["form"],
                "accession": latest_filing["accession"],
                "filing_date": latest_filing["filing_date"]
            },
            "metric": {
                "tag": metric_data["tag"],
                "value": actual_value,
                "formatted": metric_formatted,
                "currency": metric_currency,
                "period_end": metric_data["end"],
                "fiscal_year": metric_data["fiscal_year"],
                "fiscal_period": metric_data["fiscal_period"]
            },
            "estimate": self.estimate,
            "estimate_currency": metric_currency,
            "estimate_formatted": estimate_formatted,
            "outcome": outcome,
            "resolved_at": datetime.utcnow().isoformat()
        }
        
        # Update last checked
        self.last_checked_accession = latest_filing["accession"]
        
        return resolution
    
    def print_resolution(self, resolution: Dict[str, Any]):
        """Pretty print resolution result."""
        print("\n" + "="*60)
        print("🎯 MARKET RESOLVED")
        print("="*60)
        print(f"Company:      {resolution['company']}")
        print(f"Filing:       {resolution['filing']['form']} ({resolution['filing']['filing_date']})")
        print(f"Accession:    {resolution['filing']['accession']}")
        print(f"\nMetric Tag:   {resolution['metric']['tag']}")
        print(f"Period End:   {resolution['metric']['period_end']} ({resolution['metric']['fiscal_period']} {resolution['metric']['fiscal_year']})")
        print(f"\nActual:       {resolution['metric']['formatted']}")
        print(f"Estimate:     {resolution['estimate_formatted']}")
        print(f"\n{'🟢 YES' if resolution['outcome'] == 'YES' else '🔴 NO'} - Actual {'>' if resolution['outcome'] == 'YES' else '≤'} Estimate")
        print(f"\nOutcome:      {resolution['outcome']} POOL WINS")
        print("="*60)
        print(f"\nResolved at:  {resolution['resolved_at']}")
        print("\nFull data:")
        print(json.dumps(resolution, indent=2))
        print("\n")


class DartMarketResolver:
    """Resolves markets based on Korean DART filing data."""

    def __init__(self, corp_name: str, tags: list[str], estimate: float):
        if OpenDartClient is None:
            raise RuntimeError("OpenDartClient not available. Install dart dependencies.")
        self.client = OpenDartClient(corp_name=corp_name)
        self.tags = tags
        self.estimate = estimate
        self.corp_name = corp_name

    def check_for_resolution(self) -> Optional[Dict[str, Any]]:
        """Check if DART financial data allows market resolution.

        Returns:
            Resolution result dict if market can be resolved, None otherwise
        """
        metric_data = self.client.get_latest_metric(account_names=self.tags)
        if not metric_data:
            print(f"Could not extract metric for {self.corp_name}")
            return None

        actual_value = float(metric_data["value"])
        outcome = "YES" if actual_value > self.estimate else "NO"
        metric_currency = metric_data.get("currency", "krw").lower()
        metric_formatted = MarketResolver._format_amount(actual_value, metric_currency)
        estimate_formatted = MarketResolver._format_amount(self.estimate, metric_currency)

        resolution = {
            "corp_name": self.corp_name,
            "company": self.corp_name,
            "currency": metric_currency,
            "filing": {
                "form": metric_data.get("form", ""),
                "accession": metric_data.get("accession", ""),
                "filing_date": metric_data.get("filed", ""),
            },
            "metric": {
                "tag": metric_data["tag"],
                "value": actual_value,
                "formatted": metric_formatted,
                "currency": metric_currency,
                "period_end": metric_data.get("end", ""),
                "fiscal_year": metric_data.get("fiscal_year"),
                "fiscal_period": metric_data.get("fiscal_period", ""),
            },
            "estimate": self.estimate,
            "estimate_currency": metric_currency,
            "estimate_formatted": estimate_formatted,
            "outcome": outcome,
            "resolved_at": datetime.utcnow().isoformat(),
        }

        return resolution
