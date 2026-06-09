"""缓存同步核心 SSOT（sq-0009-p2）
====================================
设计原则：
- 调度（APScheduler，P5）和手动（API，P3/P4）共享同一份函数入口
- 入口处统一写 cache_sync_log（status='running'），结束时更新 status
- 单一职责：sync_* 只管拉数据写库，不检测信号
- 9 函数对外暴露，2 内部（_log_start / _log_end）

依赖：
- data.data_loader 的 sync_all_minute_data / backfill_daily_history /
  backfill_min_history / incremental_update_daily / fetch_minute_data /
  ALL_PRODUCTS
"""
from datetime import datetime
from typing import Optional

from data.data_loader import (
    get_conn,
    incremental_update_daily,
    fetch_minute_data,
    sync_all_minute_data,
    backfill_daily_history,
    backfill_min_history,
    ALL_PRODUCTS,
)


# ============================================================
# 内部：日志包装层（sq-0009-p2 内部，所有 sync_* 入口都用）
# ============================================================

def _log_start(symbol: str, period: str, sync_type: str, trigger_source: str,
              start_date: Optional[str] = None, end_date: Optional[str] = None) -> int:
    """写一条 status='running' 日志，返回 log_id

    Args:
        symbol: 'AG' / 'AU' / 'ALL'
        period: 'daily' / '5min' / '15min' / '30min' / '60min'
        sync_type: 'manual' / 'backfill'（'scheduled' 由 P5 包装层写入）
        trigger_source: 'api:POST /cache/sync/daily' / 'webapp:manual' / 'cron:minute_sync_5min'
        start_date: 'YYYY-MM-DD' 用户选择范围（仅记录，commit 9 sq-0009-round-4）
        end_date:   'YYYY-MM-DD' 用户选择范围
    """
    start_at = datetime.now().isoformat()
    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO cache_sync_log
            (symbol, period, sync_type, status, start_at, trigger_source, start_date, end_date)
            VALUES (?, ?, ?, 'running', ?, ?, ?, ?)
        """, (symbol, period, sync_type, start_at, trigger_source, start_date, end_date))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _log_end(log_id: int, status: str, rows_existing: int = 0,
             rows_new: int = 0, rows_total: int = 0, error_message: Optional[str] = None):
    """更新日志 status / end_at / rows_*

    即使主任务逻辑失败（status='failed'）也要写入 end_at + error_message，
    保证日志表不会有"僵尸 running 行"。
    """
    end_at = datetime.now().isoformat()
    conn = get_conn()
    try:
        conn.execute("""
            UPDATE cache_sync_log
            SET status=?, end_at=?, rows_existing=?, rows_new=?, rows_total=?, error_message=?
            WHERE id=?
        """, (status, end_at, rows_existing, rows_new, rows_total, error_message, log_id))
        conn.commit()
    finally:
        conn.close()


# ============================================================
# 同步函数（4 个）
# ============================================================

def sync_daily_one(symbol: str, trigger_source: str) -> dict:
    """单品种日线同步（增量）

    包装 data.data_loader.incremental_update_daily
    """
    sym = symbol.upper()
    log_id = _log_start(sym, 'daily', 'manual', trigger_source)
    try:
        df = incremental_update_daily(sym)
        rows_new = len(df)
        _log_end(log_id, 'success', rows_new=rows_new, rows_total=rows_new)
        return {
            "symbol": sym,
            "period": "daily",
            "status": "success",
            "rows_new": rows_new,
        }
    except Exception as e:
        _log_end(log_id, 'failed', error_message=str(e))
        raise


def sync_daily_all(trigger_source: str) -> dict:
    """全 38 品种日线同步（增量）

    Returns:
        {
            "status": "success" / "partial" / "failed",
            "rows_new": int,
            "success_symbols": [("AG", 1), ...],
            "fail_symbols": [("AG", "error msg"), ...]
        }
    """
    log_id = _log_start('ALL', 'daily', 'manual', trigger_source)
    success_list = []
    fail_list = []
    total_new = 0
    try:
        for sym in ALL_PRODUCTS:
            try:
                df = incremental_update_daily(sym)
                success_list.append((sym, len(df)))
                total_new += len(df)
            except Exception as e:
                fail_list.append((sym, str(e)))

        if not fail_list:
            status = 'success'
        elif success_list:
            status = 'partial'
        else:
            status = 'failed'

        _log_end(log_id, status, rows_new=total_new, rows_total=total_new)
        return {
            "status": status,
            "rows_new": total_new,
            "success_count": len(success_list),
            "fail_count": len(fail_list),
            "success_symbols": success_list,
            "fail_symbols": fail_list,
        }
    except Exception as e:
        _log_end(log_id, 'failed', error_message=str(e))
        raise


def sync_minute_one(symbol: str, period: str, trigger_source: str) -> dict:
    """单品种分时同步

    Args:
        period: '5min' / '15min' / '30min' / '60min'
    """
    if period not in ('1min', '5min', '15min', '30min', '60min'):
        raise ValueError(f"invalid period: {period}")
    sym = symbol.upper()
    log_id = _log_start(sym, period, 'manual', trigger_source)
    try:
        df = fetch_minute_data(sym, period=period)
        rows_new = len(df)
        _log_end(log_id, 'success', rows_new=rows_new, rows_total=rows_new)
        return {
            "symbol": sym,
            "period": period,
            "status": "success",
            "rows_new": rows_new,
        }
    except Exception as e:
        _log_end(log_id, 'failed', error_message=str(e))
        raise


def sync_minute_all(period: str, trigger_source: str) -> dict:
    """全 38 品种分时同步

    包装 data.data_loader.sync_all_minute_data
    """
    if period not in ('1min', '5min', '15min', '30min', '60min'):
        raise ValueError(f"invalid period: {period}")
    log_id = _log_start('ALL', period, 'manual', trigger_source)
    try:
        result = sync_all_minute_data(period=period, progress=False)
        rows_new = result.get("total_new", 0)
        success_n = len(result.get("success", []))
        fail_n = len(result.get("fail", []))
        if fail_n == 0:
            status = 'success'
        elif success_n > 0:
            status = 'partial'
        else:
            status = 'failed'
        _log_end(log_id, status, rows_new=rows_new, rows_total=rows_new)
        return {
            "status": status,
            "period": period,
            "rows_new": rows_new,
            "success_count": success_n,
            "fail_count": fail_n,
            "raw": result,
        }
    except Exception as e:
        _log_end(log_id, 'failed', error_message=str(e))
        raise


# ============================================================
# 回填函数（2 个）
# ============================================================

def backfill_daily(symbol: str, years: int, trigger_source: str,
               start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """回填日线历史

    Args:
        years: 历史年数（默认 3）
        start_date/end_date: 用户选择的时间范围（仅记录，commit 9 sq-0009-round-4）
    """
    sym = symbol.upper()
    log_id = _log_start(sym, 'daily', 'backfill', trigger_source, start_date, end_date)
    try:
        n = backfill_daily_history(sym, years=years)
        _log_end(log_id, 'success', rows_new=n, rows_total=n)
        return {
            "symbol": sym,
            "period": "daily",
            "years": years,
            "start_date": start_date,
            "end_date": end_date,
            "rows_new": n,
            "status": "success",
        }
    except Exception as e:
        _log_end(log_id, 'failed', error_message=str(e))
        raise


def backfill_minute(symbol: str, period: str, days: int, trigger_source: str,
                start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """回填分时历史

    Args:
        days: 历史天数（默认 7）
        start_date/end_date: 用户选择的时间范围（仅记录，commit 9 sq-0009-round-4）
    """
    if period not in ('1min', '5min', '15min', '30min', '60min'):
        raise ValueError(f"invalid period: {period}")
    sym = symbol.upper()
    log_id = _log_start(sym, period, 'backfill', trigger_source, start_date, end_date)
    try:
        n = backfill_min_history(sym, days=days, period=period)
        _log_end(log_id, 'success', rows_new=n, rows_total=n)
        return {
            "symbol": sym,
            "period": period,
            "days": days,
            "start_date": start_date,
            "end_date": end_date,
            "rows_new": n,
            "status": "success",
        }
    except Exception as e:
        _log_end(log_id, 'failed', error_message=str(e))
        raise


# ============================================================
# 查询函数（3 个）
# ============================================================

# 状态判定阈值（按 latest 与 now 的距离）
_COVERAGE_THRESHOLDS = {
    'daily':   {'fresh_sec': 1 * 86400,  'stale_sec': 3 * 86400},
    '5min':    {'fresh_sec': 30 * 60,    'stale_sec': 2 * 3600},
    '15min':   {'fresh_sec': 30 * 60,    'stale_sec': 2 * 3600},
    '30min':   {'fresh_sec': 1 * 3600,   'stale_sec': 4 * 3600},
    '60min':   {'fresh_sec': 1 * 3600,   'stale_sec': 4 * 3600},
}

# 数据源窗口（v1.7+sq-0009-round-3 commit 5 新增）
# 5/15/30/60min 受 akshare 限制（新浪期货页只展示最近 5-10 天）
# daily 历史可拉 3+ 年
SOURCE_WINDOW_DAYS = {
    'daily':   1095,    # 3 年
    '5min':    10,      # 新浪期货页只展示 ~10 天
    '15min':   10,
    '30min':   10,
    '60min':   10,
}


def get_coverage() -> dict:
    """按品种 × 周期覆盖率（38 品种 × 5 周期矩阵）

    状态判定阈值（按 latest 与 now 的距离）：
    - daily:    ≤ 1 天 fresh,  ≤ 3 天 stale, > 3 天 missing
    - 5/15min:  ≤ 30 分钟 fresh, ≤ 2 小时 stale, > 2 小时 missing
    - 30/60min: ≤ 1 小时 fresh,  ≤ 4 小时 stale, > 4 小时 missing

    Returns:
        {
          "symbols": ["AG", "AU", ...],
          "periods": ["daily", "5min", ...],
          "source_window_days": {"daily": 1095, "5min": 10, ...},  # sq-0009-round-3 commit 5
          "matrix": {
            "AG": {
              "daily": {"latest": "2026-06-04", "status": "fresh"},
              "5min":  {"latest": None,         "status": "missing"},
              ...
            },
            ...
          },
          "summary": {
            "total_symbols": 38, "total_cells": 190,
            "fresh_cells": 78, "stale_cells": 12, "missing_cells": 100
          }
        }
    """
    conn = get_conn()
    try:
        # 1. 查 futures_daily 各品种最新日期
        daily_latest = {
            r[0]: r[1] for r in conn.execute(
                "SELECT symbol, MAX(date) FROM futures_daily GROUP BY symbol"
            ).fetchall()
        }
        # 2. 查 futures_min 各品种 × 周期最新时间
        min_latest = {}
        for r in conn.execute(
            "SELECT symbol, period, MAX(datetime) FROM futures_min GROUP BY symbol, period"
        ).fetchall():
            min_latest.setdefault(r[0], {})[r[1]] = r[2]

        # 3. 算各 cell 状态
        now = datetime.now()
        periods = ['daily', '5min', '15min', '30min', '60min']
        matrix = {}
        fresh_cells = stale_cells = missing_cells = 0

        for sym in ALL_PRODUCTS:
            matrix[sym] = {}
            for p in periods:
                if p == 'daily':
                    latest = daily_latest.get(sym)
                else:
                    latest = min_latest.get(sym, {}).get(p)

                if not latest:
                    status = 'missing'
                else:
                    try:
                        # 兼容 'YYYY-MM-DD' 和 'YYYY-MM-DD HH:MM:SS'
                        latest_clean = str(latest).replace(' ', 'T')
                        dt = datetime.fromisoformat(latest_clean)
                        delta_sec = (now - dt).total_seconds()
                        th = _COVERAGE_THRESHOLDS[p]
                        if delta_sec <= th['fresh_sec']:
                            status = 'fresh'
                        elif delta_sec <= th['stale_sec']:
                            status = 'stale'
                        else:
                            status = 'missing'
                    except Exception:
                        status = 'missing'

                if status == 'fresh':
                    fresh_cells += 1
                elif status == 'stale':
                    stale_cells += 1
                else:
                    missing_cells += 1

                matrix[sym][p] = {
                    "latest": latest,
                    "status": status,
                }

        return {
            "symbols": list(ALL_PRODUCTS),
            "periods": periods,
            "source_window_days": SOURCE_WINDOW_DAYS,  # sq-0009-round-3 commit 5
            "matrix": matrix,
            "summary": {
                "total_symbols": len(ALL_PRODUCTS),
                "total_cells": len(ALL_PRODUCTS) * len(periods),
                "fresh_cells": fresh_cells,
                "stale_cells": stale_cells,
                "missing_cells": missing_cells,
            }
        }
    finally:
        conn.close()


def get_sync_logs(
    symbol: Optional[str] = None,
    sync_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """分页查询拉取记录

    Args:
        symbol: 品种过滤（None = 全部）
        sync_type: 'manual' / 'backfill' / 'scheduled'（None = 全部）
        status: 'running' / 'success' / 'failed' / 'partial'（None = 全部）
        page: 1-based
        page_size: 默认 20
    """
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 200:
        page_size = 20

    conn = get_conn()
    try:
        conditions = []
        params = []
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol.upper())
        if sync_type:
            conditions.append("sync_type = ?")
            params.append(sync_type)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # 计数
        count_query = f"SELECT COUNT(*) FROM cache_sync_log {where}"
        total = conn.execute(count_query, params).fetchone()[0]

        # 分页
        offset = (page - 1) * page_size
        list_query = f"""
            SELECT id, symbol, period, sync_type, status, start_at, end_at,
                   rows_existing, rows_new, rows_total, error_message, trigger_source,
                   created_at
            FROM cache_sync_log {where}
            ORDER BY start_at DESC LIMIT ? OFFSET ?
        """
        rows = conn.execute(list_query, params + [page_size, offset]).fetchall()
        cols = ["id", "symbol", "period", "sync_type", "status", "start_at", "end_at",
                "rows_existing", "rows_new", "rows_total", "error_message", "trigger_source",
                "created_at"]
        items = [dict(zip(cols, r)) for r in rows]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }
    finally:
        conn.close()


def get_schedule_state() -> list[dict]:
    """查询所有调度任务状态

    Returns:
        [
            {
              "task_name": "daily_sync",
              "last_run_at": "2026-06-07T17:00:01",
              "next_run_at": None,  # P5 接入 APScheduler 后写入
              "last_status": "success",
              "run_count": 1,
              "fail_count": 0,
              "enabled": 1,
              "updated_at": "..."
            },
            ...
        ]
    """
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT task_name, last_run_at, next_run_at, last_status,
                   run_count, fail_count, enabled, updated_at
            FROM cache_schedule_state ORDER BY task_name
        """).fetchall()
        cols = ["task_name", "last_run_at", "next_run_at", "last_status",
                "run_count", "fail_count", "enabled", "updated_at"]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()


