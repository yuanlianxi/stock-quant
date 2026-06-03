"""
集成测试（Phase 6.2）

端到端测试：信号 → 模拟下单 → 成交 → 持仓 → 价格线更新

覆盖：
1. TestEndToEndFlow - 多/空仓完整流程 + 并发锁
2. TestPriceLineOverrides - 价格线 override 持久化与重算
3. TestTurtleFieldAlignment - 与 0016 通达信字段对齐（v1.3 简化）
4. TestCScheme - v1.5 C 方案（check 类事件存前后 5 根 K 线）
5. TestPerformanceBaseline - 性能基线（100 session 建仓 / 100 调价 / 50 平仓）
"""
import sqlite3
import threading
import time
from datetime import datetime

import pandas as pd
import pytest

from api.services.event_logger import (
    get_session_event_timeline,
    query_events,
)
from api.services.line_calculator import (
    clear_cache,
    compute_lines,
    override_line,
)
from api.services.session_lifecycle import (
    get_session_detail,
    list_sessions,
    with_session_lock,
)
from api.services.sim_engine import (
    add_unit,
    close_session,
    close_unit,
    open_session,
    submit_order,
)
from strategies.trade_process_logger import (
    EVT_ADD_FILLED,
    EVT_ADD_SIGNAL,
    EVT_ENTRY_FILLED,
    EVT_ENTRY_SIGNAL,
    EVT_STOP_LOSS_CHECK,
    log_check_event_with_context,
    log_turtle_event,
    query_trade_process,
)


# ============================================================
# 1. 端到端流程
# ============================================================
class TestEndToEndFlow:
    """端到端：建仓 → 加仓 → 调价 → 减仓 → 全平"""

    def test_full_long_session_flow(self, temp_db, sim_default, turtle_strategy):
        """完整多单流程（4 unit → 调价 → 减仓 1 → 全平）"""
        # 1. 建仓
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

        # 2. 加仓到 4 units
        add_unit(sid, 17600.0)
        add_unit(sid, 17700.0)
        add_unit(sid, 17800.0)

        # 3. 验证持仓（按 session_id 过滤；prod DB 可能有其他 open session）
        sessions = list_sessions(account_id=sim_default, status="open")
        my_session = [s for s in sessions if s["session_id"] == sid]
        assert len(my_session) == 1
        assert my_session[0]["current_units"] == 4

        # 4. 价格线：多单止损 = entry - 2N = 17100；加仓 = entry + 0.5N = 17600
        lines = compute_lines(sid, use_cache=False)
        assert lines["lines"]["stop_loss"] == 17100.0
        assert lines["lines"]["add"] == 17600.0

        # 5. 调价
        result = override_line(sid, "stop_loss", 17000.0)
        assert result["lines"]["stop_loss"] == 17000.0
        assert result["overrides"]["stop_loss"] == 17000.0

        # 6. v1.5 turtle_trade_process 写入（4 个事件类型）
        now_iso = datetime.now().isoformat()
        log_turtle_event(
            sid, sim_default, EVT_ENTRY_SIGNAL, now_iso,
            signal_price=17500.0, decision_reason="e2e entry",
        )
        log_turtle_event(
            sid, sim_default, EVT_ENTRY_FILLED, now_iso,
            signal_price=17500.0, exec_price=17500.0,
            exec_status="filled", exec_hand_count=1,
            decision_reason="e2e filled",
        )
        log_turtle_event(
            sid, sim_default, EVT_ADD_SIGNAL, now_iso,
            signal_price=17600.0, decision_reason="e2e add",
        )
        log_turtle_event(
            sid, sim_default, EVT_ADD_FILLED, now_iso,
            signal_price=17600.0, exec_price=17600.0,
            exec_status="filled", exec_hand_count=1,
            decision_reason="e2e add filled",
        )

        # 验证 4 个事件类型都写入了
        events = query_trade_process(session_id=sid, days=1)
        event_types = {e["event_type"] for e in events}
        assert EVT_ENTRY_SIGNAL in event_types
        assert EVT_ENTRY_FILLED in event_types
        assert EVT_ADD_SIGNAL in event_types
        assert EVT_ADD_FILLED in event_types

        # 7. 减仓 unit 1
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT unit_id FROM position_units WHERE session_id = ? AND unit_index = 1",
            (sid,),
        )
        unit_id = cur.fetchone()["unit_id"]
        conn.close()
        close_unit(unit_id, 18000.0, "e2e test")

        # 8. 全部平仓
        close_session(sid, 18100.0, "e2e close all")

        # 9. 验证最终状态
        detail = get_session_detail(sid)
        assert detail["status"] == "closed"
        assert detail["current_units"] == 0
        assert detail["exit_reason"] == "e2e close all"

        # 10. session_event_log 应含 status_changed
        timeline = get_session_event_timeline(sid, limit=20)
        event_types_in_timeline = {e["event_type"] for e in timeline}
        assert "status_changed" in event_types_in_timeline

    def test_short_session_with_stop_loss(self, temp_db, sim_default, turtle_strategy):
        """空仓 + 止损线（反向：止损 = entry + 2N = 17900，加仓 = entry - 0.5N = 17400）"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "short",
            17500.0,
            n_value=200.0,
        )

        lines = compute_lines(sid, use_cache=False)
        assert lines["lines"]["stop_loss"] == 17900.0
        assert lines["lines"]["add"] == 17400.0

        # 加仓 + 调价
        add_unit(sid, 17400.0)
        result = override_line(sid, "stop_loss", 18000.0)
        assert result["lines"]["stop_loss"] == 18000.0

    def test_session_lock_serializes_concurrent_ops(self, temp_db, sim_default, turtle_strategy):
        """session_lock 串行化：A 持锁时 B 阻塞，A 释放后 B 拿锁"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )

        # A 持锁 0.1 秒
        def hold_lock():
            with with_session_lock(sid, "A"):
                time.sleep(0.1)

        t = threading.Thread(target=hold_lock)
        t.start()
        time.sleep(0.05)  # 让 A 拿到锁

        # B 拿锁（blocking=True + 5s 超时；A 0.1s 后放，应成功）
        with with_session_lock(sid, "B"):
            pass  # 成功拿锁

        t.join()

    def test_submit_market_and_limit_orders(self, temp_db, sim_default):
        """submit_order：市价单即时成交 + 限价单 pending"""
        # 市价单
        market_oid = submit_order(
            sim_default, "AG", "ag2607", "buy", "market", 1
        )
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT status, filled_quantity FROM sim_orders WHERE order_id = ?",
            (market_oid,),
        )
        market_row = cur.fetchone()
        conn.close()
        assert market_row["status"] == "filled"
        assert market_row["filled_quantity"] == 1

        # 限价单
        limit_oid = submit_order(
            sim_default, "AG", "ag2607", "buy", "limit", 1, price=17500.0
        )
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT status, filled_quantity FROM sim_orders WHERE order_id = ?",
            (limit_oid,),
        )
        limit_row = cur.fetchone()
        conn.close()
        assert limit_row["status"] == "pending"
        assert limit_row["filled_quantity"] == 0


