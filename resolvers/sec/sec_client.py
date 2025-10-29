"""SEC API client for fetching submissions and company facts."""

import requests
import time
from typing import Optional, Dict, Any, List

try:
    from .config import SEC_HEADERS  # type: ignore[attr-defined]
except ImportError:
    from config import SEC_HEADERS  # type: ignore


class SECClient:
    """Client for interacting with SEC EDGAR APIs."""
    
    def __init__(self, cik: str):
        self.session = requests.Session()
        self.session.headers.update(SEC_HEADERS)
        self._last_request_time = 0
        self._min_request_interval = 0.1  # 10 req/sec max
        self.cik = cik
        self.submissions_url = f"https://data.sec.gov/submissions/CIK{self.cik}.json"
        self.companyfacts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{self.cik}.json"
    
    def _rate_limit(self):
        """Ensure we don't exceed SEC rate limits (10 req/sec)."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def get_submissions(self) -> Optional[Dict[str, Any]]:
        """Fetch company submissions data.
        
        Returns:
            Dict containing recent filings, or None if request fails
        """
        self._rate_limit()
        try:
            response = self.session.get(self.submissions_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching submissions: {e}")
            return None
    
    def get_company_facts(self) -> Optional[Dict[str, Any]]:
        """Fetch company XBRL facts data.
        
        Returns:
            Dict containing company facts, or None if request fails
        """
        self._rate_limit()
        try:
            response = self.session.get(self.companyfacts_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching company facts: {e}")
            return None
    
    def get_latest_metric(self, facts: Dict[str, Any], tags: List[str]) -> Optional[Dict[str, Any]]:
        """Extract the most recent desired metric from company facts, trying tags in order.
        
        Args:
            facts: Company facts JSON from SEC API
            
        Returns:
            Dict with tag, value, end date, and accession number, or None if not found
        """
        if not facts or "facts" not in facts:
            return None
        
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        
        # Try each tag in priority order
        for tag in tags:
            node = us_gaap.get(tag, {})
            usd_facts = node.get("units", {}).get("USD", [])
            
            if usd_facts:
                # Sort by end date (most recent first)
                # Filter out facts without required fields
                valid_facts = [
                    f for f in usd_facts 
                    if all(k in f for k in ["val", "end", "accn"])
                ]
                
                if valid_facts:
                    latest = sorted(valid_facts, key=lambda x: x["end"], reverse=True)[0]
                    return {
                        "tag": tag,
                        "value": latest["val"],
                        "end": latest["end"],
                        "currency": "usd",
                        "accession": latest["accn"],
                        "form": latest.get("form", ""),
                        "filed": latest.get("filed", ""),
                        "fiscal_year": latest.get("fy", ""),
                        "fiscal_period": latest.get("fp", "")
                    }
        
        return None
    
    def get_recent_filings(self, forms: List[str]) -> List[Dict[str, Any]]:
        """Get recent filings of specified form types.
        
        Args:
            forms: List of form types to filter (e.g., ['10-Q', '10-K'])
            
        Returns:
            List of dicts with form type, accession number, and filing date
        """
        submissions = self.get_submissions()
        if not submissions:
            return []
        
        recent = submissions.get("filings", {}).get("recent", {})
        if not recent:
            return []
        
        form_list = recent.get("form", [])
        accn_list = recent.get("accessionNumber", [])
        date_list = recent.get("filingDate", [])
        
        filings = []
        for form, accn, date in zip(form_list, accn_list, date_list):
            if form in forms:
                filings.append({
                    "form": form,
                    "accession": accn,
                    "filing_date": date
                })
        
        return filings
