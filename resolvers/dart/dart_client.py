"""High level client for Korea's OpenDART disclosure system."""

from __future__ import annotations

import datetime as _dt
import re
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

try:
    import OpenDartReader as _OpenDartReader  # type: ignore
except ImportError as exc:  # pragma: no cover - dependency missing at runtime
    raise RuntimeError(
        "OpenDartReader package is required. Install it via pip or add to project dependencies."
    ) from exc

# The PyPI distribution exposes the class directly when importing the module.
# Access it via the module alias for clarity.
OpenDartReader = _OpenDartReader  # type: ignore

try:  # Optional pandas import (OpenDartReader depends on pandas, but be defensive)
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - fallback when pandas is unavailable
    pd = None  # type: ignore

try:  # Support package-style imports as well as script execution
    from .config import (  # type: ignore[attr-defined]
        DART_API_KEY,
        DART_DEFAULT_LIST_DAYS,
        DART_MIN_REQUEST_INTERVAL,
        REPORT_CODE_LABELS,
        AMOUNT_COLUMNS,
    )
except ImportError:
    from config import (  # type: ignore
        DART_API_KEY,
        DART_DEFAULT_LIST_DAYS,
        DART_MIN_REQUEST_INTERVAL,
        REPORT_CODE_LABELS,
        AMOUNT_COLUMNS,
    )


PERIOD_FISCAL_LABEL = {
    "annual": "FY",
    "business": "FY",
    "q4": "FY",
    "half": "HY",
    "q2": "HY",
    "q1": "Q1",
    "first": "Q1",
    "q3": "Q3",
    "third": "Q3",
}

PERIOD_FALLBACK_ORDER = ["half", "annual", "q3", "q1"]


class OpenDartError(RuntimeError):
    """Domain-specific error raised for OpenDART client failures."""


