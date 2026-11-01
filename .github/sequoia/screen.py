"""Sequoia-X pre-screening for GitHub Actions (phase 2 of daily_stock_analysis).

Runs 6 local technical strategies (excludes private_placement which needs
akshare/Eastmoney, unreachable from overseas runners) over a fixed universe
of stocks, using Tushare Pro as the data source (baostock is blocked from
overseas IPs).

Output: picks.json -> {"date", "universe_count", "strategies": {...},
                        "union": [...], "union_count": N}

The script NEVER exits non-zero: on any catastrophic failure it writes an
empty union so the downstream analysis job can fall back to the full list.

Usage:
    python screen.py --universe "600519,000001,..." --db /tmp/sequoia_v2.db \\
        --sequoia-dir /tmp/sequoia-x --output /tmp/picks.json \\
        [--strategies ma_volume,turtle_trade,...] [--skip-sync]

Env:
    TUSHARE_TOKEN   Tushare Pro API token (required for data sync)
    TZ              set to Asia/Shanghai by the workflow
"""

import argparse
import json
import logging
import os
import socket
import sys
import traceback
from datetime import date

# 防 baostock 网络调用 hang 死（turtle 策略的市值排序会尝试连接）
socket.setdefaulttimeout(15.0)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("screen")

# 6 local strategies (pure SQLite computation). private_placement excluded:
# it needs akshare -> Eastmoney, blocked from GitHub runners.
STRATEGY_MODULES = {
    "ma_volume": "MaVolumeStrategy",
    "turtle_trade": "TurtleTradeStrategy",
    "high_tight_flag": "HighTightFlagStrategy",
    "limit_up_shakeout": "LimitUpShakeoutStrategy",
    "uptrend_limit_down": "UptrendLimitDownStrategy",
    "rps_breakout": "RpsBreakoutStrategy",
}

STRATEGY_FILES = {
    "ma_volume": "ma_volume",
    "turtle_trade": "turtle_trade",
    "high_tight_flag": "high_tight_flag",
    "limit_up_shakeout": "limit_up_shakeout",
    "uptrend_limit_down": "uptrend_limit_down",
    "rps_breakout": "rps_breakout",
}


def parse_args():
    p = argparse.ArgumentParser(description="Sequoia-X pre-screening")
    p.add_argument("--universe", required=True,
                   help="comma/whitespace separated stock codes, e.g. 600519,000001")
    p.add_argument("--db", required=True, help="SQLite DB path")
    p.add_argument("--sequoia-dir", required=True,
                   help="path to cloned Sequoia-X repo")
    p.add_argument("--output", required=True, help="picks.json output path")
    p.add_argument("--strategies", default=",".join(STRATEGY_MODULES),
                   help="subset of strategies to run")
    p.add_argument("--skip-sync", action="store_true",
                   help="skip data sync (debug only)")
    return p.parse_args()


