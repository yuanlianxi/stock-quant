"""
模拟撮合引擎（v1.5 简化版）

职责：
1. 接受委托（市价单 / 限价单）
2. 撮合成交（按 0016 通达信规则：市价单 = signal 价成交；限价单 = 触及限价才成交）
3. 建仓 → 创建 trade_session + position_units
4. 加仓 → 0.5N 间隔检测 + 创建新 unit
5. 减仓 / 全部平仓 → 更新 position_units / trade_session
6. 同步写 sim_positions 持仓汇总
7. 写 session_event_log 事件流水（Phase 3.5 时 event_logger 接管）

注意：
- Phase 3.2 只做市价单撮合（限价单标记为 pending，Phase 3.6 再做撮合）
- 不做手续费（commission 字段保留默认 0.0）
- 不做保证金计算（margin_used 暂不更新）
- 不做资金扣减（balance / available 暂不扣）
"""
import sqlite3
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_DIR / "futures_akshare.db"


def _gen_uuid() -> str:
    """生成 UUID"""
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now().isoformat()


def _conn():
    """获取启用 FK 的连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _save_event(conn, session_id: str, account_id: str, event_type: str, context: Optional[Dict] = None,
                unit_id: Optional[str] = None, trade_id: Optional[str] = None) -> int:
    """写 session_event_log"""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO session_event_log(session_id, account_id, event_type, event_at, unit_id, trade_id, context_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, account_id, event_type, _now_iso(), unit_id, trade_id,
          json.dumps(context, ensure_ascii=False) if context else None))
    return cur.lastrowid


def submit_order(account_id: str, symbol: str, contract_code: str, direction: str,
                order_type: str, quantity: int, price: Optional[float] = None) -> str:
    """
    提交委托（市价单 = 即时成交；限价单 = pending 等待撮合）
    
    Args:
        account_id: sim_default / sim_user1 / sim_user2
        symbol: AG / AU / RB / TA ...
        contract_code: ag2607 / au2608 ...
        direction: buy / sell
        order_type: market / limit
        quantity: 手数
        price: 限价单必填；市价单 = signal 价
    
    Returns:
        order_id (UUID)
    """
    order_id = _gen_uuid()
    conn = _conn()
    try:
        cur = conn.cursor()
        # 检查 account 存在
        cur.execute("SELECT 1 FROM sim_account WHERE account_id = ?", (account_id,))
        if not cur.fetchone():
            raise ValueError(f"账户 {account_id} 不存在")
        
        # 市价单：直接撮合
        status = 'pending' if order_type == 'limit' else 'filled'
        filled_quantity = quantity if order_type == 'market' else 0
        avg_filled_price = price if order_type == 'market' else None
        
        cur.execute("""
            INSERT INTO sim_orders(order_id, account_id, session_id, symbol, contract_code, direction, order_type, quantity, price, status, filled_quantity, avg_filled_price, created_at, updated_at)
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (order_id, account_id, symbol, contract_code, direction, order_type, quantity, price, status, filled_quantity, avg_filled_price, _now_iso(), _now_iso()))
        conn.commit()
        logger.info(f"📝 委托提交: {order_id[:8]} {account_id} {direction} {symbol} {quantity}手 {order_type}@{price}")
        return order_id
    finally:
        conn.close()


