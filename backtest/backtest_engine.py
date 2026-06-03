#!/usr/bin/env python3
"""
backtest_engine.py - Backtrader 回测引擎封装（Phase 4.2 改造版）
新增 DB 持久化函数：backtest_runs + sim_trades + sim_account
"""

import backtrader as bt
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Type

# ============================================================
# Phase 4.2 新增：DB 持久化层
# ============================================================

# 路径
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "futures_akshare.db"


def _conn():
    """DB 连接（每次新建，避免跨线程问题）"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    """当前时间 ISO 格式"""
    return datetime.now().isoformat()


def ensure_backtest_account(run_id: str) -> str:
    """确保回测用账户存在，返回 account_id = backtest_<run_id>"""
    account_id = f"backtest_{run_id}"
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT OR IGNORE INTO sim_account(
                account_id, user_id, display_name, name, balance, available,
                platform_name, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 1000000.0, 1000000.0, 'backtest', ?, ?)
        """, (account_id, "backtest", f"回测 {run_id[:8]}", account_id, _now_iso(), _now_iso()))
        conn.commit()
        return account_id
    finally:
        conn.close()


def create_backtest_run(strategy_id: str, symbol: str, start_date: str, end_date: str,
                        params: Dict[str, Any], initial_capital: float) -> str:
    """创建 backtest_runs 记录（status=running），同时自动建 sim_account"""
    run_id = f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    conn = _conn()
    try:
        cur = conn.cursor()
        now = _now_iso()
        cur.execute("""
            INSERT INTO backtest_runs(
                run_id, strategy_id, symbol, start_date, end_date,
                params_json, status, initial_capital, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?, ?)
        """, (run_id, strategy_id, symbol, start_date, end_date,
              json.dumps(params, ensure_ascii=False), initial_capital, now, now))
        conn.commit()
    finally:
        conn.close()
    # 同时创建回测账户
    ensure_backtest_account(run_id)
    return run_id


