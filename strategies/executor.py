"""
策略执行器

职责：
1. 从 strategies 表加载 active 策略
2. 对每根 K 线调用 on_bar 检测信号
3. 写 strategy_signals 表（开仓信号：entry_long / entry_short）
4. 写 strategy_event_log 表（执行引擎事件：signal_detected / signal_skipped / engine_started / engine_stopped）
5. 主循环：可手动触发，也可用 cron 定时跑

注意：Phase 2.4 只写开仓信号（entry_long / entry_short）。
       turtle_trade_process（add / stop_loss / exit_20 等）是 Phase 3 写。
"""
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .base import BaseStrategy
from .loader import get_strategy, list_available_strategies

# 路径配置
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "futures_akshare.db"

# 日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def get_active_strategies() -> List[BaseStrategy]:
    """获取所有 is_active=1 的策略实例"""
    strategies: List[BaseStrategy] = []
    for info in list_available_strategies():
        if info.get('is_active') and info.get('loadable'):
            try:
                s = get_strategy(info['strategy_id'])
                strategies.append(s)
            except Exception as e:
                logger.warning(f"加载策略 {info['strategy_id']} 失败: {e}")
    return strategies


def get_recent_bars(symbol: str, lookback_bars: int = 200) -> pd.DataFrame:
    """
    从 futures_min 缓存取最近 N 根 K 线

    Returns:
        DataFrame with columns: open, high, low, close, volume, date
        Index: datetime (parsed, sorted asc)
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            """
            SELECT datetime, date, open, high, low, close, volume
            FROM futures_min
            WHERE symbol = ?
            ORDER BY datetime DESC
            LIMIT ?
            """,
            (symbol.upper(), lookback_bars),
        )
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"get_recent_bars({symbol}) 失败: {e}")
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=['datetime', 'date', 'open', 'high', 'low', 'close', 'volume'])
    try:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime').sort_index()
    except Exception as e:
        logger.error(f"get_recent_bars({symbol}) 解析 datetime 失败: {e}")
        return pd.DataFrame()
    return df


def save_signal(strategy_id: str, symbol: str, signal: Dict[str, Any]) -> int:
    """
    写一条 strategy_signals 记录

    Args:
        strategy_id: 策略 ID
        symbol: 品种
        signal: dict with keys: signal_type, direction, trigger_price,
                reference_price, reference_n, bar_time, contract_code (可选)

    Returns:
        新行的 id，失败或重复返回 -1
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO strategy_signals(
                strategy_id, symbol, contract_code, signal_type, direction,
                trigger_price, reference_price, reference_n, bar_time, period
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                strategy_id,
                symbol.upper(),
                signal.get('contract_code', ''),
                signal['signal_type'],
                signal['direction'],
                signal['trigger_price'],
                signal['reference_price'],
                signal.get('reference_n'),
                signal['bar_time'],
                signal.get('period', '5min'),
            ),
        )
        new_id = cur.lastrowid if cur.rowcount > 0 else -1
        conn.commit()
        conn.close()
        return new_id
    except Exception as e:
        logger.error(f"save_signal 失败: {e}")
        return -1


def save_event(
    strategy_id: str,
    event_type: str,
    symbol: str = '',
    context: Optional[Dict] = None,
) -> int:
    """
    写一条 strategy_event_log 记录

    event_type: signal_detected / signal_skipped / param_updated / engine_started / engine_stopped
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO strategy_event_log(
                strategy_id, event_type, event_at, symbol, context_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                strategy_id,
                event_type,
                datetime.now().isoformat(),
                symbol.upper() if symbol else None,
                json.dumps(context, ensure_ascii=False) if context else None,
            ),
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return new_id
    except Exception as e:
        logger.error(f"save_event 失败: {e}")
        return -1


def _lookup_main_contract(symbol: str) -> Optional[str]:
    """查询品种的主力合约代码（best effort，失败返回 None）"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            "SELECT contract_code FROM futures_contracts WHERE symbol = ? AND is_main = 1 LIMIT 1",
            (symbol.upper(),),
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def detect_signals_for_symbol(strategy: BaseStrategy, symbol: str) -> List[Dict[str, Any]]:
    """
    对单个品种跑 on_bar 检测

    Returns:
        信号列表（每个 dict 含 signal_type / direction / trigger_price / reference_price / reference_n / bar_time）
    """
    try:
        df = get_recent_bars(symbol, lookback_bars=200)
        if df.empty:
            logger.debug(f"{symbol} 无缓存数据，跳过")
            return []

        # 取最后一根 K 线作为 on_bar 输入
        last_bar = df.iloc[-1]
        bar_dict = {
            'datetime': last_bar.name,
            'date': last_bar.get('date', ''),
            'open': last_bar['open'],
            'high': last_bar['high'],
            'low': last_bar['low'],
            'close': last_bar['close'],
            'volume': last_bar['volume'],
        }
        bar_series = pd.Series(bar_dict)

        # 调 on_bar 检测（on_bar 内部已 try/except，不会抛）
        signals = strategy.on_bar(symbol, bar_series, df) or []

        # v1.5 Phase 3.8: 引入 trade_process_logger（session 关联的写入由 sim_engine 触发，
        # 本函数仅做策略层信号检测；check 类事件的 C 方案上下文也由 sim_engine 在收到
        # 端点调用时写）。这里仅验证模块可导入。
        from .trade_process_logger import CHECK_EVENT_TYPES  # noqa: F401
        return list(signals)
    except Exception as e:
        logger.error(f"{strategy.strategy_id} on_bar({symbol}) 失败: {e}")
        return []


