"""
Stock Quant - FastAPI 服务
==============================
提供回测、信号、仓位查询接口
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import pandas as pd
from datetime import datetime, timedelta

from strategies.turtle.position import PositionManager
from strategies.turtle.factors import calc_entry_breakout

app = FastAPI(
    title="Stock Quant API",
    description="海龟交易系统回测与服务接口",
    version="0.8.4"
)

# ============================================================
# 数据层可用性检测
# ============================================================

AKSHARE_AVAILABLE = False
BACKTRADER_AVAILABLE = False

try:
    from data.data_loader import (
        get_daily_signal_from_cache,
        get_daily_data_from_cache,
        get_minute_from_cache,
        sync_all_minute_data,
        cache_status,
        get_contract_info,
        SYMBOL_NAME,
        ALL_PRODUCTS,
        get_turtle_signals,
        get_active_signals,
        get_turtle_alerts,
        detect_signals_for_symbol,
        check_bar_signal,
    )
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    pass

try:
    import backtrader as bt
    BACKTRADER_AVAILABLE = True
except ImportError:
    pass

# ============================================================
# 数据模型
# ============================================================

class BacktestRequest(BaseModel):
    symbols: list[str]
    start_date: str
    end_date: str
    initial_capital: float = 1000000.0
    atr_period: int = 20
    entry_period: int = 55
    exit_period: int = 20
    unit_size: int = 1
    max_units: int = 4

class BacktestResponse(BaseModel):
    job_id: str
    status: str
    submitted_at: str
    elapsed: float = 0.0

class BacktestResult(BaseModel):
    job_id: str
    status: str
    symbols: list[str]
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
    params: Optional[dict] = None
    result_metrics: Optional[dict] = None
    initial_capital: Optional[float] = None
    final_capital: Optional[float] = None
    total_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    total_trades: int = 0
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None

class SignalResponse(BaseModel):
    symbol: str
    name: str = ""
    contract_code: str = ""
    direction: int
    signal_type: str
    entry_price: Optional[float] = None
    atr: Optional[float] = None
    high_55: Optional[float] = None
    low_55: Optional[float] = None
    current_price: Optional[float] = None
    timestamp: str
    note: Optional[str] = None

class PositionResponse(BaseModel):
    symbol: str
    direction: int
    total_units: int
    avg_entry_price: float
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    stops: list[float]
    atr: Optional[float] = None
    timestamp: str
    note: Optional[str] = None

# ============================================================
# 全局状态
# ============================================================

backtest_jobs: dict[str, BacktestResult] = {}
position_manager = PositionManager()
_cached_prices: dict[str, float] = {}

# ============================================================
# 工具函数
# ============================================================

def _fetch_latest_factor(symbol: str) -> Optional[dict]:
    """获取最新市场因子——纯缓存读取，不请求任何外部接口"""
    try:
        return get_daily_signal_from_cache(symbol)
    except Exception as e:
        print(f"[信号] {symbol} 缓存读取失败: {e}")
        return None


def _calc_signal(symbol: str) -> SignalResponse:
    """计算 55 日突破交易信号"""
    # 先获取品种信息（不依赖缓存是否存在）
    contract_info = get_contract_info(symbol.upper()) if AKSHARE_AVAILABLE else {"contract_code": "", "name": SYMBOL_NAME.get(symbol.upper(), symbol.upper())}

    factors = _fetch_latest_factor(symbol)
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
    _cached_prices[symbol.upper()] = close

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


def _calc_pnl(pos, current_price: float, contract_size: float = 15.0) -> float:
    if pos.total_units == 0:
        return 0.0
    return (current_price - pos.avg_entry_price) * pos.direction * contract_size * pos.total_units


# ============================================================
# 简化海龟策略（Backtrader）
# ============================================================

if BACKTRADER_AVAILABLE:
    class _TurtleStrategy(bt.Strategy):
        params = dict(
            atr_period=20,
            entry_period=55,
            exit_period=20,
            max_units=4,
        )

        def __init__(self):
            self.order = None
            self.trade_count = 0
            self.units = 0
            self.direction = 0
            self.entry_price = 0
            self.stop_price = 0
            self.atr = 20.0
            # 使用 Backtrader 内置指标（避免 Line 对象切片问题）
            self._atr = bt.indicators.ATR(self.data, period=self.params.atr_period)
            self._high_55 = bt.indicators.Highest(self.data.high, period=self.params.entry_period)
            self._low_55 = bt.indicators.Lowest(self.data.low, period=self.params.entry_period)
            self._high_20 = bt.indicators.Highest(self.data.high, period=self.params.exit_period)
            self._low_20 = bt.indicators.Lowest(self.data.low, period=self.params.exit_period)

        def notify_order(self, order):
            if order.status in [order.Completed]:
                if order.isbuy():
                    self.units += 1
                    self.trade_count += 1
                elif order.issell():
                    self.units -= 1

        def next(self):
            # 确保有足够的历史数据
            if len(self) < max(self.params.entry_period, self.params.exit_period) + 2:
                return

            close = self.data.close[0]
            if self.order:
                return

            atr_val = self._atr[0]
            high_55 = self._high_55[0]
            low_55 = self._low_55[0]
            high_20 = self._high_20[0]
            low_20 = self._low_20[0]

            # 无持仓：55日突破入市
            if self.units == 0:
                if close >= high_55:
                    self.direction = 1
                    self.entry_price = close
                    self.stop_price = close - 2 * atr_val
                    self.units = 1
                    self.order = self.buy()
                    self.trade_count += 1
                    self.atr = atr_val
                elif close <= low_55:
                    self.direction = -1
                    self.entry_price = close
                    self.stop_price = close + 2 * atr_val
                    self.units = 1
                    self.order = self.sell()
                    self.trade_count += 1
                    self.atr = atr_val

            # 有持仓：止损或 20 日反向离市
            elif self.units > 0:
                if close <= self.stop_price or close <= low_20:
                    self.order = self.sell()
                    self.units = 0
            elif self.units < 0:
                if close >= self.stop_price or close >= high_20:
                    self.order = self.buy()
                    self.units = 0


def _run_backtest_sync(req: BacktestRequest) -> dict:
    """
    Phase 4.2 改造：持久化到 backtest_runs + sim_trades
    跑之前调 create_backtest_run、成交后 record_backtest_trade、跑完 complete/fail
    """
    # 导入持久化函数
    from backtest.backtest_engine import (
        create_backtest_run, record_backtest_trade,
        complete_backtest_run, fail_backtest_run
    )

    start_time = datetime.now()
    primary_symbol = req.symbols[0] if req.symbols else "AG"
    strategy_id = "turtle_v1"  # Phase 4 暂固定

    # 1. 创建 backtest_runs 记录（status=running）+ 自动建 sim_account
    run_id = create_backtest_run(
        strategy_id=strategy_id,
        symbol=primary_symbol,
        start_date=req.start_date,
        end_date=req.end_date,
        params={
            "initial_capital": req.initial_capital,
            "symbols": req.symbols,
            "atr_period": req.atr_period,
            "entry_period": req.entry_period,
            "exit_period": req.exit_period,
            "max_units": req.max_units,
        },
        initial_capital=req.initial_capital
    )

    n_trades = 0
    try:
        if not BACKTRADER_AVAILABLE:
            raise RuntimeError("backtrader 未安装，无法执行回测")
        if not AKSHARE_AVAILABLE:
            raise RuntimeError("akshare 未安装，无法获取数据")

        cerebro = bt.Cerebro()
        cerebro.broker.setcash(req.initial_capital)
        cerebro.broker.setcommission(commission=0.0003)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="dd")
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=0.03)

        end_str = req.end_date   # YYYY-MM-DD
        start_str = req.start_date   # YYYY-MM-DD

        for symbol in req.symbols:
            try:
                df = get_daily_data_from_cache(symbol, start_str, end_str)
                if df is None or len(df) == 0:
                    print(f"[回测] {symbol} 无数据")
                    continue
                df2 = df.reset_index()[["date", "open", "high", "low", "close", "volume"]].copy()
                df2.columns = ["datetime", "open", "high", "low", "close", "volume"]
                df2["datetime"] = pd.to_datetime(df2["datetime"])
                df2.set_index("datetime", inplace=True)
                data_feed = bt.feeds.PandasData(dataname=df2)
                cerebro.adddata(data_feed, name=symbol)
                print(f"[回测] {symbol} 加载 {len(df2)} 条")
            except Exception as e:
                print(f"[回测] {symbol} 加载失败: {e}")

        cerebro.addstrategy(_TurtleStrategy,
                            atr_period=req.atr_period,
                            entry_period=req.entry_period,
                            exit_period=req.exit_period,
                            max_units=req.max_units)

        initial_value = cerebro.broker.getvalue()
        results = cerebro.run()
        final_value = cerebro.broker.getvalue()

        strat = results[0]
        sharpe = None
        max_dd = 0.0
        if hasattr(strat, "analyzers"):
            dd_analysis = strat.analyzers.dd.get_analysis()
            if "max" in dd_analysis:
                max_dd = dd_analysis["max"].get("drawdown", 0.0)
            sh = strat.analyzers.sharpe.get_analysis()
            if "sharperatio" in sh:
                sharpe = sh["sharperatio"]

        n_trades = getattr(strat, "trade_count", 0)
        total_return = (final_value - initial_value) / initial_value if initial_value else 0
        total_return_pct = total_return * 100

        # 写入 sim_trades 成交记录（如果策略有 trade_list）
        if hasattr(strat, "trade_list") and strat.trade_list:
            from backtest.backtest_engine import record_backtest_trade
            for t in strat.trade_list:
                record_backtest_trade(
                    run_id=run_id,
                    trade_id=str(uuid.uuid4()),
                    order_id=str(uuid.uuid4()),
                    symbol=t.get("symbol", primary_symbol),
                    contract_code=t.get("contract_code", f"{primary_symbol.lower()}"),
                    direction=t.get("direction", "buy"),
                    filled_price=t.get("price", 0.0),
                    filled_quantity=t.get("size", 1),
                    filled_at=t.get("datetime", start_time.isoformat())
                )
                n_trades = max(n_trades, 1)  # 至少记为 1 笔

        result_metrics = {
            "sharpe": sharpe,
            "annual_return_pct": total_return_pct,
            "max_drawdown_pct": max_dd,
        }

        # 完成 backtest_runs
        complete_backtest_run(
            run_id=run_id,
            final_capital=final_value,
            total_return_pct=total_return_pct,
            max_drawdown_pct=max_dd,
            total_trades=n_trades,
            result_metrics=result_metrics
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        return {
            "run_id": run_id,
            "status": "completed",
            "final_capital": final_value,
            "total_return": total_return,
            "max_drawdown": max_dd,
            "trades": n_trades,
            "sharpe_ratio": sharpe,
            "elapsed": elapsed,
        }
    except Exception as e:
        # 标记 failed
        try:
            fail_backtest_run(run_id, str(e))
        except Exception:
            pass
        elapsed = (datetime.now() - start_time).total_seconds()
        return {
            "run_id": run_id,
            "status": "failed",
            "error": str(e),
            "elapsed": elapsed,
            "trades": 0,
        }


# ============================================================
# API 端点
# ============================================================

@app.get("/")
async def root():
    """主页看板"""
    return FileResponse(str(WWW_DIR / "index.html"))

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ---------- 回测 ----------

@app.post("/backtest/run", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest):
    """
    Phase 4.2 改造：持久化到 backtest_runs + sim_trades
    端点 URL 不变，旧内存版 fallback 仍保留
    """
    # 内存版兼容：先建一个占位
    job_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    job = BacktestResult(
        job_id=job_id, status="running",
        symbols=req.symbols, start_date=req.start_date, end_date=req.end_date,
        initial_capital=req.initial_capital, final_capital=0.0, total_return=0.0,
        max_drawdown=0.0, trades=0, sharpe_ratio=None, completed_at=None, error=None
    )
    backtest_jobs[job_id] = job

    elapsed = 0.0
    final_status = "completed"
    try:
        # Phase 4.2: 调持久化版 _run_backtest_sync（落库 + 写 sim_trades）
        result = _run_backtest_sync(req)
        elapsed = result.get("elapsed", 0.0)
        final_status = result.get("status", "completed")
        # 内存版同步状态
        if final_status == "completed":
            job.status = "completed"
            job.final_capital = result.get("final_capital", 0.0)
            job.total_return = result.get("total_return", 0.0)
            job.max_drawdown = result.get("max_drawdown", 0.0)
            job.trades = result.get("trades", 0)
            job.sharpe_ratio = result.get("sharpe_ratio")
            # job_id 改用 run_id（便于查 DB）
            run_id = result.get("run_id", job_id)
            backtest_jobs.pop(job_id, None)
            backtest_jobs[run_id] = job
            job_id = run_id
        else:
            job.status = "failed"
            job.error = result.get("error", "unknown")
    except Exception as e:
        final_status = "failed"
        job.status = "failed"
        job.error = str(e)

    job.completed_at = datetime.now().isoformat()
    return BacktestResponse(
        job_id=job_id, status=final_status, submitted_at=job.completed_at, elapsed=elapsed
    )


# ============================================================
# Phase 4.1: 回测持久化（DB 存储）— 必须在 /backtest/{job_id} 之前注册,否则会被拦截
# ============================================================
@app.get("/backtest/runs")
async def list_backtest_runs(strategy_id: Optional[str] = None,
                              symbol: Optional[str] = None,
                              status: Optional[str] = None,
                              limit: int = 50):
    """
    查历史回测列表（多条件过滤）
    GET /backtest/runs?strategy_id=turtle_v1
    """
    import sqlite3
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    conditions = []
    params = []
    if strategy_id:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)
    cur.execute(f"""
        SELECT run_id, strategy_id, symbol, start_date, end_date, status,
               initial_capital, final_capital, total_return_pct, max_drawdown_pct,
               total_trades, created_at, completed_at
        FROM backtest_runs
        WHERE {where}
        ORDER BY created_at DESC LIMIT ?
    """, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"count": len(rows), "runs": rows}


@app.get("/backtest/runs/{run_id}")
async def get_backtest_run_detail(run_id: str):
    """查历史回测详情"""
    import sqlite3, json
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM backtest_runs WHERE run_id = ?", (run_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"回测 {run_id} 不存在")
    data = dict(row)
    try:
        data['params'] = json.loads(data.pop('params_json') or '{}')
    except Exception:
        data['params'] = {}
    try:
        data['result_metrics'] = json.loads(data.pop('result_metrics_json') or '{}')
    except Exception:
        data['result_metrics'] = {}
    return data


@app.get("/backtest/runs/{run_id}/trades")
async def get_backtest_run_trades(run_id: str, limit: int = 100):
    """查历史回测的成交列表"""
    import sqlite3
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT trade_id, order_id, account_id, session_id, symbol, contract_code,
               direction, filled_price, filled_quantity, commission, platform_name, filled_at
        FROM sim_trades
        WHERE account_id LIKE 'backtest_%' OR session_id IN (SELECT session_id FROM trade_sessions WHERE strategy_id = (SELECT strategy_id FROM backtest_runs WHERE run_id = ?))
        ORDER BY filled_at DESC LIMIT ?
    """, (run_id, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"run_id": run_id, "count": len(rows), "trades": rows}


