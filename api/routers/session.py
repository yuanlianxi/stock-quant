"""Session Router（sq-0008-p4-batch4，最后一批）
===================
拆自 api/main.py 的"Session 管理 API（v1.4 Phase 3.6）"段，含 10 个端点：
- POST /session                                  建仓
- POST /session/{session_id}/orders             加仓
- POST /session/{session_id}/orders/reduce      减仓
- POST /session/{session_id}/close              全平
- GET  /session/{session_id}/events             查事件
- GET  /session/{session_id}/trade-process      查海龟交易过程
- GET  /sessions                                列表（注意：复数）
- GET  /session/{session_id}/lines              查价格线
- PUT  /session/{session_id}/line/{line_type}   调价

设计依据（保持与 main.py 完全一致）：
- 0001_海龟期货系统设计.md §3.5 Session 管理
- 0006_数据模型与界面重构设计.md §6.4 Session Tab
- _requirements/data-model-redesign/01-design/02-backend.md §2.7

行为保证：
- 函数体逐行复制自 main.py L418-L679，未改一行。
- 函数内 import（sqlite3, api.services.*, strategies.*）保留原样（未上提），效果一致。
- 路径顺序：本 router 不使用 `prefix`，直接用全路径声明；defensive 顺序：
  literal（无 id）→ 带 id 端点（FastAPI 按声明顺序匹配，先精确后参数）。

⚠️ 路径顺序（声明顺序，按 defensive 原则）：
1. POST /session                                    （literal，无 id）
2. GET  /sessions                                   （literal，无 id，复数）
3. POST /session/{session_id}/orders                （带 id）
4. POST /session/{session_id}/orders/reduce         （带 id + 子路径）
5. POST /session/{session_id}/close                 （带 id + 子路径）
6. GET  /session/{session_id}/events                （带 id + 子路径）
7. GET  /session/{session_id}/trade-process         （带 id + 子路径）
8. GET  /session/{session_id}/lines                 （带 id + 子路径）
9. PUT  /session/{session_id}/line/{line_type}      （带 id + 子路径）

⚠️ /session vs /sessions 坑：
- 单数 `/session` 用于 8 个有 id 的端点
- 复数 `/sessions` 用于 1 个列表端点
- 本 router **不**使用 `prefix="/session"`，所有路径全路径声明，避免 prefix + 复数冲突
"""
from typing import Optional

from fastapi import APIRouter, HTTPException

from api.schemas.session import (
    LineOverrideRequest,
    OrderAddRequest,
    OrderReduceRequest,
    SessionCloseRequest,
    SessionCreateRequest,
)

router = APIRouter(tags=["session"])


# ============================================================
# Session 管理 API（v1.4 Phase 3.6）
# ============================================================
# SessionCreateRequest / OrderAddRequest / OrderReduceRequest / SessionCloseRequest /
# LineOverrideRequest 已迁到 api.schemas.session（Phase 3 sq-0008-p3-schemas）


