"""
Session 生命周期管理器（v1.5 Phase 3.3）

职责：
1. 状态机：pending → open → closed（closed 后不可重开）
2. 应用层互斥锁：session_lock dict（per session_id 锁）
3. 状态转换事件：所有 status 变化写 session_event_log
4. 重复检测：UNIQUE(account_id, strategy_id, direction, entry_time) 触发时给出友好错误
5. session 列表查询：active sessions / closed sessions

注意：
- 应用层互斥锁（非 DB 锁）：适合单进程 / 多线程；多进程部署需加 Redis 锁（Phase 7）
- HTTP 423 = Locked 状态码（RFC 4918）
"""
import sqlite3
import json
import uuid
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_DIR / "futures_akshare.db"

# 应用层 session_lock（per session_id）
_session_locks: Dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_session_lock(session_id: str) -> threading.Lock:
    """获取或创建 session 的应用层锁"""
    with _locks_lock:
        if session_id not in _session_locks:
            _session_locks[session_id] = threading.Lock()
        return _session_locks[session_id]


def _conn():
    """获取启用 FK 的连接"""
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


# ============================================================
# 状态机常量
# ============================================================
STATUS_PENDING = 'pending'
STATUS_OPEN = 'open'
STATUS_CLOSED = 'closed'

VALID_STATUSES = {STATUS_PENDING, STATUS_OPEN, STATUS_CLOSED}
ALLOWED_TRANSITIONS = {
    STATUS_PENDING: {STATUS_OPEN, STATUS_CLOSED},  # pending → open/closed
    STATUS_OPEN: {STATUS_CLOSED},                   # open → closed
    STATUS_CLOSED: set(),                            # closed 终点
}


def validate_status_transition(from_status: str, to_status: str) -> bool:
    """验证状态转换是否合法"""
    if from_status not in VALID_STATUSES:
        return False
    if to_status not in VALID_STATUSES:
        return False
    return to_status in ALLOWED_TRANSITIONS[from_status]


# ============================================================
# 核心 API
# ============================================================
class SessionLockedError(Exception):
    """Session 被其他请求持有锁（HTTP 423）"""
    def __init__(self, session_id: str, holder: str = 'other'):
        self.session_id = session_id
        self.holder = holder
        super().__init__(f"Session {session_id} 被 {holder} 锁定")


class DuplicateSessionError(Exception):
    """UNIQUE 约束冲突：相同 (account_id, strategy_id, direction, entry_time) 的 session 已存在"""
    def __init__(self, account_id: str, strategy_id: str, direction: str, entry_time: str):
        self.account_id = account_id
        self.strategy_id = strategy_id
        self.direction = direction
        self.entry_time = entry_time
        super().__init__(f"Session 已存在: account={account_id} strategy={strategy_id} dir={direction} entry_time={entry_time}")


def check_duplicate_session(account_id: str, strategy_id: str, direction: str, entry_time: str) -> bool:
    """
    检查 (account_id, strategy_id, direction, entry_time) UNIQUE 约束
    
    Returns:
        True = 有重复；False = 无重复
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM trade_sessions
            WHERE account_id = ? AND strategy_id = ? AND direction = ? AND entry_time = ?
            LIMIT 1
        """, (account_id, strategy_id, direction, entry_time))
        return cur.fetchone() is not None
    finally:
        conn.close()


def acquire_session_lock(session_id: str, holder: str = 'caller', blocking: bool = False, timeout: float = 0.0) -> bool:
    """
    拿 session 的应用层锁
    
    Args:
        session_id: 锁定的 session ID
        holder: 持锁人标识（用于调试）
        blocking: 是否阻塞等待（False = 拿不到立即返回 False）
        timeout: 阻塞超时秒数
    
    Returns:
        True = 拿到锁；False = 拿不到
    """
    lock = _get_session_lock(session_id)
    if blocking:
        acquired = lock.acquire(blocking=True, timeout=timeout)
    else:
        acquired = lock.acquire(blocking=False)
    if acquired:
        logger.debug(f"🔒 Session 锁获取: {session_id[:8]} by {holder}")
    else:
        logger.warning(f"🔒 Session 锁失败: {session_id[:8]} by {holder}")
    return acquired


def release_session_lock(session_id: str, holder: str = 'caller') -> None:
    """释放 session 的应用层锁"""
    with _locks_lock:
        if session_id in _session_locks:
            try:
                _session_locks[session_id].release()
                logger.debug(f"🔓 Session 锁释放: {session_id[:8]} by {holder}")
            except RuntimeError as e:
                logger.warning(f"🔓 Session 锁释放失败: {session_id[:8]} - {e}")


def with_session_lock(session_id: str, holder: str = 'caller'):
    """
    上下文管理器：自动拿/释放 session 锁
    
    用法：
        with with_session_lock(sid, 'api_caller'):
            # 操作 session
    """
    from contextlib import contextmanager
    @contextmanager
    def _ctx():
        if not acquire_session_lock(session_id, holder, blocking=True, timeout=5.0):
            raise SessionLockedError(session_id, holder)
        try:
            yield
        finally:
            release_session_lock(session_id, holder)
    return _ctx()


