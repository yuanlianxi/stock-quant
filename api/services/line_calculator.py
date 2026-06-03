"""
价格线计算服务（v1.5 简化版）

价格线 = 海龟策略的 3 条关键价位（实时计算，不持久化）

- 红线（stop_loss）：entry_price - 2 * N（海龟止损，2N）
- 蓝线（add）：entry_price + 0.5 * N（0.5N 加仓间隔，多 Unit 时 N 递增）
- 紫线（exit_20）：20日反向平仓位（多单：20日最低，空单：20日最高）

调价 override：用户拖动水平线 → price_overrides_json 中存新价 → 重算时优先用 override
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

# 价格线类型
LINE_STOP_LOSS = 'stop_loss'    # 红线
LINE_ADD = 'add'                # 蓝线
LINE_EXIT_20 = 'exit_20'        # 紫线

LINE_TYPES = {LINE_STOP_LOSS, LINE_ADD, LINE_EXIT_20}

# 缓存（per session_id）
_line_cache: Dict[str, Dict[str, Any]] = {}


def _conn():
    """获取启用 FK 的连接 + Row factory"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now().isoformat()


def _save_event(conn, session_id: str, account_id: str, event_type: str, context: Optional[Dict] = None) -> int:
    """写 session_event_log"""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO session_event_log(session_id, account_id, event_type, event_at, context_json)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, account_id, event_type, _now_iso(),
          json.dumps(context, ensure_ascii=False) if context else None))
    return cur.lastrowid


def _get_n_value(session_id: str) -> Optional[float]:
    """从 turtle_session_data 取 entry_atr_20（= N 值）"""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT entry_atr_20 FROM turtle_session_data WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if not row or row['entry_atr_20'] is None:
            return None
        return row['entry_atr_20']
    finally:
        conn.close()


def _get_avg_entry_price(session_id: str) -> Optional[float]:
    """计算 session 的平均入场价（4 unit 加权平均）"""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT AVG(open_price) as avg_price, COUNT(*) as cnt
            FROM position_units
            WHERE session_id = ? AND status = 'open'
        """, (session_id,))
        row = cur.fetchone()
        if not row or row['cnt'] == 0:
            return None
        return row['avg_price']
    finally:
        conn.close()


def _get_exit_20_price(session_id: str, direction: str) -> Optional[float]:
    """
    20日反向平仓位：
    - 多单 (long)：20日最低
    - 空单 (short)：20日最高
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT symbol FROM trade_sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            return None
        symbol = row['symbol']
        
        # 取最近 20 个交易日的日线数据
        cur.execute("""
            SELECT date, low, high FROM futures_daily
            WHERE symbol = ?
            ORDER BY date DESC LIMIT 20
        """, (symbol,))
        rows = cur.fetchall()
        if not rows:
            return None
        
        if direction == 'long':
            return min(r['low'] for r in rows)
        elif direction == 'short':
            return max(r['high'] for r in rows)
        return None
    finally:
        conn.close()


def _compute_lines_no_override(session_id: str) -> Dict[str, Any]:
    """计算无 override 的价格线"""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT account_id, symbol, direction, first_entry_price FROM trade_sessions WHERE session_id = ?", (session_id,))
        sess = cur.fetchone()
        if not sess:
            raise ValueError(f"session {session_id} 不存在")
        
        entry_price = sess['first_entry_price'] or _get_avg_entry_price(session_id)
        if entry_price is None:
            raise ValueError(f"session {session_id} 无 entry_price")
        
        n_value = _get_n_value(session_id) or 0.0
        exit_20_price = _get_exit_20_price(session_id, sess['direction'])
        
        # 3 线计算
        if sess['direction'] == 'long':
            stop_loss = entry_price - 2 * n_value
            add_line = entry_price + 0.5 * n_value
            exit_20_line = exit_20_price  # 多单：20日最低
        elif sess['direction'] == 'short':
            stop_loss = entry_price + 2 * n_value
            add_line = entry_price - 0.5 * n_value
            exit_20_line = exit_20_price  # 空单：20日最高
        else:
            raise ValueError(f"Unknown direction: {sess['direction']}")
        
        return {
            'entry_price': entry_price,
            'n_value': n_value,
            'direction': sess['direction'],
            'lines': {
                LINE_STOP_LOSS: round(stop_loss, 2),
                LINE_ADD: round(add_line, 2),
                LINE_EXIT_20: round(exit_20_line, 2) if exit_20_line else None
            }
        }
    finally:
        conn.close()


