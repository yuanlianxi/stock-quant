"""Signal Router（sq-0008-p4-pilot）
================
拆自 api/main.py 的"信号"段，含 2 个端点：
- GET /signals/all
- GET /signals/{symbol}

P4-Pilot：先拆 1 个最简域 router 试水，验证模式 OK 后再批量拆剩余 10 个。

ALL_PRODUCTS 来源说明：
  不在本文件重复定义，直接从 data.data_loader 导入。
  data.data_loader.ALL_PRODUCTS 是项目内唯一 SSOT（来自 instruments.yaml），
  main.py 在第 78 行也是从这里 import 的。P5 收尾时无需为 ALL_PRODUCTS
  再做提取，已天然共享。
"""
from fastapi import APIRouter

from api.helpers.signal_calc import calc_signal
from api.schemas.signal import SignalResponse
from data.data_loader import ALL_PRODUCTS

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/all")
async def get_all_signals():
    """批量获取所有品种信号"""
    results = []
    for sym in ALL_PRODUCTS:
        try:
            sig = calc_signal(sym)
            results.append(sig)
        except Exception as e:
            results.append({"symbol": sym, "error": str(e)})
    return results


@router.get("/{symbol}", response_model=SignalResponse)
async def get_signal(symbol: str):
    """
    获取交易信号（55日突破）
    GET /signals/{symbol}
    """
    return calc_signal(symbol.upper())