# ============================================================
# 2. 价格线 override
# ============================================================
class TestPriceLineOverrides:
    """价格线 override 与重算一致性"""

    def test_override_persists_across_recompute(self, temp_db, sim_default, turtle_strategy):
        """override 持久化跨重算"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )

        # 多次 override
        override_line(sid, "stop_loss", 17000.0)
        clear_cache(sid)
        r1 = compute_lines(sid, use_cache=False)
        assert r1["lines"]["stop_loss"] == 17000.0

        override_line(sid, "add", 17800.0)
        r2 = compute_lines(sid, use_cache=False)
        assert r2["lines"]["add"] == 17800.0
        # 之前 override 的 stop_loss 仍保留
        assert r2["lines"]["stop_loss"] == 17000.0

    def test_cancel_override_restores_computed(self, temp_db, sim_default, turtle_strategy):
        """取消 override 恢复计算值"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )

        override_line(sid, "stop_loss", 17000.0)
        r1 = compute_lines(sid, use_cache=False)
        assert r1["lines"]["stop_loss"] == 17000.0

        # 取消（price=None）
        override_line(sid, "stop_loss", None)
        r2 = compute_lines(sid, use_cache=False)
        # 恢复计算值：entry(17500) - 2N(400) = 17100
        assert r2["lines"]["stop_loss"] == 17100.0


