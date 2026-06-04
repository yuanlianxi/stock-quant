"""Market data Pydantic models (contracts / quotes / main-contract).

Phase 3 (sq-0008-p3-schemas): 完整化版本。

字段来源：
- ContractInfo: api/main.py /contracts/{symbol} 端点 SQL 字段
- QuoteInfo: api/main.py /quotes/{contract_code} 端点 SQL 字段
- ContractListResponse / MainContractResponse: 端点 wrapper
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ContractInfo(BaseModel):
    """合约信息（futures_contracts 表）"""
    contract_code: str = Field(..., description="合约代码（如 ag2607）")
    symbol: str = Field(..., description="品种代码 AG/AU")
    name: Optional[str] = Field(None, description="品种中文名")
    exchange: Optional[str] = Field(None, description="交易所 SHFE/DCE/CZCE/GFEX/INE")
    is_main: bool = Field(False, description="是否主力合约（1/0 → bool）")
    main_rank: Optional[int] = Field(None, description="主力排名（1=主力，2=次主力...）")
    list_date: Optional[str] = Field(None, description="上市日期")
    expire_date: Optional[str] = Field(None, description="到期日期")
    contract_size: Optional[float] = Field(None, description="合约乘数")
    point_value: Optional[float] = Field(None, description="点值")
    tick: Optional[float] = Field(None, description="最小变动价位")
    margin_ratio: Optional[float] = Field(None, description="保证金率")
    status: Optional[str] = Field(None, description="合约状态")
    volume: int = Field(0, description="成交量")
    open_interest: int = Field(0, description="持仓量")


class QuoteInfo(BaseModel):
    """行情报价（futures_quotes 表）"""
    contract_code: str = Field(..., description="合约代码")
    last_price: float = Field(..., description="最新价")
    change: float = Field(0.0, description="涨跌（绝对值）")
    change_pct: float = Field(0.0, description="涨跌幅 %")
    volume: int = Field(0, description="成交量")
    open_interest: int = Field(0, description="持仓量")
    bid_price: Optional[float] = Field(None, description="买一价")
    ask_price: Optional[float] = Field(None, description="卖一价")
    bid_volume: Optional[int] = Field(None, description="买一量")
    ask_volume: Optional[int] = Field(None, description="卖一量")
    open: Optional[float] = Field(None, description="开盘价")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    preclose: Optional[float] = Field(None, description="昨收")
    presettlement: Optional[float] = Field(None, description="昨结算")
    settlement: Optional[float] = Field(None, description="今结算")
    ts: Optional[str] = Field(None, description="行情时间戳")
    updated_at: Optional[str] = Field(None, description="DB 最后更新时间")


class ContractListResponse(BaseModel):
    """合约列表响应（GET /contracts/{symbol}）"""
    symbol: str = Field(..., description="品种代码")
    contracts: List[ContractInfo] = Field(default_factory=list, description="合约列表")
    main_contract: Optional[str] = Field(None, description="主力合约代码")


class MainContractResponse(BaseModel):
    """主力合约响应（GET /main-contract/{symbol}）"""
    symbol: str = Field(..., description="品种代码")
    main_contract: str = Field(..., description="主力合约代码")
    main_rank: Optional[int] = Field(None, description="主力排名")
    last_price: Optional[float] = Field(None, description="最新价")
    exchange: Optional[str] = Field(None, description="交易所")
    expire_date: Optional[str] = Field(None, description="到期日期")
