"""
事件流写入服务（v1.5 Phase 3.5）

统一封装 session_event_log 表的写入与查询

设计原则：
1. 9 个 log_* 函数覆盖所有已知事件类型
2. 每个 log_* 函数都接受具体参数（不接 dict）—— 类型安全
3. 事务安全：批量写入用同一个 conn
4. 与现有 sim_engine / lifecycle / line_calculator 的内部 _save_event 兼容（不破坏）
5. 高级查询：query_events + get_session_event_timeline
"""
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_DIR / "futures_akshare.db"

# 9 个事件类型
EVENT_SESSION_CREATED = 'session_created'
EVENT_ORDER_SUBMITTED = 'order_submitted'
EVENT_ORDER_FILLED = 'order_filled'
EVENT_UNITS_CHANGED = 'units_changed'
EVENT_STATUS_CHANGED = 'status_changed'
EVENT_LINE_OVERRIDDEN = 'line_overridden'
EVENT_UNIT_CLOSED = 'unit_closed'
EVENT_STOP_LOSS_TRIGGERED = 'stop_loss_triggered'
EVENT_EXIT_20_TRIGGERED = 'exit_20_triggered'

ALL_EVENT_TYPES = {
    EVENT_SESSION_CREATED,
    EVENT_ORDER_SUBMITTED,
    EVENT_ORDER_FILLED,
    EVENT_UNITS_CHANGED,
    EVENT_STATUS_CHANGED,
    EVENT_LINE_OVERRIDDEN,
    EVENT_UNIT_CLOSED,
    EVENT_STOP_LOSS_TRIGGERED,
    EVENT_EXIT_20_TRIGGERED,
}


def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now().isoformat()


def _insert_event(conn: sqlite3.Connection, session_id: str, account_id: str, event_type: str,
                 context: Optional[Dict] = None, unit_id: Optional[str] = None,
                 trade_id: Optional[str] = None) -> int:
    """
    底层事件写入（其他 9 个 log_* 函数都调这个）
    
    Returns:
        新行的 id
    """
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO session_event_log(session_id, account_id, event_type, event_at, unit_id, trade_id, context_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, account_id, event_type, _now_iso(), unit_id, trade_id,
          json.dumps(context, ensure_ascii=False) if context else None))
    return cur.lastrowid


