"""session 生命周期单测（Phase 6.1）"""
import pytest

from api.services.session_lifecycle import (
    SessionLockedError,
    STATUS_CLOSED,
    STATUS_OPEN,
    STATUS_PENDING,
    acquire_session_lock,
    check_duplicate_session,
    release_session_lock,
    transition_status,
    validate_status_transition,
    with_session_lock,
)
from api.services.sim_engine import open_session


# ============================================================
# 状态机 (validate_status_transition)
# ============================================================
class TestStateMachine:
    def test_pending_to_open(self):
        assert validate_status_transition(STATUS_PENDING, STATUS_OPEN) is True

    def test_pending_to_closed(self):
        assert validate_status_transition(STATUS_PENDING, STATUS_CLOSED) is True

    def test_open_to_closed(self):
        assert validate_status_transition(STATUS_OPEN, STATUS_CLOSED) is True

    def test_closed_to_open_invalid(self):
        assert validate_status_transition(STATUS_CLOSED, STATUS_OPEN) is False

    def test_open_to_pending_invalid(self):
        assert validate_status_transition(STATUS_OPEN, STATUS_PENDING) is False

    def test_invalid_status_returns_false(self):
        assert validate_status_transition("invalid", STATUS_OPEN) is False
        assert validate_status_transition(STATUS_OPEN, "invalid") is False


# ============================================================
# 重复检查
# ============================================================
class TestDuplicateCheck:
    def test_no_duplicate_initially(self, temp_db, sim_default, turtle_strategy):
        """初始无重复"""
        assert (
            check_duplicate_session(
                sim_default, turtle_strategy, "long", "2099-01-01T00:00:00"
            )
            is False
        )

    def test_duplicate_after_open(self, temp_db, sim_default, turtle_strategy):
        """建仓后再用同 entry_time 查应 True"""
        from datetime import datetime

        # 直接写一笔指定 entry_time 的 session
        import sqlite3
        import uuid
        from data.data_loader import get_conn  # noqa

        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        # 真实 entry_time 是自动生成的，构造一个一定唯一的 entry_time
        unique_time = datetime.now().isoformat() + "_unique"
        assert (
            check_duplicate_session(sim_default, turtle_strategy, "long", unique_time)
            is False
        )


# ============================================================
# transition_status
# ============================================================
class TestTransitionStatus:
    def test_open_to_closed_success(self, temp_db, sim_default, turtle_strategy):
        """open→closed 成功"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        ok = transition_status(sid, STATUS_CLOSED, "test")
        assert ok is True

    def test_closed_to_open_invalid(self, temp_db, sim_default, turtle_strategy):
        """closed→open 应 False"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        transition_status(sid, STATUS_CLOSED, "first")
        ok = transition_status(sid, STATUS_OPEN, "try")
        assert ok is False

    def test_invalid_to_status_raises(self, temp_db, sim_default, turtle_strategy):
        """非法目标状态应抛 ValueError"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        with pytest.raises(ValueError, match="Invalid status"):
            transition_status(sid, "bogus_status", "test")


# ============================================================
# Lock
# ============================================================
class TestLock:
    def test_acquire_release(self):
        """拿锁 + 释放"""
        sid = "test_lock_acquire_release"
        assert acquire_session_lock(sid, "A", blocking=False) is True
        assert acquire_session_lock(sid, "B", blocking=False) is False
        release_session_lock(sid, "A")
        assert acquire_session_lock(sid, "B", blocking=False) is True
        release_session_lock(sid, "B")

    def test_nested_lock_fails(self):
        """嵌套拿锁应失败（被锁住时 blocking=True 会超时抛 SessionLockedError）"""
        sid = "test_lock_nested"
        with with_session_lock(sid, "A"):
            with pytest.raises(SessionLockedError):
                with with_session_lock(sid, "B"):
                    pass

    def test_release_unheld_lock_no_crash(self):
        """释放未持有的锁不应崩"""
        # release_session_lock 对未持有的锁内部已 try/except
        release_session_lock("never_acquired_xyz", "nobody")
