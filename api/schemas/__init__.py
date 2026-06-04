"""Pydantic schemas by domain.

Schema 拆分原则：
- 每个域一个文件（common / backtest / signal / position / market / strategy / session / account）
- 跨域共享的放 common.py
- 跨域引用通过本包 re-export 兼容

Phase 3 (sq-0008-p3-schemas) 完整化版本：re-export 25 个 Pydantic 类，
便于 P4 router 阶段 import。
"""
from api.schemas import common, backtest, signal, market, position, strategy, session, account

# 常用 re-export（router 阶段方便）
from api.schemas.common import HealthResponse, ApiError
from api.schemas.backtest import (
    BacktestRequest, BacktestResponse, BacktestResult,
    BacktestRunSummary, BacktestRunDetail,
)
from api.schemas.signal import SignalResponse
from api.schemas.position import PositionResponse
from api.schemas.market import (
    ContractInfo, QuoteInfo, ContractListResponse, MainContractResponse,
)
from api.schemas.strategy import (
    StrategyCreateRequest, StrategyUpdateRequest,
    StrategyDetail, StrategySummary,
)
from api.schemas.session import (
    SessionCreateRequest, OrderAddRequest, OrderReduceRequest,
    SessionCloseRequest, LineOverrideRequest,
    SessionSummary, UnitInfo,
)
from api.schemas.account import (
    AccountOverview, AccountPosition, AccountTrade, AccountSession,
)

__all__ = [
    # 子模块
    "common", "backtest", "signal", "market", "position", "strategy", "session", "account",
    # Common
    "HealthResponse", "ApiError",
    # Backtest
    "BacktestRequest", "BacktestResponse", "BacktestResult",
    "BacktestRunSummary", "BacktestRunDetail",
    # Signal
    "SignalResponse",
    # Position
    "PositionResponse",
    # Market
    "ContractInfo", "QuoteInfo", "ContractListResponse", "MainContractResponse",
    # Strategy
    "StrategyCreateRequest", "StrategyUpdateRequest", "StrategyDetail", "StrategySummary",
    # Session
    "SessionCreateRequest", "OrderAddRequest", "OrderReduceRequest",
    "SessionCloseRequest", "LineOverrideRequest", "SessionSummary", "UnitInfo",
    # Account
    "AccountOverview", "AccountPosition", "AccountTrade", "AccountSession",
]
