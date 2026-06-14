"""Strategy Router（sq-0008-p4-batch4，最后一批）
===================
拆自 api/main.py 的"Phase 2.3: 策略 CRUD + 历史查询"段，含 8 个端点：
- GET    /strategies
- GET    /strategies/{strategy_id}
- POST   /strategies
- PUT    /strategies/{strategy_id}
- DELETE /strategies/{strategy_id}
- GET    /strategies/{strategy_id}/signals
- GET    /strategies/{strategy_id}/param-history
- GET    /strategies/{strategy_id}/events

设计依据（保持与 main.py 完全一致）：
- 0001_海龟期货系统设计.md §3.4 策略管理
- _requirements/data-model-redesign/01-design/02-backend.md §2.6

行为保证：
- 函数体逐行复制自 main.py L156-L417，未改一行。
- 函数内 `import sqlite3, json, datetime` 全部保留原样（未上提），效果一致。
- 路径顺序：本 router 不使用 `prefix`，直接用全路径声明；defensive 顺序：
  literal → 单段 id → 子路径（FastAPI 按声明顺序匹配，literal 优先避免被 `{id}` 吃掉）。

⚠️ 路径顺序（声明顺序）：
1. GET  /strategies                  （literal，无 id）
2. POST /strategies                  （literal，无 id）
3. GET  /strategies/{strategy_id}    （带 id，单段）
4. PUT  /strategies/{strategy_id}    （带 id，单段）
5. DELETE /strategies/{strategy_id}  （带 id，单段）
6. GET  /strategies/{strategy_id}/signals      （带 id + 子路径）
7. GET  /strategies/{strategy_id}/param-history（带 id + 子路径）
8. GET  /strategies/{strategy_id}/events       （带 id + 子路径）
"""
from fastapi import APIRouter, HTTPException
from api.schemas.strategy import (
    StrategyCreateRequest,
    StrategyUpdateRequest,
)

router = APIRouter(tags=["strategy"])


# ============================================================
# Phase 2.3: 策略 CRUD + 历史查询（8 个端点）
# ============================================================
# StrategyCreateRequest / StrategyUpdateRequest 已迁到 api.schemas.strategy（Phase 3 sq-0008-p3-schemas）


@router.get("/strategies")
async def list_strategies(include_inactive: bool = False):
    """
    列出所有策略
    GET /strategies?include_inactive=true
    返回：{
        "count": N,
        "strategies": [
            {"strategy_id": "...", "name": "...", "type": "...", "version": 1, "is_active": 1, "params": {...}},
            ...
        ]
    }
    """
    import sqlite3, json
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if include_inactive:
        cur.execute("SELECT strategy_id, name, type, version, description, params_json, is_active, is_paper, created_at, updated_at FROM strategies ORDER BY strategy_id")
    else:
        cur.execute("SELECT strategy_id, name, type, version, description, params_json, is_active, is_paper, created_at, updated_at FROM strategies WHERE is_active = 1 ORDER BY strategy_id")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    for r in rows:
        try:
            r['params'] = json.loads(r.pop('params_json')) if r.get('params_json') else {}
        except Exception:
            r['params'] = {}
    return {"count": len(rows), "strategies": rows}


@router.get("/strategies/{strategy_id}")
async def get_strategy_detail(strategy_id: str):
    """查单个策略详情"""
    import sqlite3, json
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM strategies WHERE strategy_id = ?", (strategy_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

    data = dict(row)
    try:
        data['params'] = json.loads(data.pop('params_json')) if data.get('params_json') else {}
    except Exception:
        data['params'] = {}
    return data