def open_session(account_id: str, strategy_id: str, symbol: str, contract_code: str,
                 direction: str, entry_price: float, n_value: Optional[float] = None) -> str:
    """
    建仓创建 session + 第 1 个 unit
    
    Args:
        account_id: 账户
        strategy_id: 策略
        symbol: 品种
        contract_code: 合约
        direction: long / short
        entry_price: 入场价
        n_value: 海龟 N 值（optional）
    
    Returns:
        session_id (UUID)
    """
    session_id = _gen_uuid()
    unit_id = _gen_uuid()
    order_id = _gen_uuid()
    trade_id = _gen_uuid()
    
    conn = _conn()
    try:
        cur = conn.cursor()
        now = _now_iso()
        
        # 1. 写 trade_sessions
        cur.execute("""
            INSERT INTO trade_sessions(session_id, account_id, strategy_id, symbol, contract_code, direction, status, entry_time, first_entry_price, current_units, total_units, entry_basis_price, entry_locked_atr, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, 1, 1, ?, ?, ?, ?)
        """, (session_id, account_id, strategy_id, symbol, contract_code, direction, now, entry_price, entry_price, n_value, now, now))
        
        # 2. 写 position_units（unit_index=1）
        cur.execute("""
            INSERT INTO position_units(unit_id, session_id, account_id, unit_index, open_price, current_price, open_hand_count, status, is_gap, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?, 1, 'open', 0, ?, ?)
        """, (unit_id, session_id, account_id, entry_price, entry_price, now, now))
        
        # 3. 写 sim_orders（建仓订单）
        cur.execute("""
            INSERT INTO sim_orders(order_id, account_id, session_id, symbol, contract_code, direction, order_type, quantity, status, filled_quantity, avg_filled_price, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'market', 1, 'filled', 1, ?, ?, ?)
        """, (order_id, account_id, session_id, symbol, contract_code, direction, entry_price, now, now))
        
        # 4. 写 sim_trades
        cur.execute("""
            INSERT INTO sim_trades(trade_id, order_id, account_id, session_id, symbol, contract_code, direction, filled_price, filled_quantity, commission, filled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0.0, ?)
        """, (trade_id, order_id, account_id, session_id, symbol, contract_code, direction, entry_price, now))
        
        # 5. 更新 sim_positions（持仓汇总）
        cur.execute("""
            INSERT INTO sim_positions(account_id, symbol, contract_code, quantity, avg_cost, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(account_id, symbol) DO UPDATE SET
                quantity = quantity + 1,
                avg_cost = ((avg_cost * quantity) + excluded.avg_cost) / (quantity + 1),
                updated_at = excluded.updated_at
        """, (account_id, symbol, contract_code, entry_price, now))
        
        # 6. 写 turtle_session_data（v1.4：建仓瞬间锁定 55日高/低 + ATR）
        if n_value is not None:
            cur.execute("""
                INSERT INTO turtle_session_data(session_id, entry_atr_20, add_count, skip_add_count, is_gap_entry, is_breakout_confirm, created_at, updated_at)
                VALUES (?, ?, 0, 0, 0, 0, ?, ?)
            """, (session_id, n_value, now, now))
        
        # 7. 写 session_event_log（4 个事件）
        _save_event(conn, session_id, account_id, 'session_created',
                    context={'entry_price': entry_price, 'basis_price': entry_price, 'atr': n_value})
        _save_event(conn, session_id, account_id, 'order_submitted',
                    unit_id=None, context={'order_id': order_id, 'price': entry_price, 'hand_count': 1, 'direction': direction})
        _save_event(conn, session_id, account_id, 'order_filled',
                    unit_id=unit_id, trade_id=trade_id, context={'trade_id': trade_id, 'filled_price': entry_price, 'slippage': 0, 'fee': 0.0})
        _save_event(conn, session_id, account_id, 'units_changed',
                    unit_id=unit_id, context={'from_units': 0, 'to_units': 1, 'unit_id': unit_id, 'reason': '建仓'})
        
        conn.commit()
        
        # 8. v1.5 Phase 3.8: 写 turtle_trade_process（entry_signal + entry_filled）
        # 注：trade_process_logger 自带连接、独立事务，失败不影响主流程
        try:
            from strategies.trade_process_logger import log_turtle_event, EVT_ENTRY_SIGNAL, EVT_ENTRY_FILLED
            sig_type = 'entry_long' if direction == 'long' else 'entry_short'
            log_turtle_event(
                session_id=session_id, account_id=account_id,
                event_type=EVT_ENTRY_SIGNAL,
                bar_time=now,
                bar_open=entry_price, bar_high=entry_price,
                bar_low=entry_price, bar_close=entry_price,
                signal_type=sig_type,
                signal_price=entry_price,
                reference_price=entry_price,
                n_value=n_value,
                decision_reason=f'v1.5 on_bar: {strategy_id} {direction} @ {entry_price}'
            )
            log_turtle_event(
                session_id=session_id, account_id=account_id,
                event_type=EVT_ENTRY_FILLED,
                bar_time=now,
                bar_open=entry_price, bar_high=entry_price,
                bar_low=entry_price, bar_close=entry_price,
                signal_type=sig_type,
                signal_price=entry_price,
                exec_status='filled',
                exec_price=entry_price,
                exec_hand_count=1,
                exec_time=now,
                slippage=0,
                decision_reason='撮合成交'
            )
        except Exception as _e:
            logger.warning(f"写 turtle_trade_process entry 事件失败（不影响主流程）: {_e}")
        logger.info(f"✅ 建仓成功: {session_id[:8]} {account_id} {strategy_id} {direction} {symbol} {entry_price} N={n_value}")
        return session_id
    except Exception as e:
        conn.rollback()
        logger.error(f"open_session 失败: {e}")
        raise
    finally:
        conn.close()