class OpenDartClient:
    """Wrapper around FinanceData's OpenDartReader with repo-friendly helpers.

    The goal is to expose a small, ergonomic surface that mirrors the SEC client
    so downstream resolvers can swap between US (EDGAR) and KR (DART) data with
    minimal effort.

    References:
      - https://github.com/FinanceData/OpenDartReader
      - DART API docs: https://opendart.fss.or.kr/guide
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        corp_code: Optional[str] = None,
        corp_name: Optional[str] = None,
        auto_find: bool = True,
    ) -> None:
        """Create an OpenDART client.

        Args:
            api_key: OpenDART API key (defaults to env-configured value)
            corp_code: 8-digit corporation identifier (고유번호)
            corp_name: Korean company name (full or partial)
            auto_find: When ``corp_name`` is provided but ``corp_code`` is not,
                automatically resolve the code via ``find_corp_code``.

        Raises:
            OpenDartError: if no API key is configured.
        """

        self.api_key = api_key or DART_API_KEY
        if not self.api_key:
            raise OpenDartError(
                "Missing OpenDART API key. Set DART_API_KEY in your environment "
                "or pass api_key explicitly."
            )

        self._dart = OpenDartReader(self.api_key)
        self._last_request_ts = 0.0
        self._min_interval = max(DART_MIN_REQUEST_INTERVAL, 0.0)

        self.corp_code: Optional[str] = None
        if corp_code:
            self.corp_code = self._normalize_corp_code(corp_code)
        elif corp_name and auto_find:
            self.corp_code = self.find_corp_code(corp_name)
        self.corp_name = corp_name

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------
    def _normalize_corp_code(self, corp_code: str) -> str:
        code = corp_code.strip()
        if not code:
            raise OpenDartError("corp_code cannot be empty")
        return code

    def _rate_limit(self) -> None:
        if self._min_interval <= 0:
            return
        elapsed = time.time() - self._last_request_ts
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_ts = time.time()

    def _call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self._rate_limit()
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - third-party errors wrapped
            raise OpenDartError(str(exc)) from exc

    def _ensure_corp_code(self, corp_code: Optional[str] = None) -> str:
        code = corp_code or self.corp_code
        if not code:
            raise OpenDartError(
                "corp_code is required. Pass corp_code to the method or set it "
                "when instantiating OpenDartClient."
            )
        return self._normalize_corp_code(code)

    def _to_records(self, frame: Any) -> List[Dict[str, Any]]:
        if frame is None:
            return []
        if pd is not None:
            dataframe_cls = getattr(pd, "DataFrame", None)
            if dataframe_cls is not None and isinstance(frame, dataframe_cls):
                if frame.empty:
                    return []
                na_sentinel = getattr(pd, "NA", None)
                if na_sentinel is not None:
                    frame = frame.replace({na_sentinel: None})
                frame = frame.where(pd.notnull(frame), None)
                return frame.to_dict(orient="records")
        if hasattr(frame, "to_dict"):
            try:
                return list(frame.to_dict("records"))  # type: ignore[call-arg]
            except Exception:  # pragma: no cover - fallback path
                pass
        if isinstance(frame, dict):
            return [frame]
        if isinstance(frame, list):
            return frame
        raise OpenDartError("Unexpected response type from OpenDartReader")

    # ------------------------------------------------------------------
    # Public API (company discovery)
    # ------------------------------------------------------------------
    def find_corp_code(self, query: str) -> str:
        """Resolve a corporation code from code or name."""

        if not query:
            raise OpenDartError("Query cannot be empty when searching corp code")
        # OpenDartReader already accepts either code or name; simply pass through
        code = self._call(self._dart.find_corp_code, query)
        if not code:
            raise OpenDartError(f"No corporation found for query '{query}'")
        return self._normalize_corp_code(code)

    def get_company(self, corp_code: Optional[str] = None) -> Dict[str, Any]:
        """Fetch company overview (기업개황)."""

        code = self._ensure_corp_code(corp_code)
        frame = self._call(self._dart.company, code)
        records = self._to_records(frame)
        if not records:
            raise OpenDartError(f"No company overview returned for corp_code {code}")
        return records[0]

    def search_companies(self, name: str) -> List[Dict[str, Any]]:
        """Search companies whose names contain the given keyword."""

        if not name:
            return []
        frame = self._call(self._dart.company_by_name, name)
        return self._to_records(frame)

    # ------------------------------------------------------------------
    # Disclosure listings
    # ------------------------------------------------------------------
    def list_filings(
        self,
        corp_code: Optional[str] = None,
        start: Optional[str | _dt.date] = None,
        end: Optional[str | _dt.date] = None,
        kind: Optional[str] = None,
        final: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Return filings within a date range.

        Args:
            corp_code: specific corporation (defaults to client's corp)
            start: YYYY-MM-DD string or date; defaults to N days ago (config)
            end: YYYY-MM-DD string or date; defaults to today
            kind: Disclosure kind (A~J). See REPORT_KIND_CODES in docs.
            final: include original filings or only finalized (`final=True`)
            limit: optional manual cap on the number of rows returned
        """

        code = self._ensure_corp_code(corp_code)

        start_str = self._coerce_date_str(start, days_back=DART_DEFAULT_LIST_DAYS)
        end_str = self._coerce_date_str(end, default_today=True)

        kwargs: Dict[str, Any] = {
            "corp": code,
            "start": start_str,
            "end": end_str,
        }
        if kind:
            kwargs["kind"] = kind
        if final is not None:
            kwargs["final"] = final

        frame = self._call(self._dart.list, **kwargs)
        records = self._to_records(frame)

        if limit is not None:
            return records[:limit]
        return records

    def get_recent_filings(
        self,
        forms: Optional[Sequence[str]] = None,
        limit: int = 30,
        corp_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Mimic SECClient.get_recent_filings with DART data."""

        code = self._ensure_corp_code(corp_code)
        forms = list(forms) if forms else []

        records: List[Dict[str, Any]] = []
        if forms:
            for form in forms:
                subset = self.list_filings(corp_code=code, kind=form, limit=limit)
                records.extend(subset)
        else:
            records = self.list_filings(corp_code=code, limit=limit)

        trimmed = records[:limit]
        results: List[Dict[str, Any]] = []
        for rec in trimmed:
            filing_date_raw = rec.get("rcept_dt")
            filing_date = self._normalize_date_string(filing_date_raw) if filing_date_raw else None
            results.append(
                {
                    "form": rec.get("report_nm"),
                    "accession": rec.get("rcept_no"),
                    "filing_date": filing_date,
                    "raw": rec,
                }
            )
        return results

    # ------------------------------------------------------------------
    # Financial statements helpers
    # ------------------------------------------------------------------
    def get_financial_statements(
        self,
        year: int,
        period: str = "annual",
        corp_code: Optional[str] = None,
        consolidated: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch financial statement rows for a given year/period.

        Args:
            year: Fiscal year (e.g., 2023)
            period: One of ``annual``, ``q1``, ``half``, ``q3``
            corp_code: override corporation
            consolidated: Use consolidated financial statements (CFS) or separate (OFS)
        """

        code = self._ensure_corp_code(corp_code)
        reprt_code = self._resolve_report_code(period)
        # OpenDartReader currently exposes only consolidated statements via finstate.
        # Separate financials require a different endpoint; for now we ignore the flag.

        frame = self._call(self._dart.finstate, code, year, reprt_code=reprt_code)
        return self._to_records(frame)

    def get_financial_metric(
        self,
        account_names: Sequence[str],
        year: int,
        period: str = "annual",
        corp_code: Optional[str] = None,
        consolidated: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Return the first matching financial statement row for the given accounts.

        The first account name (case-insensitive) that matches ``account_nm`` will be
        selected. Returns structured data with numeric conversions for convenience.
        """

        if not account_names:
            raise OpenDartError("account_names must contain at least one entry")

        statements = self.get_financial_statements(
            year=year,
            period=period,
            corp_code=corp_code,
            consolidated=consolidated,
        )

        if not statements:
            return None

        lowered = [name.lower() for name in account_names]

        for row in statements:
            account_nm = str(row.get("account_nm", ""))
            if account_nm.lower() in lowered:
                return self._build_metric_response(row, year, period, consolidated)

        return None

    def _build_metric_response(
        self,
        row: Dict[str, Any],
        year: int,
        period: str,
        consolidated: bool,
    ) -> Dict[str, Any]:
        reprt_code = self._resolve_report_code(period)
        parsed_amounts = {
            key: self._parse_amount(row.get(key))
            for key in AMOUNT_COLUMNS
            if key in row
        }
        currency_raw = row.get("currency") or "KRW"
        currency_norm = str(currency_raw).strip().lower() if currency_raw else "krw"

        return {
            "account_name": row.get("account_nm"),
            "account_id": row.get("account_id"),
            "current_amount": parsed_amounts.get("thstrm_amount"),
            "current_label": row.get("thstrm_nm"),
            "current_date": row.get("thstrm_dt"),
            "previous_amount": parsed_amounts.get("frmtrm_amount"),
            "previous_label": row.get("frmtrm_nm"),
            "previous_date": row.get("frmtrm_dt"),
            "two_periods_ago_amount": parsed_amounts.get("bfefrmtrm_amount"),
            "currency": currency_norm,
            "report": {
                "year": year,
                "period": period,
                "reprt_code": reprt_code,
                "reprt_name": REPORT_CODE_LABELS.get(reprt_code, reprt_code),
                "consolidated": consolidated,
            },
            "raw": row,
        }

    # ------------------------------------------------------------------
    # Metric interface aligned with SECClient
    # ------------------------------------------------------------------
    def get_latest_metric(
        self,
        account_names: Sequence[str],
        year: Optional[int] = None,
        period: Optional[str] = None,
        corp_code: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not account_names:
            raise OpenDartError("account_names must contain at least one value")

        code = self._ensure_corp_code(corp_code)
        context_year, context_period, context_filing = self._infer_reporting_context(code)

        years_to_try = self._build_year_candidates(year, context_year)
        periods_to_try = self._build_period_candidates(period, context_period)

        names = list(account_names)

        for candidate_year in years_to_try:
            for candidate_period in periods_to_try:
                metric = self.get_financial_metric(
                    names,
                    year=candidate_year,
                    period=candidate_period,
                    corp_code=code,
                )
                if metric and metric.get("current_amount") is not None:
                    return self._build_latest_metric_payload(metric, context_filing)

        return None

    def _build_latest_metric_payload(
        self,
        metric: Dict[str, Any],
        filing: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        report = metric.get("report", {})
        raw = metric.get("raw", {})
        period_key = str(report.get("period", "")).lower()
        fiscal_label = PERIOD_FISCAL_LABEL.get(period_key, period_key.upper())
        end_date = self._extract_period_end(metric.get("current_date"))
        accession = raw.get("rcept_no") or (filing.get("rcept_no") if filing else None)
        filed = filing.get("rcept_dt") if filing else None

        return {
            "tag": metric.get("account_name"),
            "value": metric.get("current_amount"),
            "end": end_date,
            "currency": metric.get("currency", "krw"),
            "accession": accession,
            "form": report.get("reprt_name", ""),
            "filed": filed,
            "fiscal_year": report.get("year"),
            "fiscal_period": fiscal_label,
        }

    def _infer_reporting_context(
        self, corp_code: str
    ) -> Tuple[Optional[int], Optional[str], Optional[Dict[str, Any]]]:
        filings = self.list_filings(corp_code=corp_code, kind="A", limit=1)
        if not filings:
            return None, None, None
        filing = filings[0]
        report_nm = filing.get("report_nm", "")
        year = self._extract_year(filing) or self._extract_year_from_report(report_nm)
        period = self._infer_period_from_report(report_nm)
        return year, period, filing

    def _build_year_candidates(
        self, explicit_year: Optional[int], inferred_year: Optional[int]
    ) -> List[int]:
        if explicit_year is not None:
            return [explicit_year]
        candidates: List[int] = []
        if inferred_year is not None:
            candidates.append(inferred_year)
            candidates.append(inferred_year - 1)
        else:
            today = _dt.date.today()
            candidates.append(today.year)
            candidates.append(today.year - 1)
        unique: List[int] = []
        seen = set()
        for value in candidates:
            if value not in seen:
                unique.append(value)
                seen.add(value)
        return unique

    def _build_period_candidates(
        self, explicit_period: Optional[str], inferred_period: Optional[str]
    ) -> List[str]:
        if explicit_period:
            return [explicit_period]
        candidates: List[str] = []
        if inferred_period:
            candidates.append(inferred_period)
        for period in PERIOD_FALLBACK_ORDER:
            if period not in candidates:
                candidates.append(period)
        return candidates

    def _extract_period_end(self, period_text: Optional[str]) -> Optional[str]:
        if not period_text:
            return None
        text = str(period_text)
        if "~" in text:
            end_part = text.split("~")[-1]
        else:
            end_part = text
        normalized = self._normalize_date_string(end_part.strip())
        return normalized or None

    def _normalize_date_string(self, text: Optional[str]) -> str:
        if text is None:
            return ""
        cleaned = str(text).strip().replace(".", "-").replace("/", "-")
        match = re.match(r"(\d{4})-?(\d{2})-?(\d{2})", cleaned)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        return cleaned

    def _extract_year(self, filing: Dict[str, Any]) -> Optional[int]:
        for key in ("bsns_year", "year", "rcept_dt"):
            value = filing.get(key)
            if not value:
                continue
            if isinstance(value, int):
                return value
            try:
                return int(str(value)[:4])
            except (TypeError, ValueError):
                continue
        return None

    def _extract_year_from_report(self, report_nm: str) -> Optional[int]:
        if not report_nm:
            return None
        match = re.search(r"(20\d{2})", report_nm)
        if match:
            return int(match.group(1))
        return None

    def _infer_period_from_report(self, report_nm: str) -> Optional[str]:
        if not report_nm:
            return None
        lower = report_nm.lower()
        mappings = {
            "반기": "half",
            "semi": "half",
            "사업": "annual",
            "연간": "annual",
            "1분기": "q1",
            "1q": "q1",
            "3분기": "q3",
            "3q": "q3",
        }
        for keyword, period in mappings.items():
            if keyword in lower:
                return period
        return None

    # ------------------------------------------------------------------
    # Disclosure content helpers
    # ------------------------------------------------------------------
    def get_document(self, receipt_no: str) -> str:
        """Return the raw text for a specific filing (공시서류원본)."""

        if not receipt_no:
            raise OpenDartError("receipt_no is required")
        return self._call(self._dart.document, receipt_no)

    def get_document_list(self, receipt_no: str) -> List[Dict[str, Any]]:
        """Return all document nodes (사업/감사보고서 등)."""

        if not receipt_no:
            raise OpenDartError("receipt_no is required")
        docs = self._call(self._dart.document_all, receipt_no)
        if isinstance(docs, list):
            normalised: List[Dict[str, Any]] = []
            for doc in docs:
                if isinstance(doc, dict):
                    normalised.append({
                        "title": doc.get("title"),
                        "text": doc.get("text"),
                    })
                else:
                    normalised.append({
                        "title": None,
                        "text": doc,
                    })
            return normalised
        return self._to_records(docs)

    def list_sub_documents(self, receipt_no: str, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
        """List sub-documents (하위 문서). Optionally filter by keyword."""

        if not receipt_no:
            raise OpenDartError("receipt_no is required")
        if keyword:
            frame = self._call(self._dart.sub_docs, receipt_no, match=keyword)
        else:
            frame = self._call(self._dart.sub_docs, receipt_no)
        return self._to_records(frame)

    def list_attachments(self, receipt_no: str) -> Dict[str, str]:
        """Return a mapping of attachment names to download URLs."""

        if not receipt_no:
            raise OpenDartError("receipt_no is required")
        return self._call(self._dart.attach_files, receipt_no) or {}

    def download_attachment(self, url: str, destination: str) -> None:
        """Download a single attachment to ``destination`` path."""

        if not url:
            raise OpenDartError("url is required for download")
        if not destination:
            raise OpenDartError("destination path is required for download")
        self._call(self._dart.download, url, destination)

    # ------------------------------------------------------------------
    # Event / shareholding helpers
    # ------------------------------------------------------------------
    def get_events(
        self,
        corp: Optional[str] = None,
        event: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Wrapper for 주요사항보고 (events)."""

        corp_identifier = corp or self.corp_code or self.corp_name
        if not corp_identifier:
            raise OpenDartError("corp or initialized corporation must be provided")
        frame = self._call(
            self._dart.event,
            corp_identifier,
            event,
            start=start,
            end=end,
        )
        return self._to_records(frame)

    def get_major_shareholders(self, corp: Optional[str] = None) -> List[Dict[str, Any]]:
        corp_identifier = corp or self.corp_code or self.corp_name
        if not corp_identifier:
            raise OpenDartError("corp must be provided")
        frame = self._call(self._dart.major_shareholders, corp_identifier)
        return self._to_records(frame)

    def get_major_exec_shareholders(self, corp: Optional[str] = None) -> List[Dict[str, Any]]:
        corp_identifier = corp or self.corp_code or self.corp_name
        if not corp_identifier:
            raise OpenDartError("corp must be provided")
        frame = self._call(self._dart.major_shareholders_exec, corp_identifier)
        return self._to_records(frame)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def _coerce_date_str(
        self,
        value: Optional[str | _dt.date],
        *,
        default_today: bool = False,
        days_back: Optional[int] = None,
    ) -> str:
        if isinstance(value, str) and value:
            return value
        if isinstance(value, _dt.date):
            return value.strftime("%Y-%m-%d")

        today = _dt.date.today()
        if default_today:
            return today.strftime("%Y-%m-%d")
        if days_back is not None:
            start_date = today - _dt.timedelta(days=days_back)
            return start_date.strftime("%Y-%m-%d")
        return today.strftime("%Y-%m-%d")

    def _resolve_report_code(self, period: str) -> str:
        period_key = (period or "annual").lower()
        mapping = {
            "annual": "11014",
            "business": "11014",
            "q4": "11014",
            "q1": "11011",
            "first": "11011",
            "half": "11012",
            "semiannual": "11012",
            "q2": "11012",
            "q3": "11013",
            "third": "11013",
        }
        code = mapping.get(period_key)
        if not code:
            raise OpenDartError(
                f"Unsupported period '{period}'. Expected one of: {sorted(set(mapping.keys()))}"
            )
        return code

    def _parse_amount(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text or text in {"-", "NaN", "nan"}:
            return None
        text = text.replace(",", "")
        try:
            return float(text)
        except ValueError:
            return None