# ============================================================
# 9 个 log_* 函数
# ============================================================
def log_session_created(session_id: str, account_id: str,
                        entry_price: float, basis_price: float, atr: Optional[float] = None) -> int:
    """建仓创建 session"""
    conn = _conn()
    try:
        event_id = _insert_event(conn, session_id, account_id, EVENT_SESSION_CREATED,
                                 context={'entry_price': entry_price, 'basis_price': basis_price, 'atr': atr})
        conn.commit()
        logger.info(f"📝 事件: session_created {session_id[:8]}")
        return event_id
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_order_submitted(session_id: str, account_id: str, order_id: str,
                        price: float, hand_count: int, direction: str) -> int:
    """委托提交"""
    conn = _conn()
    try:
        event_id = _insert_event(conn, session_id, account_id, EVENT_ORDER_SUBMITTED,
                                 context={'order_id': order_id, 'price': price, 'hand_count': hand_count, 'direction': direction})
        conn.commit()
        return event_id
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_order_filled(session_id: str, account_id: str, unit_id: str, trade_id: str,
                     filled_price: float, slippage: float = 0.0, fee: float = 0.0) -> int:
    """委托成交"""
    conn = _conn()
    try:
        event_id = _insert_event(conn, session_id, account_id, EVENT_ORDER_FILLED,
                                 unit_id=unit_id, trade_id=trade_id,
                                 context={'trade_id': trade_id, 'filled_price': filled_price, 'slippage': slippage, 'fee': fee})
        conn.commit()
        return event_id
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_units_changed(session_id: str, account_id: str, unit_id: str,
                      from_units: int, to_units: int, reason: str = '') -> int:
    """Unit 数变化"""
    conn = _conn()
    try:
        event_id = _insert_event(conn, session_id, account_id, EVENT_UNITS_CHANGED,
                                 unit_id=unit_id,
                                 context={'from_units': from_units, 'to_units': to_units, 'unit_id': unit_id, 'reason': reason})
        conn.commit()
        return event_id
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_status_changed(session_id: str, account_id: str,
                       from_status: str, to_status: str, reason: str = '') -> int:
    """session 状态变化"""
    conn = _conn()
    try:
        event_id = _insert_event(conn, session_id, account_id, EVENT_STATUS_CHANGED,
                                 context={'from_status': from_status, 'to_status': to_status, 'reason': reason})
        conn.commit()
        return event_id
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_line_overridden(session_id: str, account_id: str,
                        line_type: str, old_price: Optional[float], new_price: Optional[float]) -> int:
    """价格线被用户调价"""
    conn = _conn()
    try:
        event_id = _insert_event(conn, session_id, account_id, EVENT_LINE_OVERRIDDEN,
                                 context={'line_type': line_type, 'old_price': old_price, 'new_price': new_price})
        conn.commit()
        return event_id
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_unit_closed(session_id: str, account_id: str, unit_id: str,
                    close_price: float, reason: str, open_price: Optional[float] = None,
                    session_close: bool = False) -> int:
    """unit 减仓/平仓"""
    conn = _conn()
    try:
        ctx = {'close_price': close_price, 'reason': reason, 'open_price': open_price}
        if session_close:
            ctx['session_close'] = True
        event_id = _insert_event(conn, session_id, account_id, EVENT_UNIT_CLOSED,
                                 unit_id=unit_id, context=ctx)
        conn.commit()
        return event_id
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_stop_loss_triggered(session_id: str, account_id: str,
                            stop_price: float, fill_price: float, exit_reason: str = '') -> int:
    """止损触发"""
    conn = _conn()
    try:
        event_id = _insert_event(conn, session_id, account_id, EVENT_STOP_LOSS_TRIGGERED,
                                 context={'stop_price': stop_price, 'fill_price': fill_price, 'exit_reason': exit_reason})
        conn.commit()
        return event_id
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_exit_20_triggered(session_id: str, account_id: str,
                          reverse_price: float, fill_price: float, exit_reason: str = '') -> int:
    """20日反向触发"""
    conn = _conn()
    try:
        event_id = _insert_event(conn, session_id, account_id, EVENT_EXIT_20_TRIGGERED,
                                 context={'reverse_price': reverse_price, 'fill_price': fill_price, 'exit_reason': exit_reason})
        conn.commit()
        return event_id
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# 批量写入（事务原子）
# ============================================================
def log_batch(events: List[Dict[str, Any]]) -> List[int]:
    """
    批量写入事件（事务原子）
    
    Args:
        events: 每项必须含 session_id / account_id / event_type / context
                可选 unit_id / trade_id
    
    Returns:
        新行 id 列表
    """
    conn = _conn()
    try:
        ids = []
        for ev in events:
            event_id = _insert_event(
                conn,
                ev['session_id'],
                ev['account_id'],
                ev['event_type'],
                context=ev.get('context'),
                unit_id=ev.get('unit_id'),
                trade_id=ev.get('trade_id')
            )
            ids.append(event_id)
        conn.commit()
        logger.info(f"📝 批量事件: {len(ids)} 条")
        return ids
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# 高级查询
# ============================================================
def query_events(session_id: Optional[str] = None,
                event_type: Optional[str] = None,
                days: int = 30,
                limit: int = 100) -> List[Dict[str, Any]]:
    """
    查询事件（多条件过滤）
    
    Args:
        session_id: 限定 session（None = 全部）
        event_type: 限定类型（None = 全部）
        days: 时间窗口（最近 N 天）
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
            conditions.append("event_at >= ?")
            params.append(since)
        
        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        cur.execute(f"""
            SELECT id, session_id, account_id, event_type, event_at, unit_id, trade_id, context_json
            FROM session_event_log
            WHERE {where}
            ORDER BY event_at DESC LIMIT ?
        """, params)
        rows = [dict(r) for r in cur.fetchall()]
        # 解析 context_json
        for r in rows:
            try:
                r['context'] = json.loads(r.pop('context_json') or '{}')
            except Exception:
                r['context'] = {}
        return rows
    finally:
        conn.close()


def get_session_event_timeline(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    单个 session 的事件时间线（按时间正序）
    
    Returns:
        [
            {'event_at': '2026-06-03T11:00:00', 'event_type': 'session_created', 'summary': '建仓 800.0 N=10.0', 'context': {...}},
            ...
        ]
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT event_type, event_at, unit_id, trade_id, context_json
            FROM session_event_log
            WHERE session_id = ?
            ORDER BY event_at ASC LIMIT ?
        """, (session_id, limit))
        rows = cur.fetchall()
        timeline = []
        for r in rows:
            try:
                ctx = json.loads(r['context_json'] or '{}')
            except Exception:
                ctx = {}
            timeline.append({
                'event_at': r['event_at'],
                'event_type': r['event_type'],
                'unit_id': r['unit_id'],
                'trade_id': r['trade_id'],
                'context': ctx,
                'summary': _summarize_event(r['event_type'], ctx)
            })
        return timeline
    finally:
        conn.close()