def run_executor(
    symbols: Optional[List[str]] = None,
    write_to_db: bool = True,
) -> Dict[str, Any]:
    """
    执行器主入口

    Args:
        symbols: 品种列表（None = 用最近 30 天有数据的品种）
        write_to_db: 是否写 DB（False = 试跑模式）

    Returns:
        {
            "started_at": "...",
            "finished_at": "...",
            "duration_seconds": float,
            "strategies_run": int,
            "symbols_scanned": int,
            "signals_detected": int,
            "signals": [...]
        }
    """
    started_at = datetime.now()
    logger.info(f"=== 策略执行器启动 @ {started_at.isoformat()} (write_to_db={write_to_db}) ===")

    # 1. 加载策略
    strategies = get_active_strategies()

    # 2. 写 engine_started 事件（每个 active 策略一条）
    if write_to_db:
        for s in strategies:
            save_event(s.strategy_id, 'engine_started', context={'started_at': started_at.isoformat()})

    if not strategies:
        logger.warning("无可用 active 策略，跳过")
        finished_at = datetime.now()
        if write_to_db:
            # 仍然写 engine_stopped 留痕（用虚拟 id 也行，但这里跳过避免脏数据）
            pass
        return {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": (finished_at - started_at).total_seconds(),
            "strategies_run": 0,
            "symbols_scanned": 0,
            "signals_detected": 0,
            "signals": [],
        }

    # 3. 决定要扫描的品种
    if not symbols:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute(
                "SELECT DISTINCT symbol FROM futures_daily WHERE date >= date('now', '-30 days') LIMIT 10"
            )
            symbols = [r[0] for r in cur.fetchall()]
            conn.close()
        except Exception as e:
            logger.error(f"查品种列表失败: {e}")
            symbols = []

    if not symbols:
        logger.warning("无可用品种，跳过")
        finished_at = datetime.now()
        if write_to_db:
            for s in strategies:
                save_event(
                    s.strategy_id,
                    'engine_stopped',
                    context={'finished_at': finished_at.isoformat(), 'signals': 0, 'symbols': 0},
                )
        return {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": (finished_at - started_at).total_seconds(),
            "strategies_run": len(strategies),
            "symbols_scanned": 0,
            "signals_detected": 0,
            "signals": [],
        }

    # 4. 对每个策略 × 每个品种跑 on_bar
    all_signals: List[Dict[str, Any]] = []
    for strategy in strategies:
        for symbol in symbols:
            signals = detect_signals_for_symbol(strategy, symbol)
            for sig in signals:
                # 补 strategy_id
                sig['strategy_id'] = strategy.strategy_id
                # 查主力合约（best effort）
                if not sig.get('contract_code'):
                    cc = _lookup_main_contract(symbol)
                    if cc:
                        sig['contract_code'] = cc
                all_signals.append(sig)

                if write_to_db:
                    new_id = save_signal(strategy.strategy_id, symbol, sig)
                    if new_id > 0:
                        save_event(
                            strategy.strategy_id,
                            'signal_detected',
                            symbol,
                            {
                                'signal_type': sig['signal_type'],
                                'trigger_price': sig['trigger_price'],
                                'reference_price': sig.get('reference_price'),
                            },
                        )
                        logger.info(
                            f"  ✅ {strategy.strategy_id} 检测到 {sig['signal_type']} @ {symbol} "
                            f"price={sig['trigger_price']:.2f}"
                        )
                    else:
                        save_event(
                            strategy.strategy_id,
                            'signal_skipped',
                            symbol,
                            {
                                'reason': 'UNIQUE 约束冲突或写入失败',
                                'signal_type': sig['signal_type'],
                                'bar_time': sig.get('bar_time'),
                            },
                        )
                else:
                    logger.info(
                        f"  [试跑] {strategy.strategy_id} 检测到 {sig['signal_type']} @ {symbol} "
                        f"price={sig['trigger_price']:.2f}"
                    )

    finished_at = datetime.now()
    duration = (finished_at - started_at).total_seconds()

    # 5. 写 engine_stopped 事件
    if write_to_db:
        for s in strategies:
            save_event(
                s.strategy_id,
                'engine_stopped',
                context={
                    'finished_at': finished_at.isoformat(),
                    'signals': len(all_signals),
                    'duration_seconds': duration,
                },
            )

    logger.info(
        f"=== 策略执行器完成 @ {finished_at.isoformat()} "
        f"（耗时 {duration:.2f}s，策略 {len(strategies)} 个，品种 {len(symbols)} 个，信号 {len(all_signals)} 个）==="
    )
    return {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": duration,
        "strategies_run": len(strategies),
        "symbols_scanned": len(symbols),
        "signals_detected": len(all_signals),
        "signals": all_signals,
    }


# CLI 入口
if __name__ == "__main__":
    import sys

    write_to_db = "--dry-run" not in sys.argv
    result = run_executor(write_to_db=write_to_db)
    print(json.dumps(result, ensure_ascii=False, indent=2))