def add_unit(session_id: str, add_price: float, n_value: Optional[float] = None) -> str:
    """
    加仓（海龟 0.5N 间隔检测由调用方负责）
    
    Returns:
        unit_id (UUID)
    """
    unit_id = _gen_uuid()
    order_id = _gen_uuid()
    trade_id = _gen_uuid()
    
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT account_id, strategy_id, symbol, contract_code, direction, current_units, total_units FROM trade_sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"session {session_id} 不存在")
        account_id, strategy_id, symbol, contract_code, direction, current_units, total_units = row
        
        if current_units >= 4:
            raise ValueError(f"session {session_id} 已达最大 unit 数（4）")
        
        new_unit_index = current_units + 1
        now = _now_iso()
        
        # 1. 写 position_units
        cur.execute("""
            INSERT INTO position_units(unit_id, session_id, account_id, unit_index, open_price, current_price, open_hand_count, status, is_gap, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, 'open', 0, ?, ?)
        """, (unit_id, session_id, account_id, new_unit_index, add_price, add_price, now, now))
        
        # 2. 写 sim_orders / sim_trades
        cur.execute("""
            INSERT INTO sim_orders(order_id, account_id, session_id, symbol, contract_code, direction, order_type, quantity, status, filled_quantity, avg_filled_price, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'market', 1, 'filled', 1, ?, ?, ?)
        """, (order_id, account_id, session_id, symbol, contract_code, direction, add_price, now, now))
        
        cur.execute("""
            INSERT INTO sim_trades(trade_id, order_id, account_id, session_id, symbol, contract_code, direction, filled_price, filled_quantity, commission, filled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0.0, ?)
        """, (trade_id, order_id, account_id, session_id, symbol, contract_code, direction, add_price, now))
        
        # 3. 更新 trade_sessions
        cur.execute("UPDATE trade_sessions SET current_units = ?, total_units = ?, updated_at = ? WHERE session_id = ?", (new_unit_index, total_units + 1, now, session_id))
        
        # 4. 更新 sim_positions
        cur.execute("""
            UPDATE sim_positions SET quantity = quantity + 1, avg_cost = ((avg_cost * quantity) + ?) / (quantity + 1), updated_at = ?
            WHERE account_id = ? AND symbol = ?
        """, (add_price, now, account_id, symbol))
        
        # 5. 更新 turtle_session_data.add_count
        cur.execute("UPDATE turtle_session_data SET add_count = add_count + 1, updated_at = ? WHERE session_id = ?", (now, session_id))
        
        # 6. 写 events
        _save_event(conn, session_id, account_id, 'order_submitted',
                    context={'order_id': order_id, 'price': add_price, 'hand_count': 1, 'direction': direction})
        _save_event(conn, session_id, account_id, 'order_filled',
                    unit_id=unit_id, trade_id=trade_id, context={'trade_id': trade_id, 'filled_price': add_price})
        _save_event(conn, session_id, account_id, 'units_changed',
                    unit_id=unit_id, context={'from_units': current_units, 'to_units': new_unit_index, 'unit_id': unit_id, 'reason': '加仓'})
        
        conn.commit()
        
        # 7. v1.5 Phase 3.8: 写 turtle_trade_process（add_signal + add_filled）
        try:
            from strategies.trade_process_logger import log_turtle_event, EVT_ADD_SIGNAL, EVT_ADD_FILLED
            sig_type = 'add_long' if direction == 'long' else 'add_short'
            log_turtle_event(
                session_id=session_id, account_id=account_id,
                event_type=EVT_ADD_SIGNAL,
                bar_time=now,
                bar_open=add_price, bar_high=add_price,
                bar_low=add_price, bar_close=add_price,
                signal_type=sig_type,
                signal_price=add_price,
                reference_price=add_price,
                n_value=n_value,
                decision_reason=f'v1.5 加仓 signal: {direction} unit {new_unit_index} @ {add_price}'
            )
            log_turtle_event(
                session_id=session_id, account_id=account_id,
                event_type=EVT_ADD_FILLED,
                bar_time=now,
                bar_open=add_price, bar_high=add_price,
                bar_low=add_price, bar_close=add_price,
                signal_type=sig_type,
                signal_price=add_price,
                exec_status='filled',
                exec_price=add_price,
                exec_hand_count=1,
                exec_time=now,
                slippage=0,
                decision_reason='加仓成交'
            )
        except Exception as _e:
            logger.warning(f"写 turtle_trade_process add 事件失败（不影响主流程）: {_e}")
        logger.info(f"✅ 加仓成功: {session_id[:8]} {symbol} unit {current_units}→{new_unit_index} @ {add_price}")
        return unit_id
    except Exception as e:
        conn.rollback()
        logger.error(f"add_unit 失败: {e}")
        raise
    finally:
        conn.close()


