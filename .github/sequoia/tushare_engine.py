"""Tushare-backed market data engine, schema-compatible with Sequoia-X.

Replaces Sequoia-X's baostock DataEngine (which is unreachable from overseas
IPs, e.g. GitHub Actions runners) with Tushare Pro as the data source.

SQLite schema is IDENTICAL to Sequoia-X's `stock_daily` table so the
strategy classes (`MaVolumeStrategy`, `TurtleTradeStrategy`, ...) can be
used unmodified::

    stock_daily(symbol TEXT, date TEXT, open REAL, high REAL, low REAL,
                close REAL, volume REAL, turnover REAL,
                UNIQUE(symbol, date))

Semantics (matching Sequoia-X / baostock):
  - symbol: pure digit code, e.g. "600519"
  - date:   "YYYY-MM-DD"
  - open/high/low/close: 后复权 prices (via Tushare adj_factor)
  - volume:   shares (Tushare vol is in lots -> x100)
  - turnover: amount in yuan (Tushare amount is in thousand yuan -> x1000)

Only the interface used by strategies is implemented:
  db_path, get_local_symbols(), get_ohlcv(symbol), _to_baostock_code()
plus sync()/backfill() for data maintenance.
"""

import logging
import os
import sqlite3
import time
from datetime import date, timedelta

import pandas as pd

log = logging.getLogger("tushare_engine")

SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_daily (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol   TEXT    NOT NULL,
    date     TEXT    NOT NULL,
    open     REAL,
    high     REAL,
    low      REAL,
    close    REAL,
    volume   REAL,
    turnover REAL,
    UNIQUE (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_symbol_date ON stock_daily (symbol, date);
"""

# Tushare needs a few points for `daily`; keep history at 2 years.
BACKFILL_START = "20240101"


def to_ts_code(symbol: str) -> str:
    """Pure digit code -> Tushare ts_code, e.g. 600519 -> 600519.SH."""
    symbol = symbol.strip()
    suffix = "SH" if symbol.startswith(("6", "9")) else "SZ"
    return f"{symbol}.{suffix}"


def to_plain_code(ts_code: str) -> str:
    return ts_code.split(".")[0]


class TushareEngine:
    """Minimal engine exposing the Sequoia-X DataEngine interface."""

    def __init__(self, db_path: str, token: str):
        self.db_path = db_path
        self._token = token
        self._pro = None
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)

    # -- lazy Tushare client -------------------------------------------
    @property
    def pro(self):
        if self._pro is None:
            import tushare as ts
            ts.set_token(self._token)
            self._pro = ts.pro_api()
        return self._pro

    # -- Sequoia-X compatible interface ---------------------------------
    def get_local_symbols(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT DISTINCT symbol FROM stock_daily").fetchall()
        return [r[0] for r in rows]

    def get_ohlcv(self, symbol: str) -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql(
                "SELECT * FROM stock_daily WHERE symbol = ? ORDER BY date",
                conn, params=(symbol,),
            )
        return df

    @staticmethod
    def _to_baostock_code(symbol: str) -> str:
        # Kept for turtle_trade compatibility (its market-cap lookup degrades
        # gracefully when baostock is unreachable; sorting just becomes no-op).
        prefix = "sh" if symbol.startswith(("6", "9")) else "sz"
        return f"{prefix}.{symbol}"

    # -- data sync --------------------------------------------------------
    def _fetch_daily(self, ts_code: str, start: str, end: str) -> pd.DataFrame:
        df = self.pro.daily(ts_code=ts_code, start_date=start, end_date=end)
        time.sleep(0.15)
        return df

    def _fetch_adj(self, ts_code: str, start: str, end: str) -> pd.DataFrame:
        try:
            df = self.pro.adj_factor(ts_code=ts_code, start_date=start, end_date=end)
            time.sleep(0.15)
            return df
        except Exception as exc:  # adj_factor may need extra points; degrade
            log.warning("adj_factor failed for %s: %s (fallback: unadjusted)",
                        ts_code, exc)
            return pd.DataFrame()

    def _to_rows(self, symbol: str, daily: pd.DataFrame,
                 adj: pd.DataFrame) -> list:
        """Merge daily bars with adj factors -> 后复权 rows for stock_daily."""
        if daily is None or daily.empty:
            return []
        daily = daily.copy()
        daily["trade_date"] = daily["trade_date"].astype(str)
        if adj is not None and not adj.empty:
            adj = adj.copy()
            adj["trade_date"] = adj["trade_date"].astype(str)
            merged = daily.merge(adj[["trade_date", "adj_factor"]],
                                 on="trade_date", how="left")
            merged["adj_factor"] = merged["adj_factor"].ffill().bfill().fillna(1.0)
        else:
            merged = daily.copy()
            merged["adj_factor"] = 1.0
        f = merged["adj_factor"]
        rows = []
        for _, r in merged.iterrows():
            d = r["trade_date"]
            dt = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
            vol = float(r["vol"]) if pd.notna(r["vol"]) else 0.0
            amt = float(r["amount"]) if pd.notna(r["amount"]) else 0.0
            if vol <= 0:
                continue
            rows.append((
                symbol, dt,
                float(r["open"]) * f.loc[r.name],
                float(r["high"]) * f.loc[r.name],
                float(r["low"]) * f.loc[r.name],
                float(r["close"]) * f.loc[r.name],
                vol * 100.0,      # lots -> shares
                amt * 1000.0,     # thousand yuan -> yuan
            ))
        return rows

    def _upsert(self, rows: list) -> int:
        if not rows:
            return 0
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO stock_daily
                   (symbol, date, open, high, low, close, volume, turnover)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        return len(rows)

    def _max_date(self) -> str | None:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT MAX(date) FROM stock_daily").fetchone()
        return row[0] if row and row[0] else None

    def backfill(self, symbols: list, start: str = BACKFILL_START) -> int:
        """Full history for the universe (first run only)."""
        end = date.today().strftime("%Y%m%d")
        total = 0
        for i, sym in enumerate(symbols):
            ts_code = to_ts_code(sym)
            try:
                daily = self._fetch_daily(ts_code, start, end)
                adj = self._fetch_adj(ts_code, start, end)
                total += self._upsert(self._to_rows(sym, daily, adj))
            except Exception as exc:
                log.warning("[%s] backfill failed: %s", sym, exc)
            if (i + 1) % 50 == 0:
                log.info("backfill progress: %d/%d", i + 1, len(symbols))
        log.info("backfill done: %d rows for %d symbols", total, len(symbols))
        return total

    def sync_incremental(self, symbols: list) -> int:
        """Fill (max_local_date, today] for every symbol in the universe."""
        maxd = self._max_date()
        if not maxd:
            return self.backfill(symbols)
        start = (date.fromisoformat(maxd) + timedelta(days=1)).strftime("%Y%m%d")
        end = date.today().strftime("%Y%m%d")
        if start > end:
            log.info("DB already up to date (max date %s)", maxd)
            return 0
        total = 0
        for sym in symbols:
            ts_code = to_ts_code(sym)
            try:
                daily = self._fetch_daily(ts_code, start, end)
                adj = self._fetch_adj(ts_code, start, end)
                total += self._upsert(self._to_rows(sym, daily, adj))
            except Exception as exc:
                log.warning("[%s] incremental sync failed: %s", sym, exc)
        log.info("incremental sync done: %d rows (%s -> %s)", total, start, end)
        return total
