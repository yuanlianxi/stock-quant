"""Synchronous backtest runner.

Phase 2 抽自 api/main.py L249-322（_TurtleStrategy 类）+ L326-478（_run_backtest_sync 函数）。

注：_TurtleStrategy 与 _run_backtest_sync 强耦合（后者前向引用前者），
因此一并迁出。main.py 不再持有这两个符号。
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

import pandas as pd

from api.schemas.backtest import BacktestRequest
from data.data_loader import get_daily_data_from_cache

logger = logging.getLogger(__name__)

# Backtrader 可用性检测 —— 原 main.py 顶部 try/except 派生
try:
    import backtrader as bt
    BACKTRADER_AVAILABLE = True
except ImportError:
    BACKTRADER_AVAILABLE = False

# akshare 可用性检测 —— _run_backtest_sync 内部需要
try:
    import akshare as _ak  # noqa: F401
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False


# ============================================================
# 简化海龟策略（Backtrader）
# ============================================================

if BACKTRADER_AVAILABLE:
    class _TurtleStrategy(bt.Strategy):
        """原 api/main.py L252-322 的 _TurtleStrategy，签名/逻辑 0 改动。"""
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


def run_backtest_sync(req: BacktestRequest) -> dict:
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
        sharpe: Optional[float] = None
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