def transition_status(session_id: str, to_status: str, reason: str = '') -> bool:
    """
    状态转换：pending → open → closed
    
    Returns:
        True = 转换成功；False = 转换非法
    """
    if to_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {to_status}")
    
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT account_id, status FROM trade_sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"session {session_id} 不存在")
        account_id, from_status = row
        
        if not validate_status_transition(from_status, to_status):
            logger.warning(f"❌ 非法状态转换: {session_id[:8]} {from_status} → {to_status}")
            return False
        
        now = _now_iso()
        update_fields = ['status = ?', 'updated_at = ?']
        params = [to_status, now]
        if to_status == STATUS_CLOSED:
            update_fields.append('exit_time = ?')
            update_fields.append('exit_reason = ?')
            params.extend([now, reason])
        
        params.append(session_id)
        cur.execute(f"UPDATE trade_sessions SET {', '.join(update_fields)} WHERE session_id = ?", params)
        
        # 写 status_changed 事件
        _save_event(conn, session_id, account_id, 'status_changed',
                    context={'from_status': from_status, 'to_status': to_status, 'reason': reason})
        
        conn.commit()
        logger.info(f"✅ 状态转换: {session_id[:8]} {from_status} → {to_status} ({reason})")
        return True
    finally:
        conn.close()


def list_sessions(account_id: Optional[str] = None, status: Optional[str] = None, 
                  strategy_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    列出会话（按条件过滤）
    
    Args:
        account_id: 账户（None = 全部）
        status: 状态过滤（None = 全部 / 'open' / 'closed' / 'pending'）
        strategy_id: 策略过滤
        limit: 返回数量上限
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        conditions = []
        params = []
        if account_id:
            conditions.append("account_id = ?")
            params.append(account_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if strategy_id:
            conditions.append("strategy_id = ?")
            params.append(strategy_id)
        
        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        cur.execute(f"""
            SELECT session_id, account_id, strategy_id, symbol, contract_code, direction, status,
                   entry_time, exit_time, current_units, total_units, first_entry_price,
                   entry_basis_price, entry_locked_atr, exit_reason
            FROM trade_sessions
            WHERE {where}
            ORDER BY entry_time DESC LIMIT ?
        """, params)
        rows = [dict(row) for row in cur.fetchall()]
        return rows
    finally:
        conn.close()


def get_session_detail(session_id: str) -> Optional[Dict[str, Any]]:
    """
    单个 session 完整详情（含 4 units + turtle_session_data + 最近 20 events）
    """
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM trade_sessions WHERE session_id = ?", (session_id,))
        sess_row = cur.fetchone()
        if not sess_row:
            return None
        session = dict(sess_row)
        # 解析 price_overrides_json
        try:
            session['price_overrides'] = json.loads(session.pop('price_overrides_json') or '{}')
        except Exception:
            session['price_overrides'] = {}
        
        # units
        cur.execute("SELECT * FROM position_units WHERE session_id = ? ORDER BY unit_index", (session_id,))
        session['units'] = [dict(r) for r in cur.fetchall()]
        
        # turtle_session_data
        cur.execute("SELECT * FROM turtle_session_data WHERE session_id = ?", (session_id,))
        tsd_row = cur.fetchone()
        session['turtle_data'] = dict(tsd_row) if tsd_row else None
        
        # 最近 20 events
        cur.execute("""
            SELECT id, event_type, event_at, unit_id, trade_id, context_json
            FROM session_event_log
            WHERE session_id = ?
            ORDER BY event_at DESC LIMIT 20
        """, (session_id,))
        events = [dict(r) for r in cur.fetchall()]
        for e in events:
            try:
                e['context'] = json.loads(e.pop('context_json') or '{}')
            except Exception:
                e['context'] = {}
        session['events'] = events
        
        return session
    finally:
        conn.close()


# CLI 入口
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  list [account_id] [status]  - 列出会话")
        print("  detail <session_id>          - 单个 session 详情")
        print("  transition <session_id> <to_status> [reason]  - 状态转换")
        print("  check_duplicate <account> <strategy> <direction> <entry_time>  - 检查重复")
        sys.exit(0)
    
    cmd = sys.argv[1]
    if cmd == 'list':
        kwargs = {}
        if len(sys.argv) > 2:
            kwargs['account_id'] = sys.argv[2]
        if len(sys.argv) > 3:
            kwargs['status'] = sys.argv[3]
        sessions = list_sessions(**kwargs)
        print(f"共 {len(sessions)} 个 session:")
        for s in sessions[:5]:
            print(f"  {s['session_id'][:8]} {s['account_id']} {s['strategy_id']} {s['direction']} {s['symbol']} {s['status']} units={s['current_units']}")
    elif cmd == 'detail':
        detail = get_session_detail(sys.argv[2])
        if detail:
            print(f"session: {detail['session_id']}")
            print(f"  status: {detail['status']}")
            print(f"  units: {len(detail.get('units', []))}")
            for u in detail.get('units', []):
                print(f"    unit {u['unit_index']}: open={u['open_price']} status={u['status']}")
            print(f"  events: {len(detail.get('events', []))}")
        else:
            print("session 不存在")
    elif cmd == 'transition':
        ok = transition_status(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else '')
        print(f"ok={ok}")
    elif cmd == 'check_duplicate':
        dup = check_duplicate_session(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        print(f"duplicate={dup}")
    else:
        print(f"未知命令: {cmd}")
