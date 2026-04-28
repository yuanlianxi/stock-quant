#!/usr/bin/env python3
"""测试回测引擎"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.backtest_engine import create_engine
from backtest.data_loader import get_data_loader
import backtrader as bt


class TestStrategy(bt.Strategy):
    """测试策略 - 简单买入持有"""

    def __init__(self):
        self.order = None

    def next(self):
        if self.order:
            return
        # 第一天买入
        if len(self) == 1:
            self.order = self.buy()


def test_engine():
    """测试回测引擎"""
    print("=" * 50)
    print("回测引擎测试")
    print("=" * 50)

    # 创建引擎
    config = {
        'initial_cash': 1000000,
        'commission': 0.0003,
    }
    engine = create_engine(config)
    print(f"初始资金: {engine.config['initial_cash']}")
    print(f"手续费: {engine.config['commission']}")

    # 获取数据
    loader = get_data_loader()
    df = loader.get_etf_daily('510300', '2020-01-01', '2023-12-31')

    if df.empty:
        print("获取数据失败")
        return

    print(f"数据条数: {len(df)}")

    # 转换数据格式
    import pandas as pd
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')

    datafeed = bt.feeds.PandasData(
        dataname=df,
        datetime=None,
        open='open',
        high='high',
        low='low',
        close='close',
        volume='volume',
        openinterest=-1,
    )

    # 添加数据和策略
    engine.add_data(datafeed)
    engine.add_strategy(TestStrategy)

    # 运行回测
    result = engine.run()

    print(f"\n回测结果:")
    print(f"  初始资金: {result['initial_value']:,.2f}")
    print(f"  最终资金: {result['final_value']:,.2f}")
    print(f"  收益率: {result['return_pct']:.2f}%")

    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == '__main__':
    import pandas as pd
    test_engine()