@router.post("/strategies")
async def create_strategy(req: StrategyCreateRequest):
    """
    创建策略（同时写 strategy_param_history 第一条）
    """
    import sqlite3, json
    from datetime import datetime
    conn = sqlite3.connect('data/futures_akshare.db')
    cur = conn.cursor()

    # 检查 UNIQUE(name, version)
    cur.execute("SELECT 1 FROM strategies WHERE name = ? AND version = ?", (req.name, req.version))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail=f"策略 {req.name} v{req.version} 已存在")

    now = datetime.now().isoformat()
    try:
        cur.execute("""
            INSERT INTO strategies(strategy_id, name, version, type, description, params_json, is_active, is_paper, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (req.strategy_id, req.name, req.version, req.type, req.description,
              json.dumps(req.params, ensure_ascii=False), req.is_active, req.is_paper, now, now))

        # 写第一条参数历史
        cur.execute("""
            INSERT INTO strategy_param_history(strategy_id, name, version, params_json, changed_at, changed_by, change_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (req.strategy_id, req.name, req.version,
              json.dumps(req.params, ensure_ascii=False), now, 'system', '创建策略'))

        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        raise HTTPException(status_code=409, detail=f"DB 完整性错误：{e}")
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

    conn.close()
    return {"created": req.strategy_id, "version": req.version, "params_history_id": cur.lastrowid}


@router.put("/strategies/{strategy_id}")
async def update_strategy(strategy_id: str, req: StrategyUpdateRequest):
    """
    更新策略参数（同时写 strategy_param_history）
    """
    import sqlite3, json
    from datetime import datetime
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT name, version FROM strategies WHERE strategy_id = ?", (strategy_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

    now = datetime.now().isoformat()
    try:
        cur.execute("""
            UPDATE strategies
            SET params_json = ?, updated_at = ?
            WHERE strategy_id = ?
        """, (json.dumps(req.params, ensure_ascii=False), now, strategy_id))

        cur.execute("""
            INSERT INTO strategy_param_history(strategy_id, name, version, params_json, changed_at, changed_by, change_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (strategy_id, row["name"], row["version"],
              json.dumps(req.params, ensure_ascii=False), now, req.changed_by, req.change_reason))

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

    conn.close()
    return {"updated": strategy_id, "params_history_id": cur.lastrowid}


@router.delete("/strategies/{strategy_id}")
async def soft_delete_strategy(strategy_id: str):
    """
    软删除（is_active = 0），保留历史
    """
    import sqlite3
    from datetime import datetime
    conn = sqlite3.connect('data/futures_akshare.db')
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM strategies WHERE strategy_id = ?", (strategy_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

    now = datetime.now().isoformat()
    cur.execute("UPDATE strategies SET is_active = 0, updated_at = ? WHERE strategy_id = ?", (now, strategy_id))
    conn.commit()
    conn.close()
    return {"deactivated": strategy_id, "timestamp": now}


@router.get("/strategies/{strategy_id}/signals")
async def get_strategy_signals(strategy_id: str, symbol: str = "", days: int = 30, limit: int = 100):
    """
    查信号历史（v1.3 精简：仅 entry_long / entry_short）
    GET /strategies/turtle_v1/signals?symbol=AG&days=30
    """
    import sqlite3
    from datetime import datetime, timedelta
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    since = (datetime.now() - timedelta(days=days)).isoformat()

    if symbol:
        cur.execute("""
            SELECT * FROM strategy_signals
            WHERE strategy_id = ? AND symbol = ? AND bar_time >= ?
            ORDER BY bar_time DESC LIMIT ?
        """, (strategy_id, symbol, since, limit))
    else:
        cur.execute("""
            SELECT * FROM strategy_signals
            WHERE strategy_id = ? AND bar_time >= ?
            ORDER BY bar_time DESC LIMIT ?
        """, (strategy_id, since, limit))

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    return {
        "strategy_id": strategy_id,
        "symbol": symbol or "all",
        "days": days,
        "count": len(rows),
        "signals": rows
    }


@router.get("/strategies/{strategy_id}/param-history")
async def get_param_history(strategy_id: str, limit: int = 50):
    """
    查参数迭代历史
    GET /strategies/turtle_v1/param-history?limit=20
    """
    import sqlite3
    import json
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM strategy_param_history
        WHERE strategy_id = ?
        ORDER BY changed_at DESC LIMIT ?
    """, (strategy_id, limit))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    # 解析 params_json
    for r in rows:
        try:
            r['params'] = json.loads(r.pop('params_json')) if r.get('params_json') else {}
        except Exception:
            r['params'] = {}

    return {"strategy_id": strategy_id, "count": len(rows), "history": rows}


@router.get("/strategies/{strategy_id}/events")
async def get_strategy_events(strategy_id: str, days: int = 30, limit: int = 100):
    """
    查策略事件日志
    GET /strategies/turtle_v1/events?days=7
    """
    import sqlite3
    import json
    from datetime import datetime, timedelta
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    cur.execute("""
        SELECT * FROM strategy_event_log
        WHERE strategy_id = ? AND event_at >= ?
        ORDER BY event_at DESC LIMIT ?
    """, (strategy_id, since, limit))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    # 解析 context_json
    for r in rows:
        try:
            r['context'] = json.loads(r.pop('context_json')) if r.get('context_json') else {}
        except Exception:
            r['context'] = {}

    return {"strategy_id": strategy_id, "days": days, "count": len(rows), "events": rows}


# ============================================================
# v0.18.14 data-model Phase 2 收尾：v1.5 trade-process 端点
# ============================================================
# 注意：当前 schema 下 turtle_trade_process 表无 strategy_id 字段（trade_sessions 表
# 是 Phase 3 才建）。务实实现：按 account_id 过滤；Phase 3 实施后会自动 JOIN
# trade_sessions.strategy_id 严格过滤。

@router.get("/strategies/{strategy_id}/trade-process")
async def get_trade_process(strategy_id: str, account_id: str = None, limit: int = 100):
    """
    v1.5 过程数据（最近 N 条）
    GET /strategies/turtle_v1/trade-process?account_id=sim_default&limit=50

    返回：{
        "strategy_id": "turtle_v1",
        "account_id": "sim_default",  # 可选
        "count": N,
        "records": [
            {"id": ..., "session_id": ..., "event_type": ..., "bar_time": ..., ...},
            ...
        ]
    }

    注：当前 Phase 1 schema 不含 trade_sessions 表，无法严格按 strategy_id 过滤。
    Phase 3 实施 trade_sessions 后，切换为 JOIN trade_sessions.strategy_id 过滤。
    """
    import sqlite3
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if account_id:
        cur.execute("""
            SELECT * FROM turtle_trade_process
            WHERE account_id = ?
            ORDER BY bar_time DESC LIMIT ?
        """, (account_id, limit))
    else:
        cur.execute("""
            SELECT * FROM turtle_trade_process
            ORDER BY bar_time DESC LIMIT ?
        """, (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {
        "strategy_id": strategy_id,
        "account_id": account_id,
        "count": len(rows),
        "phase3_note": "Phase 3 trade_sessions 实施后切换为 JOIN strategy_id 过滤",
        "records": rows
    }
