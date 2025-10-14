import os
from dotenv import load_dotenv

load_dotenv()

# SEC API Configuration
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "RevenueBetPrototype contact@example.com")
SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate"
}

# Polling Configuration (can be overridden by CLI)
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "600"))

# Target form types
TARGET_FORMS = ["10-Q", "10-K"]

# Helpful defaults for common metrics (can be overridden by CLI input)
DEFAULT_REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "Revenues"
]

DEFAULT_NET_INCOME_TAGS = [
    "NetIncomeLoss",
    "ProfitLoss"
]