def compute_lines(session_id: str, use_cache: bool = True) -> Dict[str, Any]:
    """
    计算价格线（带 override + 缓存）
    
    Args:
        session_id: session ID
        use_cache: True = 用缓存（除非 override 变了）
    
    Returns:
        {
            'session_id': '...',
            'entry_price': 17500.0,
            'n_value': 200.0,
            'direction': 'long',
            'lines': {
                'stop_loss': 17100.0,
                'add': 17600.0,
                'exit_20': 16900.0
            },
            'overrides': {
                'stop_loss': 17050.0,  # 用户调过
                'add': null,
                'exit_20': null
            }
        }
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        # 取 price_overrides_json
        cur.execute("SELECT account_id, price_overrides_json FROM trade_sessions WHERE session_id = ?", (session_id,))
        sess = cur.fetchone()
        if not sess:
            raise ValueError(f"session {session_id} 不存在")
        
        try:
            overrides = json.loads(sess['price_overrides_json'] or '{}')
        except Exception:
            overrides = {}
        
        # 缓存检查：override 没变 + use_cache=True → 用缓存
        cache_key = session_id
        if use_cache and cache_key in _line_cache:
            cached = _line_cache[cache_key]
            if cached.get('overrides') == overrides:
                return cached['result']
        
        # 计算基础线
        result = _compute_lines_no_override(session_id)
        result['session_id'] = session_id
        result['overrides'] = {lt: overrides.get(lt) for lt in LINE_TYPES}
        
        # 应用 override
        for line_type, override_price in overrides.items():
            if line_type in LINE_TYPES and override_price is not None:
                result['lines'][line_type] = round(override_price, 2)
        
        # 写缓存
        _line_cache[cache_key] = {
            'overrides': dict(overrides),
            'result': result
        }
        
        return result
    finally:
        conn.close()


def override_line(session_id: str, line_type: str, price: Optional[float], account_id: Optional[str] = None) -> Dict[str, Any]:
    """
    用户调价：写入 price_overrides_json + 写 line_overridden 事件
    
    Args:
        session_id: session ID
        line_type: stop_loss / add / exit_20
        price: 新价格（None = 取消 override）
        account_id: 用于写事件（可选，从 session 推）
    
    Returns:
        调价后最新的价格线
    """
    if line_type not in LINE_TYPES:
        raise ValueError(f"Invalid line_type: {line_type}，必须是 {LINE_TYPES}")
    
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT account_id, price_overrides_json FROM trade_sessions WHERE session_id = ?", (session_id,))
        sess = cur.fetchone()
        if not sess:
            raise ValueError(f"session {session_id} 不存在")
        actual_account_id = sess['account_id']
        if account_id is None:
            account_id = actual_account_id
        
        try:
            overrides = json.loads(sess['price_overrides_json'] or '{}')
        except Exception:
            overrides = {}
        
        old_price = overrides.get(line_type)
        if price is None:
            overrides.pop(line_type, None)
        else:
            overrides[line_type] = float(price)
        
        # 写 price_overrides_json
        cur.execute("""
            UPDATE trade_sessions
            SET price_overrides_json = ?, updated_at = ?
            WHERE session_id = ?
        """, (json.dumps(overrides, ensure_ascii=False), _now_iso(), session_id))
        
        # 写 line_overridden 事件
        _save_event(conn, session_id, account_id, 'line_overridden',
                    context={'line_type': line_type, 'old_price': old_price, 'new_price': price})
        
        conn.commit()
        
        # 失效缓存
        _line_cache.pop(session_id, None)
        
        logger.info(f"✅ 调价: {session_id[:8]} {line_type} {old_price} → {price}")
        
        # 返回新价格线
        return compute_lines(session_id, use_cache=False)
    except Exception as e:
        conn.rollback()
        logger.error(f"override_line 失败: {e}")
        raise
    finally:
        conn.close()


def clear_cache(session_id: Optional[str] = None) -> None:
    """清缓存（None = 清全部）"""
    if session_id is None:
        _line_cache.clear()
    else:
        _line_cache.pop(session_id, None)


# CLI 入口
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  compute <session_id>")
        print("  override <session_id> <line_type> <price>   # price = 'null' 取消")
        print("  clear [session_id]")
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == 'compute':
        result = compute_lines(sys.argv[2], use_cache=False)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'override':
        price = None if sys.argv[4] == 'null' else float(sys.argv[4])
        result = override_line(sys.argv[2], sys.argv[3], price)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'clear':
        sid = sys.argv[2] if len(sys.argv) > 2 else None
        clear_cache(sid)
        print(f"cache cleared (session_id={sid})")
    else:
        print(f"未知命令: {cmd}")
