"""事件日志单测（Phase 6.1）"""
import pytest

from api.services.event_logger import (
    EVENT_ORDER_FILLED,
    EVENT_ORDER_SUBMITTED,
    EVENT_SESSION_CREATED,
    EVENT_STATUS_CHANGED,
    EVENT_UNITS_CHANGED,
    get_session_event_timeline,
    log_batch,
    log_line_overridden,
    log_order_filled,
    log_order_submitted,
    log_session_created,
    log_status_changed,
    log_stop_loss_triggered,
    log_unit_closed,
    log_units_changed,
    query_events,
)
from api.services.sim_engine import open_session


# ============================================================
# log_session_created / log_order_*
# ============================================================
class TestLogSessionEvents:
    def test_log_session_created(self, temp_db, sim_default, turtle_strategy):
        """建仓事件"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_session_created(sid, sim_default, 17500.0, 17500.0, atr=200.0)
        assert eid > 0

    def test_log_order_submitted(self, temp_db, sim_default, turtle_strategy):
        """委托事件"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_order_submitted(sid, sim_default, "order-1", 17500.0, 1, "buy")
        assert eid > 0

    def test_log_order_filled(self, temp_db, sim_default, turtle_strategy):
        """成交事件"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_order_filled(sid, sim_default, "unit-1", "trade-1", 17500.0)
        assert eid > 0


# ============================================================
# log_units_changed / log_status_changed / log_unit_closed
# ============================================================
class TestLogStateEvents:
    def test_log_units_changed(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_units_changed(sid, sim_default, "unit-1", 0, 1, reason="建仓")
        assert eid > 0

    def test_log_status_changed(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_status_changed(sid, sim_default, "open", "closed", "stop_loss")
        assert eid > 0

    def test_log_unit_closed(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_unit_closed(sid, sim_default, "unit-1", 17800.0, "stop_loss", open_price=17500.0)
        assert eid > 0


# ============================================================
# log_line_overridden / log_stop_loss_triggered
# ============================================================
class TestLogLineAndTrigger:
    def test_log_line_overridden(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_line_overridden(sid, sim_default, "stop_loss", 17100.0, 17000.0)
        assert eid > 0

    def test_log_stop_loss_triggered(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        eid = log_stop_loss_triggered(sid, sim_default, 17000.0, 17500.0, "stop_loss")
        assert eid > 0


# ============================================================
# log_batch
# ============================================================
class TestLogBatch:
    def test_log_batch(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        events = [
            {
                "session_id": sid,
                "account_id": sim_default,
                "event_type": EVENT_SESSION_CREATED,
                "context": {"entry_price": 17500.0},
            },
            {
                "session_id": sid,
                "account_id": sim_default,
                "event_type": EVENT_ORDER_SUBMITTED,
                "context": {"order_id": "x", "price": 17500.0, "hand_count": 1, "direction": "buy"},
            },
        ]
        ids = log_batch(events)
        assert len(ids) == 2
        assert all(i > 0 for i in ids)


# ============================================================
# query_events / get_session_event_timeline
# ============================================================
class TestQueryEvents:
    def test_query_events_by_session(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        log_session_created(sid, sim_default, 17500.0, 17500.0, atr=200.0)
        log_order_submitted(sid, sim_default, "o-1", 17500.0, 1, "buy")
        events = query_events(session_id=sid)
        assert len(events) >= 2
        assert all(e["session_id"] == sid for e in events)

    def test_get_session_event_timeline(self, temp_db, sim_default, turtle_strategy):
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        log_session_created(sid, sim_default, 17500.0, 17500.0, atr=200.0)
        log_status_changed(sid, sim_default, "open", "closed", "test")
        timeline = get_session_event_timeline(sid)
        assert isinstance(timeline, list)
        assert len(timeline) >= 2
