"""
T1 海龟交易系统 - 仓位管理层 + 策略主类
=========================================
Unit 计算、加仓逻辑、止损阶梯；TurtleStrategy 主类（继承 BaseStrategy）
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List

import pandas as pd

from strategies.base import BaseStrategy


@dataclass
class TurtleUnit:
    """单个 Unit（头寸单位）"""
    unit_id: int           # 第几个 Unit（1~4）
    entry_price: float     # 成交价
    atr_at_entry: float    # 入场时的 ATR（N值）
    stop_price: float      # 该 Unit 的止损价
    direction: int         # 1=做多, -1=做空

    def is_stopped(self, current_price: float, direction: int) -> bool:
        """检查是否触发止损"""
        if direction == 1:
            return current_price <= self.stop_price
        else:  # 空头
            return current_price >= self.stop_price


@dataclass
class TurtlePosition:
    """单个品种的海龟持仓"""
    symbol: str
    direction: int                    # 1=多头, -1=空头
    units: list[TurtleUnit]           # 当前 Unit 列表（最多4个）
    atr: float                        # 当前 ATR（N值）
    entry_high_55: float              # 入市时的 55日最高（多头）
    entry_low_55: float               # 入市时的 55日最低（空头）
    avg_entry_price: float            # 加权平均入场价
    skip_adjust: bool                # 跳空加仓时跳过后续止损调整

    @property
    def total_units(self) -> int:
        return len(self.units)

    @property
    def total_risk(self) -> float:
        """总风险金额（用于计算账户风险度）"""
        return sum(u.atr_at_entry * 2 for u in self.units)  # 每个 Unit 2N 风险

    def update_stop_ladder(self, new_atr: float):
        """
        更新止损阶梯（每加仓1个 Unit，前序全部上移 0.5N）
        跳空例外：skip_adjust=True 时新 Unit 独立止损，前序不调整
        """
        if self.skip_adjust:
            # 跳空：新 Unit 止损按标准公式 entry_price - direction * 2 * atr
            # 前序止损维持不变，不再动态调整
            if self.units:
                latest = self.units[-1]
                latest.stop_price = latest.entry_price - self.direction * 2 * new_atr
            self.skip_adjust = False
            return

        # 正常加仓：前序止损上移 0.5N
        half_n = new_atr / 2
        for i, unit in enumerate(self.units):
            if self.direction == 1:
                unit.stop_price = unit.entry_price - (i + 2) * half_n
            else:
                unit.stop_price = unit.entry_price + (i + 2) * half_n

    def check_add_unit(self, current_price: float, atr: float, max_units: int = 4) -> bool:
        """
        判断是否可以加仓
        条件：1）当前 Unit < 4；2）价格相对上一 Unit 有利方向移动 ≥ 0.5N
        """
        if len(self.units) >= max_units:
            return False

        last_unit = self.units[-1]
        required_move = atr / 2

        if self.direction == 1:  # 多头
            return current_price >= last_unit.entry_price + required_move
        else:  # 空头
            return current_price <= last_unit.entry_price - required_move

    def check_exit_20(self, low_20: float, high_20: float) -> bool:
        """
        20日反向突破离市
        多头：收盘价或日内低点 < 20日最低
        空头：收盘价或日内高点 > 20日最高
        """
        if self.direction == 1:
            return low_20 is not None  # 多头用 low_20 触发
        else:
            return high_20 is not None  # 空头用 high_20 触发


class PositionManager:
    """
    仓位管理器
    维护多个品种的海龟持仓，执行加仓/止损/离市逻辑
    """

    def __init__(self):
        self.positions: dict[str, TurtlePosition] = {}
        self.single_max: int = 4
        self.directional_max: int = 12
        self.correlated_max: int = 10

    def add_position(
        self,
        symbol: str,
        direction: int,
        entry_price: float,
        atr: float,
        unit_size: int,
        high_55: float,
        low_55: float
    ) -> Optional[TurtlePosition]:
        """建仓（第一个 Unit）"""
        if symbol in self.positions:
            return None  # 已有持仓

        units = []
        for i in range(unit_size):
            stop = entry_price - direction * (i + 1) * atr * 2
            units.append(TurtleUnit(
                unit_id=i + 1,
                entry_price=entry_price,
                atr_at_entry=atr,
                stop_price=stop,
                direction=direction
            ))

        pos = TurtlePosition(
            symbol=symbol,
            direction=direction,
            units=units,
            atr=atr,
            entry_high_55=high_55,
            entry_low_55=low_55,
            avg_entry_price=entry_price,
            skip_adjust=False
        )
        self.positions[symbol] = pos
        return pos

    def add_unit(
        self,
        symbol: str,
        price: float,
        atr: float,
        is_gap: bool = False
    ) -> bool:
        """
        加仓一个 Unit
        is_gap=True 表示跳空加仓（跳过后续止损调整）
        """
        if symbol not in self.positions:
            return False

        pos = self.positions[symbol]
        if len(pos.units) >= self.single_max:
            return False

        # 检查是否满足加仓条件
        if not pos.check_add_unit(price, atr):
            return False

        # 新 Unit 止损 = 入场价 - 2N（相对入场价）
        stop = price - pos.direction * 2 * atr

        new_unit = TurtleUnit(
            unit_id=len(pos.units) + 1,
            entry_price=price,
            atr_at_entry=atr,
            stop_price=stop,
            direction=pos.direction
        )
        pos.units.append(new_unit)
        pos.skip_adjust = is_gap
        pos.update_stop_ladder(atr)

        # 更新平均入场价
        total_cost = sum(u.entry_price for u in pos.units)
        pos.avg_entry_price = total_cost / len(pos.units)

        return True

    def check_stops(self, current_prices: dict[str, float]) -> list[tuple[str, int, float]]:
        """
        检查所有持仓的止损触发
        返回：[('AG', 1, 3725.0), ...] = (品种, Unit手数, 触发价格)
        """
        triggered = []
        for symbol, pos in self.positions.items():
            if symbol not in current_prices:
                continue
            price = current_prices[symbol]
            for unit in pos.units:
                if unit.is_stopped(price, pos.direction):
                    triggered.append((symbol, 1, unit.stop_price))
        return triggered

    def total_directional_units(self, direction: int) -> int:
        """计算同向总 Unit 数"""
        return sum(
            pos.total_units
            for pos in self.positions.values()
            if pos.direction == direction
        )

    def total_group_units(self, group_name: str) -> int:
        """计算同关联组总 Unit 数"""
        # 需要配合 instruments.yaml 的关联组信息
        return 0  # 配合 factors.py 的 check_portfolio_limits


class TurtleStrategy(BaseStrategy):
    """
    海龟策略 V1 主类（继承 BaseStrategy）

    策略 ID：turtle_v1
    显示名：海龟T1

    该类是把现有仓位管理逻辑（PositionManager）和入场/出场检测
    包装为统一的 BaseStrategy 接口。Phase 2.4 之前 on_bar 仅为
    占位实现，Phase 2.4 会接入真实 K 线驱动。
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        super().__init__(params=params)
        # 内部持有一个 PositionManager 实例（保留现有仓位管理能力）
        self.pm: PositionManager = PositionManager()
        # 状态记录：每个品种最近一次状态
        self._last_state: Dict[str, Dict[str, Any]] = {}

    @property
    def strategy_id(self) -> str:
        return "turtle_v1"

    @property
    def strategy_name(self) -> str:
        return "海龟T1"

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "entry_n": 55,
            "exit_n": 20,
            "add_interval": 0.5,
            "stop_loss": 2,
            "atr_n": 20,
            "max_units": 4,
            "risk_per_trade": 2000,
        }

    def on_bar(self, symbol: str, bar: pd.Series, history: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        海龟策略 on_bar（v1.5 Phase 3.8 退仓优先版）

        退仓优先顺序：止损 > 加仓 > 20日反向
        1. 止损检测：close < entry_n周期最低 - 2N → stop_loss_check（命中立即返回）
        2. 加仓检测：close > 55周期高 → entry_long
           0.5N 间隔加仓：close > 55周期高 + 0.5N → add_signal
           跳空：gap >= 0.5N → add_skipped_gap
        3. 20日反向：close < 20日低 → check_exit

        加仓 / 止损 / 20日反向平仓的实际写入由 sim_engine 在 open_session /
        add_unit / close_unit 触发，本函数只发信号。
        """
        try:
            if history is None or history.empty:
                return []

            entry_n = int(self.params.get('entry_n', 55))
            exit_n = int(self.params.get('exit_n', 20))
            add_interval = float(self.params.get('add_interval', 0.5))
            stop_loss = float(self.params.get('stop_loss', 2))

            if len(history) < max(entry_n, exit_n):
                return []

            signals: List[Dict[str, Any]] = []

            # bar_time 兼容
            bar_time = bar.get('datetime') if 'datetime' in bar.index else bar.name
            if hasattr(bar_time, 'isoformat'):
                bar_time_str = bar_time.isoformat()
            else:
                bar_time_str = str(bar_time)

            close = float(bar['close'])

            # 计算 N 值（ATR(20)）—— 简化版：用 high-low 平均作为 N 估计
            try:
                n_value = float((history['high'] - history['low']).iloc[-20:].mean())
            except Exception:
                n_value = 0.0

            # === 退仓优先 1: 止损检测（命中立即返回）===
            if len(history) >= entry_n and n_value > 0:
                n_period_low = float(history['low'].iloc[-entry_n:].min())
                stop_price = n_period_low - stop_loss * n_value
                if close < stop_price:
                    signals.append({
                        'signal_type': 'stop_loss_check',
                        'direction': 'exit',  # 退仓
                        'trigger_price': close,
                        'reference_price': stop_price,
                        'reference_n': n_value,
                        'bar_time': bar_time_str,
                        'bar': bar,  # 传给 executor 触发 C 方案
                        'history': history,  # 同上
                        'reason': f'止损: close {close:.2f} < stop {stop_price:.2f} (2N={stop_loss*n_value:.2f})'
                    })
                    return signals  # 退仓优先，立即返回

            # === 加仓 / 入场检测 ===
            if len(history) >= entry_n:
                try:
                    high_55 = float(history['high'].iloc[-entry_n:].max())
                except Exception:
                    high_55 = 0.0

                if high_55 and close > high_55:
                    signals.append({
                        'signal_type': 'entry_long',
                        'direction': 'long',
                        'trigger_price': close,
                        'reference_price': high_55,
                        'reference_n': n_value,
                        'bar_time': bar_time_str,
                        'reason': f'{entry_n}周期突破：close {close:.2f} > {entry_n}周期高 {high_55:.2f}'
                    })
                    return signals  # 突破信号优先返回

                # 0.5N 间隔加仓
                if n_value > 0:
                    add_threshold = high_55 + add_interval * n_value
                    gap = (close - float(history['close'].iloc[-2])) if len(history) >= 2 else 0
                    if close > add_threshold and gap < add_interval * n_value:  # 不跳空
                        signals.append({
                            'signal_type': 'add_signal',
                            'direction': 'long',
                            'trigger_price': close,
                            'reference_price': add_threshold,
                            'reference_n': n_value,
                            'bar_time': bar_time_str,
                            'reason': f'0.5N加仓: close {close:.2f} > {add_threshold:.2f}'
                        })
                        return signals
                    elif close > add_threshold and gap >= add_interval * n_value:  # 跳空
                        signals.append({
                            'signal_type': 'add_skipped_gap',
                            'direction': 'long',
                            'trigger_price': close,
                            'reference_price': add_threshold,
                            'reference_n': n_value,
                            'bar_time': bar_time_str,
                            'is_gap': 1,
                            'gap_size': gap,
                            'reason': f'跳空跳过: close {close:.2f} 跳空 {gap:.2f} >= 0.5N={add_interval*n_value:.2f}'
                        })
                        return signals

            # === 20日反向检测（最后才检查）===
            if len(history) >= exit_n:
                try:
                    low_20 = float(history['low'].iloc[-exit_n:].min())
                except Exception:
                    low_20 = 0.0
                if low_20 and close < low_20:
                    signals.append({
                        'signal_type': 'check_exit',
                        'direction': 'exit',
                        'trigger_price': close,
                        'reference_price': low_20,
                        'reference_n': n_value,
                        'bar_time': bar_time_str,
                        'bar': bar,
                        'history': history,
                        'reason': f'20日反向: close {close:.2f} < 20日低 {low_20:.2f}'
                    })

            return signals
        except Exception as e:
            # 失败不抛异常，避免主循环崩
            try:
                import logging
                logging.getLogger(__name__).warning(f"on_bar({symbol}) 失败: {e}")
            except Exception:
                pass
            return []

    def get_state(self) -> Dict[str, Any]:
        """返回当前策略状态（持仓摘要 + 最近 N 值）"""
        positions = {}
        for sym, pos in self.pm.positions.items():
            positions[sym] = {
                "direction": pos.direction,
                "total_units": pos.total_units,
                "avg_entry_price": pos.avg_entry_price,
                "current_atr": pos.atr,
            }
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "params": self.params,
            "positions": positions,
        }


if __name__ == "__main__":
    print("=== PositionManager 测试 ===\n")

    pm = PositionManager()

    # 测试：白银 AG 多头建仓
    pos = pm.add_position(
        symbol="AG",
        direction=1,
        entry_price=3765,
        atr=20,
        unit_size=1,
        high_55=3765,
        low_55=3700
    )
    print(f"[1] 建仓 AG 1 Unit @ 3765, ATR=20")
    print(f"    持仓：{pos.total_units} Unit, 平均价={pos.avg_entry_price}")
    print(f"    止损阶梯：{[u.stop_price for u in pos.units]}")

    # 测试：AG 加仓（第2个 Unit）
    ok = pm.add_unit("AG", price=3775, atr=20)
    print(f"\n[2] AG +1 Unit @ 3775: {'成功' if ok else '失败'}")
    print(f"    持仓：{pos.total_units} Unit, 平均价={pos.avg_entry_price:.1f}")
    print(f"    止损阶梯：{[f'{u.stop_price:.1f}' for u in pos.units]}")

    # 测试：AG 继续加仓（第3、第4个 Unit）
    pm.add_unit("AG", price=3785, atr=20)
    pm.add_unit("AG", price=3795, atr=20)
    print(f"\n[3] AG 满仓 4 Unit")
    print(f"    持仓：{pos.total_units} Unit, 平均价={pos.avg_entry_price:.1f}")
    print(f"    止损阶梯：{[f'{u.stop_price:.1f}' for u in pos.units]}")
    print(f"    总风险：{pos.total_risk} 元（每 Unit 2N = {2*20*15} 元/手, 共 {pos.total_units} 手）")

    # 测试：止损检查
    stops = pm.check_stops({"AG": 3720})
    print(f"\n[4] 止损检查 AG@3720: 触发 {len(stops)} 个")

    print("\n=== 完成 ===")