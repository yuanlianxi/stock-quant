"""Latest factor fetcher.

Phase 2 抽自 api/main.py L178-185。
"""
from typing import Optional

from data.data_loader import get_daily_signal_from_cache


def fetch_latest_factor(symbol: str) -> Optional[dict]:
    """获取最新市场因子——纯缓存读取，不请求任何外部接口。

    Args:
        symbol: 品种代码（如 AG、CU）

    Returns:
        dict: 包含 close / atr / high_55 / low_55 等字段；如无数据返回 None
    """
    try:
        return get_daily_signal_from_cache(symbol)
    except Exception as e:
        print(f"[信号] {symbol} 缓存读取失败: {e}")
        return None
