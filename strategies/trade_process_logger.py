"""
海龟交易过程数据写入服务（v1.5 Phase 3.8）

职责：
1. 写 turtle_trade_process 表（10 个 event_type）
2. check 类事件 C 方案实现（stop_loss_check / check_exit 触发存前后 5 根 K 线）
3. 退仓优先顺序（止损 > 加仓）
4. 高级查询（get_trade_process）
"""
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "futures_akshare.db"

# 10 个 event_type 枚举
EVT_ENTRY_SIGNAL = 'entry_signal'
EVT_ENTRY_FILLED = 'entry_filled'
EVT_ADD_SIGNAL = 'add_signal'
EVT_ADD_FILLED = 'add_filled'
EVT_ADD_SKIPPED_GAP = 'add_skipped_gap'
EVT_STOP_LOSS_CHECK = 'stop_loss_check'
EVT_STOP_LOSS_TRIGGERED = 'stop_loss_triggered'
EVT_CHECK_EXIT = 'check_exit'
EVT_EXIT_20_TRIGGERED = 'exit_20_triggered'
EVT_UNIT_CLOSED = 'unit_closed'

ALL_EVENT_TYPES = {
    EVT_ENTRY_SIGNAL, EVT_ENTRY_FILLED,
    EVT_ADD_SIGNAL, EVT_ADD_FILLED, EVT_ADD_SKIPPED_GAP,
    EVT_STOP_LOSS_CHECK, EVT_STOP_LOSS_TRIGGERED,
    EVT_CHECK_EXIT, EVT_EXIT_20_TRIGGERED,
    EVT_UNIT_CLOSED,
}

# check 类事件（用 C 方案：触发时存前后 5 根 K 线）
CHECK_EVENT_TYPES = {EVT_STOP_LOSS_CHECK, EVT_CHECK_EXIT}

# C 方案：前后 5 根
CHECK_CONTEXT_BARS = 5


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now().isoformat()


def log_turtle_event(session_id: str, account_id: str, event_type: str,
                     bar_time: str, bar_open: Optional[float] = None,
                     bar_high: Optional[float] = None, bar_low: Optional[float] = None,
                     bar_close: Optional[float] = None,
                     signal_type: Optional[str] = None,
                     signal_price: Optional[float] = None,
                     reference_price: Optional[float] = None,
                     n_value: Optional[float] = None,
                     unit_id: Optional[int] = None,
                     exec_status: Optional[str] = None,
                     exec_price: Optional[float] = None,
                     exec_hand_count: Optional[int] = None,
                     exec_time: Optional[str] = None,
                     slippage: Optional[float] = None,
                     is_gap: int = 0,
                     gap_size: Optional[float] = None,
                     decision_reason: Optional[str] = None) -> int:
    """
    写一条 turtle_trade_process 事件
    
    Returns:
        新行 id
    """
    if event_type not in ALL_EVENT_TYPES:
        raise ValueError(f"Invalid event_type: {event_type}")
    
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO turtle_trade_process(
                session_id, account_id, event_type, bar_time,
                bar_open, bar_high, bar_low, bar_close,
                signal_type, signal_price, reference_price, n_value,
                unit_id, exec_status, exec_price, exec_hand_count, exec_time,
                slippage, is_gap, gap_size, decision_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, account_id, event_type, bar_time,
              bar_open, bar_high, bar_low, bar_close,
              signal_type, signal_price, reference_price, n_value,
              unit_id, exec_status, exec_price, exec_hand_count, exec_time,
              slippage, is_gap, gap_size, decision_reason))
        new_id = cur.lastrowid
        conn.commit()
        logger.info(f"📝 turtle_event: {event_type:20s} {session_id[:8]} bar={bar_time}")
        return new_id
    except Exception as e:
        conn.rollback()
        logger.error(f"log_turtle_event 失败: {e}")
        raise
    finally:
        conn.close()


