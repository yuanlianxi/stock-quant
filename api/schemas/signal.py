"""Signal domain schemas (Pydantic models).

Phase 3 (sq-0008-p3-schemas): 完整化版本。

字段来源：api/helpers/signal_calc.py L30-70 实际使用 + 原 P2 schemas/signal.py 字段。
0 行为变更：保持与 main.py / signal_calc.py 完全一致。
"""
from pydantic import BaseModel, Field
from typing import Optional


class SignalResponse(BaseModel):
    """信号响应 - 55 日突破信号

    字段来源：api/helpers/signal_calc.py L30-70 实际使用字段。
    """
    symbol: str = Field(..., description="品种代码")
    name: str = Field("", description="品种中文名")
    contract_code: str = Field("", description="主力合约代码")
    direction: int = Field(..., description="方向 1=long, -1=short, 0=none")
    signal_type: str = Field(..., description="信号类型 entry/exit/none")
    entry_price: Optional[float] = Field(None, description="入场/突破价")
    atr: Optional[float] = Field(None, description="ATR 20 日值")
    high_55: Optional[float] = Field(None, description="55 日最高价")
    low_55: Optional[float] = Field(None, description="55 日最低价")
    current_price: Optional[float] = Field(None, description="当前收盘价")
    timestamp: str = Field(..., description="信号生成时间 ISO 格式")
    note: Optional[str] = Field(None, description="备注（如数据不可用时给出原因）")
