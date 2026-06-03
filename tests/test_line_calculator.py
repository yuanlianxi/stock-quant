"""价格线计算单测（Phase 6.1）"""
import pytest

from api.services.line_calculator import (
    LINE_ADD,
    LINE_EXIT_20,
    LINE_STOP_LOSS,
    clear_cache,
    compute_lines,
    override_line,
)
from api.services.sim_engine import open_session


# ============================================================
# compute_lines
# ============================================================
class TestComputeLines:
    def test_long_session_basic_lines(self, temp_db, sim_default, turtle_strategy):
        """多单基础 3 色价格线"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        result = compute_lines(sid, use_cache=False)

        assert result["direction"] == "long"
        assert result["entry_price"] == 17500.0
        assert result["n_value"] == 200.0
        # 多单：止损 = entry - 2N = 17500 - 400 = 17100
        assert result["lines"][LINE_STOP_LOSS] == 17100.0
        # 多单：加仓 = entry + 0.5N = 17500 + 100 = 17600
        assert result["lines"][LINE_ADD] == 17600.0

    def test_short_session_lines(self, temp_db, sim_default, turtle_strategy):
        """空单反向"""
        sid = open_session(
            sim_default,
            turtle_strategy,
            "AG",
            "ag2607",
            "short",
            17500.0,
            n_value=200.0,
        )
        result = compute_lines(sid, use_cache=False)
        # 空单：止损 = entry + 2N = 17500 + 400 = 17900
        assert result["lines"][LINE_STOP_LOSS] == 17900.0
        # 空单：加仓 = entry - 0.5N = 17500 - 100 = 17400
        assert result["lines"][LINE_ADD] == 17400.0

    def test_nonexist_session_raises(self, temp_db):
        """不存在 session 应报错"""
        with pytest.raises(ValueError, match="session.*不存在"):
            compute_lines("non_exist_session_xyz", use_cache=False)


# ============================================================
# override_line
# ============================================================
class TestOverrideLine:
    def test_override_takes_precedence(self, temp_db, sim_default, turtle_strategy):
        """override 优先于计算值"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        result = override_line(sid, LINE_STOP_LOSS, 17000.0)
        assert result["lines"][LINE_STOP_LOSS] == 17000.0
        assert result["overrides"][LINE_STOP_LOSS] == 17000.0

    def test_override_cancel(self, temp_db, sim_default, turtle_strategy):
        """override None 取消"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        override_line(sid, LINE_STOP_LOSS, 17000.0)
        result2 = override_line(sid, LINE_STOP_LOSS, None)
        # 应回到计算值 17100.0
        assert result2["lines"][LINE_STOP_LOSS] == 17100.0
        assert result2["overrides"][LINE_STOP_LOSS] is None

    def test_invalid_line_type_raises(self, temp_db, sim_default, turtle_strategy):
        """invalid line_type 报错"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        with pytest.raises(ValueError, match="Invalid line_type"):
            override_line(sid, "invalid_type", 100.0)


# ============================================================
# Cache
# ============================================================
class TestCache:
    def test_cache_hit_on_same_state(self, temp_db, sim_default, turtle_strategy):
        """同 override 状态两次结果一致（缓存命中）"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        clear_cache(sid)
        r1 = compute_lines(sid, use_cache=True)
        r2 = compute_lines(sid, use_cache=True)
        assert r1 == r2

    def test_cache_invalidate_on_override(self, temp_db, sim_default, turtle_strategy):
        """override 变失效缓存"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        clear_cache(sid)
        compute_lines(sid, use_cache=True)  # 首次
        override_line(sid, LINE_ADD, 17800.0)
        result = compute_lines(sid, use_cache=True)
        # override 已写入 DB + 失效缓存，再次 compute 应拿到新值
        assert result["lines"][LINE_ADD] == 17800.0

    def test_clear_cache_specific_session(self, temp_db, sim_default, turtle_strategy):
        """清指定 session 缓存"""
        sid = open_session(
            sim_default, turtle_strategy, "AG", "ag2607", "long", 17500.0, n_value=200.0
        )
        compute_lines(sid, use_cache=True)
        clear_cache(sid)
        # 再次 compute 不会报错
        result = compute_lines(sid, use_cache=True)
        assert result["session_id"] == sid
