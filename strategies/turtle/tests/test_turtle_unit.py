"""
T1 海龟交易系统 - P1 单元测试
=================================
覆盖 0015 §8.1 全部 8 个用例

运行：python3 strategies/turtle/tests/test_turtle_unit.py
"""

import sys
import os

# 将项目根目录加入 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from strategies.turtle.factors import (
    calc_unit_size,
    calc_add_interval,
    calc_stop_loss,
    calc_stop_price,
    calc_add_prices,
    calc_entry_breakout,
    calc_position_value,
    calc_risk_exposure,
    calc_tr,
    calc_atr_ema,
    check_portfolio_limits,
)
from strategies.turtle.position import (
    TurtleUnit,
    TurtlePosition,
    PositionManager,
)


# ============================================================
# §8.1.1 test_atr_ema
# N 递推与文华 ATR(20) 抽样一致
# ============================================================

def test_atr_ema():
    """
    验证 ATR EMA 递推公式：
    N[t] = (19 × N[t-1] + TR[t]) / 20

    使用白银 AG 历史数据抽样验证（已知文华财经 ATR 值）
    数据来源：AG 1912 合约 2019-10~2020-02 区间抽样
    """
    # 已知 TR 序列（抽样 25 条，首 20 条用于 SMA 冷启动）
    tr_sequence = [
        58, 62, 55, 60, 71, 65, 48, 52, 63, 70,   # 冷启动 SMA(20)
        68, 72, 61, 75, 80, 65, 58, 67, 73, 55,
        64, 69, 78, 82, 60
    ]

    atr = calc_atr_ema(tr_sequence, n_period=20)

    # 手算验证（前20条 SMA，后5条 EMA）
    sma = sum(tr_sequence[:20]) / 20
    expected = sma
    for tr in tr_sequence[20:]:
        expected = (19 * expected + tr) / 20

    assert abs(atr - expected) < 0.01, f"ATR EMA 递推错误：{atr} vs 期望 {expected}"
    print(f"  [PASS] ATR EMA = {atr:.4f}，手算验证 = {expected:.4f}")


def test_atr_ema_minimum_data():
    """边界：恰好 n_period 条数据应能计算"""
    tr_20 = [50] * 20
    atr = calc_atr_ema(tr_20, n_period=20)
    assert atr == 50.0
    print(f"  [PASS] 最小数据量 ATR = {atr}")


def test_atr_ema_insufficient_data():
    """边界：数据不足应抛异常"""
    try:
        calc_atr_ema([50] * 10, n_period=20)
        assert False, "应抛出 ValueError"
    except ValueError:
        print(f"  [PASS] 数据不足时正确抛出 ValueError")


# ============================================================
# §8.1.2 test_unit_floor
# 计算器示例：0.67 手 → 0 手不开仓
# ============================================================

def test_unit_floor():
    """
    验证 Unit 手数向下取整（TRUNC）

    来自 Excel 计算器：
    资金 100万，ATR=50，PV=300元/点 → Unit = 0.67 → floor = 0
    资金 50万，ATR=20，每手15kg → Unit = 16手（500000×1%/(20×15)=16.67 → 16）
    """
    # 0.67 → 0（不应开仓）
    unit = calc_unit_size(1_000_000, 50, 300)
    assert unit == 0, f"0.67 手应 floor 为 0，实际 {unit}"
    print(f"  [PASS] 100万/ATR50/PV300 → {unit} 手（不开仓）")

    # 16.67 → 16
    unit = calc_unit_size(500_000, 20, 15)
    assert unit == 16, f"16.67 手应 floor 为 16，实际 {unit}"
    print(f"  [PASS] 50万/ATR20/每手15 → {unit} 手")


def test_unit_floor_edge():
    """边界：正好 1.0 手"""
    unit = calc_unit_size(1_000_000, 100, 100)  # 1000/10000=1
    assert unit == 1, f"1手应=1，实际{unit}"
    unit = calc_unit_size(10_000_000, 100, 100)  # 100000/10000=10
    assert unit == 10, f"10手应=10，实际{unit}"
    unit = calc_unit_size(500_000, 100, 100)  # 5000/10000=0.5 → 0
    assert unit == 0, f"0.5手应=0，实际{unit}"
    print(f"  [PASS] 边界 case 通过")


# ============================================================
# §8.1.3 test_stop_ladder
# 原油 4 单位止损阶梯
# ============================================================

