"""撮合引擎单测（Phase 6.1）"""
import sqlite3

import pytest

from api.services.sim_engine import (
    add_unit,
    close_session,
    close_unit,
    open_session,
    submit_order,
)


# ============================================================
# submit_order
# ============================================================
class TestSubmitOrder:
    def test_market_order_immediate_fill(self, temp_db, sim_default):
        """市价单即时成交"""
        oid = submit_order(sim_default, "AG", "ag2607", "buy", "market", 1)
        assert oid is not None

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT status, filled_quantity FROM sim_orders WHERE order_id = ?", (oid,)
        )
        row = cur.fetchone()
        conn.close()
        assert row["status"] == "filled"
        assert row["filled_quantity"] == 1

    def test_limit_order_pending(self, temp_db, sim_default):
        """限价单 pending"""
        oid = submit_order(
            sim_default, "AG", "ag2607", "buy", "limit", 1, price=17500.0
        )
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT status, filled_quantity FROM sim_orders WHERE order_id = ?", (oid,)
        )
        row = cur.fetchone()
        conn.close()
        assert row["status"] == "pending"
        assert row["filled_quantity"] == 0

    def test_nonexist_account_raises(self, temp_db):
        """不存在账户应报错"""
        with pytest.raises(ValueError, match="账户.*不存在"):
            submit_order("non_exist_account_xyz", "AG", "ag2607", "buy", "market", 1)


# ============================================================
# open_session
# ============================================================
class TestOpenSession:
    def test_open_long_session(self, temp_db, sim_default, turtle_strategy):
        """建多仓 session"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )
        assert sid is not None

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT status, current_units, total_units, direction FROM trade_sessions WHERE session_id = ?",
            (sid,),
        )
        row = cur.fetchone()
        conn.close()
        assert row["status"] == "open"
        assert row["current_units"] == 1
        assert row["total_units"] == 1
        assert row["direction"] == "long"

    def test_short_session(self, temp_db, sim_default, turtle_strategy):
        """建空仓 session"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "short",
            17500.0,
            n_value=200.0,
        )
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT direction, status FROM trade_sessions WHERE session_id = ?", (sid,)
        )
        row = cur.fetchone()
        conn.close()
        assert row["direction"] == "short"
        assert row["status"] == "open"

    def test_nonexist_strategy_raises(self, temp_db, sim_default):
        """不存在 strategy_id 应 FK 报错"""
        with pytest.raises(Exception):  # sqlite3.IntegrityError
            open_session(
                sim_default,
                "non_exist_strategy_xyz",
                "AG",
                "ag2607",
                "long",
                17500.0,
            )


# ============================================================
# add_unit
# ============================================================
class TestAddUnit:
    def test_add_unit_1_to_2_to_3(self, temp_db, sim_default, turtle_strategy):
        """加仓 1→2→3"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )

        add_unit(sid, 17600.0)
        add_unit(sid, 17700.0)

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT current_units, total_units FROM trade_sessions WHERE session_id = ?",
            (sid,),
        )
        row = cur.fetchone()
        conn.close()
        assert row["current_units"] == 3
        assert row["total_units"] == 3

    def test_max_4_units_raises(self, temp_db, sim_default, turtle_strategy):
        """超过 4 units 应报错"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )
        add_unit(sid, 17600.0)  # 2
        add_unit(sid, 17700.0)  # 3
        add_unit(sid, 17800.0)  # 4
        with pytest.raises(ValueError, match="已达最大 unit"):
            add_unit(sid, 17900.0)  # 5 应报错


# ============================================================
# close_unit
# ============================================================
class TestCloseUnit:
    def test_close_one_unit(self, temp_db, sim_default, turtle_strategy):
        """减仓单个 unit"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT unit_id FROM position_units WHERE session_id = ? AND unit_index = 1",
            (sid,),
        )
        unit_id = cur.fetchone()["unit_id"]
        conn.close()

        close_unit(unit_id, 17800.0, "test")

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT status, close_price FROM position_units WHERE unit_id = ?",
            (unit_id,),
        )
        row = cur.fetchone()
        conn.close()
        assert row["status"] == "closed"
        assert row["close_price"] == 17800.0


# ============================================================
# close_session
# ============================================================
class TestCloseSession:
    def test_close_session_all_units(self, temp_db, sim_default, turtle_strategy):
        """全部平仓 + 关闭所有 units"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )
        add_unit(sid, 17600.0)
        add_unit(sid, 17700.0)
        add_unit(sid, 17800.0)

        close_session(sid, 17900.0, "test")

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT status, current_units FROM trade_sessions WHERE session_id = ?",
            (sid,),
        )
        sess = cur.fetchone()
        cur.execute(
            "SELECT COUNT(*) as cnt FROM position_units WHERE session_id = ? AND status = 'open'",
            (sid,),
        )
        units_open = cur.fetchone()["cnt"]
        conn.close()
        assert sess["status"] == "closed"
        assert sess["current_units"] == 0
        assert units_open == 0

    def test_close_already_closed_raises(self, temp_db, sim_default, turtle_strategy):
        """已关闭的 session 再关应报错"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )
        close_session(sid, 18000.0, "first")
        with pytest.raises(ValueError):
            close_session(sid, 18000.0, "second")

    def test_nonexist_session_raises(self, temp_db):
        """不存在的 session 应报错"""
        with pytest.raises(ValueError, match="session.*不存在"):
            close_session("non_exist_session_xyz", 18000.0, "test")
