"""P&L calculator.

Phase 2 抽自 api/main.py L239-241。
"""


def calc_pnl(pos, current_price: float, contract_size: float = 15.0) -> float:
    """根据持仓计算当前浮动盈亏。

    Args:
        pos: 持仓对象（含 direction / avg_entry_price / total_units 字段）
        current_price: 当前价格
        contract_size: 合约乘数（默认 15，AG/AU 用）

    Returns:
        float: 浮动盈亏金额
    """
    if pos.total_units == 0:
        return 0.0
    return (current_price - pos.avg_entry_price) * pos.direction * contract_size * pos.total_units
