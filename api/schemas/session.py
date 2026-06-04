"""Session-related Pydantic models.

Phase 3 (sq-0008-p3-schemas): 完整化版本。

字段来源：
- SessionCreateRequest / OrderAddRequest / OrderReduceRequest / SessionCloseRequest /
  LineOverrideRequest: api/main.py L1057-1086 原 Pydantic 类
  （0 行为变更：保留原版字段名 account_id, contract_code, n_value, price, close_price, exit_price）
- SessionSummary / UnitInfo: 推断（基于 /sessions 端点和 position_units 表）
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class SessionCreateRequest(BaseModel):
    """建仓请求（POST /session）

    字段来源：api/main.py L1057-1065 原 Pydantic 类。
    """
    account_id: str = Field(..., description="账户 ID")
    strategy_id: str = Field(..., description="策略 ID")
    symbol: str = Field(..., description="品种代码")
    contract_code: str = Field(..., description="合约代码（如 ag2607）")
    direction: str = Field(..., description="方向 long / short")
    entry_price: float = Field(..., description="入场价")
    n_value: Optional[float] = Field(None, description="N 值（ATR 估算）")
    user_note: Optional[str] = Field(None, description="用户备注")


class OrderAddRequest(BaseModel):
    """加仓请求（POST /session/{id}/orders）

    字段来源：api/main.py L1068-1071 原 Pydantic 类。
    """
    price: float = Field(..., description="加仓价")
    n_value: Optional[float] = Field(None, description="N 值（加仓时 ATR 重算）")
    reason: str = Field("manual", description="加仓原因 manual/signal/auto")


class OrderReduceRequest(BaseModel):
    """减仓请求（POST /session/{id}/orders/reduce）

    字段来源：api/main.py L1074-1077 原 Pydantic 类。
    """
    unit_id: str = Field(..., description="Unit ID")
    close_price: float = Field(..., description="平仓价")
    reason: str = Field("manual", description="减仓原因 manual/stop/profit_take")


class SessionCloseRequest(BaseModel):
    """全平请求（POST /session/{id}/close）

    字段来源：api/main.py L1080-1082 原 Pydantic 类。
    """
    exit_price: float = Field(..., description="平仓价")
    reason: str = Field("manual", description="平仓原因 manual/stop/signal/timeout")


class LineOverrideRequest(BaseModel):
    """调价请求（PUT /session/{id}/line/{line_type}）

    字段来源：api/main.py L1085-1086 原 Pydantic 类。
    """
    price: Optional[float] = Field(None, description="新价格（None=取消 override）")


class SessionSummary(BaseModel):
    """Session 摘要（GET /sessions 列表项）

    字段来源：trade_sessions 表核心字段。
    """
    session_id: str = Field(..., description="Session ID")
    account_id: str = Field(..., description="账户 ID")
    symbol: str = Field(..., description="品种代码")
    strategy_id: str = Field(..., description="策略 ID")
    direction: str = Field(..., description="方向 long/short")
    status: str = Field(..., description="状态 open/closed/partial")
    entry_price: float = Field(..., description="入场价（首单）")
    current_price: Optional[float] = Field(None, description="当前价")
    pnl: float = Field(0.0, description="浮动盈亏")
    hand_count: int = Field(1, description="总手数")
    opened_at: str = Field(..., description="开仓时间")


class UnitInfo(BaseModel):
    """Unit 持仓单元（position_units 表）"""
    unit_id: str = Field(..., description="Unit ID")
    unit_no: int = Field(..., description="Unit 序号（1-4）")
    session_id: str = Field(..., description="所属 Session")
    account_id: str = Field(..., description="账户 ID")
    symbol: str = Field(..., description="品种代码")
    direction: str = Field(..., description="方向 long/short")
    hand_count: int = Field(..., description="手数")
    entry_price: float = Field(..., description="入场价")
    is_active: bool = Field(..., description="是否活跃")
    is_gap: bool = Field(False, description="是否 0.5N 加仓 unit")
    opened_at: str = Field(..., description="开 Unit 时间")
    closed_at: Optional[str] = Field(None, description="平 Unit 时间")
    close_price: Optional[float] = Field(None, description="平 Unit 价")
    pnl: float = Field(0.0, description="Unit PnL")