def close_unit(unit_id: str, close_price: float, reason: str = 'manual') -> bool:
    """
    减仓 / 平单个 unit
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT pu.session_id, pu.account_id, ts.symbol, pu.open_price, pu.open_hand_count
            FROM position_units pu
            JOIN trade_sessions ts ON pu.session_id = ts.session_id
            WHERE pu.unit_id = ?
        """, (unit_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"unit {unit_id} 不存在")
        session_id, account_id, symbol, open_price, hand_count = row
        
        now = _now_iso()
        
        # 1. 更新 position_units
        cur.execute("UPDATE position_units SET status = 'closed', close_price = ?, close_time = ?, close_hand_count = ?, updated_at = ? WHERE unit_id = ?",
                    (close_price, now, hand_count, now, unit_id))
        
        # 2. 更新 trade_sessions.current_units
        cur.execute("UPDATE trade_sessions SET current_units = current_units - 1, updated_at = ? WHERE session_id = ?", (now, session_id))
        
        # 3. 更新 sim_positions
        cur.execute("UPDATE sim_positions SET quantity = quantity - 1, updated_at = ? WHERE account_id = ? AND symbol = ?", (now, account_id, symbol))
        
        # 4. 写 event
        _save_event(conn, session_id, account_id, 'unit_closed',
                    unit_id=unit_id, context={'close_price': close_price, 'reason': reason, 'open_price': open_price, 'pnl': close_price - open_price})
        
        conn.commit()
        
        # 5. v1.5 Phase 3.8: 写 turtle_trade_process（unit_closed）
        try:
            from strategies.trade_process_logger import log_turtle_event, EVT_UNIT_CLOSED
            log_turtle_event(
                session_id=session_id, account_id=account_id,
                event_type=EVT_UNIT_CLOSED,
                bar_time=now,
                bar_open=open_price, bar_high=close_price,
                bar_low=open_price, bar_close=close_price,
                signal_type='manual',
                signal_price=close_price,
                exec_status='closed',
                exec_price=close_price,
                exec_hand_count=hand_count,
                exec_time=now,
                slippage=close_price - open_price,
                decision_reason=reason
            )
        except Exception as _e:
            logger.warning(f"写 turtle_trade_process unit_closed 事件失败（不影响主流程）: {_e}")
        logger.info(f"✅ 减仓成功: unit {unit_id[:8]} {symbol} @ {close_price} (open {open_price}, reason {reason})")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"close_unit 失败: {e}")
        raise
    finally:
        conn.close()