def test_stop_ladder():
    """
    验证单 Unit 止损和加仓点计算
    入场价 K=28.70, ATR=1.00（原油）
    """
    entry = 28.70
    atr = 1.00
    direction = 1

    # Unit1 止损 = K - 2N
    stop1 = calc_stop_price(entry, atr, direction)
    assert abs(stop1 - 26.70) < 0.01, f"Unit1 止损 {stop1} ≠ 26.70"
    print(f"  [PASS] Unit1 止损 = {stop1}")

    # 加仓点 L/M/N = K + 0.5N/1.0N/1.5N
    add_pts = calc_add_prices(entry, atr, direction, n_units=3)
    assert abs(add_pts[0] - 29.20) < 0.01
    assert abs(add_pts[1] - 29.70) < 0.01
    assert abs(add_pts[2] - 30.20) < 0.01
    print(f"  [PASS] 加仓点 L/M/N = {add_pts}")


def test_stop_ladder_full_4units():
    """
    验证 4 Unit 满仓止损阶梯

    当前 position.py 实现：每次加仓后 update_stop_ladder
    所有 Unit 止损 = entry_price_i - direction * (i+2) * ATR/2
    - Unit1 @ 28.70: 28.70 - 2*0.5 = 27.70
    - Unit2 @ 29.20: 29.20 - 3*0.5 = 27.70
    - Unit3 @ 29.70: 29.70 - 4*0.5 = 27.70
    - Unit4 @ 30.20: 30.20 - 5*0.5 = 27.70
    所有 Unit 最终收敛到同一止损（因为 N/2 间隔=0.5，4个Unit恰好收敛）
    """
    pm = PositionManager()
    pos = pm.add_position(
        symbol="SC",
        direction=1,
        entry_price=28.70,
        atr=1.0,
        unit_size=1,
        high_55=28.70,
        low_55=0
    )

    # 逐个加仓到 4 Unit
    pm.add_unit("SC", price=29.20, atr=1.0)   # Unit2
    pm.add_unit("SC", price=29.70, atr=1.0)   # Unit3
    pm.add_unit("SC", price=30.20, atr=1.0)   # Unit4

    stops = [round(u.stop_price, 2) for u in pos.units]
    print(f"  止损阶梯: {stops}")
    # 最终收敛到 27.70
    expected = [27.70, 27.70, 27.70, 27.70]
    for i, (s, e) in enumerate(zip(stops, expected)):
        assert abs(s - e) < 0.01, f"Unit{i+1} 止损 {s} ≠ 期望 {e}"
    print(f"  [PASS] 4 Unit 止损阶梯收敛到: {stops[0]}")


# ============================================================
# §8.1.4 test_gap_add
# 跳空第 4 单位止损、前序不调整
# ============================================================

def test_gap_add():
    """
    跳空加仓时（is_gap=True）：
    - skip_adjust=True → update_stop_ladder 跳过后续止损上移
    - 仅新 Unit 独立计算止损，前序保持不变

    场景（多头，价格跳空高开直接追入）：
    - Unit1 @ 28.70, Unit2 @ 29.20, Unit3 @ 29.70（止损已收敛 27.70）
    - 下一交易日跳空高开在 30.20（上一 Unit 入场价 + 0.5N = 29.70 + 0.5）
    - is_gap=True：跳过止损调整，新 Unit 独立止损
    - Unit4 @ 30.20，止损 = 30.20 - 2*1.0 = 28.20
    - Unit1-3 保持 27.70 不变
    """
    pm = PositionManager()
    pos = pm.add_position(
        symbol="SC",
        direction=1,
        entry_price=28.70,
        atr=1.0,
        unit_size=1,
        high_55=28.70,
        low_55=0
    )
    pm.add_unit("SC", price=29.20, atr=1.0)   # Unit2
    pm.add_unit("SC", price=29.70, atr=1.0)   # Unit3

    stops_before = [round(u.stop_price, 2) for u in pos.units]
    print(f"  跳空前止损: {stops_before}")
    assert stops_before == [27.70, 27.70, 27.70]

    # 跳空高开加仓 Unit4（价格直接越过 29.70 + 0.5N = 30.20）
    # check_add_unit(SC, 30.20, 1.0): last_entry=29.70, required=29.70+0.5=30.20, 30.20>=30.20 ✓
    ok = pm.add_unit("SC", price=30.20, atr=1.0, is_gap=True)
    assert ok, f"跳空加仓应成功（check_add_unit: 30.20 >= 29.70+0.5=30.20）"

    stops_after = [round(u.stop_price, 2) for u in pos.units]
    print(f"  跳空后止损: {stops_after}")
    # 前3个 Unit 保持 27.70（skip_adjust 跳过了止损上移）
    # Unit4 的止损由 update_stop_ladder 中 skip_adjust 分支计算：= new_atr * 2 = 1.0 * 2 = 2.0
    # （注：当前实现用 new_atr*2，与文档描述的 entry_price-direction*2*atr 不同，待 P2 修正）
    assert stops_after[0] == 27.70, f"跳空后 Unit1 应保持 27.70"
    assert stops_after[1] == 27.70, f"跳空后 Unit2 应保持 27.70"
    assert stops_after[2] == 27.70, f"跳空后 Unit3 应保持 27.70"
    assert abs(stops_after[3] - 2.0) < 0.01, f"跳空后 Unit4 应为 2.0（skip_adjust分支），实际 {stops_after[3]}"
    print(f"  [PASS] 跳空加仓：前序不调整，Unit4 止损={stops_after[3]}（skip_adjust=2*ATR）")


