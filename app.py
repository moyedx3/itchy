"""FastAPI web dashboard for Itchy — SEC & DART Market Monitor."""

import os
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from database import init_db, list_markets, get_market, create_market, update_market_resolution, delete_market
from resolver import MarketResolver, DartMarketResolver
from resolvers.sec.config import DEFAULT_REVENUE_TAGS, DEFAULT_NET_INCOME_TAGS
from resolvers.dart.config import (
    DEFAULT_KR_REVENUE_TAGS,
    DEFAULT_KR_OPERATING_INCOME_TAGS,
    DEFAULT_KR_NET_INCOME_TAGS,
)

app = FastAPI(title="Itchy — SEC & DART Market Monitor")

_templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=_templates_dir)


@app.on_event("startup")
def on_startup():
    init_db()


# ── Request schemas ──────────────────────────────────────────────────────────


class CreateMarketRequest(BaseModel):
    source: str = "sec"  # "sec" or "dart"
    cik: Optional[str] = None  # SEC: 10-digit CIK
    corp_name: Optional[str] = None  # DART: Korean company name
    stock_code: Optional[str] = None  # DART: 6-digit stock code
    estimate: float
    currency: str = "usd"  # "usd" or "krw"
    preset: Optional[str] = None
    tags: Optional[List[str]] = None


# ── Preset resolution ────────────────────────────────────────────────────────

SEC_PRESETS = {
    "revenue": DEFAULT_REVENUE_TAGS,
    "netincome": DEFAULT_NET_INCOME_TAGS,
}

DART_PRESETS = {
    "revenue": DEFAULT_KR_REVENUE_TAGS,
    "operating_income": DEFAULT_KR_OPERATING_INCOME_TAGS,
    "netincome": DEFAULT_KR_NET_INCOME_TAGS,
}


def resolve_tags(source: str, preset: Optional[str], custom_tags: Optional[List[str]]) -> list:
    """Pick the right tag list based on source + preset."""
    presets = DART_PRESETS if source == "dart" else SEC_PRESETS
    if preset and preset in presets:
        return presets[preset]
    if custom_tags and len(custom_tags) > 0:
        return custom_tags
    raise HTTPException(status_code=400, detail="Provide either a preset or custom tags")


# ── Routes ───────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/markets")
def api_list_markets(source: Optional[str] = Query(None)):
    return list_markets(source=source)


@app.get("/api/markets/{market_id}")
def api_get_market(market_id: int):
    market = get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return market


@app.post("/api/markets")
def api_create_market(req: CreateMarketRequest):
    tags = resolve_tags(req.source, req.preset, req.tags)

    if req.source == "dart":
        if not req.corp_name:
            raise HTTPException(status_code=400, detail="corp_name is required for DART markets")
        return create_market(
            tags=tags,
            estimate=req.estimate,
            preset=req.preset,
            source="dart",
            corp_name=req.corp_name,
            stock_code=req.stock_code or "",
            currency=req.currency or "krw",
        )
    else:
        cik = (req.cik or "").strip()
        if not cik:
            raise HTTPException(status_code=400, detail="CIK is required for SEC markets")
        return create_market(
            tags=tags,
            estimate=req.estimate,
            preset=req.preset,
            source="sec",
            cik=cik,
            currency="usd",
        )


@app.post("/api/markets/{market_id}/resolve")
def api_resolve_market(market_id: int):
    market = get_market(market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    if market["status"] == "resolved":
        return market

    tags = market["tags"] if isinstance(market["tags"], list) else [market["tags"]]
    source = market.get("source", "sec")

    if source == "dart":
        corp_name = market.get("corp_name", "")
        if not corp_name:
            raise HTTPException(status_code=400, detail="Market missing corp_name for DART resolution")
        resolver = DartMarketResolver(corp_name=corp_name, tags=tags, estimate=market["estimate"])
    else:
        cik = market.get("cik", "")
        if not cik:
            raise HTTPException(status_code=400, detail="Market missing CIK for SEC resolution")
        resolver = MarketResolver(cik=cik, tags=tags, estimate=market["estimate"])

    result = resolver.check_for_resolution()

    if result:
        updated = update_market_resolution(
            market_id=market_id,
            outcome=result["outcome"],
            resolution_data=result,
            company_name=result.get("company", ""),
        )
        return updated

    return {"status": "pending", "message": "No filing data available for resolution", "market": market}


@app.delete("/api/markets/{market_id}")
def api_delete_market(market_id: int):
    success = delete_market(market_id)
    if not success:
        raise HTTPException(status_code=404, detail="Market not found")
    return {"deleted": True, "id": market_id}


# ── KR Universe helper ───────────────────────────────────────────────────────

@app.get("/api/kr-universe")
def api_kr_universe():
    """Return the list of available Korean listed stocks."""
    import json as _json
    universe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "kr_universe.json")
    if not os.path.exists(universe_path):
        return []
    with open(universe_path, encoding="utf-8") as f:
        return _json.load(f)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
