"""Backtest Router（sq-0008-p4-batch3）
===================
拆自 api/main.py 的"回测"段（Phase 4.2），含 5 个端点：
- POST /backtest/run
- GET  /backtest/runs
- GET  /backtest/runs/{run_id}
- GET  /backtest/runs/{run_id}/trades
- GET  /backtest/{job_id}

设计依据（保持与 main.py 完全一致）：
- 0006_数据模型与界面重构设计.md §6.3 回测 Tab
- _requirements/data-model-redesign/01-design/02-backend.md §2.4

行为保证：
- 函数体逐行复制自 main.py L151-L313，未改一行。
- imports 集中在模块顶部（main.py 中部分端点用的是函数内 import sqlite3 / json，
  本 router 统一提到模块顶部，效果一致）。

⚠️ 路径顺序问题（重要）：
- FastAPI 路由按声明顺序匹配。`/backtest/run` 是 POST 精确路径，`/backtest/runs` 是 GET 集合。
- 必须先注册 `run`（POST）再注册 `runs`（GET），否则 GET /backtest/runs 会被
  /backtest/runs/{run_id} 拦截。本文件已按此顺序声明。

状态变量说明：
- main.py 原模块级 `backtest_jobs: dict[str, BacktestResult] = {}` 已被本 router 内部实例替代。
- 行为兼容：内存版 backtest_jobs 仅在调用 /backtest/run 期间存在；调用 /backtest/{job_id}
  查不到时回退 DB（与原 main.py 行为一致）。
- P5 收尾会统一抽到 api.state.py 共享。
"""
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from api.helpers.backtest_runner import run_backtest_sync
from api.schemas.backtest import (
    BacktestRequest, BacktestResponse, BacktestResult,
)

# 短期重复实例（与 main.py L127 `backtest_jobs` 等价；P5 收尾会统一抽到 api.state）
backtest_jobs: dict[str, BacktestResult] = {}

router = APIRouter(prefix="/backtest", tags=["backtest"])


# ============================================================
# 必须先注册 /run（POST 精确路径），再注册 /runs（GET 集合）
# ============================================================

@router.post("/run", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest):
    """
    Phase 4.2 改造：持久化到 backtest_runs + sim_trades
    端点 URL 不变，旧内存版 fallback 仍保留
    """
    # 内存版兼容：先建一个占位
    job_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    job = BacktestResult(
        job_id=job_id, status="running",
        symbols=req.symbols, start_date=req.start_date, end_date=req.end_date,
        initial_capital=req.initial_capital, final_capital=0.0, total_return=0.0,
        max_drawdown=0.0, trades=0, sharpe_ratio=None, completed_at=None, error=None
    )
    backtest_jobs[job_id] = job

    elapsed = 0.0
    final_status = "completed"
    try:
        # Phase 4.2: 调持久化版 run_backtest_sync（落库 + 写 sim_trades）
        result = run_backtest_sync(req)
        elapsed = result.get("elapsed", 0.0)
        final_status = result.get("status", "completed")
        # 内存版同步状态
        if final_status == "completed":
            job.status = "completed"
            job.final_capital = result.get("final_capital", 0.0)
            job.total_return = result.get("total_return", 0.0)
            job.max_drawdown = result.get("max_drawdown", 0.0)
            job.trades = result.get("trades", 0)
            job.sharpe_ratio = result.get("sharpe_ratio")
            # job_id 改用 run_id（便于查 DB）
            run_id = result.get("run_id", job_id)
            backtest_jobs.pop(job_id, None)
            backtest_jobs[run_id] = job
            job_id = run_id
        else:
            job.status = "failed"
            job.error = result.get("error", "unknown")
    except Exception as e:
        final_status = "failed"
        job.status = "failed"
        job.error = str(e)

    job.completed_at = datetime.now().isoformat()
    return BacktestResponse(
        job_id=job_id, status=final_status, submitted_at=job.completed_at, elapsed=elapsed
    )


# ============================================================
# Phase 4.1: 回测持久化（DB 存储）— 必须在 /backtest/{job_id} 之前注册,否则会被拦截
# ============================================================
@router.get("/runs")
async def list_backtest_runs(strategy_id: Optional[str] = None,
                              symbol: Optional[str] = None,
                              status: Optional[str] = None,
                              limit: int = 50):
    """
    查历史回测列表（多条件过滤）
    GET /backtest/runs?strategy_id=turtle_v1
    """
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    conditions = []
    params = []
    if strategy_id:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)
    cur.execute(f"""
        SELECT run_id, strategy_id, symbol, start_date, end_date, status,
               initial_capital, final_capital, total_return_pct, max_drawdown_pct,
               total_trades, created_at, completed_at
        FROM backtest_runs
        WHERE {where}
        ORDER BY created_at DESC LIMIT ?
    """, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"count": len(rows), "runs": rows}


@router.get("/runs/{run_id}")
async def get_backtest_run_detail(run_id: str):
    """查历史回测详情"""
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM backtest_runs WHERE run_id = ?", (run_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"回测 {run_id} 不存在")
    data = dict(row)
    try:
        data['params'] = json.loads(data.pop('params_json') or '{}')
    except Exception:
        data['params'] = {}
    try:
        data['result_metrics'] = json.loads(data.pop('result_metrics_json') or '{}')
    except Exception:
        data['result_metrics'] = {}
    return data


@router.get("/runs/{run_id}/trades")
async def get_backtest_run_trades(run_id: str, limit: int = 100):
    """查历史回测的成交列表"""
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT trade_id, order_id, account_id, session_id, symbol, contract_code,
               direction, filled_price, filled_quantity, commission, platform_name, filled_at
        FROM sim_trades
        WHERE account_id LIKE 'backtest_%' OR session_id IN (SELECT session_id FROM trade_sessions WHERE strategy_id = (SELECT strategy_id FROM backtest_runs WHERE run_id = ?))
        ORDER BY filled_at DESC LIMIT ?
    """, (run_id, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"run_id": run_id, "count": len(rows), "trades": rows}



@router.get("/{job_id}")
async def get_backtest(job_id: str):
    """Phase 4.2 改造：优先查 DB（backtest_runs），fallback 到内存版"""
    # 1. 先查内存版（兼容）
    if job_id in backtest_jobs:
        return backtest_jobs[job_id]
    # 2. 查 DB
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM backtest_runs WHERE run_id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"回测 {job_id} 不存在")
    data = dict(row)
    try:
        data['params'] = json.loads(data.pop('params_json') or '{}')
    except Exception:
        data['params'] = {}
    try:
        data['result_metrics'] = json.loads(data.pop('result_metrics_json') or '{}')
    except Exception:
        data['result_metrics'] = {}
    return data
