"""海龟交易过程日志单测（Phase 6.1）"""
import pytest

from api.services.sim_engine import open_session
from strategies.trade_process_logger import (
    EVT_ADD_FILLED,
    EVT_ADD_SIGNAL,
    EVT_CHECK_EXIT,
    EVT_ENTRY_FILLED,
    EVT_ENTRY_SIGNAL,
    EVT_STOP_LOSS_CHECK,
    EVT_STOP_LOSS_TRIGGERED,
    EVT_UNIT_CLOSED,
    get_trade_process_summary,
    log_turtle_event,
)


# ============================================================
# log_turtle_event
# ============================================================
class TestLogTurtleEvent:
    def test_log_entry_signal(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_turtle_event(
            session_id=sid,
            account_id=sim_default,
            event_type=EVT_ENTRY_SIGNAL,
            bar_time="2026-06-03T10:00:00",
            signal_type="entry_long",
            signal_price=17500.0,
            n_value=200.0,
        )
        assert eid > 0

    def test_log_entry_filled(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_turtle_event(
            session_id=sid,
            account_id=sim_default,
            event_type=EVT_ENTRY_FILLED,
            bar_time="2026-06-03T10:00:00",
            signal_type="entry_long",
            signal_price=17500.0,
            exec_status="filled",
            exec_price=17500.0,
            exec_hand_count=1,
        )
        assert eid > 0

    def test_log_add_signal(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_turtle_event(
            session_id=sid,
            account_id=sim_default,
            event_type=EVT_ADD_SIGNAL,
            bar_time="2026-06-03T11:00:00",
            signal_type="add_long",
            signal_price=17600.0,
            n_value=200.0,
        )
        assert eid > 0

    def test_log_add_filled(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_turtle_event(
            session_id=sid,
            account_id=sim_default,
            event_type=EVT_ADD_FILLED,
            bar_time="2026-06-03T11:00:00",
            signal_type="add_long",
            signal_price=17600.0,
            exec_status="filled",
            exec_price=17600.0,
            exec_hand_count=1,
        )
        assert eid > 0

    def test_log_stop_loss_check(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_turtle_event(
            session_id=sid,
            account_id=sim_default,
            event_type=EVT_STOP_LOSS_CHECK,
            bar_time="2026-06-03T12:00:00",
            signal_type="stop_loss_check",
            decision_reason="check stop loss",
        )
        assert eid > 0

    def test_log_check_exit(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_turtle_event(
            session_id=sid,
            account_id=sim_default,
            event_type=EVT_CHECK_EXIT,
            bar_time="2026-06-03T13:00:00",
            signal_type="check_exit",
        )
        assert eid > 0

    def test_log_stop_loss_triggered(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_turtle_event(
            session_id=sid,
            account_id=sim_default,
            event_type=EVT_STOP_LOSS_TRIGGERED,
            bar_time="2026-06-03T14:00:00",
            signal_type="stop_loss",
            exec_status="closed",
            exec_price=17000.0,
        )
        assert eid > 0

    def test_log_unit_closed(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_turtle_event(
            session_id=sid,
            account_id=sim_default,
            event_type=EVT_UNIT_CLOSED,
            bar_time="2026-06-03T15:00:00",
            signal_type="manual",
            exec_status="closed",
            exec_price=17800.0,
            exec_hand_count=1,
        )
        assert eid > 0

    def test_invalid_event_type_raises(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        with pytest.raises(ValueError, match="Invalid event_type"):
            log_turtle_event(
                session_id=sid,
                account_id=sim_default,
                event_type="bogus_event",
                bar_time="2026-06-03T16:00:00",
            )


# ============================================================
# get_trade_process_summary
# ============================================================
class TestSummary:
    def test_get_summary(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        # 内部已经写了 entry_signal + entry_filled
        summary = get_trade_process_summary(sid)
        assert isinstance(summary, dict)
        # open_session 内部 + 我们直接调用，至少各 1
        assert summary.get(EVT_ENTRY_SIGNAL, 0) >= 1
        assert summary.get(EVT_ENTRY_FILLED, 0) >= 1
