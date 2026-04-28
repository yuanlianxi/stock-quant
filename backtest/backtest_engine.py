#!/usr/bin/env python3
"""
backtest_engine.py - Backtrader 回测引擎封装
"""

import backtrader as bt
from datetime import datetime
from typing import Optional, Dict, Any, Type


class BacktestEngine:
    """回测引擎封装类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化回测引擎

        Args:
            config: 配置字典，包含：
                - initial_cash: 初始资金（默认 1000000）
                - commission: 手续费（默认 0.0003）
                - stamp_tax: 印花税（默认 0.001）
                - slippage: 滑点（默认 0.0001）
        """
        from .config import DEFAULT_CONFIG

        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.cerebro = None
        self.results = None

    def _create_cerebro(self):
        """创建 Cerebro 实例"""
        self.cerebro = bt.Cerebro()

        # 设置初始资金
        self.cerebro.broker.setcash(self.config['initial_cash'])

        # 设置手续费
        self.cerebro.broker.setcommission(commission=self.config['commission'])

        # 设置印花税（卖出时收取）
        # Backtrader 没有内置印花税，需要通过自定义 CommissionInfo 实现
        # 简化处理：在策略中卖出时额外计算

        # 设置滑点
        # Backtrader 没有内置滑点，通过自定义 slippage broker 实现
        self.cerebro.broker.set_slippage_perc(
            perc=self.config['slippage'],
            slip_open=True,
            slip_close=True
        )

    def add_data(self, datafeed: bt.feeds.DataBase):
        """
        添加数据源

        Args:
            datafeed: Backtrader 数据源
        """
        if self.cerebro is None:
            self._create_cerebro()
        self.cerebro.adddata(datafeed)

    def add_strategy(self, strategy_class: Type[bt.Strategy], **params):
        """
        添加策略

        Args:
            strategy_class: 策略类（继承自 bt.Strategy）
            **params: 策略参数
        """
        if self.cerebro is None:
            self._create_cerebro()
        self.cerebro.addstrategy(strategy_class, **params)

    def run(self) -> Dict[str, Any]:
        """
        运行回测

        Returns:
            包含初始资金、最终资金、收益率的字典
        """
        if self.cerebro is None:
            raise ValueError("请先添加数据源和策略")

        # 记录初始资金
        initial_value = self.cerebro.broker.getvalue()

        # 运行回测
        self.results = self.cerebro.run()

        # 获取最终资金
        final_value = self.cerebro.broker.getvalue()

        # 计算收益率
        return_rate = (final_value - initial_value) / initial_value

        return {
            'initial_value': initial_value,
            'final_value': final_value,
            'return_rate': return_rate,
            'return_pct': return_rate * 100,
            'cerebro': self.cerebro,
            'results': self.results,
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        获取回测指标（需要先运行 run）

        Returns:
            绩效指标字典
        """
        if self.results is None:
            return {}

        # 从策略实例获取分析器数据
        metrics = {}
        for strat in self.results:
            if hasattr(strat, 'analyzers'):
                for name, analyzer in strat.analyzers.items():
                    if hasattr(analyzer, 'get_analysis'):
                        try:
                            analysis = analyzer.get_analysis()
                            metrics[name] = analysis
                        except Exception:
                            pass
        return metrics


class TradeAnalyzer(bt.analyzers.TradeAnalyzer):
    """交易分析器"""
    pass


class SharpeRatio(bt.analyzers.SharpeRatio):
    """夏普比率分析器"""
    pass


class DrawDown(bt.analyzers.DrawDown):
    """回撤分析器"""
    pass


class AnnualReturn(bt.analyzers.AnnualReturn):
    """年化收益率分析器"""
    pass


def create_engine(config: Optional[Dict[str, Any]] = None) -> BacktestEngine:
    """
    创建回测引擎的便捷函数

    Args:
        config: 配置字典

    Returns:
        BacktestEngine 实例
    """
    engine = BacktestEngine(config)
    engine._create_cerebro()
    return engine