def close_session(session_id: str, exit_price: float, reason: str = 'manual') -> bool:
    """
    全部平仓（关闭整个 session + 所有 open units）
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT account_id, symbol, current_units, status FROM trade_sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"session {session_id} 不存在")
        account_id, symbol, current_units, session_status = row
        
        if session_status != 'open':
            raise ValueError(f"session {session_id} 状态为 {session_status}，不能再次 close")
        
        now = _now_iso()
        
        # 1. 关闭所有 open units
        cur.execute("SELECT unit_id, open_price FROM position_units WHERE session_id = ? AND status = 'open'", (session_id,))
        open_units = cur.fetchall()
        for u_id, u_open in open_units:
            cur.execute("UPDATE position_units SET status = 'closed', close_price = ?, close_time = ?, close_hand_count = open_hand_count, updated_at = ? WHERE unit_id = ?",
                        (exit_price, now, now, u_id))
            _save_event(conn, session_id, account_id, 'unit_closed',
                        unit_id=u_id, context={'close_price': exit_price, 'reason': reason, 'open_price': u_open, 'session_close': True})
        
        # 2. 更新 trade_sessions
        cur.execute("UPDATE trade_sessions SET status = 'closed', exit_time = ?, exit_reason = ?, current_units = 0, updated_at = ? WHERE session_id = ?",
                    (now, reason, now, session_id))
        
        # 3. 清 sim_positions（quantity 设为 0，保留记录）
        cur.execute("UPDATE sim_positions SET quantity = 0, updated_at = ? WHERE account_id = ? AND symbol = ?", (now, account_id, symbol))
        
        # 4. 写 status_changed event
        _save_event(conn, session_id, account_id, 'status_changed', context={'from_status': 'open', 'to_status': 'closed', 'reason': reason})
        
        conn.commit()
        logger.info(f"✅ 全部平仓: session {session_id[:8]} {symbol} @ {exit_price} ({len(open_units)} units, reason {reason})")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"close_session 失败: {e}")
        raise
    finally:
        conn.close()


# CLI 入口（用于手动测试）
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python -m api.services.sim_engine <command> [args]")
        print("  submit <account_id> <symbol> <contract> <direction> <order_type> <quantity> [price]")
        print("  open <account_id> <strategy_id> <symbol> <contract> <direction> <entry_price> [n_value]")
        print("  add <session_id> <add_price> [n_value]")
        print("  close_unit <unit_id> <close_price> [reason]")
        print("  close_session <session_id> <exit_price> [reason]")
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == 'open':
        session_id = open_session(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], float(sys.argv[7]),
                                  float(sys.argv[8]) if len(sys.argv) > 8 else None)
        print(f"session_id={session_id}")
    elif cmd == 'add':
        unit_id = add_unit(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]) if len(sys.argv) > 4 else None)
        print(f"unit_id={unit_id}")
    elif cmd == 'close_unit':
        ok = close_unit(sys.argv[2], float(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else 'manual')
        print(f"ok={ok}")
    elif cmd == 'close_session':
        ok = close_session(sys.argv[2], float(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else 'manual')
        print(f"ok={ok}")
    else:
        print(f"未知命令: {cmd}")
