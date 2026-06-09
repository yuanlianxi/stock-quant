"""Pydantic schemas for cache 域（sq-0009-p4）

6 端点对应 6+ schemas：
- GET /cache/coverage          → CacheCoverageResponse
- GET /cache/sync/logs         → SyncLogListResponse / SyncLogListItem
- GET /cache/sync/logs/{id}    → SyncLogDetail
- GET /cache/schedule          → ScheduleStateListResponse / ScheduleStateItem
- POST /cache/schedule/.../toggle → ScheduleToggleRequest / ScheduleToggleResponse
- POST /cache/backfill         → BackfillRequest / BackfillResponse
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============================================================
# /cache/coverage
# ============================================================

class CoverageCell(BaseModel):
    """38 品种 × 5 周期矩阵中一个单元"""
    latest: Optional[str] = None         # '2026-06-07' 或 '2026-06-07 17:00:00'
    status: str = Field(..., description="fresh / stale / missing")


class CacheCoverageResponse(BaseModel):
    """GET /cache/coverage 响应"""
    symbols: List[str] = Field(..., description="33 品种代码列表")
    periods: List[str] = Field(..., description="5 周期列表（daily/5min/15min/30min/60min）")
    matrix: Dict[str, Dict[str, CoverageCell]] = Field(
        ..., description="matrix[symbol][period] = CoverageCell"
    )
    summary: Dict[str, int] = Field(
        ..., description="total_symbols / total_cells / fresh_cells / stale_cells / missing_cells"
    )


# ============================================================
# /cache/sync/logs
# ============================================================

class SyncLogListItem(BaseModel):
    """拉取记录单条（列表项）"""
    id: int
    symbol: str
    period: str
    sync_type: str                       # manual / backfill / scheduled
    status: str                          # running / success / failed / partial
    start_at: str
    end_at: Optional[str] = None
    rows_existing: int = 0
    rows_new: int = 0
    rows_total: int = 0
    error_message: Optional[str] = None
    trigger_source: Optional[str] = None
    created_at: str


class SyncLogListResponse(BaseModel):
    """GET /cache/sync/logs 分页响应"""
    total: int
    page: int
    page_size: int
    items: List[SyncLogListItem]


class SyncLogDetail(SyncLogListItem):
    """GET /cache/sync/logs/{log_id} 详情（结构同列表项）"""
    pass


# ============================================================
# /cache/schedule
# ============================================================

class ScheduleStateItem(BaseModel):
    """调度任务状态"""
    task_name: str                       # daily_sync / minute_sync_5min
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None    # P5 APScheduler 接入后写入
    last_status: Optional[str] = None    # success / failed
    run_count: int = 0
    fail_count: int = 0
    enabled: int                         # 0 / 1
    updated_at: Optional[str] = None


class ScheduleStateListResponse(BaseModel):
    """GET /cache/schedule 响应"""
    items: List[ScheduleStateItem]


class ScheduleToggleRequest(BaseModel):
    """POST /cache/schedule/{task_name}/toggle 请求体

    注：实际 task_name 在 URL 路径里，请求体只放 enabled
    """
    enabled: bool


class ScheduleToggleResponse(BaseModel):
    """POST /cache/schedule/{task_name}/toggle 响应"""
    task_name: str
    enabled: bool
    updated: bool                        # True if 任务存在并更新成功


# ============================================================
# /cache/backfill
# ============================================================

class BackfillRequest(BaseModel):
    """POST /cache/backfill 请求体"""
    symbol: str                          # 'AG' / 'AU' / ...
    period: str                          # 'daily' / '5min' / '15min' / '30min' / '60min'
    years: Optional[int] = None          # period='daily' 时用
    days: Optional[int] = None           # period='5min/15min/30min/60min' 时用
    start_date: Optional[str] = None     # sq-0009-round-4 commit 9: 用户选择范围
    end_date: Optional[str] = None       # sq-0009-round-4 commit 9: 用户选择范围


class BackfillResponse(BaseModel):
    """POST /cache/backfill 响应"""
    symbol: str
    period: str
    rows_new: int
    status: str                          # success / failed
    years: Optional[int] = None
    days: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