def parse_universe(raw: str) -> list:
    import re
    codes = [c.strip() for c in re.split(r"[,\s;|]+", raw or "") if c.strip()]
    # keep pure-digit A-share codes, dedupe preserving order
    seen, out = set(), []
    for c in codes:
        c = c.split(".")[0].upper()
        if c.isdigit() and len(c) == 6 and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def write_output(path: str, payload: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def empty_payload(universe_count: int, error: str) -> dict:
    return {
        "date": date.today().isoformat(),
        "universe_count": universe_count,
        "strategies": {},
        "union": [],
        "union_count": 0,
        "error": error,
    }


def main() -> int:
    args = parse_args()
    universe = parse_universe(args.universe)
    log.info("universe: %d stocks", len(universe))

    if not universe:
        write_output(args.output, empty_payload(0, "empty universe"))
        return 0

    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token and not args.skip_sync:
        log.error("TUSHARE_TOKEN not set; cannot sync data")
        write_output(args.output, empty_payload(len(universe),
                                                "TUSHARE_TOKEN missing"))
        return 0

    # -- import engine (local file, same dir as this script) --
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tushare_engine import TushareEngine

    # -- import Sequoia-X strategies (duck-typed engine) --
    # strategy modules do `from sequoia_x.strategy.base import ...` and
    # `from sequoia_x.core.logger import get_logger`; make both importable.
    # NOTE: no fork/modification of Sequoia-X needed. Strategies require a
    # Settings object at construction but never USE it in run(); we pass a
    # dummy webhook URL and never instantiate FeishuNotifier, so nothing
    # is ever pushed.
    sys.path.insert(0, args.sequoia_dir)
    try:
        from sequoia_x.core.config import Settings
        settings = Settings(feishu_webhook_url="disabled-for-screening")
    except Exception:
        log.error("failed building Settings:\n%s", traceback.format_exc())
        write_output(args.output, empty_payload(len(universe),
                                                "settings build failed"))
        return 0
    classes = {}
    try:
        for name in [s.strip() for s in args.strategies.split(",") if s.strip()]:
            if name not in STRATEGY_MODULES:
                log.warning("unknown strategy %s, skipped", name)
                continue
            mod = __import__(f"sequoia_x.strategy.{STRATEGY_FILES[name]}",
                             fromlist=[STRATEGY_MODULES[name]])
            classes[name] = getattr(mod, STRATEGY_MODULES[name])
    except Exception:
        log.error("failed importing strategies:\n%s", traceback.format_exc())
        write_output(args.output, empty_payload(len(universe),
                                                "strategy import failed"))
        return 0

    log.info("strategies: %s", sorted(classes))

    # -- sync data --
    engine = TushareEngine(args.db, token)
    if not args.skip_sync:
        try:
            n = engine.sync_incremental(universe)
            log.info("synced %d rows", n)
        except Exception:
            log.error("data sync failed:\n%s", traceback.format_exc())
            write_output(args.output, empty_payload(len(universe),
                                                    "data sync failed"))
            return 0
    else:
        log.info("--skip-sync: using existing DB as-is")

    local = set(engine.get_local_symbols())
    missing = [s for s in universe if s not in local]
    if missing:
        log.warning("%d universe symbols have no data (e.g. long suspended): %s",
                    len(missing), ",".join(missing[:10]))

    # -- run strategies, each isolated --
    results = {}
    for name, cls in classes.items():
        try:
            picked = cls(engine=engine, settings=settings).run()
            picked = [p for p in (picked or [])]
            results[name] = sorted(set(picked))
            log.info("strategy %-18s -> %d picks", name, len(results[name]))
        except Exception:
            log.error("strategy %s crashed:\n%s", name, traceback.format_exc())
            results[name] = []

    union = sorted({s for picks in results.values() for s in picks})
    log.info("UNION: %d / %d", len(union), len(universe))

    write_output(args.output, {
        "date": date.today().isoformat(),
        "universe_count": len(universe),
        "strategies": results,
        "union": union,
        "union_count": len(union),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""Sequoia-X pre-screening for GitHub Actions (phase 2 of daily_stock_analysis).

Runs 6 local technical strategies (excludes private_placement which needs
akshare/Eastmoney, unreachable from overseas runners) over a fixed universe
of stocks, using Tushare Pro as the data source (baostock is blocked from
overseas IPs).

Output: picks.json -> {"date", "universe_count", "strategies": {...},
                        "union": [...], "union_count": N}

The script NEVER exits non-zero: on any catastrophic failure it writes an
empty union so the downstream analysis job can fall back to the full list.

Usage:
    python screen.py --universe "600519,000001,..." --db /tmp/sequoia_v2.db \\
        --sequoia-dir /tmp/sequoia-x --output /tmp/picks.json \\
        [--strategies ma_volume,turtle_trade,...] [--skip-sync]

Env:
    TUSHARE_TOKEN   Tushare Pro API token (required for data sync)
    TZ              set to Asia/Shanghai by the workflow
"""

import argparse
import json
import logging
import os
import socket
import sys
import traceback
from datetime import date

# 防 baostock 网络调用 hang 死（turtle 策略的市值排序会尝试连接）
socket.setdefaulttimeout(15.0)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("screen")

# 6 local strategies (pure SQLite computation). private_placement excluded:
# it needs akshare -> Eastmoney, blocked from GitHub runners.
STRATEGY_MODULES = {
    "ma_volume": "MaVolumeStrategy",
    "turtle_trade": "TurtleTradeStrategy",
    "high_tight_flag": "HighTightFlagStrategy",
    "limit_up_shakeout": "LimitUpShakeoutStrategy",
    "uptrend_limit_down": "UptrendLimitDownStrategy",
    "rps_breakout": "RpsBreakoutStrategy",
}

STRATEGY_FILES = {
    "ma_volume": "ma_volume",
    "turtle_trade": "turtle_trade",
    "high_tight_flag": "high_tight_flag",
    "limit_up_shakeout": "limit_up_shakeout",
    "uptrend_limit_down": "uptrend_limit_down",
    "rps_breakout": "rps_breakout",
}


def parse_args():
    p = argparse.ArgumentParser(description="Sequoia-X pre-screening")
    p.add_argument("--universe", required=True,
                   help="comma/whitespace separated stock codes, e.g. 600519,000001")
    p.add_argument("--db", required=True, help="SQLite DB path")
    p.add_argument("--sequoia-dir", required=True,
                   help="path to cloned Sequoia-X repo")
    p.add_argument("--output", required=True, help="picks.json output path")
    p.add_argument("--strategies", default=",".join(STRATEGY_MODULES),
                   help="subset of strategies to run")
    p.add_argument("--skip-sync", action="store_true",
                   help="skip data sync (debug only)")
    return p.parse_args()


def parse_universe(raw: str) -> list:
    import re
    codes = [c.strip() for c in re.split(r"[,\s;|]+", raw or "") if c.strip()]
    # keep pure-digit A-share codes, dedupe preserving order
    seen, out = set(), []
    for c in codes:
        c = c.split(".")[0].upper()
        if c.isdigit() and len(c) == 6 and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def write_output(path: str, payload: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def empty_payload(universe_count: int, error: str) -> dict:
    return {
        "date": date.today().isoformat(),
        "universe_count": universe_count,
        "strategies": {},
        "union": [],
        "union_count": 0,
        "error": error,
    }


def main() -> int:
    args = parse_args()
    universe = parse_universe(args.universe)
    log.info("universe: %d stocks", len(universe))

    if not universe:
        write_output(args.output, empty_payload(0, "empty universe"))
        return 0

    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token and not args.skip_sync:
        log.error("TUSHARE_TOKEN not set; cannot sync data")
        write_output(args.output, empty_payload(len(universe),
                                                "TUSHARE_TOKEN missing"))
        return 0

    # -- import engine (local file, same dir as this script) --
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tushare_engine import TushareEngine

    # -- import Sequoia-X strategies (duck-typed engine) --
    # strategy modules do `from sequoia_x.strategy.base import ...` and
    # `from sequoia_x.core.logger import get_logger`; make both importable.
    # NOTE: no fork/modification of Sequoia-X needed. Strategies require a
    # Settings object at construction but never USE it in run(); we pass a
    # dummy webhook URL and never instantiate FeishuNotifier, so nothing
    # is ever pushed.
    sys.path.insert(0, args.sequoia_dir)
    try:
        from sequoia_x.core.config import Settings
        settings = Settings(feishu_webhook_url="disabled-for-screening")
    except Exception:
        log.error("failed building Settings:\n%s", traceback.format_exc())
        write_output(args.output, empty_payload(len(universe),
                                                "settings build failed"))
        return 0
    classes = {}
    try:
        for name in [s.strip() for s in args.strategies.split(",") if s.strip()]:
            if name not in STRATEGY_MODULES:
                log.warning("unknown strategy %s, skipped", name)
                continue
            mod = __import__(f"sequoia_x.strategy.{STRATEGY_FILES[name]}",
                             fromlist=[STRATEGY_MODULES[name]])
            classes[name] = getattr(mod, STRATEGY_MODULES[name])
    except Exception:
        log.error("failed importing strategies:\n%s", traceback.format_exc())
        write_output(args.output, empty_payload(len(universe),
                                                "strategy import failed"))
        return 0

    log.info("strategies: %s", sorted(classes))

    # -- sync data --
    engine = TushareEngine(args.db, token)
    if not args.skip_sync:
        try:
            n = engine.sync_incremental(universe)
            log.info("synced %d rows", n)
        except Exception:
            log.error("data sync failed:\n%s", traceback.format_exc())
            write_output(args.output, empty_payload(len(universe),
                                                    "data sync failed"))
            return 0
    else:
        log.info("--skip-sync: using existing DB as-is")

    local = set(engine.get_local_symbols())
    missing = [s for s in universe if s not in local]
    if missing:
        log.warning("%d universe symbols have no data (e.g. long suspended): %s",
                    len(missing), ",".join(missing[:10]))

    # -- run strategies, each isolated --
    results = {}
    for name, cls in classes.items():
        try:
            picked = cls(engine=engine, settings=settings).run()
            picked = [p for p in (picked or [])]
            results[name] = sorted(set(picked))
            log.info("strategy %-18s -> %d picks", name, len(results[name]))
        except Exception:
            log.error("strategy %s crashed:\n%s", name, traceback.format_exc())
            results[name] = []

    union = sorted({s for picks in results.values() for s in picks})
    log.info("UNION: %d / %d", len(union), len(universe))

    write_output(args.output, {
        "date": date.today().isoformat(),
        "universe_count": len(universe),
        "strategies": results,
        "union": union,
        "union_count": len(union),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
