"""Account Router（sq-0008-p4-batch2）
===================
拆自 api/main.py 的"账户中心"段（Phase 5.1），含 5 个端点：
- GET /account/overview
- GET /account/{account_id}/positions
- GET /account/{account_id}/units
- GET /account/{account_id}/sessions
- GET /account/{account_id}/trades

设计依据（保持与 main.py 完全一致）：
- 0006_数据模型与界面重构设计.md §6.5 账户中心 Tab
- _requirements/data-model-redesign/01-design/02-backend.md §2.2

行为保证：
- 函数体逐行复制自 main.py L286-L524，未改一行。
- imports 集中在模块顶部（main.py 中部分端点用的是函数内 import，本 router
  统一提到模块顶部，效果一致）。
"""
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException

from api.services.line_calculator import compute_lines

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/overview")
async def account_overview(account_id: str = "sim_default", strategy_id: Optional[str] = None, days: int = 30):
    """
    账户总览（聚合 5 表 + 价格线）
    GET /account/overview?account_id=sim_default
    """
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. 账户余额
    cur.execute("SELECT * FROM sim_account WHERE account_id = ?", (account_id,))
    acc_row = cur.fetchone()
    if not acc_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"账户 {account_id} 不存在")
    account = dict(acc_row)

    # 2. 持仓列表
    cur.execute("SELECT * FROM sim_positions WHERE account_id = ?", (account_id,))
    positions = [dict(r) for r in cur.fetchall()]

    # 3. Open sessions（含 price lines）
    if strategy_id:
        cur.execute("""
            SELECT * FROM trade_sessions
            WHERE account_id = ? AND strategy_id = ? AND status = 'open'
            ORDER BY entry_time DESC
        """, (account_id, strategy_id))
    else:
        cur.execute("""
            SELECT * FROM trade_sessions
            WHERE account_id = ? AND status = 'open'
            ORDER BY entry_time DESC
        """, (account_id,))
    open_sessions_raw = [dict(r) for r in cur.fetchall()]

    # 为每个 open session 算价格线
    open_sessions = []
    for s in open_sessions_raw:
        try:
            lines = compute_lines(s['session_id'], use_cache=True)
            s['lines'] = lines
        except Exception:
            s['lines'] = None
        # 解析 price_overrides_json
        try:
            s['price_overrides'] = json.loads(s.get('price_overrides_json') or '{}')
        except Exception:
            s['price_overrides'] = {}
        s.pop('price_overrides_json', None)
        open_sessions.append(s)

    # 4. 最近 N 天成交
    cur.execute("""
        SELECT * FROM sim_trades
        WHERE account_id = ? AND filled_at >= date('now', ?)
        ORDER BY filled_at DESC LIMIT 50
    """, (account_id, f'-{days} days'))
    recent_trades = [dict(r) for r in cur.fetchall()]

    # 5. 4 Unit 明细（来自所有 open session 的 position_units）
    all_units = []
    for s in open_sessions_raw:
        cur.execute("""
            SELECT * FROM position_units
            WHERE session_id = ? AND status = 'open'
            ORDER BY unit_index
        """, (s['session_id'],))
        units = [dict(r) for r in cur.fetchall()]
        for u in units:
            try:
                u['price_overrides'] = json.loads(u.get('price_overrides_json') or '{}') if u.get('price_overrides_json') else {}
            except Exception:
                u['price_overrides'] = {}
            u.pop('price_overrides_json', None)
        all_units.extend(units)

    conn.close()

    # 6. 计算总览统计
    total_position_value = sum((p.get('avg_cost') or 0) * (p.get('quantity') or 0) for p in positions)
    total_unrealized_pnl = sum(p.get('unrealized_pnl') or 0 for p in positions)
    total_realized_pnl = account.get('realized_pnl') or 0

    return {
        "account": account,
        "summary": {
            "balance": account.get('balance', 0),
            "available": account.get('available', 0),
            "margin_used": account.get('margin_used', 0),
            "position_value": round(total_position_value, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "realized_pnl": round(total_realized_pnl, 2),
            "open_sessions_count": len(open_sessions),
            "open_units_count": len(all_units),
            "recent_trades_count": len(recent_trades)
        },
        "positions": positions,
        "open_sessions": open_sessions,
        "open_units": all_units,
        "recent_trades": recent_trades,
        "days": days
    }


@router.get("/{account_id}/positions")
async def account_positions(account_id: str):
    """账户持仓列表"""
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM sim_positions WHERE account_id = ?", (account_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"account_id": account_id, "count": len(rows), "positions": rows}


@router.get("/{account_id}/units")
async def account_units(account_id: str, status: Optional[str] = "open"):
    """账户 4 Unit 明细（按 session_id 分组）"""
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if status:
        cur.execute("""
            SELECT * FROM position_units
            WHERE account_id = ? AND status = ?
            ORDER BY session_id, unit_index
        """, (account_id, status))
    else:
        cur.execute("""
            SELECT * FROM position_units
            WHERE account_id = ?
            ORDER BY session_id, unit_index
        """, (account_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    # 解析 price_overrides_json
    for r in rows:
        if 'price_overrides_json' in r:
            try:
                r['price_overrides'] = json.loads(r.pop('price_overrides_json') or '{}') if r.get('price_overrides_json') else {}
            except Exception:
                r['price_overrides'] = {}
                r.pop('price_overrides_json', None)
        else:
            r['price_overrides'] = {}

    # 按 session_id 分组
    by_session = {}
    for u in rows:
        sid = u['session_id']
        if sid not in by_session:
            by_session[sid] = []
        by_session[sid].append(u)

    return {
        "account_id": account_id,
        "status": status or "all",
        "count": len(rows),
        "by_session": by_session,
        "units": rows
    }


@router.get("/{account_id}/sessions")
async def account_sessions(account_id: str, status: Optional[str] = None,
                           strategy_id: Optional[str] = None, limit: int = 50):
    """账户 session 列表"""
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    conditions = ["account_id = ?"]
    params = [account_id]
    if status:
        conditions.append("status = ?")
        params.append(status)
    if strategy_id:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)
    params.append(limit)
    where = " AND ".join(conditions)
    cur.execute(f"""
        SELECT * FROM trade_sessions
        WHERE {where}
        ORDER BY entry_time DESC LIMIT ?
    """, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    for r in rows:
        if 'price_overrides_json' in r:
            try:
                r['price_overrides'] = json.loads(r.pop('price_overrides_json') or '{}') if r.get('price_overrides_json') else {}
            except Exception:
                r['price_overrides'] = {}
                r.pop('price_overrides_json', None)
        else:
            r['price_overrides'] = {}

    return {
        "account_id": account_id,
        "status": status or "all",
        "strategy_id": strategy_id or "all",
        "count": len(rows),
        "sessions": rows
    }


@router.get("/{account_id}/trades")
async def account_trades(account_id: str, days: int = 30, limit: int = 100):
    """账户成交记录"""
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    cur.execute("""
        SELECT * FROM sim_trades
        WHERE account_id = ? AND filled_at >= ?
        ORDER BY filled_at DESC LIMIT ?
    """, (account_id, since, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {
        "account_id": account_id,
        "days": days,
        "count": len(rows),
        "trades": rows
    }
