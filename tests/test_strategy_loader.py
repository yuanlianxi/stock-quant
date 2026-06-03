"""策略 V1/V2 版本切换单测（Phase 6.1）"""
import pytest

from strategies.loader import get_strategy, list_available_strategies


# ============================================================
# get_strategy
# ============================================================
class TestGetStrategy:
    def test_load_turtle_v1(self, temp_db):
        """加载海龟 V1"""
        s = get_strategy("turtle_v1")
        assert s is not None
        assert s.strategy_id == "turtle_v1"
        assert s.strategy_name == "海龟T1"
        # 海龟默认参数
        assert s.default_params["entry_n"] == 55
        assert s.default_params["exit_n"] == 20

    def test_dual_ma_v1_in_list(self, temp_db):
        """dual_ma_v1 在列表中（loadable=False 因为没实现）"""
        s = list_available_strategies()
        dm = [x for x in s if x["strategy_id"] == "dual_ma_v1"]
        assert len(dm) == 1
        # dual_ma_v1 没 V1/strategy.py 模块 → loadable=False
        assert dm[0]["loadable"] is False

    def test_nonexist_strategy_raises(self, temp_db):
        """不存在 strategy 应报错"""
        with pytest.raises(ValueError, match="策略.*不存在"):
            get_strategy("non_exist_strategy_xyz")


# ============================================================
# list_available_strategies
# ============================================================
class TestListStrategies:
    def test_list_contains_turtle(self, temp_db):
        """列表应包含 turtle_v1"""
        s = list_available_strategies()
        ids = [x["strategy_id"] for x in s]
        assert "turtle_v1" in ids

    def test_list_has_required_fields(self, temp_db):
        """列表项含 loadable / error 字段"""
        s = list_available_strategies()
        for item in s:
            assert "loadable" in item
            assert "error" in item
            assert "strategy_id" in item
            assert "name" in item
            assert "is_active" in item


# ============================================================
# get_active_strategies
# ============================================================
class TestActiveStrategies:
    def test_get_active_strategies(self, temp_db):
        """获取所有 active 策略（turtle_v1 active=1）"""
        from strategies.executor import get_active_strategies

        actives = get_active_strategies()
        assert any(s.strategy_id == "turtle_v1" for s in actives)

    def test_dual_ma_v1_not_active(self, temp_db):
        """dual_ma_v1 is_active=0，不应在 active 列表中"""
        from strategies.executor import get_active_strategies

        actives = get_active_strategies()
        ids = [s.strategy_id for s in actives]
        assert "dual_ma_v1" not in ids


# ============================================================
# 海龟 V1 on_bar 接口冒烟
# ============================================================
class TestTurtleV1OnBar:
    def test_on_bar_no_history_returns_empty(self, temp_db):
        """无 history 不应崩，signal 应为空"""
        import pandas as pd

        s = get_strategy("turtle_v1")
        # 喂一个 bar，history 空 DataFrame
        bar = pd.Series(
            {
                "datetime": "2026-06-03T10:00:00",
                "open": 17500.0,
                "high": 17520.0,
                "low": 17480.0,
                "close": 17510.0,
                "volume": 100,
            }
        )
        empty_history = pd.DataFrame(
            columns=["datetime", "open", "high", "low", "close", "volume"]
        )
        signals = s.on_bar("AG", bar, history=empty_history)
        # 无 history → 不应有 signal
        assert isinstance(signals, list)
        assert signals == []