@router.post("/session")
async def create_session(req: SessionCreateRequest):
    """
    手动建仓：创建 trade_session + 第 1 个 unit

    Errors:
        409: 同一 (account, strategy, direction) 在去重窗口内重复
        500: FK 约束失败 / DB 错误
    """
    import sqlite3
    from api.services.sim_engine import open_session

    # 应用层重复检查：
    # 1) 同一 (account, strategy, direction) 已有 open session → 拒
    # 2) 同一组合 60 秒内创建过 session（去重窗口）→ 拒
    conn = sqlite3.connect("data/futures_akshare.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM trade_sessions
        WHERE account_id = ? AND strategy_id = ? AND direction = ?
          AND status = 'open'
        LIMIT 1
        """,
        (req.account_id, req.strategy_id, req.direction),
    )
    if cur.fetchone() is not None:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=(
                f"Session 已存在（account={req.account_id} "
                f"strategy={req.strategy_id} direction={req.direction} 已有 open session）"
            ),
        )
    cur.execute(
        """
        SELECT 1 FROM trade_sessions
        WHERE account_id = ? AND strategy_id = ? AND direction = ?
          AND entry_time >= datetime('now', '-60 seconds')
        LIMIT 1
        """,
        (req.account_id, req.strategy_id, req.direction),
    )
    if cur.fetchone() is not None:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=(
                f"Session 重复（account={req.account_id} "
                f"strategy={req.strategy_id} direction={req.direction} 60 秒内已创建）"
            ),
        )
    conn.close()

    try:
        session_id = open_session(
            account_id=req.account_id,
            strategy_id=req.strategy_id,
            symbol=req.symbol,
            contract_code=req.contract_code,
            direction=req.direction,
            entry_price=req.entry_price,
            n_value=req.n_value,
        )
        return {
            "session_id": session_id,
            "status": "open",
            "current_units": 1,
            "first_entry_price": req.entry_price,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/orders")
async def session_orders(session_id: str, req: OrderAddRequest):
    """
    加仓（海龟 0.5N 间隔检测由调用方负责，API 只管加）

    Returns:
        {"unit_id": "...", "session_id": "...", "action": "add"}
    """
    from api.services.sim_engine import add_unit
    from api.services.session_lifecycle import with_session_lock, SessionLockedError

    try:
        with with_session_lock(session_id, "api_caller"):
            unit_id = add_unit(session_id, req.price, req.n_value)
            return {"unit_id": unit_id, "session_id": session_id, "action": "add"}
    except SessionLockedError as e:
        raise HTTPException(status_code=423, detail=f"Session 被锁定: {e.holder}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/orders/reduce")
async def session_orders_reduce(session_id: str, req: OrderReduceRequest):
    """减仓单个 unit"""
    from api.services.sim_engine import close_unit
    from api.services.session_lifecycle import with_session_lock, SessionLockedError

    try:
        with with_session_lock(session_id, "api_caller"):
            ok = close_unit(req.unit_id, req.close_price, req.reason)
            return {"ok": ok, "unit_id": req.unit_id, "action": "reduce"}
    except SessionLockedError as e:
        raise HTTPException(status_code=423, detail=f"Session 被锁定: {e.holder}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/close")
async def close_session_endpoint(session_id: str, req: SessionCloseRequest):
    """全部平仓"""
    from api.services.sim_engine import close_session
    from api.services.session_lifecycle import with_session_lock, SessionLockedError

    try:
        with with_session_lock(session_id, "api_caller"):
            ok = close_session(session_id, req.exit_price, req.reason)
            return {
                "ok": ok,
                "session_id": session_id,
                "action": "close_all",
                "reason": req.reason,
            }
    except SessionLockedError as e:
        raise HTTPException(status_code=423, detail=f"Session 被锁定: {e.holder}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/events")
async def get_session_events(
    session_id: str,
    event_type: Optional[str] = None,
    days: int = 30,
    limit: int = 100,
):
    """
    查 session 事件流水（v1.4 核心端点）
    GET /session/{id}/events?event_type=line_overridden&days=7
    """
    from api.services.event_logger import query_events

    events = query_events(
        session_id=session_id, event_type=event_type, days=days, limit=limit
    )
    return {
        "session_id": session_id,
        "event_type": event_type or "all",
        "days": days,
        "count": len(events),
        "events": events,
    }


@router.get("/session/{session_id}/trade-process")
async def get_trade_process(
    session_id: str,
    event_type: Optional[str] = None,
    days: int = 30,
    limit: int = 100,
):
    """
    查海龟交易过程流水（v1.5 Phase 3.8 核心端点）
    GET /session/{id}/trade-process
    GET /session/{id}/trade-process?event_type=stop_loss_check
    GET /session/{id}/trade-process?event_type=entry_signal&days=7
    """
    from strategies.trade_process_logger import query_trade_process, get_trade_process_summary

    events = query_trade_process(
        session_id=session_id, event_type=event_type, days=days, limit=limit
    )
    summary = get_trade_process_summary(session_id)
    return {
        "session_id": session_id,
        "event_type": event_type or "all",
        "days": days,
        "count": len(events),
        "summary": summary,
        "events": events,
    }


@router.get("/sessions")
async def list_sessions_endpoint(
    account_id: Optional[str] = None,
    status: Optional[str] = None,
    strategy_id: Optional[str] = None,
    limit: int = 100,
):
    """
    查 sessions 列表（多条件过滤）
    GET /sessions?status=open
    GET /sessions?account_id=sim_default&status=closed
    """
    from api.services.session_lifecycle import list_sessions

    sessions = list_sessions(
        account_id=account_id, status=status, strategy_id=strategy_id, limit=limit
    )
    return {"count": len(sessions), "sessions": sessions}


@router.get("/session/{session_id}/lines")
async def get_session_lines(session_id: str, use_cache: bool = True):
    """
    查价格线（实时计算 + 缓存）
    GET /session/{id}/lines
    """
    from api.services.line_calculator import compute_lines

    try:
        lines = compute_lines(session_id, use_cache=use_cache)
        return lines
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/session/{session_id}/line/{line_type}")
async def override_line_endpoint(
    session_id: str, line_type: str, req: LineOverrideRequest
):
    """
    用户调价

    PUT /session/{id}/line/stop_loss
    Body: {"price": 17000.0}

    PUT /session/{id}/line/stop_loss
    Body: {"price": null}  # 取消 override
    """
    from api.services.line_calculator import override_line
    from api.services.session_lifecycle import with_session_lock, SessionLockedError

    try:
        with with_session_lock(session_id, "api_caller"):
            result = override_line(session_id, line_type, req.price)
            return result
    except SessionLockedError as e:
        raise HTTPException(status_code=423, detail=f"Session 被锁定: {e.holder}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