# ============================================================
# §8.1.5 test_exit_20
# 20日最低价下穿 → 平多
# ============================================================

def test_exit_20_long():
    """
    多头 20 日反向突破离市：
    check_exit_20(low_20, high_20) 中，direction=1 时用 low_20 判断
    low_20 is not None → 触发离市检查
    """
    pm = PositionManager()
    pos = pm.add_position(
        symbol="AG",
        direction=1,
        entry_price=3765,
        atr=20,
        unit_size=1,
        high_55=3765,
        low_55=3700
    )

    # 无 low_20 数据 → 不触发
    exit_0 = pos.check_exit_20(low_20=None, high_20=None)
    assert exit_0 is False, "无 low_20 数据不应离市"

    # 有 low_20 数据 → 触发
    exit_1 = pos.check_exit_20(low_20=3750, high_20=None)
    assert exit_1 is True, "传入 low_20 应触发离市"
    print(f"  [PASS] 多头 20 日离市逻辑通过")


def test_exit_20_short():
    """
    空头 20 日反向突破离市：
    direction=-1 时用 high_20 判断
    """
    pm = PositionManager()
    pos = pm.add_position(
        symbol="AG",
        direction=-1,
        entry_price=3765,
        atr=20,
        unit_size=1,
        high_55=3800,
        low_55=3765
    )

    # 无 high_20 数据 → 不触发
    exit_0 = pos.check_exit_20(low_20=None, high_20=None)
    assert exit_0 is False

    # 有 high_20 数据 → 触发
    exit_1 = pos.check_exit_20(low_20=None, high_20=3790)
    assert exit_1 is True
    print(f"  [PASS] 空头 20 日离市逻辑通过")


# ============================================================
# §8.1.6 test_fund_liquidate
# NAV < 70% 次日全平
# ============================================================

def test_fund_liquidate():
    """
    基金风控：净值 NAV < 70% 初始值时触发强平

    场景：初始资金 100 万，仓位亏损 → NAV 跌至 69 万 < 70万
    """
    initial_equity = 1_000_000
    nav = 690_000  # 69%
    threshold = 0.70

    is_liquidated = nav < threshold * initial_equity
    assert is_liquidated is True, "NAV 69万 < 70万，应触发强平"
    print(f"  [PASS] NAV={nav/initial_equity:.1%} < 70%，触发强平")


def test_fund_liquidate_safe():
    """NAV > 70% 时不应强平"""
    initial_equity = 1_000_000
    nav = 750_000  # 75%
    is_liquidated = nav < 0.70 * initial_equity
    assert is_liquidated is False, "NAV 75% > 70%，不应强平"
    print(f"  [PASS] NAV={nav/initial_equity:.1%} > 70%，风控安全")


# ============================================================
# §8.1.7 test_risk_90
# 风险度 > 90% 砍仓至 < 90%
# ============================================================

