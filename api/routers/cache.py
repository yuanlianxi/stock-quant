"""Cache Router（sq-0008-p4-batch2 + sq-0009-p4）
==================
sq-0008-p4-batch2 拆出 1 端点：GET /cache/status
sq-0009-p4 扩 6 端点：coverage / sync/logs / sync/logs/{id} / schedule / schedule/.../toggle / backfill

合计 7 端点。
"""
from typing import Optional
from fastapi import APIRouter, HTTPException

from data.data_loader import cache_status
from api.cache_sync import (
    get_coverage,
    get_sync_logs,
    get_schedule_state,
    toggle_schedule,
    backfill_daily as cs_backfill_daily,
    backfill_minute as cs_backfill_minute,
)


router = APIRouter(prefix="/cache", tags=["cache"])


# ============================================================
# sq-0008 旧端点（保留）
# ============================================================

@router.get("/status")
async def get_cache_status():
    """缓存状态诊断（sq-0008 旧）"""
    return cache_status()


# ============================================================
# sq-0009-p4 新增：coverage / logs / schedule / backfill
# ============================================================

@router.get("/coverage")
async def get_cache_coverage():
    """38 品种 × 5 周期覆盖率矩阵（sq-0009-p4）

    Returns:
        CacheCoverageResponse
    """
    return get_coverage()


@router.get("/sync/logs")
async def list_sync_logs(
    symbol: Optional[str] = None,
    sync_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """拉取记录分页查询（sq-0009-p4）

    Args:
        symbol: 品种过滤（如 'AG' / 'ALL'）
        sync_type: 'manual' / 'backfill' / 'scheduled'
        status: 'running' / 'success' / 'failed' / 'partial'
        page: 1-based
        page_size: 1-200，默认 20
    """
    return get_sync_logs(
        symbol=symbol,
        sync_type=sync_type,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.get("/sync/logs/{log_id}")
async def get_sync_log_detail(log_id: int):
    """单条拉取记录详情（sq-0009-p4）"""
    result = get_sync_logs(page=1, page_size=1)
    # 简单实现：分页查 1 条再过滤
    conn_result = get_sync_logs(page=1, page_size=200)
    target = next((item for item in conn_result["items"] if item["id"] == log_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"log_id {log_id} not found")
    return target


@router.get("/schedule")
async def list_schedule_state():
    """所有调度任务状态列表（sq-0009-p4）"""
    return {"items": get_schedule_state()}


@router.post("/schedule/{task_name}/toggle")
async def toggle_schedule_task(task_name: str, enabled: bool):
    """启停调度任务（sq-0009-p4 + sq-0009-p5 联动）

    Args:
        task_name: 'daily_sync' / 'minute_sync_5min'
        enabled: True/False
    """
    # 1. 更新数据库
    ok = toggle_schedule(task_name, enabled)
    if not ok:
        raise HTTPException(status_code=404, detail=f"task_name {task_name} not found")
    # 2. 联动 APScheduler
    try:
        from api.scheduler import toggle_task
        toggle_task(task_name, enabled)
    except Exception:
        # scheduler 未启动时（测试场景）静默
        pass
    return {
        "task_name": task_name,
        "enabled": enabled,
        "updated": True,
    }


@router.post("/backfill")
async def trigger_backfill(
    symbol: str,
    period: str,
    years: Optional[int] = None,
    days: Optional[int] = None,
    start_date: Optional[str] = None,   # sq-0009-round-4 commit 9
    end_date: Optional[str] = None,     # sq-0009-round-4 commit 9
):
    """回填历史数据（sq-0009-p4 + sq-0009-round-4 commit 9）

    Args:
        symbol: 品种代码
        period: 'daily' / '5min' / '15min' / '30min' / '60min'
        years: period='daily' 时用（如 3 = 回填 3 年）
        days:  period='5min/15min/30min/60min' 时用（如 30 = 回填 30 天）
        start_date/end_date: 用户选择的时间范围（YYYY-MM-DD），仅记录到 cache_sync_log

    Note: akshare 限制，分钟数据实际只能回填最近 5-10 天
    """
    if period == "daily":
        if years is None:
            years = 3  # 默认 3 年
        result = cs_backfill_daily(symbol, years=years, trigger_source="api:POST /cache/backfill",
                                   start_date=start_date, end_date=end_date)
        return result
    elif period in ("5min", "15min", "30min", "60min"):
        if days is None:
            days = 7   # 默认 7 天
        result = cs_backfill_minute(symbol, period=period, days=days, trigger_source="api:POST /cache/backfill",
                                     start_date=start_date, end_date=end_date)
        return result
    else:
        raise HTTPException(status_code=400, detail=f"invalid period: {period}")