# ============================================================
# 3. 与 0016 通达信字段对齐（v1.3 简化）
# ============================================================
class TestTurtleFieldAlignment:
    """v1.3 简化：direction 只 long/short；schema 一致性"""

    def test_direction_long_short_enum(self, temp_db, sim_default, turtle_strategy):
        """direction 只 long / short（DB schema 约束）"""
        # 多仓
        sid_long = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT direction FROM trade_sessions WHERE session_id = ?", (sid_long,)
        )
        d_long = cur.fetchone()["direction"]
        conn.close()
        assert d_long == "long"

        # 空仓
        sid_short = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "short", 17500.0, n_value=200.0
        )
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT direction FROM trade_sessions WHERE session_id = ?", (sid_short,)
        )
        d_short = cur.fetchone()["direction"]
        conn.close()
        assert d_short == "short"

    def test_status_open_closed_enum(self, temp_db, sim_default, turtle_strategy):
        """status 只 open / closed / pending"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT status FROM trade_sessions WHERE session_id = ?", (sid,))
        s_open = cur.fetchone()["status"]
        conn.close()
        assert s_open == "open"

        close_session(sid, 18000.0, "test")

        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT status FROM trade_sessions WHERE session_id = ?", (sid,))
        s_closed = cur.fetchone()["status"]
        conn.close()
        assert s_closed == "closed"


# ============================================================
# 4. v1.5 C 方案
# ============================================================
class TestCScheme:
    """C 方案：check 类事件存前后 5 根 K 线（trigger 前后各 5，共 11 根）"""

    def test_c_scheme_11_bars(self, temp_db, sim_default, turtle_strategy):
        """C 方案：trigger 前后各 5 根 = 11 根"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )

        # 造 20 根 K 线
        history = pd.DataFrame(
            {
                "open": [100 + i for i in range(20)],
                "high": [105 + i for i in range(20)],
                "low": [95 + i for i in range(20)],
                "close": [102 + i for i in range(20)],
            },
            index=pd.date_range("2026-05-01", periods=20, freq="D"),
        )

        # 触发 idx=10（前后各 5 = idx 5..15，共 11 根）
        trigger_bar = history.iloc[10]
        ids = log_check_event_with_context(
            session_id=sid,
            account_id=sim_default,
            check_type=EVT_STOP_LOSS_CHECK,
            trigger_bar=trigger_bar,
            history=history,
        )
        assert len(ids) == 11

        # 验证 1 条 is_gap=1（trigger 那一根）
        conn = sqlite3.connect(str(temp_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) as cnt FROM turtle_trade_process "
            "WHERE session_id = ? AND event_type = ? AND is_gap = 1",
            (sid, EVT_STOP_LOSS_CHECK),
        )
        gap_count = cur.fetchone()["cnt"]
        conn.close()
        assert gap_count == 1

    def test_c_scheme_at_edge(self, temp_db, sim_default, turtle_strategy):
        """C 方案：trigger 在边缘时退化（idx=0 只能取 0..5 = 6 根）"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )

        # 造 20 根 K 线
        history = pd.DataFrame(
            {
                "open": [100 + i for i in range(20)],
                "high": [105 + i for i in range(20)],
                "low": [95 + i for i in range(20)],
                "close": [102 + i for i in range(20)],
            },
            index=pd.date_range("2026-05-01", periods=20, freq="D"),
        )

        # 触发 idx=0（max(0, 0-5)=0, min(19, 0+5)=5 → 共 6 根）
        trigger_bar = history.iloc[0]
        ids = log_check_event_with_context(
            session_id=sid,
            account_id=sim_default,
            check_type=EVT_STOP_LOSS_CHECK,
            trigger_bar=trigger_bar,
            history=history,
        )
        # 0..5 共 6 根
        assert len(ids) == 6


# ============================================================
# 5. 性能基线
# ============================================================
class TestPerformanceBaseline:
    """性能基线测试（不追求极限，只记录基线）"""

    def test_100_sessions_open_perf(self, temp_db, sim_default, turtle_strategy):
        """100 个 session 建仓性能（基线 < 30s）"""
        start = time.time()
        sids = []
        for i in range(100):
            sid = open_session(
                sim_default,
                turtle_strategy,
                "AG",
                "ag2607",
                "long",
                17500.0 + i,
                n_value=200.0,
            )
            sids.append(sid)
        elapsed = time.time() - start
        assert len(sids) == 100
        # 基线：100 session 应 < 30s
        assert elapsed < 30.0, f"100 sessions took {elapsed:.2f}s > 30s"

    def test_100_overrides_perf(self, temp_db, sim_default, turtle_strategy):
        """100 次调价性能（基线 < 5s）"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "long",
            17500.0,
            n_value=200.0,
        )

        start = time.time()
        for i in range(100):
            override_line(sid, "stop_loss", 17000.0 + i)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"100 overrides took {elapsed:.2f}s > 5s"

    def test_50_add_units_then_close(self, temp_db, sim_default, turtle_strategy):
        """50 个 session 各加 4 unit 然后全部平仓（基线 < 15s）"""
        sids = []
        for i in range(50):
            sid = open_session(
                sim_default,
                turtle_strategy,
                "AG",
                "ag2607",
                "long",
                17500.0 + i,
                n_value=200.0,
            )
            add_unit(sid, 17600.0 + i)
            add_unit(sid, 17700.0 + i)
            add_unit(sid, 17800.0 + i)
            sids.append(sid)

        start = time.time()
        for sid in sids:
            close_session(sid, 18000.0, "perf test")
        elapsed = time.time() - start
        assert elapsed < 15.0, f"50 sessions close took {elapsed:.2f}s > 15s"