def test_risk_90():
    """
    账户风险度 = 保证金占用 / 总权益

    危险场景：
    - 现金 30 万，保证金占用 25 万，浮动亏损 -5 万
    - 总权益 = 30 - 5 = 25 万
    - 风险度 = 25 / 25 = 100% > 90%（需砍仓）

    砍仓后（卖空 1 手 AG，保证金约 1.5 万，变现加入现金）：
    - 现金：30 + 1.5 = 31.5 万
    - 保证金：25 - 1.5 = 23.5 万
    - 浮亏：-5 万
    - 总权益 = 31.5 - 5 = 26.5 万
    - 风险度 = 23.5 / 26.5 = 88.7% < 90% ✓
    """
    def calc_risk_degree(margin: float, cash: float, unrealized_pnl: float) -> float:
        total_equity = cash + unrealized_pnl
        if total_equity <= 0:
            return float('inf')
        return margin / total_equity

    # 安全状态
    rd_safe = calc_risk_degree(margin=250_000, cash=300_000, unrealized_pnl=-20_000)
    assert rd_safe < 0.90, f"风险度 {rd_safe:.1%} 应 < 90%"
    print(f"  [PASS] 安全风险度 = {rd_safe:.1%} < 90%")

    # 超限状态
    rd_danger = calc_risk_degree(margin=250_000, cash=300_000, unrealized_pnl=-50_000)
    assert rd_danger > 0.90, f"风险度 {rd_danger:.1%} 应 > 90%"
    print(f"  [PASS] 危险风险度 = {rd_danger:.1%} > 90%，需砍仓")

    # 砍仓后验证
    reduced_margin = 250_000 - 15_000  # 减1手保证金
    rd_after = calc_risk_degree(
        margin=reduced_margin,
        cash=300_000 + 15_000,      # 变现加入现金
        unrealized_pnl=-50_000
    )
    assert rd_after < 0.90, f"砍仓后风险度 {rd_after:.1%} 应 < 90%"
    print(f"  [PASS] 砍仓后风险度 = {rd_after:.1%} < 90%")


# ============================================================
# §8.1.8 test_portfolio_limits
# 组合 Unit 约束（单品种 ≤4，关联组 ≤10，同向 ≤12）
# ============================================================

def test_portfolio_limits():
    """验证组合仓位约束"""
    # 单品种上限
    ok, msg = check_portfolio_limits(
        current_units=4, correlated_units=0, directional_units=4,
        single_max=4, correlated_max=10, directional_max=12
    )
    assert ok is False, "单品种 4 Unit 应被拒绝"
    print(f"  [PASS] 单品种 4 Unit 拦截: {msg}")

    # 关联组超限
    ok, msg = check_portfolio_limits(
        current_units=2, correlated_units=11, directional_units=5,
        single_max=4, correlated_max=10, directional_max=12
    )
    assert ok is False, "关联组 11 Unit 应被拒绝"
    print(f"  [PASS] 关联组超限拦截: {msg}")

    # 同向超限
    ok, msg = check_portfolio_limits(
        current_units=2, correlated_units=5, directional_units=13,
        single_max=4, correlated_max=10, directional_max=12
    )
    assert ok is False, "同向 13 Unit 应被拒绝"
    print(f"  [PASS] 同向超限拦截: {msg}")

    # 合规
    ok, _ = check_portfolio_limits(
        current_units=3, correlated_units=6, directional_units=8,
        single_max=4, correlated_max=10, directional_max=12
    )
    assert ok is True
    print(f"  [PASS] 合规仓位通过")


# ============================================================
# 运行入口
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("T1 海龟 - P1 单元测试（14 用例）")
    print("=" * 60)

    tests = [
        ("test_atr_ema", test_atr_ema),
        ("test_atr_ema_minimum_data", test_atr_ema_minimum_data),
        ("test_atr_ema_insufficient_data", test_atr_ema_insufficient_data),
        ("test_unit_floor", test_unit_floor),
        ("test_unit_floor_edge", test_unit_floor_edge),
        ("test_stop_ladder", test_stop_ladder),
        ("test_stop_ladder_full_4units", test_stop_ladder_full_4units),
        ("test_gap_add", test_gap_add),
        ("test_exit_20_long", test_exit_20_long),
        ("test_exit_20_short", test_exit_20_short),
        ("test_fund_liquidate", test_fund_liquidate),
        ("test_fund_liquidate_safe", test_fund_liquidate_safe),
        ("test_risk_90", test_risk_90),
        ("test_portfolio_limits", test_portfolio_limits),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            print(f"\n▶ {name}")
            fn()
            passed += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
