"""Market Router（sq-0008-p4-batch3）
===================
拆自 api/main.py 的"合约 / 行情 / 主力 / 分时 / 日线"段（Phase 1.3 + Phase 5.1），含 6 个端点：
- GET /contracts/{symbol}
- GET /quotes/{contract_code}
- GET /main-contract/{symbol}
- GET /minute/{symbol}
- GET /daily/{symbol}
- POST /minute/sync

设计依据（保持与 main.py 完全一致）：
- 0001_海龟期货系统设计.md §3.3 数据接入层
- _requirements/data-model-redesign/01-design/02-backend.md §2.3

行为保证：
- 函数体逐行复制自 main.py L317-L1133，未改一行。
- imports 集中在模块顶部（main.py 中部分端点用的是函数内 import sqlite3 / datetime / math，
  本 router 统一提到模块顶部，效果一致）。
"""
import math
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
from fastapi import APIRouter, HTTPException

# 顶部 import 一次性引入所有需要的依赖（main.py 原本是函数内 import）
try:
    from data.data_loader import (
        get_minute_from_cache,
        sync_all_minute_data,
        get_contract_info,
        SYMBOL_NAME,
        check_bar_signal,
        get_daily_data_from_cache,
    )
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

router = APIRouter(tags=["market"])


# ============================================================
# Phase 1.3：合约 / 行情 / 主力查询
# ============================================================

@router.get("/contracts/{symbol}")
async def get_contracts(symbol: str):
    """
    查询某品种的所有合约（含主力标记）
    GET /contracts/AG

    返回：{
        "symbol": "AG",
        "count": 4,
        "main_contract": "ag2607",
        "contracts": [
            {"contract_code": "ag2607", "is_main": 1, "main_rank": 1, ...},
            ...
        ]
    }
    """
    sym = symbol.upper()
    try:
        conn = sqlite3.connect('data/futures_akshare.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT contract_code, symbol, name, exchange, list_date, expire_date,
                   is_main, main_rank, contract_size, point_value, tick,
                   margin_ratio, status
            FROM futures_contracts
            WHERE symbol = ?
            ORDER BY is_main DESC, main_rank ASC
        """, (sym,))
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询合约失败: {e}")

    if not rows:
        return {
            "symbol": sym, "count": 0, "main_contract": None,
            "contracts": [],
            "note": f"无 {sym} 合约数据，请先运行 sync_all_contracts_and_main()"
        }

    main = next((r["contract_code"] for r in rows if r["is_main"] == 1), None)
    return {"symbol": sym, "count": len(rows), "main_contract": main, "contracts": rows}


@router.get("/quotes/{contract_code}")
async def get_quote(contract_code: str):
    """
    查询某合约实时行情
    GET /quotes/ag2607

    返回：{"contract_code": "ag2607", "data": {...} | None, "note": "..."}
    """
    code = contract_code.lower()
    try:
        conn = sqlite3.connect('data/futures_akshare.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT contract_code, symbol, trade, change_abs, change_pct,
                   open, high, low, preclose, presettlement, settlement,
                   volume, position, bidprice1, askprice1, bidvol1, askvol1,
                   ticktime, updated_at
            FROM futures_quotes
            WHERE contract_code = ?
        """, (code,))
        row = cur.fetchone()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询行情失败: {e}")

    if not row:
        return {
            "contract_code": code, "data": None,
            "note": f"无 {code} 行情数据，请等待实时同步或调用 POST /quotes/sync"
        }

    return {"contract_code": code, "data": dict(row)}