def toggle_schedule(task_name: str, enabled: bool) -> bool:
    """启停调度任务（更新 cache_schedule_state.enabled）

    APScheduler 同步留给 P5（api/scheduler.py 启动时读这张表注册 cron）。
    本函数 v1 只更新表，scheduler 启停联动在 P5 接入。

    Returns:
        True if 更新成功（task_name 存在）
    """
    conn = get_conn()
    try:
        updated_at = datetime.now().isoformat()
        cur = conn.execute("""
            UPDATE cache_schedule_state
            SET enabled=?, updated_at=?
            WHERE task_name=?
        """, (1 if enabled else 0, updated_at, task_name))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def update_schedule_after_run(task_name: str, status: str):
    """P5 包装层用：调度任务执行后更新 cache_schedule_state

    Args:
        task_name: 'daily_sync' / 'minute_sync_5min'
        status: 'success' / 'failed'
    """
    conn = get_conn()
    try:
        last_run_at = datetime.now().isoformat()
        if status == 'success':
            conn.execute("""
                UPDATE cache_schedule_state
                SET last_run_at=?, last_status=?, run_count=run_count+1, updated_at=?
                WHERE task_name=?
            """, (last_run_at, status, last_run_at, task_name))
        else:
            conn.execute("""
                UPDATE cache_schedule_state
                SET last_run_at=?, last_status=?, fail_count=fail_count+1, updated_at=?
                WHERE task_name=?
            """, (last_run_at, status, last_run_at, task_name))
        conn.commit()
    finally:
        conn.close()
