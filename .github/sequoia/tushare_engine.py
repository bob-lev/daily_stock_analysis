




聊天
打开聊天和旁聊
Muse
20:12
助手消息：根因找到了，而且很具体：**你改的 `OPENAI_MODEL` 没生效**。

日志里白纸黑字：`litellm initialized (model=deepseek-ai/DeepSeek-V4.1-Fl…`——用的还是**旧值**（不带 `openai/` 前缀），212 只继续在同一步全军覆没，报错跟上一轮一字不差。

为什么没生效？看 workflow 第 125 行：

```
OPENAI_MODEL: ${{ vars.OPENAI_MODEL || secrets.OPENAI_MODEL }}
```

**Variables 优先于 Secrets**。最可能的情况：你的 Variables 里还留着旧值的 `OPENAI_MODEL`，把它在 Secrets 里改成新值也没用——旧值盖掉了新值。（`SINGLE_STOCK_NOTIFY=true` 生效了，说明 Variables 通道是通的。）

修复：去 Settings → Secrets and variables → Actions，**先看 Variables 标签页**——如果有 `OPENAI_MODEL`，改成 `openai/deepseek-ai/DeepSeek-V4.1-Flash` 或直接删掉；再确认 Secrets 里的也是新值。**改完之后再触发运行**（启动时读取，跑起来再改没用）。

另外今晚 18:00 的定时任务一直没启动（Actions 里没新运行），20:30 我会自动核验一次。
用户消息：OPENAI_API_KEY 填写什么
助手消息：填你的**硅基流动 API Key**——就是在 cloud.siliconflow.cn 控制台 → API 密钥里创建的那个。

（之前配紫微斗数网站时你用过的那个 key 就行，还在的话直接复制；找不到了就新建一个。）

注意是填到 GitHub 仓库的 Secrets 里你自己操作，别发给我。
用户消息：改过了，已经手动运行了
助手消息：看到新运行已经启动了（1 分钟前，in_progress）。这次模型名应该对了，等它跑完——约 40–80 分钟。20:30 的自动核验也会看这一轮的状态，有结论了我告诉你。
助手消息：20:30 核验结论：**今晚 18:00 的定时运行确定没有发生**——仓库里没有任何 schedule 触发的运行，只有三次手动运行。workflow 本身是 active 状态（你没 Disable），定时配置也在，就是 GitHub 没触发，原因不明，明天 18:00 再观察一次。

现在就看正在跑的这轮手动验证了，等它跑完看 Telegram 是否收到 212 只推送，你不用做任何操作。
用户消息：212 只推送收到了 有点烧token
助手消息：🎉 定论了：212 只推送全收到 = **全链路正式跑通**！这三天的折腾值了——模型名修复生效，分析、推送都正常了。

关于烧 token（约 ¥3–5/天），给你个降本选项，还记得之前说的二期方案吗：

**Sequoia-X 前置筛选**：先用免费的技术形态筛选把 212 只缩到 ~50 只候选，再让 LLM 深度分析这 50 只。成本直接降到现在的 **1/4**（一天一块多），而且你每天只看 50 份精华报告，反而更轻松。

要不要上这个二期？要的话我来搭。
用户消息：二期搭建的话运行在本地还是其他
都不用——直接跑在 GitHub Actions 里，跟你现在的分析 workflow 同一个地方，不需要你本地电脑开着，也不需要另租服务器。

架构是这样的：

Sequoia-X 本身是个 Python 程序（7 个技术形态策略），用 SQLite 存历史 K 线，数据源是 baostock，零 token 成本
在你 fork 的 workflow 里加一个前置筛选 job：每天先跑 Sequoia-X 技术筛选（212 只 → ~50 只），结果传给后面的 LLM 分析 job
公开仓库的 Actions 分钟数免费，所以二期不增加任何机器成本和 token 成本，全自动，你什么都不用管
有两个要实测的点，我提前说明：

baostock 从 GitHub 海外机器能不能连上——未知，要跑一次才知道；连不上就改用你已有的 Tushare 做数据源适配
SQLite 历史库的持久化——Actions 机器每次是新的，用官方缓存机制存数据库（首次回填约 12 分钟，之后每天增量 2–3 分钟），这是常规做法
工作量主要是改你 fork 的 workflow 文件（加筛选 job + 传参），改法我这边准备好给你，你粘贴就行。

要我现在开始搭二期吗？

你：
开始吧

二期已经开工。目前进展：

代码分析已派出去（Sequoia-X 的筛选输出格式、去飞书化、策略开关、数据引擎结构）
我这边实测了一个关键风险：baostock 从海外网络连不上（登录直接被重置连接），GitHub 的机器也在海外，所以 Sequoia-X 默认数据源很可能用不了——备选是用你已经配好的 Tushare（在 Actions 上验证过是通的），等代码分析结果看数据引擎好不好换
workflow 集成点已找到：analyze job 里 STOCK_LIST_CONFIG 的位置，加前置筛选 job 即可
等分析结果回来我就出完整集成方案。

二期搭好了，代码全部写完并实测通过。先说结论：

不用你本地跑，也不用租服务器——筛选跑在 GitHub Actions 里，一期 workflow 加一个前置任务就行。Sequoia-X 一行不用改，运行时直接 clone。

实测中解决的两个坑：

baostock 海外连不上（我实测登录直接被重置）→ 改用你的 Tushare（Actions 上验证过是通的），我写了数据适配器，表结构和 Sequoia-X 完全兼容
turtle 策略会调 baostock 查市值 → 实测确认被墙时优雅降级，只丢市值排序，选股不受影响
文件都在 sequoia-phase2 目录，你按 README 三步操作：传 3 个文件 → 改 workflow 3 处（补丁文件里有精确到行的说明）→ 手动验证一次。筛选失败会自动回退到 212 只全量，不会把一期搞坏。









README
MD

tushare_engine.py
PY

screen.py
PY

requirements.txt
TXT


WORKFLOW_PATCH.md
MD
你：
接下来需要我怎么操作

三步，你在网页上操作就行：

1. 传 3 个文件（约 5 分钟）
打开 https://github.com/bob-lev/daily_stock_analysis → Add file → Create new file，文件名填 .github/sequoia/tushare_engine.py，把我刚发你的同名文件内容粘贴进去 → Commit changes。同样再建 .github/sequoia/screen.py 和 .github/sequoia/requirements.txt。

2. 改 workflow（约 10 分钟）
打开 .github/workflows/00-daily-analysis.yml 点 ✏️，按 WORKFLOW_PATCH.md 改 3 处：

jobs: 后面插入整段 screen job
analyze: 下面加一行 needs: screen
env 加 SCREENED_LIST 一行，名单解析加优先分支（有筛选结果用筛选的，没有自动回退 212 只）
改完 Commit changes。
3. 手动跑一次验证
Actions → 每日股票分析 → Run workflow。看两处日志：screen job 显示 UNION: N / 212，analyze job 显示 🎯 二期技术筛选命中 N 只。Telegram 应该收到 N 只推送（不是 212 只了）。

跑完跟我说结果，有问题我来修。

tushare_engine.py
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
