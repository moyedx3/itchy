"""SQLite persistence for markets."""

import sqlite3
import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "itchy.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL DEFAULT 'sec',
            cik TEXT NOT NULL DEFAULT '',
            corp_name TEXT NOT NULL DEFAULT '',
            stock_code TEXT NOT NULL DEFAULT '',
            company_name TEXT DEFAULT '',
            tags TEXT NOT NULL,
            estimate REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'usd',
            preset TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            outcome TEXT,
            resolution_data TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            resolved_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a Row to dict, parsing JSON fields."""
    d = dict(row)
    for json_field in ("tags", "resolution_data"):
        if d.get(json_field):
            try:
                d[json_field] = json.loads(d[json_field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def list_markets(source: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_db()
    if source:
        rows = db.execute(
            "SELECT * FROM markets WHERE source = ? ORDER BY created_at DESC", (source,)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM markets ORDER BY created_at DESC").fetchall()
    db.close()
    return [_row_to_dict(row) for row in rows]


def get_market(market_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    row = db.execute("SELECT * FROM markets WHERE id = ?", (market_id,)).fetchone()
    db.close()
    return _row_to_dict(row) if row else None


def create_market(
    tags: list,
    estimate: float,
    preset: str = None,
    source: str = "sec",
    cik: str = "",
    corp_name: str = "",
    stock_code: str = "",
    currency: str = "usd",
) -> Dict[str, Any]:
    db = get_db()
    cursor = db.execute(
        """INSERT INTO markets (source, cik, corp_name, stock_code, company_name, tags, estimate, currency, preset, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (source, cik, corp_name, stock_code, corp_name, json.dumps(tags), estimate, currency, preset, "active"),
    )
    market_id = cursor.lastrowid
    db.commit()
    row = db.execute("SELECT * FROM markets WHERE id = ?", (market_id,)).fetchone()
    db.close()
    return _row_to_dict(row)


def update_market_resolution(
    market_id: int, outcome: str, resolution_data: dict, company_name: str
) -> Dict[str, Any]:
    db = get_db()
    now = datetime.utcnow().isoformat()
    db.execute(
        """UPDATE markets
           SET status = 'resolved', outcome = ?, resolution_data = ?,
               resolved_at = ?, company_name = ?
           WHERE id = ?""",
        (outcome, json.dumps(resolution_data), now, company_name, market_id),
    )
    db.commit()
    row = db.execute("SELECT * FROM markets WHERE id = ?", (market_id,)).fetchone()
    db.close()
    return _row_to_dict(row)


def delete_market(market_id: int) -> bool:
    db = get_db()
    cursor = db.execute("DELETE FROM markets WHERE id = ?", (market_id,))
    db.commit()
    db.close()
    return cursor.rowcount > 0
