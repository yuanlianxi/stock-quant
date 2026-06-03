"""多账户隔离单测（Phase 6.1）"""
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
# 多账户独立
# ============================================================
class TestMultiAccount:
    def test_two_accounts_independent_sessions(
        self, temp_db, sim_default, sim_user1, turtle_strategy
    ):
        """两个账户各自建仓不冲突"""
        sid1 = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        sid2 = open_session(
            sim_user1, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        assert sid1 != sid2

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT account_id, COUNT(*) as cnt FROM trade_sessions "
            "GROUP BY account_id ORDER BY account_id"
        )
        rows = cur.fetchall()
        conn.close()

        account_ids = [r["account_id"] for r in rows]
        assert sim_default in account_ids
        assert sim_user1 in account_ids

    def test_close_one_account_does_not_affect_other(
        self, temp_db, sim_default, sim_user1, turtle_strategy
    ):
        """平一个账户不影响另一个"""
        sid1 = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        sid2 = open_session(
            sim_user1, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )

        close_session(sid1, 18000.0, "close sim_default")

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT status FROM trade_sessions WHERE session_id = ?", (sid1,))
        s1 = cur.fetchone()["status"]
        cur.execute("SELECT status FROM trade_sessions WHERE session_id = ?", (sid2,))
        s2 = cur.fetchone()["status"]
        conn.close()

        assert s1 == "closed"
        assert s2 == "open"

    def test_add_unit_one_account_no_effect(
        self, temp_db, sim_default, sim_user1, turtle_strategy
    ):
        """一个账户加仓不影响另一个"""
        sid1 = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        sid2 = open_session(
            sim_user1, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )

        add_unit(sid1, 17600.0)
        add_unit(sid1, 17700.0)

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT current_units FROM trade_sessions WHERE session_id = ?", (sid1,))
        s1_units = cur.fetchone()["current_units"]
        cur.execute("SELECT current_units FROM trade_sessions WHERE session_id = ?", (sid2,))
        s2_units = cur.fetchone()["current_units"]
        conn.close()

        assert s1_units == 3
        assert s2_units == 1

    def test_three_accounts_orders_independent(
        self, temp_db, sim_default, sim_user1, sim_user2
    ):
        """三账户订单独立（各账户本次至少 1 单）"""
        oid1 = submit_order(sim_default, "AG", "ag2607", "buy", "market", 1)
        oid2 = submit_order(sim_user1, "AG", "ag2607", "buy", "market", 1)
        oid3 = submit_order(sim_user2, "AG", "ag2607", "buy", "market", 1)

        assert oid1 != oid2 != oid3
        assert oid1 != oid3

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT account_id, COUNT(*) as cnt FROM sim_orders WHERE order_id IN (?, ?, ?) GROUP BY account_id",
            (oid1, oid2, oid3),
        )
        rows = cur.fetchall()
        conn.close()
        # 3 个订单分别在 3 个账户
        account_counts = {r["account_id"]: r["cnt"] for r in rows}
        assert account_counts[sim_default] == 1
        assert account_counts[sim_user1] == 1
        assert account_counts[sim_user2] == 1

    def test_close_unit_one_account_no_effect(
        self, temp_db, sim_default, sim_user1, turtle_strategy
    ):
        """一个账户 close_unit 不影响另一个账户的 unit"""
        sid1 = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        sid2 = open_session(
            sim_user1, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )

        # 取 sid1 的 unit1
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT unit_id FROM position_units WHERE session_id = ? AND unit_index = 1",
            (sid1,),
        )
        unit1 = cur.fetchone()["unit_id"]
        conn.close()

        close_unit(unit1, 17800.0, "partial close")

        # sid1 current_units 应 -1
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT current_units FROM trade_sessions WHERE session_id = ?", (sid1,)
        )
        s1_units = cur.fetchone()["current_units"]
        cur.execute(
            "SELECT current_units FROM trade_sessions WHERE session_id = ?", (sid2,)
        )
        s2_units = cur.fetchone()["current_units"]
        conn.close()
        assert s1_units == 0
        assert s2_units == 1
