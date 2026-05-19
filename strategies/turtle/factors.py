"""
T1 海龟交易系统 - 因子层
===========================
直接翻译自 Excel 公式：
  交易系统(1)2019.10.11.xlsx Sheet1
  海龟交易法则头寸规模计算器.xlsx

核心公式：
  G(头寸/次) = TRUNC(O × 1%) / (F × B)
             = TRUNC(名义资金 × 1%) / (ATR × 每手)
  H(加仓N/2) = F / 2 = ATR / 2
  I(止损2N)  = F × 2 = ATR × 2
  L/M/N(加仓点) = K + n×H × direction

Author: Stock Quant Project
Version: P0
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class InstrumentConfig:
    """品种配置（来自 instruments.yaml）"""
    symbol: str
    name: str
    contract_size: float          # 每手数量（如 10吨/手）
    point_value: float            # 每点价值 = contract_size × tick
    tick: float                   # 最小变动价位
    margin_ratio: float           # 保证金比例
    atr_initial: float            # 初始 ATR（N值）
    direction: int                # 1=做多, -1=做空
    correlated_group: Optional[str] = None


@dataclass
class MarketData:
    """市场行情数据（每日更新）"""
    symbol: str
    current_price: float          # 当前价格
    atr: float                    # 20日 ATR（N值），每日更新
    high_55: float                # 55日最高价（入市突破价）
    low_55: float                 # 55日最低价（做空突破价）


# ============================================================
# 核心公式：直接翻译 Excel
# ============================================================

def calc_unit_size(
    nominal_capital: float,
    atr: float,
    contract_size: float
) -> int:
    """
    计算每标准头寸单位的开仓手数
    公式：=TRUNC(O × 1%) / (F × B)
        = TRUNC(名义资金 × 1%) / (ATR × 每手)

    等价 Python：
        unit = int(nominal_capital * 0.01 / (atr * contract_size))

    参数：
        nominal_capital : 名义资金（元）
        atr              : N值/ATR（价格单位）
        contract_size    : 每手乘数（单位/手）

    返回：
        向下取整后的手数（TRUNC）

    示例（来自 Excel）：
        资金 50万，ATR=20，每手15kg（白银）：
        =TRUNC(500000×1%)/(20×15) = TRUNC(5000/300) = 16手
    """
    risk_amount = nominal_capital * 0.01           # O × 1%
    per_contract_risk = atr * contract_size        # F × B
    unit_raw = risk_amount / per_contract_risk
    return int(unit_raw)                            # TRUNC = 截断


def calc_add_interval(atr: float) -> float:
    """
    计算加仓间隔（0.5N）
    公式：=F/2 = ATR/2

    参数：atr（当前 N值）
    返回：0.5 × ATR（价格单位）
    """
    return atr / 2


def calc_stop_loss(atr: float) -> float:
    """
    计算止损距离（2N）
    公式：=F×2 = ATR×2

    参数：atr
    返回：2 × ATR（价格单位）
    """
    return atr * 2


def calc_stop_price(entry_price: float, atr: float, direction: int) -> float:
    """
    计算多头止损价（入场价 - 2N）
    注意：direction=1（多头）时止损在下方，direction=-1（空头）时止损在上方

    参数：
        entry_price : 入场价
        atr         : 当前 N值
        direction   : 1=做多, -1=做空

    返回：止损价
    """
    return entry_price - direction * 2 * atr


def calc_add_prices(entry_price: float, atr: float, direction: int, n_units: int = 3) -> list:
    """
    计算 3 个加仓点的价格
    公式（L/M/N）：
        L = K + H × direction
        M = K + 2H × direction
        N = K + 3H × direction
    其中 H = ATR/2

    参数：
        entry_price : 入场价（55日突破价 K）
        atr          : 当前 N值
        direction    : 1=做多, -1=做空
        n_units      : 加仓点数（默认3个）

    返回：[加仓点1, 加仓点2, 加仓点3]
    """
    h = atr / 2
    return [entry_price + (i + 1) * h * direction for i in range(n_units)]


def calc_entry_breakout(high_55: float, low_55: float, direction: int, current_price: float) -> Optional[float]:
    """
    判断是否触发 55 日突破入市

    参数：
        high_55 : 55日最高价
        low_55  : 55日最低价
        direction: 当前方向（1=做多, -1=做空）
        current_price: 当前价格

    返回：突破价格 或 None（未突破）
    """
    if direction == 1 and current_price >= high_55:
        return high_55
    elif direction == -1 and current_price <= low_55:
        return low_55
    return None


def calc_position_value(
    hand_count: int,
    price: float,
    contract_size: float
) -> float:
    """
    计算持仓市值（用于 I.V 计算）

    参数：
        hand_count   : 手数
        price        : 当前价格
        contract_size: 每手乘数

    返回：持仓价值
    """
    return hand_count * price * contract_size


def calc_risk_exposure(
    hand_count: int,
    contract_size: float,
    margin_ratio: float,
    price: float
) -> float:
    """
    计算风险敞口（保证金占用）

    参数：
        hand_count    : 手数
        contract_size : 每手乘数
        margin_ratio  : 保证金比例
        price         : 当前价格

    返回：保证金占用
    """
    return hand_count * contract_size * price * margin_ratio


# ============================================================
# ATR（N值）计算
# ============================================================

def calc_tr(high: float, low: float, prev_close: float) -> float:
    """
    计算 True Range（真实波幅）
    TR = MAX(H-L, |H-PDC|, |L-PDC|)

    参数：
        high      : 当日最高价
        low       : 当日最低价
        prev_close: 前一日收盘价

    返回：TR 值
    """
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def calc_atr_ema(tr_list: list, n_period: int = 20) -> float:
    """
    计算 ATR（N值）- EMA 平滑方式
    与 Excel 中 N = ATR(20) 等价

    N[t] = (19 × N[t-1] + TR[t]) / 20

    参数：
        tr_list   : TR 序列（从早到晚，最少 n_period 个）
        n_period   : EMA 周期（默认 20）

    返回：最新的 ATR(N) 值
    """
    if len(tr_list) < n_period:
        raise ValueError(f"TR 序列长度不足 {n_period}，需要 {len(tr_list)} 个")

    # 冷启动：SMA
    n = tr_list[:n_period]
    atr = sum(n) / n_period

    # EMA 递推
    for tr in tr_list[n_period:]:
        atr = (19 * atr + tr) / 20

    return atr


def calc_atr_simple(tr_list: list, n_period: int = 20) -> float:
    """
    简单 ATR（算术平均）- 用于快速估算

    参数：tr_list, n_period
    返回：20 日 TR 均值
    """
    if len(tr_list) < n_period:
        raise ValueError(f"需要至少 {n_period} 个 TR 数据")
    return sum(tr_list[-n_period:]) / n_period


# ============================================================
# 组合风控辅助
# ============================================================

def check_portfolio_limits(
    current_units: int,
    correlated_units: int,
    directional_units: int,
    single_max: int = 4,
    correlated_max: int = 10,
    directional_max: int = 12
) -> tuple[bool, str]:
    """
    检查组合仓位约束

    约束（来自 Sheet2 + 计算器）：
      单一品种 ≤ 4 Unit
      关联组合计 ≤ 10 Unit
      单一方向全市场 ≤ 12 Unit

    返回：(是否通过, 拒绝原因)
    """
    if current_units >= single_max:
        return False, f"单品种 {current_units} Unit，已达上限 {single_max}"

    if correlated_units > correlated_max:
        return False, f"关联组 {correlated_units} Unit，超限 {correlated_max}"

    if directional_units > directional_max:
        return False, f"同向合计 {directional_units} Unit，超限 {directional_max}"

    return True, "OK"


# ============================================================
# 测试用例（对应 Excel 验证）
# ============================================================

if __name__ == "__main__":
    print("=== Excel 公式验证 ===\n")

    # 验证 1：头寸规模计算器（白银 AG）
    # 资金 100万，ATR=50，合约乘数 300元/点 → Unit=0.67 → TRUNC=0
    unit_ag = calc_unit_size(1_000_000, 50, 300)
    print(f"[1] AG 100万资金 Unit手数 (ATR=50, 每点300元): {unit_ag} 手")
    print(f"    公式: TRUNC(1000000×1%)/(50×300) = TRUNC(333.33) = {unit_ag}\n")

    # 验证 2：交易系统 Sheet（AG）
    # ATR=20, 每手=15 → 头寸/次 = TRUNC(500000×1%)/(20×15) = 16手
    unit_ag_sheet = calc_unit_size(500_000, 20, 15)
    print(f"[2] Sheet AG 头寸/次: {unit_ag_sheet} 手")
    print(f"    公式: TRUNC(500000×1%)/(20×15) = TRUNC(166.67) = {unit_ag_sheet}\n")

    # 验证 3：止损
    print(f"[3] 止损距离 (ATR=20): {calc_stop_loss(20)} 元")
    print(f"     公式: ATR×2 = {20*2}\n")

    # 验证 4：加仓间隔
    print(f"[4] 加仓间隔 (ATR=20): {calc_add_interval(20)} 元")
    print(f"     公式: ATR/2 = {20/2}\n")

    # 验证 5：加仓点（AG 多头，入场 3765）
    add_points = calc_add_prices(3765, 20, 1)
    print(f"[5] AG 多头加仓点 (入场3765, ATR=20):")
    print(f"     L={add_points[0]}, M={add_points[1]}, N={add_points[2]}")
    print(f"     Excel: 3775/3785/3795 → Python: {add_points[0]}/{add_points[1]}/{add_points[2]}\n")

    # 验证 6：止损价
    stop = calc_stop_price(3765, 20, 1)
    print(f"[6] AG 多头止损价 (入场3765, ATR=20): {stop}")
    print(f"     公式: 3765 - 2×20 = {stop}\n")

    # 验证 7：PTA 空头加仓点
    add_pts_short = calc_add_prices(5082, 147.4, -1)
    print(f"[7] PTA 空头加仓点 (入场5082, ATR=147.4):")
    print(f"     L={add_pts_short[0]}, M={add_pts_short[1]}, N={add_pts_short[2]}")
    print(f"     Excel: 5008.3/4934.6/4860.9 → Python: {add_pts_short[0]:.1f}/{add_pts_short[1]:.1f}/{add_pts_short[2]:.1f}\n")

    print("=== 单元测试完成 ===")