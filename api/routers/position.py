"""Position Router（sq-0008-p4-batch2）
==================
拆自 api/main.py 的"仓位"段，含 2 个端点：
- GET  /position/{symbol}
- POST /position/{symbol}/add

position_manager 实例说明：
  main.py 在第 121 行创建 `position_manager = PositionManager()`，并被这 2 个端点使用。
  本 router 短期自建一份新实例（方案 A），P5 收尾时统一抽到 api/state.py 共享。
  短期内两端实例是分开的，行为差异：本端点写入的仓位不会反映到 main.py 中任何
  仍引用旧 position_manager 的代码（但本批次拆完后 main.py 已不再使用）。
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException

from api.helpers.pnl import calc_pnl
from api.schemas.position import PositionResponse
from api.state import cached_prices
from strategies.turtle.position import PositionManager

# 短期重复实例（P5 收尾会迁到 api.state）
position_manager = PositionManager()

router = APIRouter(prefix="/position", tags=["position"])


@router.get("/{symbol}", response_model=PositionResponse)
async def get_position(symbol: str):
    """
    查询仓位状态（会话级内存）
    GET /position/{symbol}
    """
    sym = symbol.upper()
    if sym in position_manager.positions:
        pos = position_manager.positions[sym]
        current_price = cached_prices.get(sym)
        unrealized_pnl = calc_pnl(pos, current_price) if current_price else None
        return PositionResponse(
            symbol=sym, direction=pos.direction, total_units=pos.total_units,
            avg_entry_price=pos.avg_entry_price, current_price=current_price,
            unrealized_pnl=unrealized_pnl,
            stops=[u.stop_price for u in pos.units],
            atr=pos.atr, timestamp=datetime.now().isoformat(),
            note="会话级内存持仓，服务重启后重置"
        )

    return PositionResponse(
        symbol=sym, direction=0, total_units=0, avg_entry_price=0.0,
        current_price=cached_prices.get(sym),
        unrealized_pnl=None, stops=[], atr=None,
        timestamp=datetime.now().isoformat(),
        note="无持仓"
    )


@router.post("/{symbol}/add")
async def add_position(symbol: str, direction: int, price: float, atr: float):
    """
    手动登记持仓（测试用）
    POST /position/{symbol}/add
    """
    sym = symbol.upper()
    result = position_manager.add_position(
        symbol=sym, direction=direction, entry_price=price,
        atr=atr, unit_size=1, high_55=price, low_55=price
    )
    if result is None:
        raise HTTPException(status_code=400, detail=f"{sym} 已有持仓")
    cached_prices[sym] = price
    return {
        "symbol": sym, "direction": direction, "entry_price": price,
        "atr": atr, "units": 1, "timestamp": datetime.now().isoformat()
    }
