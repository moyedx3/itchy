"""Configuration for OpenDART client."""

import os
from dotenv import load_dotenv


load_dotenv()


# API configuration
DART_API_KEY = os.getenv("DART_API_KEY") or os.getenv("OPEN_DART_API_KEY")


# Simple rate limiting (OpenDART allows up to 10 requests per second, but we stay safe)
DART_MIN_REQUEST_INTERVAL = float(os.getenv("DART_MIN_REQUEST_INTERVAL", "0.2"))


# Default window for filings queries (OpenDART caps list results to 10,000 rows)
DART_DEFAULT_LIST_DAYS = int(os.getenv("DART_DEFAULT_LIST_DAYS", "90"))


# Human-friendly names for reprt_code values used by finstate API
REPORT_CODE_LABELS = {
    "11011": "Q1 Report",
    "11012": "Semiannual Report",
    "11013": "Q3 Report",
    "11014": "Annual Report",
}


# Columns returned from finstate that contain numeric amounts we care about
AMOUNT_COLUMNS = (
    "thstrm_amount",  # current period
    "frmtrm_amount",  # previous period
    "bfefrmtrm_amount",  # two periods ago (annual only)
)