def _summarize_event(event_type: str, context: Dict) -> str:
    """生成 1 行可读摘要"""
    if event_type == EVENT_SESSION_CREATED:
        return f"建仓 {context.get('entry_price', '?')} N={context.get('atr', '?')}"
    elif event_type == EVENT_ORDER_SUBMITTED:
        return f"委托 {context.get('direction', '?')} {context.get('hand_count', '?')}手 @ {context.get('price', '?')}"
    elif event_type == EVENT_ORDER_FILLED:
        return f"成交 @ {context.get('filled_price', '?')} (slippage={context.get('slippage', 0)})"
    elif event_type == EVENT_UNITS_CHANGED:
        return f"Units {context.get('from_units', '?')}→{context.get('to_units', '?')} ({context.get('reason', '')})"
    elif event_type == EVENT_STATUS_CHANGED:
        return f"状态 {context.get('from_status', '?')}→{context.get('to_status', '?')} ({context.get('reason', '')})"
    elif event_type == EVENT_LINE_OVERRIDDEN:
        return f"调价 {context.get('line_type', '?')}: {context.get('old_price')}→{context.get('new_price')}"
    elif event_type == EVENT_UNIT_CLOSED:
        pnl = ''
        if context.get('open_price') and context.get('close_price'):
            diff = context['close_price'] - context['open_price']
            pnl = f" (pnl={diff:.2f})"
        return f"平仓 unit @ {context.get('close_price', '?')}{pnl}"
    elif event_type == EVENT_STOP_LOSS_TRIGGERED:
        return f"止损 @ {context.get('stop_price', '?')}"
    elif event_type == EVENT_EXIT_20_TRIGGERED:
        return f"20日反向 @ {context.get('reverse_price', '?')}"
    return event_type


# CLI 入口
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  timeline <session_id> [limit]")
        print("  query [session_id] [event_type] [days]")
        print("  types  # 列出所有 event_type")
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == 'timeline':
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50
        tl = get_session_event_timeline(sys.argv[2], limit)
        print(f"共 {len(tl)} 条事件:")
        for e in tl:
            print(f"  {e['event_at'][:19]} {e['event_type']:18s} {e['summary']}")
    elif cmd == 'query':
        kwargs = {}
        if len(sys.argv) > 2:
            kwargs['session_id'] = sys.argv[2]
        if len(sys.argv) > 3:
            kwargs['event_type'] = sys.argv[3]
        kwargs['days'] = int(sys.argv[4]) if len(sys.argv) > 4 else 30
        events = query_events(**kwargs)
        print(f"共 {len(events)} 条")
        for e in events[:5]:
            print(f"  {e['event_at'][:19]} {e['event_type']:18s} {e['context']}")
    elif cmd == 'types':
        for t in sorted(ALL_EVENT_TYPES):
            print(f"  {t}")
    else:
        print(f"未知命令: {cmd}")
