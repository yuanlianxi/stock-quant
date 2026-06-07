"""tests/test_cache_sync.py（sq-0009-p7）
===================
覆盖 api.cache_sync 的核心 SSOT 函数：
- 9 函数 import OK（基础冒烟）
- get_coverage() 返回结构含 33 品种 × 5 周期 + summary
- get_sync_logs() 分页返回结构正确
- get_schedule_state() 含 2 任务（daily_sync + minute_sync_5min）
- toggle_schedule() 写库成功
"""
import sys
from pathlib import Path

# 把项目根加入 sys.path（pytest 默认会加，但保险起见）
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.data_loader import init_db, get_conn
from api.cache_sync import (
    sync_daily_one, sync_daily_all, sync_minute_one, sync_minute_all,
    backfill_daily, backfill_minute,
    get_coverage, get_sync_logs, get_schedule_state,
    toggle_schedule, update_schedule_after_run,
    _log_start, _log_end,
)


def setup_module(_):
    """每个 module 跑前初始化 DB（幂等）"""
    init_db()


def test_imports():
    """9 函数 + 2 内部 + 1 update = 12 函数可导入"""
    assert callable(sync_daily_one)
    assert callable(sync_daily_all)
    assert callable(sync_minute_one)
    assert callable(sync_minute_all)
    assert callable(backfill_daily)
    assert callable(backfill_minute)
    assert callable(get_coverage)
    assert callable(get_sync_logs)
    assert callable(get_schedule_state)
    assert callable(toggle_schedule)
    assert callable(update_schedule_after_run)
    assert callable(_log_start)
    assert callable(_log_end)


def test_get_coverage_structure():
    """get_coverage 返回 33 品种 × 5 周期 + summary"""
    cov = get_coverage()
    assert "symbols" in cov
    assert "periods" in cov
    assert "matrix" in cov
    assert "summary" in cov

    # 实际 ALL_PRODUCTS 长度（data_loader.py）
    assert cov["summary"]["total_symbols"] == len(cov["symbols"])
    assert cov["summary"]["total_cells"] == len(cov["symbols"]) * len(cov["periods"])
    assert cov["summary"]["fresh_cells"] + cov["summary"]["stale_cells"] + cov["summary"]["missing_cells"] == cov["summary"]["total_cells"]

    # periods 必须含 daily/5min/15min/30min/60min
    assert set(cov["periods"]) == {"daily", "5min", "15min", "30min", "60min"}

    # 每个 cell 有 latest + status
    sample = cov["symbols"][0]
    for p in cov["periods"]:
        cell = cov["matrix"][sample][p]
        assert "latest" in cell
        assert cell["status"] in ("fresh", "stale", "missing")


def test_get_sync_logs_empty():
    """get_sync_logs 无写入时 total=0"""
    r = get_sync_logs(page=1, page_size=20)
    assert "total" in r
    assert "page" in r
    assert "page_size" in r
    assert "items" in r
    assert r["page"] == 1
    assert r["page_size"] == 20
    assert r["total"] >= 0
    assert isinstance(r["items"], list)


def test_get_sync_logs_pagination():
    """get_sync_logs 分页参数边界"""
    r1 = get_sync_logs(page=1, page_size=5)
    assert r1["page_size"] == 5

    r2 = get_sync_logs(page=0, page_size=999)  # 边界
    assert r2["page"] == 1              # 越界回退
    assert r2["page_size"] == 20        # 越界回退


def test_get_schedule_state_seeded():
    """P1 已 seed 2 任务（daily_sync + minute_sync_5min）"""
    items = get_schedule_state()
    assert len(items) == 2
    names = {s["task_name"] for s in items}
    assert names == {"daily_sync", "minute_sync_5min"}


def test_toggle_schedule():
    """toggle_schedule 写库成功 + 返回 True"""
    # 先开启
    ok1 = toggle_schedule("minute_sync_5min", True)
    assert ok1 is True
    # 再关闭
    ok2 = toggle_schedule("minute_sync_5min", False)
    assert ok2 is True
    # 不存在的任务
    ok3 = toggle_schedule("nonexistent_task", True)
    assert ok3 is False

    # 验证 DB 状态
    conn = get_conn()
    row = conn.execute(
        "SELECT enabled FROM cache_schedule_state WHERE task_name='minute_sync_5min'"
    ).fetchone()
    assert row[0] == 0
    conn.close()


def test_log_start_end():
    """_log_start + _log_end 写日志闭环"""
    log_id = _log_start("TEST_SYM", "daily", "manual", "api:TEST")
    assert log_id > 0

    _log_end(log_id, "success", rows_existing=10, rows_new=5, rows_total=15)

    # 验证
    conn = get_conn()
    row = conn.execute(
        "SELECT status, rows_existing, rows_new, rows_total FROM cache_sync_log WHERE id=?",
        (log_id,)
    ).fetchone()
    conn.close()
    assert row[0] == "success"
    assert row[1] == 10
    assert row[2] == 5
    assert row[3] == 15


def test_log_end_with_error():
    """_log_end 失败状态写 error_message"""
    log_id = _log_start("FAIL_SYM", "5min", "manual", "api:TEST")
    _log_end(log_id, "failed", error_message="connection timeout")

    conn = get_conn()
    row = conn.execute(
        "SELECT status, error_message FROM cache_sync_log WHERE id=?",
        (log_id,)
    ).fetchone()
    conn.close()
    assert row[0] == "failed"
    assert "timeout" in row[1]
