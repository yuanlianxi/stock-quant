#!/usr/bin/env python3
"""回测运行脚本 - 样例"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.data_loader import get_data_loader


def main():
    # 示例：获取沪深 300ETF 数据
    loader = get_data_loader()

    print("获取沪深 300ETF (510300) 日线数据...")
    df = loader.get_etf_daily('510300', '2018-01-01', '2023-12-31')

    if not df.empty:
        print(f"获取到 {len(df)} 条数据")
        print(df.head())
    else:
        print("获取数据失败")


if __name__ == '__main__':
    main()