@router.get("/main-contract/{symbol}")
async def get_main_contract(symbol: str):
    """
    快速查询某品种主力合约
    GET /main-contract/AG

    返回：{"symbol": "AG", "main_contract": "ag2607", "main_rank": 1, ...}
    """
    sym = symbol.upper()
    try:
        conn = sqlite3.connect('data/futures_akshare.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT contract_code, main_rank, exchange, expire_date
            FROM futures_contracts
            WHERE symbol = ? AND is_main = 1
            LIMIT 1
        """, (sym,))
        row = cur.fetchone()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询主力合约失败: {e}")

    if not row:
        return {
            "symbol": sym, "main_contract": None, "main_rank": None,
            "note": f"未识别 {sym} 主力合约，请先调用 sync_all_contracts_and_main()"
        }

    return {
        "symbol": sym,
        "main_contract": row["contract_code"],
        "main_rank": row["main_rank"],
        "exchange": row["exchange"],
        "expire_date": row["expire_date"],
    }


# ============================================================
# 分时数据 / 日线
# ============================================================

@router.get("/minute/{symbol}")
async def get_minute_data(symbol: str, period: str = "5min", limit: int = 500, date: str = "", days: int = 0):
    """
    查询某品种分时数据（纯缓存，不请求外部）
    GET /minute/{symbol}?period=5min&date=2026-05-28   -> 指定单天
    GET /minute/{symbol}?period=5min&days=3            -> 近3天
    GET /minute/{symbol}?period=5min                  -> 默认今天

    v1.5：records 每行新增 `date` 字段（YYYY-MM-DD），如 DB 中 date 为 NULL 则从 datetime 派生。
    """
    sym = symbol.upper()
    try:
        df = get_minute_from_cache(sym, period=period, limit=limit, date=date, days=days)
        if df is None or len(df) == 0:
            note = f"无 {date} 的缓存数据" if date else (f"近{days}天无数据" if days else "无今天缓存数据，请先调用 /minute/sync 同步")
            return {"symbol": sym, "period": period, "date": date or (f"近{days}天" if days else "today"), "records": [], "note": note}
        # v1.5：补齐 date 字段（DB 中为 NULL 时从 datetime 派生前 10 位）
        has_date_col = "date" in df.columns
        records = []
        for idx, row in df.iterrows():
            r = {"datetime": str(idx), **row.to_dict()}
            if not has_date_col or r.get("date") is None or (isinstance(r.get("date"), float) and pd.isna(r.get("date"))):
                # 从 datetime 字符串前 10 位派生
                r["date"] = str(idx)[:10]
            records.append(r)
        date_label = date or (f"近{days}天" if days else "today")
        return {"symbol": sym, "period": period, "date": date_label, "count": len(records), "records": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily/{symbol}")
async def get_daily_data(symbol: str, days: int = 30, include_atr: bool = True):
    """
    查询某品种日线数据（v1.5：含 atr + main_contract_code 字段）
    GET /daily/AG?days=30         -> 近 30 天
    GET /daily/AG?days=365        -> 近 1 年
    GET /daily/AG?days=1095       -> 近 3 年
    GET /daily/AG?days=30&include_atr=false  -> 关闭 atr 字段
    """
    sym = symbol.upper()
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        df = get_daily_data_from_cache(sym, start_date, end_date)
        if df is None or len(df) == 0:
            return {"symbol": sym, "date": f"近{days}天", "records": [], "note": f"无最近{days}天数据"}
        # v1.5：增加 atr + main_contract_code 字段
        records = []
        for idx, row in df.iterrows():
            r = {
                "datetime": str(idx.date()),
                "date": str(idx.date()),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
            }
            # v1.5 新增：atr（data_loader 已计算）
            if include_atr and "atr" in df.columns:
                atr_val = row.get("atr")
                if atr_val is not None and not (isinstance(atr_val, float) and math.isnan(atr_val)):
                    r["atr"] = atr_val
                else:
                    r["atr"] = None
            # v1.5 新增：main_contract_code（DB 中读取，可能为 NULL）
            if "main_contract_code" in df.columns:
                mc = row.get("main_contract_code")
                if mc is not None and not (isinstance(mc, float) and math.isnan(mc)):
                    r["main_contract_code"] = mc
                else:
                    r["main_contract_code"] = None
            # 过滤无效 OHLC
            if all(r.get(c) is not None and not (isinstance(r[c], float) and math.isnan(r[c])) for c in ["open", "high", "low", "close"]):
                records.append(r)
        return {"symbol": sym, "date": f"近{days}天", "count": len(records), "records": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 同步分时数据（顺便检测信号）
# ============================================================

@router.post("/minute/sync")
async def sync_minute_data(period: str = "5min"):
    """同步分时数据并检测信号"""
    # 先同步
    result = sync_all_minute_data(period=period, progress=False)

    # 对每个成功同步的品种，检测最后一根 K 线的信号
    new_signals = []
    for sym, contract_code, count, latest in (result.get("success") or []):
        if count > 0:
            # 取最后一根 K 线
            df = get_minute_from_cache(sym, period=period, limit=1)
            if len(df) > 0:
                row = df.iloc[-1]
                bar_time = str(df.index[-1])
                ci = get_contract_info(sym)
                name = ci.get("name", SYMBOL_NAME.get(sym, sym))
                sigs = check_bar_signal(
                    symbol=sym,
                    bar_close=float(row["close"]),
                    bar_high=float(row["high"]),
                    bar_low=float(row["low"]),
                    bar_time=bar_time,
                    period=period,
                    name=name,
                    contract_code=ci.get("contract_code", ""),
                )
                new_signals.extend(sigs)

    return {
        "sync": result,
        "new_signals": len(new_signals),
        "signals": new_signals,
    }
