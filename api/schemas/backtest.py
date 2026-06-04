"""Backtest domain schemas (Pydantic models).

Phase 3 (sq-0008-p3-schemas): 完整化版本。

字段来源：
- BacktestRequest: api/helpers/backtest_runner.py L120-150 实际使用
- BacktestResponse / BacktestResult / BacktestRunSummary / BacktestRunDetail:
  从 api/main.py L83-176 原 Pydantic 类原样迁出（0 行为变更，仅补充 Field 描述）
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class BacktestRequest(BaseModel):
    """回测请求（API 入口契约）。

    字段来源：api/helpers/backtest_runner.py L120-150 实际使用字段。
    """
    symbols: List[str] = Field(..., description="品种代码列表（必填，至少 1 个）")
    start_date: str = Field(..., description="起始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD")
    initial_capital: float = Field(1000000.0, description="初始资金")
    atr_period: int = Field(20, description="ATR 周期（默认 20）")
    entry_period: int = Field(55, description="入场突破周期（默认 55）")
    exit_period: int = Field(20, description="出场反向周期（默认 20）")
    unit_size: int = Field(1, description="单 unit 手数（默认 1）")
    max_units: int = Field(4, description="最大 unit 数（默认 4）")


class BacktestResponse(BaseModel):
    """回测任务提交响应（最小信息）。"""
    job_id: str = Field(..., description="回测任务 ID（内存版为 uuid[:8]，DB 版为 run_id）")
    status: str = Field(..., description="任务状态 running/completed/failed")
    submitted_at: str = Field(..., description="提交时间 ISO 格式")
    elapsed: float = Field(0.0, description="耗时（秒）")


class BacktestResult(BaseModel):
    """回测结果（内存版兼容字段）。"""
    job_id: str
    status: str
    symbols: List[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    max_drawdown: float
    trades: int
    sharpe_ratio: Optional[float] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class BacktestRunSummary(BaseModel):
    """历史回测列表项（精简）"""
    run_id: str
    strategy_id: str
    symbol: str
    start_date: str
    end_date: str
    status: str
    initial_capital: Optional[float] = None
    final_capital: Optional[float] = None
    total_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    total_trades: int = 0
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class BacktestRunDetail(BaseModel):
    """历史回测详情（完整）"""
    run_id: str
    strategy_id: str
    symbol: str
    start_date: str
    end_date: str
    status: str
    params: Optional[Dict[str, Any]] = None
    result_metrics: Optional[Dict[str, Any]] = None
    initial_capital: Optional[float] = None
    final_capital: Optional[float] = None
    total_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    total_trades: int = 0
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
