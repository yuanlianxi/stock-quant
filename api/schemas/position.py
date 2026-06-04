"""Position domain schemas (Pydantic models).

Phase 3 (sq-0008-p3-schemas): 完整化版本。

字段来源：api/main.py L600-650 (/position/{symbol} 端点) 实际构造。
0 行为变更：保持与 main.py 完全一致。
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class PositionResponse(BaseModel):
    """仓位响应

    字段来源：api/main.py L600-650 /position/{symbol} 端点构造。
    """
    symbol: str = Field(..., description="品种代码")
    direction: int = Field(..., description="方向 1=long, -1=short, 0=无持仓")
    total_units: int = Field(..., description="总 unit 数")
    avg_entry_price: float = Field(..., description="平均入场价")
    current_price: Optional[float] = Field(None, description="当前价")
    unrealized_pnl: Optional[float] = Field(None, description="未实现盈亏")
    stops: List[float] = Field(..., description="各 unit 止损价列表")
    atr: Optional[float] = Field(None, description="持仓 ATR")
    timestamp: str = Field(..., description="响应时间 ISO 格式")
    note: Optional[str] = Field(None, description="备注（会话级内存提示）")