# ============================================================
# Phase 5.1 - 账户中心 API（5 端点）
# 设计依据：0006_数据模型与界面重构设计.md §6.5 账户中心 Tab
# 拆分：_requirements/data-model-redesign/01-design/02-backend.md §2.2
# ============================================================

@app.get("/account/overview")
async def account_overview(account_id: str = "sim_default", strategy_id: Optional[str] = None, days: int = 30):
    """
    账户总览（聚合 5 表 + 价格线）
    GET /account/overview?account_id=sim_default
    """
    import sqlite3, json
    from api.services.line_calculator import compute_lines

    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. 账户余额
    cur.execute("SELECT * FROM sim_account WHERE account_id = ?", (account_id,))
    acc_row = cur.fetchone()
    if not acc_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"账户 {account_id} 不存在")
    account = dict(acc_row)

    # 2. 持仓列表
    cur.execute("SELECT * FROM sim_positions WHERE account_id = ?", (account_id,))
    positions = [dict(r) for r in cur.fetchall()]

    # 3. Open sessions（含 price lines）
    if strategy_id:
        cur.execute("""
            SELECT * FROM trade_sessions
            WHERE account_id = ? AND strategy_id = ? AND status = 'open'
            ORDER BY entry_time DESC
        """, (account_id, strategy_id))
    else:
        cur.execute("""
            SELECT * FROM trade_sessions
            WHERE account_id = ? AND status = 'open'
            ORDER BY entry_time DESC
        """, (account_id,))
    open_sessions_raw = [dict(r) for r in cur.fetchall()]

    # 为每个 open session 算价格线
    open_sessions = []
    for s in open_sessions_raw:
        try:
            lines = compute_lines(s['session_id'], use_cache=True)
            s['lines'] = lines
        except Exception:
            s['lines'] = None
        # 解析 price_overrides_json
        try:
            s['price_overrides'] = json.loads(s.get('price_overrides_json') or '{}')
        except Exception:
            s['price_overrides'] = {}
        s.pop('price_overrides_json', None)
        open_sessions.append(s)

    # 4. 最近 N 天成交
    cur.execute("""
        SELECT * FROM sim_trades
        WHERE account_id = ? AND filled_at >= date('now', ?)
        ORDER BY filled_at DESC LIMIT 50
    """, (account_id, f'-{days} days'))
    recent_trades = [dict(r) for r in cur.fetchall()]

    # 5. 4 Unit 明细（来自所有 open session 的 position_units）
    all_units = []
    for s in open_sessions_raw:
        cur.execute("""
            SELECT * FROM position_units
            WHERE session_id = ? AND status = 'open'
            ORDER BY unit_index
        """, (s['session_id'],))
        units = [dict(r) for r in cur.fetchall()]
        for u in units:
            try:
                u['price_overrides'] = json.loads(u.get('price_overrides_json') or '{}') if u.get('price_overrides_json') else {}
            except Exception:
                u['price_overrides'] = {}
            u.pop('price_overrides_json', None)
        all_units.extend(units)

    conn.close()

    # 6. 计算总览统计
    total_position_value = sum((p.get('avg_cost') or 0) * (p.get('quantity') or 0) for p in positions)
    total_unrealized_pnl = sum(p.get('unrealized_pnl') or 0 for p in positions)
    total_realized_pnl = account.get('realized_pnl') or 0

    return {
        "account": account,
        "summary": {
            "balance": account.get('balance', 0),
            "available": account.get('available', 0),
            "margin_used": account.get('margin_used', 0),
            "position_value": round(total_position_value, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "realized_pnl": round(total_realized_pnl, 2),
            "open_sessions_count": len(open_sessions),
            "open_units_count": len(all_units),
            "recent_trades_count": len(recent_trades)
        },
        "positions": positions,
        "open_sessions": open_sessions,
        "open_units": all_units,
        "recent_trades": recent_trades,
        "days": days
    }


@app.get("/account/{account_id}/positions")
async def account_positions(account_id: str):
    """账户持仓列表"""
    import sqlite3
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM sim_positions WHERE account_id = ?", (account_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"account_id": account_id, "count": len(rows), "positions": rows}


@app.get("/account/{account_id}/units")
async def account_units(account_id: str, status: Optional[str] = "open"):
    """账户 4 Unit 明细（按 session_id 分组）"""
    import sqlite3, json
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if status:
        cur.execute("""
            SELECT * FROM position_units
            WHERE account_id = ? AND status = ?
            ORDER BY session_id, unit_index
        """, (account_id, status))
    else:
        cur.execute("""
            SELECT * FROM position_units
            WHERE account_id = ?
            ORDER BY session_id, unit_index
        """, (account_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    # 解析 price_overrides_json
    for r in rows:
        if 'price_overrides_json' in r:
            try:
                r['price_overrides'] = json.loads(r.pop('price_overrides_json') or '{}') if r.get('price_overrides_json') else {}
            except Exception:
                r['price_overrides'] = {}
                r.pop('price_overrides_json', None)
        else:
            r['price_overrides'] = {}

    # 按 session_id 分组
    by_session = {}
    for u in rows:
        sid = u['session_id']
        if sid not in by_session:
            by_session[sid] = []
        by_session[sid].append(u)

    return {
        "account_id": account_id,
        "status": status or "all",
        "count": len(rows),
        "by_session": by_session,
        "units": rows
    }


@app.get("/account/{account_id}/sessions")
async def account_sessions(account_id: str, status: Optional[str] = None,
                           strategy_id: Optional[str] = None, limit: int = 50):
    """账户 session 列表"""
    import sqlite3, json
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    conditions = ["account_id = ?"]
    params = [account_id]
    if status:
        conditions.append("status = ?")
        params.append(status)
    if strategy_id:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)
    params.append(limit)
    where = " AND ".join(conditions)
    cur.execute(f"""
        SELECT * FROM trade_sessions
        WHERE {where}
        ORDER BY entry_time DESC LIMIT ?
    """, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    for r in rows:
        if 'price_overrides_json' in r:
            try:
                r['price_overrides'] = json.loads(r.pop('price_overrides_json') or '{}') if r.get('price_overrides_json') else {}
            except Exception:
                r['price_overrides'] = {}
                r.pop('price_overrides_json', None)
        else:
            r['price_overrides'] = {}

    return {
        "account_id": account_id,
        "status": status or "all",
        "strategy_id": strategy_id or "all",
        "count": len(rows),
        "sessions": rows
    }


@app.get("/account/{account_id}/trades")
async def account_trades(account_id: str, days: int = 30, limit: int = 100):
    """账户成交记录"""
    import sqlite3
    from datetime import datetime, timedelta
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    cur.execute("""
        SELECT * FROM sim_trades
        WHERE account_id = ? AND filled_at >= ?
        ORDER BY filled_at DESC LIMIT ?
    """, (account_id, since, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {
        "account_id": account_id,
        "days": days,
        "count": len(rows),
        "trades": rows
    }


@app.get("/backtest/{job_id}")
async def get_backtest(job_id: str):
    """Phase 4.2 改造：优先查 DB（backtest_runs），fallback 到内存版"""
    import sqlite3, json
    # 1. 先查内存版（兼容）
    if job_id in backtest_jobs:
        return backtest_jobs[job_id]
    # 2. 查 DB
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM backtest_runs WHERE run_id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"回测 {job_id} 不存在")
    data = dict(row)
    try:
        data['params'] = json.loads(data.pop('params_json') or '{}')
    except Exception:
        data['params'] = {}
    try:
        data['result_metrics'] = json.loads(data.pop('result_metrics_json') or '{}')
    except Exception:
        data['result_metrics'] = {}
    return data

# ---------- 信号 ----------

@app.get("/signals/all")
async def get_all_signals():
    """批量获取所有品种信号"""
    results = []
    for sym in ALL_PRODUCTS:
        try:
            sig = _calc_signal(sym)
            results.append(sig)
        except Exception as e:
            results.append({"symbol": sym, "error": str(e)})
    return results


@app.get("/signals/{symbol}", response_model=SignalResponse)
async def get_signal(symbol: str):
    """
    获取交易信号（55日突破）
    GET /signals/{symbol}
    """
    return _calc_signal(symbol.upper())

# ---------- 仓位 ----------

@app.get("/position/{symbol}", response_model=PositionResponse)
async def get_position(symbol: str):
    """
    查询仓位状态（会话级内存）
    GET /position/{symbol}
    """
    sym = symbol.upper()
    if sym in position_manager.positions:
        pos = position_manager.positions[sym]
        current_price = _cached_prices.get(sym)
        unrealized_pnl = _calc_pnl(pos, current_price) if current_price else None
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
        current_price=_cached_prices.get(sym),
        unrealized_pnl=None, stops=[], atr=None,
        timestamp=datetime.now().isoformat(),
        note="无持仓"
    )


@app.post("/position/{symbol}/add")
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
    _cached_prices[sym] = price
    return {
        "symbol": sym, "direction": direction, "entry_price": price,
        "atr": atr, "units": 1, "timestamp": datetime.now().isoformat()
    }

# ---------- Phase 1.3 新增：合约 / 行情 / 主力查询 ----------

@app.get("/contracts/{symbol}")
async def get_contracts(symbol: str):
    """
    查询某品种的所有合约（含主力标记）
    GET /contracts/AG

    返回：{
        "symbol": "AG",
        "count": 4,
        "main_contract": "ag2607",
        "contracts": [
            {"contract_code": "ag2607", "is_main": 1, "main_rank": 1, ...},
            ...
        ]
    }
    """
    import sqlite3
    sym = symbol.upper()
    try:
        conn = sqlite3.connect('data/futures_akshare.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT contract_code, symbol, name, exchange, list_date, expire_date,
                   is_main, main_rank, contract_size, point_value, tick,
                   margin_ratio, status
            FROM futures_contracts
            WHERE symbol = ?
            ORDER BY is_main DESC, main_rank ASC
        """, (sym,))
        rows = [dict(row) for row in cur.fetchall()]
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询合约失败: {e}")

    if not rows:
        return {
            "symbol": sym, "count": 0, "main_contract": None,
            "contracts": [],
            "note": f"无 {sym} 合约数据，请先运行 sync_all_contracts_and_main()"
        }

    main = next((r["contract_code"] for r in rows if r["is_main"] == 1), None)
    return {"symbol": sym, "count": len(rows), "main_contract": main, "contracts": rows}


@app.get("/quotes/{contract_code}")
async def get_quote(contract_code: str):
    """
    查询某合约实时行情
    GET /quotes/ag2607

    返回：{"contract_code": "ag2607", "data": {...} | None, "note": "..."}
    """
    import sqlite3
    code = contract_code.lower()
    try:
        conn = sqlite3.connect('data/futures_akshare.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT contract_code, symbol, trade, change_abs, change_pct,
                   open, high, low, preclose, presettlement, settlement,
                   volume, position, bidprice1, askprice1, bidvol1, askvol1,
                   ticktime, updated_at
            FROM futures_quotes
            WHERE contract_code = ?
        """, (code,))
        row = cur.fetchone()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询行情失败: {e}")

    if not row:
        return {
            "contract_code": code, "data": None,
            "note": f"无 {code} 行情数据，请等待实时同步或调用 POST /quotes/sync"
        }

    return {"contract_code": code, "data": dict(row)}


@app.get("/main-contract/{symbol}")
async def get_main_contract(symbol: str):
    """
    快速查询某品种主力合约
    GET /main-contract/AG

    返回：{"symbol": "AG", "main_contract": "ag2607", "main_rank": 1, ...}
    """
    import sqlite3
    sym = symbol.upper()
    try:
        conn = sqlite3.connect('data/futures_akshare.db')
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT contract_code, main_rank, exchange, expire_date
            FROM futures_contracts
            WHERE symbol = ? AND is_main = 1
            LIMIT 1
        """, (sym,))
        row = cur.fetchone()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询主力合约失败: {e}")

    if not row:
        return {
            "symbol": sym, "main_contract": None, "main_rank": None,
            "note": f"未识别 {sym} 主力合约，请先调用 sync_all_contracts_and_main()"
        }

    return {
        "symbol": sym,
        "main_contract": row["contract_code"],
        "main_rank": row["main_rank"],
        "exchange": row["exchange"],
        "expire_date": row["expire_date"],
    }


# ---------- Phase 2.3: 策略 CRUD + 历史查询（7 个端点） ----------

class StrategyCreateRequest(BaseModel):
    strategy_id: str
    name: str
    type: str
    version: int = 1
    description: str = ""
    params: dict = {}
    is_active: int = 1
    is_paper: int = 1


class StrategyUpdateRequest(BaseModel):
    params: dict
    change_reason: str = ""
    changed_by: str = "user"


@app.get("/strategies")
async def list_strategies(include_inactive: bool = False):
    """
    列出所有策略
    GET /strategies?include_inactive=true
    返回：{
        "count": N,
        "strategies": [
            {"strategy_id": "...", "name": "...", "type": "...", "version": 1, "is_active": 1, "params": {...}},
            ...
        ]
    }
    """
    import sqlite3, json
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if include_inactive:
        cur.execute("SELECT strategy_id, name, type, version, description, params_json, is_active, is_paper, created_at, updated_at FROM strategies ORDER BY strategy_id")
    else:
        cur.execute("SELECT strategy_id, name, type, version, description, params_json, is_active, is_paper, created_at, updated_at FROM strategies WHERE is_active = 1 ORDER BY strategy_id")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    for r in rows:
        try:
            r['params'] = json.loads(r.pop('params_json')) if r.get('params_json') else {}
        except Exception:
            r['params'] = {}
    return {"count": len(rows), "strategies": rows}


@app.get("/strategies/{strategy_id}")
async def get_strategy_detail(strategy_id: str):
    """查单个策略详情"""
    import sqlite3, json
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM strategies WHERE strategy_id = ?", (strategy_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

    data = dict(row)
    try:
        data['params'] = json.loads(data.pop('params_json')) if data.get('params_json') else {}
    except Exception:
        data['params'] = {}
    return data


@app.post("/strategies")
async def create_strategy(req: StrategyCreateRequest):
    """
    创建策略（同时写 strategy_param_history 第一条）
    """
    import sqlite3, json
    from datetime import datetime
    conn = sqlite3.connect('data/futures_akshare.db')
    cur = conn.cursor()

    # 检查 UNIQUE(name, version)
    cur.execute("SELECT 1 FROM strategies WHERE name = ? AND version = ?", (req.name, req.version))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail=f"策略 {req.name} v{req.version} 已存在")

    now = datetime.now().isoformat()
    try:
        cur.execute("""
            INSERT INTO strategies(strategy_id, name, version, type, description, params_json, is_active, is_paper, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (req.strategy_id, req.name, req.version, req.type, req.description,
              json.dumps(req.params, ensure_ascii=False), req.is_active, req.is_paper, now, now))

        # 写第一条参数历史
        cur.execute("""
            INSERT INTO strategy_param_history(strategy_id, name, version, params_json, changed_at, changed_by, change_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (req.strategy_id, req.name, req.version,
              json.dumps(req.params, ensure_ascii=False), now, 'system', '创建策略'))

        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.close()
        raise HTTPException(status_code=409, detail=f"DB 完整性错误：{e}")
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

    conn.close()
    return {"created": req.strategy_id, "version": req.version, "params_history_id": cur.lastrowid}


@app.put("/strategies/{strategy_id}")
async def update_strategy(strategy_id: str, req: StrategyUpdateRequest):
    """
    更新策略参数（同时写 strategy_param_history）
    """
    import sqlite3, json
    from datetime import datetime
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT name, version FROM strategies WHERE strategy_id = ?", (strategy_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

    now = datetime.now().isoformat()
    try:
        cur.execute("""
            UPDATE strategies
            SET params_json = ?, updated_at = ?
            WHERE strategy_id = ?
        """, (json.dumps(req.params, ensure_ascii=False), now, strategy_id))

        cur.execute("""
            INSERT INTO strategy_param_history(strategy_id, name, version, params_json, changed_at, changed_by, change_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (strategy_id, row["name"], row["version"],
              json.dumps(req.params, ensure_ascii=False), now, req.changed_by, req.change_reason))

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

    conn.close()
    return {"updated": strategy_id, "params_history_id": cur.lastrowid}


@app.delete("/strategies/{strategy_id}")
async def soft_delete_strategy(strategy_id: str):
    """
    软删除（is_active = 0），保留历史
    """
    import sqlite3
    from datetime import datetime
    conn = sqlite3.connect('data/futures_akshare.db')
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM strategies WHERE strategy_id = ?", (strategy_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")

    now = datetime.now().isoformat()
    cur.execute("UPDATE strategies SET is_active = 0, updated_at = ? WHERE strategy_id = ?", (now, strategy_id))
    conn.commit()
    conn.close()
    return {"deactivated": strategy_id, "timestamp": now}


@app.get("/strategies/{strategy_id}/signals")
async def get_strategy_signals(strategy_id: str, symbol: str = "", days: int = 30, limit: int = 100):
    """
    查信号历史（v1.3 精简：仅 entry_long / entry_short）
    GET /strategies/turtle_v1/signals?symbol=AG&days=30
    """
    import sqlite3
    from datetime import datetime, timedelta
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    since = (datetime.now() - timedelta(days=days)).isoformat()

    if symbol:
        cur.execute("""
            SELECT * FROM strategy_signals
            WHERE strategy_id = ? AND symbol = ? AND bar_time >= ?
            ORDER BY bar_time DESC LIMIT ?
        """, (strategy_id, symbol, since, limit))
    else:
        cur.execute("""
            SELECT * FROM strategy_signals
            WHERE strategy_id = ? AND bar_time >= ?
            ORDER BY bar_time DESC LIMIT ?
        """, (strategy_id, since, limit))

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    return {
        "strategy_id": strategy_id,
        "symbol": symbol or "all",
        "days": days,
        "count": len(rows),
        "signals": rows
    }


@app.get("/strategies/{strategy_id}/param-history")
async def get_param_history(strategy_id: str, limit: int = 50):
    """
    查参数迭代历史
    GET /strategies/turtle_v1/param-history?limit=20
    """
    import sqlite3
    import json
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM strategy_param_history
        WHERE strategy_id = ?
        ORDER BY changed_at DESC LIMIT ?
    """, (strategy_id, limit))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    # 解析 params_json
    for r in rows:
        try:
            r['params'] = json.loads(r.pop('params_json')) if r.get('params_json') else {}
        except Exception:
            r['params'] = {}

    return {"strategy_id": strategy_id, "count": len(rows), "history": rows}


@app.get("/strategies/{strategy_id}/events")
async def get_strategy_events(strategy_id: str, days: int = 30, limit: int = 100):
    """
    查策略事件日志
    GET /strategies/turtle_v1/events?days=7
    """
    import sqlite3
    import json
    from datetime import datetime, timedelta
    conn = sqlite3.connect('data/futures_akshare.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    cur.execute("""
        SELECT * FROM strategy_event_log
        WHERE strategy_id = ? AND event_at >= ?
        ORDER BY event_at DESC LIMIT ?
    """, (strategy_id, since, limit))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()

    # 解析 context_json
    for r in rows:
        try:
            r['context'] = json.loads(r.pop('context_json')) if r.get('context_json') else {}
        except Exception:
            r['context'] = {}

    return {"strategy_id": strategy_id, "days": days, "count": len(rows), "events": rows}


# ============================================================
# Session 管理 API（v1.4 Phase 3.6）
# ============================================================

class SessionCreateRequest(BaseModel):
    account_id: str
    strategy_id: str
    symbol: str
    contract_code: str
    direction: str  # long / short
    entry_price: float
    n_value: Optional[float] = None
    user_note: Optional[str] = None


class OrderAddRequest(BaseModel):
    price: float
    n_value: Optional[float] = None
    reason: str = "manual"


class OrderReduceRequest(BaseModel):
    unit_id: str
    close_price: float
    reason: str = "manual"


class SessionCloseRequest(BaseModel):
    exit_price: float
    reason: str = "manual"


class LineOverrideRequest(BaseModel):
    price: Optional[float] = None  # None = 取消 override


@app.post("/session")
async def create_session(req: SessionCreateRequest):
    """
    手动建仓：创建 trade_session + 第 1 个 unit

    Errors:
        409: 同一 (account, strategy, direction) 在去重窗口内重复
        500: FK 约束失败 / DB 错误
    """
    import sqlite3
    from api.services.sim_engine import open_session

    # 应用层重复检查：
    # 1) 同一 (account, strategy, direction) 已有 open session → 拒
    # 2) 同一组合 60 秒内创建过 session（去重窗口）→ 拒
    conn = sqlite3.connect("data/futures_akshare.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM trade_sessions
        WHERE account_id = ? AND strategy_id = ? AND direction = ?
          AND status = 'open'
        LIMIT 1
        """,
        (req.account_id, req.strategy_id, req.direction),
    )
    if cur.fetchone() is not None:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=(
                f"Session 已存在（account={req.account_id} "
                f"strategy={req.strategy_id} direction={req.direction} 已有 open session）"
            ),
        )
    cur.execute(
        """
        SELECT 1 FROM trade_sessions
        WHERE account_id = ? AND strategy_id = ? AND direction = ?
          AND entry_time >= datetime('now', '-60 seconds')
        LIMIT 1
        """,
        (req.account_id, req.strategy_id, req.direction),
    )
    if cur.fetchone() is not None:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=(
                f"Session 重复（account={req.account_id} "
                f"strategy={req.strategy_id} direction={req.direction} 60 秒内已创建）"
            ),
        )
    conn.close()

    try:
        session_id = open_session(
            account_id=req.account_id,
            strategy_id=req.strategy_id,
            symbol=req.symbol,
            contract_code=req.contract_code,
            direction=req.direction,
            entry_price=req.entry_price,
            n_value=req.n_value,
        )
        return {
            "session_id": session_id,
            "status": "open",
            "current_units": 1,
            "first_entry_price": req.entry_price,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/{session_id}/orders")
async def session_orders(session_id: str, req: OrderAddRequest):
    """
    加仓（海龟 0.5N 间隔检测由调用方负责，API 只管加）

    Returns:
        {"unit_id": "...", "session_id": "...", "action": "add"}
    """
    from api.services.sim_engine import add_unit
    from api.services.session_lifecycle import with_session_lock, SessionLockedError

    try:
        with with_session_lock(session_id, "api_caller"):
            unit_id = add_unit(session_id, req.price, req.n_value)
            return {"unit_id": unit_id, "session_id": session_id, "action": "add"}
    except SessionLockedError as e:
        raise HTTPException(status_code=423, detail=f"Session 被锁定: {e.holder}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/{session_id}/orders/reduce")
async def session_orders_reduce(session_id: str, req: OrderReduceRequest):
    """减仓单个 unit"""
    from api.services.sim_engine import close_unit
    from api.services.session_lifecycle import with_session_lock, SessionLockedError

    try:
        with with_session_lock(session_id, "api_caller"):
            ok = close_unit(req.unit_id, req.close_price, req.reason)
            return {"ok": ok, "unit_id": req.unit_id, "action": "reduce"}
    except SessionLockedError as e:
        raise HTTPException(status_code=423, detail=f"Session 被锁定: {e.holder}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/{session_id}/close")
async def close_session_endpoint(session_id: str, req: SessionCloseRequest):
    """全部平仓"""
    from api.services.sim_engine import close_session
    from api.services.session_lifecycle import with_session_lock, SessionLockedError

    try:
        with with_session_lock(session_id, "api_caller"):
            ok = close_session(session_id, req.exit_price, req.reason)
            return {
                "ok": ok,
                "session_id": session_id,
                "action": "close_all",
                "reason": req.reason,
            }
    except SessionLockedError as e:
        raise HTTPException(status_code=423, detail=f"Session 被锁定: {e.holder}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{session_id}/events")
async def get_session_events(
    session_id: str,
    event_type: Optional[str] = None,
    days: int = 30,
    limit: int = 100,
):
    """
    查 session 事件流水（v1.4 核心端点）
    GET /session/{id}/events?event_type=line_overridden&days=7
    """
    from api.services.event_logger import query_events

    events = query_events(
        session_id=session_id, event_type=event_type, days=days, limit=limit
    )
    return {
        "session_id": session_id,
        "event_type": event_type or "all",
        "days": days,
        "count": len(events),
        "events": events,
    }


@app.get("/session/{session_id}/trade-process")
async def get_trade_process(
    session_id: str,
    event_type: Optional[str] = None,
    days: int = 30,
    limit: int = 100,
):
    """
    查海龟交易过程流水（v1.5 Phase 3.8 核心端点）
    GET /session/{id}/trade-process
    GET /session/{id}/trade-process?event_type=stop_loss_check
    GET /session/{id}/trade-process?event_type=entry_signal&days=7
    """
    from strategies.trade_process_logger import query_trade_process, get_trade_process_summary

    events = query_trade_process(
        session_id=session_id, event_type=event_type, days=days, limit=limit
    )
    summary = get_trade_process_summary(session_id)
    return {
        "session_id": session_id,
        "event_type": event_type or "all",
        "days": days,
        "count": len(events),
        "summary": summary,
        "events": events,
    }


@app.get("/sessions")
async def list_sessions_endpoint(
    account_id: Optional[str] = None,
    status: Optional[str] = None,
    strategy_id: Optional[str] = None,
    limit: int = 100,
):
    """
    查 sessions 列表（多条件过滤）
    GET /sessions?status=open
    GET /sessions?account_id=sim_default&status=closed
    """
    from api.services.session_lifecycle import list_sessions

    sessions = list_sessions(
        account_id=account_id, status=status, strategy_id=strategy_id, limit=limit
    )
    return {"count": len(sessions), "sessions": sessions}


@app.get("/session/{session_id}/lines")
async def get_session_lines(session_id: str, use_cache: bool = True):
    """
    查价格线（实时计算 + 缓存）
    GET /session/{id}/lines
    """
    from api.services.line_calculator import compute_lines

    try:
        lines = compute_lines(session_id, use_cache=use_cache)
        return lines
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/session/{session_id}/line/{line_type}")
async def override_line_endpoint(
    session_id: str, line_type: str, req: LineOverrideRequest
):
    """
    用户调价

    PUT /session/{id}/line/stop_loss
    Body: {"price": 17000.0}

    PUT /session/{id}/line/stop_loss
    Body: {"price": null}  # 取消 override
    """
    from api.services.line_calculator import override_line
    from api.services.session_lifecycle import with_session_lock, SessionLockedError

    try:
        with with_session_lock(session_id, "api_caller"):
            result = override_line(session_id, line_type, req.price)
            return result
    except SessionLockedError as e:
        raise HTTPException(status_code=423, detail=f"Session 被锁定: {e.holder}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- 分时数据同步 ----------

@app.get("/minute/{symbol}")
async def get_minute_data(symbol: str, period: str = "5min", limit: int = 500, date: str = "", days: int = 0):
    """
    查询某品种分时数据（纯缓存，不请求外部）
    GET /minute/{symbol}?period=5min&date=2026-05-28   -> 指定单天
    GET /minute/{symbol}?period=5min&days=3            -> 近3天
    GET /minute/{symbol}?period=5min                  -> 默认今天

    v1.5：records 每行新增 `date` 字段（YYYY-MM-DD），如 DB 中 date 为 NULL 则从 datetime 派生。
    """
    sym = symbol.upper()
    try:
        df = get_minute_from_cache(sym, period=period, limit=limit, date=date, days=days)
        if df is None or len(df) == 0:
            note = f"无 {date} 的缓存数据" if date else (f"近{days}天无数据" if days else "无今天缓存数据，请先调用 /minute/sync 同步")
            return {"symbol": sym, "period": period, "date": date or (f"近{days}天" if days else "today"), "records": [], "note": note}
        # v1.5：补齐 date 字段（DB 中为 NULL 时从 datetime 派生前 10 位）
        has_date_col = "date" in df.columns
        records = []
        for idx, row in df.iterrows():
            r = {"datetime": str(idx), **row.to_dict()}
            if not has_date_col or r.get("date") is None or (isinstance(r.get("date"), float) and pd.isna(r.get("date"))):
                # 从 datetime 字符串前 10 位派生
                r["date"] = str(idx)[:10]
            records.append(r)
        date_label = date or (f"近{days}天" if days else "today")
        return {"symbol": sym, "period": period, "date": date_label, "count": len(records), "records": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/daily/{symbol}")
async def get_daily_data(symbol: str, days: int = 30, include_atr: bool = True):
    """
    查询某品种日线数据（v1.5：含 atr + main_contract_code 字段）
    GET /daily/AG?days=30         -> 近 30 天
    GET /daily/AG?days=365        -> 近 1 年
    GET /daily/AG?days=1095       -> 近 3 年
    GET /daily/AG?days=30&include_atr=false  -> 关闭 atr 字段
    """
    from datetime import datetime, timedelta
    import math
    sym = symbol.upper()
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        df = get_daily_data_from_cache(sym, start_date, end_date)
        if df is None or len(df) == 0:
            return {"symbol": sym, "date": f"近{days}天", "records": [], "note": f"无最近{days}天数据"}
        # v1.5：增加 atr + main_contract_code 字段
        records = []
        for idx, row in df.iterrows():
            r = {
                "datetime": str(idx.date()),
                "date": str(idx.date()),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
            }
            # v1.5 新增：atr（data_loader 已计算）
            if include_atr and "atr" in df.columns:
                atr_val = row.get("atr")
                if atr_val is not None and not (isinstance(atr_val, float) and math.isnan(atr_val)):
                    r["atr"] = atr_val
                else:
                    r["atr"] = None
            # v1.5 新增：main_contract_code（DB 中读取，可能为 NULL）
            if "main_contract_code" in df.columns:
                mc = row.get("main_contract_code")
                if mc is not None and not (isinstance(mc, float) and math.isnan(mc)):
                    r["main_contract_code"] = mc
                else:
                    r["main_contract_code"] = None
            # 过滤无效 OHLC
            if all(r.get(c) is not None and not (isinstance(r[c], float) and math.isnan(r[c])) for c in ["open", "high", "low", "close"]):
                records.append(r)
        return {"symbol": sym, "date": f"近{days}天", "count": len(records), "records": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/status")
async def get_cache_status():
    """缓存状态诊断"""
    return cache_status()


# ---------- 海龟信号 API ----------

@app.get("/turtle/signals/{symbol}")
async def get_symbol_turtle_signals(symbol: str, days: int = 30):
    """查询某品种近 N 天的所有信号"""
    return get_turtle_signals(symbol.upper(), days=days)


@app.get("/turtle/signals/active")
async def get_turtle_active():
    """当前所有未离市的入场信号"""
    return get_active_signals()


@app.get("/turtle/signals/alerts")
async def get_turtle_alerts_endpoint(since_minutes: int = 30):
    """最近 N 分钟内的新信号（用于前端推送）"""
    return get_turtle_alerts(since_minutes=since_minutes)


@app.post("/turtle/scan/{symbol}")
async def scan_symbol_signals(symbol: str, period: str = "5min"):
    """对指定品种扫描历史分钟数据，检测所有信号"""
    sigs = detect_signals_for_symbol(symbol.upper(), period=period)
    return {"symbol": symbol.upper(), "signals_found": len(sigs), "signals": sigs}


@app.post("/turtle/scan/all")
async def scan_all_signals(period: str = "5min"):
    """全量扫描所有品种历史信号"""
    results = {}
    for sym in ALL_PRODUCTS:
        try:
            sigs = detect_signals_for_symbol(sym, period=period)
            results[sym] = {"signals_found": len(sigs), "signals": sigs}
        except Exception as e:
            results[sym] = {"error": str(e)}
    total = sum(v.get("signals_found", 0) for v in results.values())
    return {"total_signals": total, "details": results}


@app.get("/turtle/signal/latest")
async def get_latest_signal(symbol: str):
    """获取某品种最新一条信号"""
    sigs = get_turtle_signals(symbol.upper(), days=7)
    return sigs[0] if sigs else None


# ---------- 同步时顺便检测信号 ----------

@app.post("/minute/sync")
async def sync_minute_data(period: str = "5min"):
    """同步分时数据并检测信号"""
    # 先同步
    result = sync_all_minute_data(period=period, progress=False)

    # 对每个成功同步的品种，检测最后一根 K 线的信号
    new_signals = []
    for sym, contract_code, count, latest in (result.get("success") or []):
        if count > 0:
            # 取最后一根 K 线
            df = get_minute_from_cache(sym, period=period, limit=1)
            if len(df) > 0:
                row = df.iloc[-1]
                bar_time = str(df.index[-1])
                ci = get_contract_info(sym)
                name = ci.get("name", SYMBOL_NAME.get(sym, sym))
                sigs = check_bar_signal(
                    symbol=sym,
                    bar_close=float(row["close"]),
                    bar_high=float(row["high"]),
                    bar_low=float(row["low"]),
                    bar_time=bar_time,
                    period=period,
                    name=name,
                    contract_code=ci.get("contract_code", ""),
                )
                new_signals.extend(sigs)

    return {
        "sync": result,
        "new_signals": len(new_signals),
        "signals": new_signals,
    }


# ---------- 静态页面托管（与 API 同端口）----------
WWW_DIR = PROJECT_ROOT / "www"
app.mount("/www", StaticFiles(directory=str(WWW_DIR), html=True), name="www")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