def record_backtest_trade(run_id: str, trade_id: str, order_id: str,
                          symbol: str, contract_code: str, direction: str,
                          filled_price: float, filled_quantity: int,
                          filled_at: str) -> bool:
    """回测每个成交写 sim_trades（platform_name=backtest）"""
    account_id = f"backtest_{run_id}"
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sim_trades(
                trade_id, order_id, account_id, session_id, symbol, contract_code,
                direction, filled_price, filled_quantity, commission, platform_name, filled_at
            )
            VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, 0.0, 'backtest', ?)
        """, (trade_id, order_id, account_id, symbol, contract_code, direction,
              filled_price, filled_quantity, filled_at))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"[record_backtest_trade] 失败: {e}")
        return False
    finally:
        conn.close()


def complete_backtest_run(run_id: str, final_capital: float, total_return_pct: float,
                          max_drawdown_pct: float, total_trades: int,
                          result_metrics: Dict[str, Any]) -> bool:
    """回测完成时更新 backtest_runs 状态（status=completed）"""
    conn = _conn()
    try:
        cur = conn.cursor()
        now = _now_iso()
        cur.execute("""
            UPDATE backtest_runs
            SET status = 'completed', final_capital = ?, total_return_pct = ?,
                max_drawdown_pct = ?, total_trades = ?, result_metrics_json = ?,
                completed_at = ?, updated_at = ?
            WHERE run_id = ?
        """, (final_capital, total_return_pct, max_drawdown_pct, total_trades,
              json.dumps(result_metrics, ensure_ascii=False), now, now, run_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"[complete_backtest_run] 失败: {e}")
        return False
    finally:
        conn.close()


def fail_backtest_run(run_id: str, error_message: str) -> bool:
    """回测失败时更新 backtest_runs 状态（status=failed）"""
    conn = _conn()
    try:
        cur = conn.cursor()
        now = _now_iso()
        cur.execute("""
            UPDATE backtest_runs
            SET status = 'failed', error_message = ?, updated_at = ?
            WHERE run_id = ?
        """, (error_message, now, run_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        print(f"[fail_backtest_run] 失败: {e}")
        return False
    finally:
        conn.close()


# ============================================================
# 原有 Backtrader 封装（保留）
# ============================================================


class BacktestEngine:
    """回测引擎封装类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化回测引擎

        Args:
            config: 配置字典，包含：
                - initial_cash: 初始资金（默认 1000000）
                - commission: 手续费（默认 0.0003）
                - stamp_tax: 印花税（默认 0.001）
                - slippage: 滑点（默认 0.0001）
        """
        from .config import DEFAULT_CONFIG

        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.cerebro = None
        self.results = None

    def _create_cerebro(self):
        """创建 Cerebro 实例"""
        self.cerebro = bt.Cerebro()

        # 设置初始资金
        self.cerebro.broker.setcash(self.config['initial_cash'])

        # 设置手续费
        self.cerebro.broker.setcommission(commission=self.config['commission'])

        # 设置印花税（卖出时收取）
        # Backtrader 没有内置印花税，需要通过自定义 CommissionInfo 实现
        # 简化处理：在策略中卖出时额外计算

        # 设置滑点
        # Backtrader 没有内置滑点，通过自定义 slippage broker 实现
        self.cerebro.broker.set_slippage_perc(
            perc=self.config['slippage'],
            slip_open=True,
            slip_close=True
        )

    def add_data(self, datafeed: bt.feeds.DataBase):
        """
        添加数据源

        Args:
            datafeed: Backtrader 数据源
        """
        if self.cerebro is None:
            self._create_cerebro()
        self.cerebro.adddata(datafeed)

    def add_strategy(self, strategy_class: Type[bt.Strategy], **params):
        """
        添加策略

        Args:
            strategy_class: 策略类（继承自 bt.Strategy）
            **params: 策略参数
        """
        if self.cerebro is None:
            self._create_cerebro()
        self.cerebro.addstrategy(strategy_class, **params)

    def run(self) -> Dict[str, Any]:
        """
        运行回测

        Returns:
            包含初始资金、最终资金、收益率的字典
        """
        if self.cerebro is None:
            raise ValueError("请先添加数据源和策略")

        # 记录初始资金
        initial_value = self.cerebro.broker.getvalue()

        # 运行回测
        self.results = self.cerebro.run()

        # 获取最终资金
        final_value = self.cerebro.broker.getvalue()

        # 计算收益率
        return_rate = (final_value - initial_value) / initial_value

        return {
            'initial_value': initial_value,
            'final_value': final_value,
            'return_rate': return_rate,
            'return_pct': return_rate * 100,
            'cerebro': self.cerebro,
            'results': self.results,
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        获取回测指标（需要先运行 run）

        Returns:
            绩效指标字典
        """
        if self.results is None:
            return {}

        # 从策略实例获取分析器数据
        metrics = {}
        for strat in self.results:
            if hasattr(strat, 'analyzers'):
                for name, analyzer in strat.analyzers.items():
                    if hasattr(analyzer, 'get_analysis'):
                        try:
                            analysis = analyzer.get_analysis()
                            metrics[name] = analysis
                        except Exception:
                            pass
        return metrics


class TradeAnalyzer(bt.analyzers.TradeAnalyzer):
    """交易分析器"""
    pass


class SharpeRatio(bt.analyzers.SharpeRatio):
    """夏普比率分析器"""
    pass


class DrawDown(bt.analyzers.DrawDown):
    """回撤分析器"""
    pass


class AnnualReturn(bt.analyzers.AnnualReturn):
    """年化收益率分析器"""
    pass


def create_engine(config: Optional[Dict[str, Any]] = None) -> BacktestEngine:
    """
    创建回测引擎的便捷函数

    Args:
        config: 配置字典

    Returns:
        BacktestEngine 实例
    """
    engine = BacktestEngine(config)
    engine._create_cerebro()
    return engine
