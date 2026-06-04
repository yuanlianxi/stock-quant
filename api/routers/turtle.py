"""Turtle Router（sq-0008-p4-batch3）
===================
拆自 api/main.py 的"海龟信号"段（Phase 3.x），含 6 个端点：
- GET  /turtle/signals/{symbol}
- GET  /turtle/signals/active
- GET  /turtle/signals/alerts
- POST /turtle/scan/{symbol}
- POST /turtle/scan/all
- GET  /turtle/signal/latest

设计依据（保持与 main.py 完全一致）：
- 0001_海龟期货系统设计.md §3.4 海龟信号
- _requirements/data-model-redesign/01-design/02-backend.md §2.5

行为保证：
- 函数体逐行复制自 main.py L1050-L1095，未改一行。
- imports 集中在模块顶部（main.py 用了 try-except 包大段 data.data_loader imports，
  本 router 同样保留 try-except 容错，效果一致）。
"""
from fastapi import APIRouter

# 顶部 import 一次性引入所有需要的依赖（main.py 原本是 try-except 包大段）
try:
    from data.data_loader import (
        ALL_PRODUCTS,
        get_turtle_signals,
        get_active_signals,
        get_turtle_alerts,
        detect_signals_for_symbol,
    )
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

router = APIRouter(prefix="/turtle", tags=["turtle"])


# ============================================================
# 海龟信号 API
# ============================================================

@router.get("/signals/{symbol}")
async def get_symbol_turtle_signals(symbol: str, days: int = 30):
    """查询某品种近 N 天的所有信号"""
    return get_turtle_signals(symbol.upper(), days=days)


@router.get("/signals/active")
async def get_turtle_active():
    """当前所有未离市的入场信号"""
    return get_active_signals()


@router.get("/signals/alerts")
async def get_turtle_alerts_endpoint(since_minutes: int = 30):
    """最近 N 分钟内的新信号（用于前端推送）"""
    return get_turtle_alerts(since_minutes=since_minutes)


@router.post("/scan/{symbol}")
async def scan_symbol_signals(symbol: str, period: str = "5min"):
    """对指定品种扫描历史分钟数据，检测所有信号"""
    sigs = detect_signals_for_symbol(symbol.upper(), period=period)
    return {"symbol": symbol.upper(), "signals_found": len(sigs), "signals": sigs}


@router.post("/scan/all")
async def scan_all_signals(period: str = "5min"):
    """全量扫描所有品种历史信号"""
    results = {}
    for sym in ALL_PRODUCTS:
        try:
            sigs = detect_signals_for_symbol(sym, period=period)
            results[sym] = {"signals_found": len(sigs), "signals": sigs}
        except Exception as e:
            results[sym] = {"error": str(e)}
    total = sum(v.get("signals_found", 0) for v in results.values())
    return {"total_signals": total, "details": results}


@router.get("/signal/latest")
async def get_latest_signal(symbol: str):
    """获取某品种最新一条信号"""
    sigs = get_turtle_signals(symbol.upper(), days=7)
    return sigs[0] if sigs else None
