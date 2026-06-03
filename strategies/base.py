"""
策略抽象基类
所有具体策略（turtle V1, dual_ma V1 等）必须继承 BaseStrategy
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import pandas as pd


class BaseStrategy(ABC):
    """
    策略抽象基类

    子类必须实现：
    - strategy_id: 策略 ID（如 'turtle_v1'）
    - strategy_name: 策略显示名
    - on_bar(): 每根 K 线触发，返回信号列表
    - get_state(): 获取策略状态（用于 UI 展示）
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = params if params is not None else self.default_params

    @property
    @abstractmethod
    def strategy_id(self) -> str:
        """策略 ID（如 'turtle_v1'）"""
        pass

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """策略显示名（如 '海龟T1'）"""
        pass

    @property
    def default_params(self) -> Dict[str, Any]:
        """默认参数（子类可覆盖）"""
        return {}

    @abstractmethod
    def on_bar(self, symbol: str, bar: pd.Series, history: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        每根 K 线触发
        返回信号列表，每个信号为 dict：
        {
            'signal_type': 'entry_long' | 'entry_short',
            'direction': 'long' | 'short',
            'trigger_price': float,
            'reference_price': float,
            'reference_n': float,
            'bar_time': str (ISO),
            'reason': str (可选)
        }
        """
        pass

    def get_state(self) -> Dict[str, Any]:
        """获取策略状态（默认返回空 dict，子类可覆盖）"""
        return {}