def log_check_event_with_context(session_id: str, account_id: str, check_type: str,
                                  trigger_bar, history: pd.DataFrame,
                                  **kwargs) -> List[int]:
    """
    C 方案：check 类事件触发时存前后 5 根 K 线（trigger_bar 前后各 5 根，共 11 根或更少）
    
    Args:
        check_type: EVT_STOP_LOSS_CHECK 或 EVT_CHECK_EXIT
        trigger_bar: 触发的那根 K 线（pd.Series；name 是 datetime）
        history: 完整 K 线 DataFrame（datetime 索引）
        **kwargs: 传给 log_turtle_event 的其他参数
    
    Returns:
        新行 id 列表
    """
    if check_type not in CHECK_EVENT_TYPES:
        raise ValueError(f"Invalid check event: {check_type}")
    
    trigger_time = trigger_bar.name if hasattr(trigger_bar, 'name') else None
    if trigger_time is None or history is None or history.empty:
        # 退化：只写 trigger 那一根
        return [log_turtle_event(
            session_id, account_id, check_type, str(trigger_time or _now_iso()),
            bar_open=trigger_bar.get('open') if trigger_bar is not None else None,
            bar_high=trigger_bar.get('high') if trigger_bar is not None else None,
            bar_low=trigger_bar.get('low') if trigger_bar is not None else None,
            bar_close=trigger_bar.get('close') if trigger_bar is not None else None,
            **kwargs
        )]
    
    # 找 trigger_time 在 history 里的位置
    if trigger_time not in history.index:
        # 退化：只写 trigger
        return [log_turtle_event(session_id, account_id, check_type, str(trigger_time), **kwargs)]
    
    trigger_idx = history.index.get_loc(trigger_time)
    start_idx = max(0, trigger_idx - CHECK_CONTEXT_BARS)
    end_idx = min(len(history) - 1, trigger_idx + CHECK_CONTEXT_BARS)
    
    ids = []
    for i in range(start_idx, end_idx + 1):
        bar = history.iloc[i]
        bar_time_str = str(history.index[i])
        is_trigger = (i == trigger_idx)
        
        ids.append(log_turtle_event(
            session_id, account_id, check_type, bar_time_str,
            bar_open=bar.get('open'),
            bar_high=bar.get('high'),
            bar_low=bar.get('low'),
            bar_close=bar.get('close'),
            is_gap=1 if is_trigger else 0,
            decision_reason=f"C方案: {check_type} @ idx {i} (trigger idx {trigger_idx})" if is_trigger else f"C方案 context bar {i - trigger_idx:+d}",
            **kwargs
        ))
    
    logger.info(f"📝 C方案: {check_type} {session_id[:8]} 写 {len(ids)} 根 K 线 (idx {start_idx}-{end_idx}, trigger={trigger_idx})")
    return ids


def query_trade_process(session_id: Optional[str] = None,
                        event_type: Optional[str] = None,
                        days: int = 30,
                        limit: int = 100) -> List[Dict[str, Any]]:
    """
    查询 turtle_trade_process 事件
    
    Args:
        session_id: 限定 session
        event_type: 限定类型
        days: 时间窗口
        limit: 返回数量
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        conditions = []
        params = []
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if days > 0:
            since = (datetime.now() - timedelta(days=days)).isoformat()
            conditions.append("bar_time >= ?")
            params.append(since)
        
        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        cur.execute(f"""
            SELECT * FROM turtle_trade_process
            WHERE {where}
            ORDER BY bar_time DESC LIMIT ?
        """, params)
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        conn.close()


def get_trade_process_summary(session_id: str) -> Dict[str, int]:
    """
    单个 session 的事件统计（按 event_type 分组）
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT event_type, COUNT(*) as cnt FROM turtle_trade_process
            WHERE session_id = ?
            GROUP BY event_type
        """, (session_id,))
        return {r['event_type']: r['cnt'] for r in cur.fetchall()}
    finally:
        conn.close()


# CLI 入口
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  query [session_id] [event_type] [days]")
        print("  summary <session_id>")
        print("  types")
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == 'query':
        kwargs = {'limit': 100}
        if len(sys.argv) > 2:
            kwargs['session_id'] = sys.argv[2]
        if len(sys.argv) > 3:
            kwargs['event_type'] = sys.argv[3]
        if len(sys.argv) > 4:
            kwargs['days'] = int(sys.argv[4])
        events = query_trade_process(**kwargs)
        print(f"共 {len(events)} 条:")
        for e in events[:5]:
            print(f"  {e['bar_time'][:19]} {e['event_type']:25s} {e.get('decision_reason', '')}")
    elif cmd == 'summary':
        s = get_trade_process_summary(sys.argv[2])
        print(f"事件统计: {s}")
    elif cmd == 'types':
        for t in sorted(ALL_EVENT_TYPES):
            print(f"  {t}")
    else:
        print(f"未知命令: {cmd}")
