"""Account-related Pydantic models.

Phase 3 (sq-0008-p3-schemas): 完整化版本。

字段来源：
- AccountOverview: 推断（基于 /account/overview 端点返回的 summary 子结构 + 5 表聚合）
- AccountPosition: 推断（基于 sim_positions 表字段）
- AccountTrade: 推断（基于 sim_trades 表字段）
- AccountSession: 推断（基于 trade_sessions 表字段）
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AccountOverview(BaseModel):
    """账户概览（GET /account/overview）

    字段来源：/account/overview 端点 summary 子结构。
    """
    account_id: str = Field(..., description="账户 ID")
    total_pnl: float = Field(0.0, description="总盈亏（realized + unrealized）")
    today_pnl: float = Field(0.0, description="当日盈亏")
    position_count: int = Field(0, description="持仓数")
    active_sessions: int = Field(0, description="活跃 session 数")
    closed_sessions: int = Field(0, description="已平 session 数")
    initial_capital: float = Field(0.0, description="初始资金")
    current_capital: float = Field(0.0, description="当前资金 = balance + margin_used")
    balance: float = Field(0.0, description="账户余额")
    available: float = Field(0.0, description="可用资金")
    margin_used: float = Field(0.0, description="占用保证金")
    position_value: float = Field(0.0, description="持仓市值")
    unrealized_pnl: float = Field(0.0, description="未实现盈亏")
    realized_pnl: float = Field(0.0, description="已实现盈亏")
    open_units_count: int = Field(0, description="未平 unit 数")
    recent_trades_count: int = Field(0, description="最近成交数")
    win_rate: float = Field(0.0, description="胜率")
    max_drawdown: float = Field(0.0, description="最大回撤 %")


class AccountPosition(BaseModel):
    """账户持仓（GET /account/{account_id}/positions 列表项）

    字段来源：sim_positions 表字段。
    """
    account_id: str = Field(..., description="账户 ID")
    symbol: str = Field(..., description="品种代码")
    direction: str = Field(..., description="方向 long/short")
    hand_count: int = Field(..., description="手数")
    quantity: int = Field(0, description="数量")
    entry_price: float = Field(..., description="入场均价")
    avg_cost: float = Field(0.0, description="平均成本")
    current_price: float = Field(0.0, description="当前价")
    pnl: float = Field(0.0, description="浮动盈亏")
    unrealized_pnl: float = Field(0.0, description="未实现盈亏")
    pnl_pct: float = Field(0.0, description="盈亏百分比")
    session_id: str = Field(..., description="所属 Session ID")
    entry_at: str = Field(..., description="入场时间")


class AccountTrade(BaseModel):
    """账户成交（GET /account/{account_id}/trades 列表项）

    字段来源：sim_trades 表字段。
    """
    trade_id: str = Field(..., description="成交 ID")
    account_id: str = Field(..., description="账户 ID")
    symbol: str = Field(..., description="品种代码")
    contract_code: Optional[str] = Field(None, description="合约代码")
    direction: str = Field(..., description="方向 long/short")
    hand_count: int = Field(..., description="手数")
    filled_quantity: int = Field(0, description="成交数量")
    price: float = Field(..., description="成交价")
    filled_price: float = Field(0.0, description="成交均价")
    commission: float = Field(0.0, description="手续费")
    pnl: float = Field(0.0, description="本笔盈亏")
    ts: str = Field(..., description="成交时间")
    filled_at: str = Field(..., description="成交时间 ISO")
    session_id: Optional[str] = Field(None, description="所属 Session ID")
    strategy_id: Optional[str] = Field(None, description="策略 ID")


class AccountSession(BaseModel):
    """账户 Session（GET /account/{account_id}/sessions 列表项）

    字段来源：trade_sessions 表字段。
    """
    session_id: str = Field(..., description="Session ID")
    account_id: str = Field(..., description="账户 ID")
    symbol: str = Field(..., description="品种代码")
    strategy_id: str = Field(..., description="策略 ID")
    direction: str = Field(..., description="方向 long/short")
    status: str = Field(..., description="状态 open/closed/partial")
    entry_price: float = Field(..., description="入场价（首单）")
    opened_at: str = Field(..., description="开仓时间")
    entry_time: Optional[str] = Field(None, description="开仓时间 ISO（字段同义）")
    closed_at: Optional[str] = Field(None, description="平仓时间")
    pnl: float = Field(0.0, description="本 Session 盈亏")
    price_overrides: Dict[str, Any] = Field(default_factory=dict, description="价格线 override 字典")
