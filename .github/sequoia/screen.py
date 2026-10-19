




聊天
打开聊天和旁聊
Muse
20:16
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
助手消息：都不用——**直接跑在 GitHub Actions 里**，跟你现在的分析 workflow 同一个地方，不需要你本地电脑开着，也不需要另租服务器。

架构是这样的：

- Sequoia-X 本身是个 Python 程序（7 个技术形态策略），用 SQLite 存历史 K 线，数据源是 baostock，零 token 成本
- 在你 fork 的 workflow 里加一个**前置筛选 job**：每天先跑 Sequoia-X 技术筛选（212 只 → ~50 只），结果传给后面的 LLM 分析 job
- 公开仓库的 Actions 分钟数免费，所以二期**不增加任何机器成本和 token 成本**，全自动，你什么都不用管

有两个要实测的点，我提前说明：

1. **baostock 从 GitHub 海外机器能不能连上**——未知，要跑一次才知道；连不上就改用你已有的 Tushare 做数据源适配
2. **SQLite 历史库的持久化**——Actions 机器每次是新的，用官方缓存机制存数据库（首次回填约 12 分钟，之后每天增量 2–3 分钟），这是常规做法

工作量主要是改你 fork 的 workflow 文件（加筛选 job + 传参），改法我这边准备好给你，你粘贴就行。

要我现在开始搭二期吗？
用户消息：开始吧
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

d391bca0.png
你：
这个怎么处理

直接点绿色 Commit changes 就行，保持选中的 Commit directly to the main branch 不动。

因为 workflow 跑的是 main 分支，文件必须进 main 才生效。选另一个（new branch）还得多一步合并，没必要。

screen.py
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
