"""Signal calculator.

Phase 2 抽自 api/main.py L187-237。
"""
from datetime import datetime
from typing import Optional

from api.helpers.factor import fetch_latest_factor
from api.schemas.signal import SignalResponse
from api.state import cached_prices
from data.data_loader import SYMBOL_NAME, get_contract_info

# AKSHARE_AVAILABLE 检测 —— 原 main.py 顶部 try/except 派生
try:
    import akshare as _ak  # noqa: F401
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False


def calc_signal(symbol: str) -> SignalResponse:
    """计算 55 日突破交易信号。

    返回 SignalResponse 含：symbol, name, contract_code, direction, signal_type,
    entry_price, atr, high_55, low_55, current_price, timestamp, note

    副作用：写入 `api.state.cached_prices[symbol]` 供 `/position/{symbol}` 端点读取。
    """
    # 先获取品种信息（不依赖缓存是否存在）
    contract_info = get_contract_info(symbol.upper()) if AKSHARE_AVAILABLE else {"contract_code": "", "name": SYMBOL_NAME.get(symbol.upper(), symbol.upper())}

    factors = fetch_latest_factor(symbol)
    if factors is None:
        return SignalResponse(
            symbol=symbol.upper(),
            name=contract_info.get("name", SYMBOL_NAME.get(symbol.upper(), symbol.upper())),
            contract_code=contract_info.get("contract_code", ""),
            direction=0, signal_type="none",
            entry_price=None, atr=None, high_55=None, low_55=None,
            current_price=None, timestamp=datetime.now().isoformat(),
            note="数据暂不可用（akshare 未安装或网络故障）"
        )

    close = factors["close"]
    atr = factors["atr"]
    high_55 = factors["high_55"]
    low_55 = factors["low_55"]
    cached_prices[symbol.upper()] = close

    direction = 0
    breakout_price = None
    signal_type = "none"

    if close >= high_55:
        direction = 1
        breakout_price = high_55
        signal_type = "entry"
    elif close <= low_55:
        direction = -1
        breakout_price = low_55
        signal_type = "entry"

    return SignalResponse(
        symbol=symbol.upper(),
        name=contract_info.get("name", SYMBOL_NAME.get(symbol.upper(), symbol.upper())),
        contract_code=contract_info.get("contract_code", ""),
        direction=direction,
        signal_type=signal_type,
        entry_price=breakout_price,
        atr=atr,
        high_55=high_55,
        low_55=low_55,
        current_price=close,
        timestamp=datetime.now().isoformat(),
        note=None
    )
