"""
pytest 配置文件（Phase 6.1）

策略：
1. 临时 sqlite DB（每个测试函数独立）—— 复制 production DB 到 tempfile
2. Monkey-patch 所有 service / loader 的 _conn / get_conn / sqlite3.connect 走同一个 DB_PATH
3. 4 个账户 + 1 个策略 fixture
4. 自动清理（fixture teardown）

绝不修改 production DB。
"""
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# ============================================================
# 项目根路径
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
PROD_DB_PATH = PROJECT_ROOT / "data" / "futures_akshare.db"


# ============================================================
# 临时 DB（每个测试函数独立）
# ============================================================
@pytest.fixture
def temp_db(monkeypatch):
    """
    临时 sqlite DB fixture

    实现：
    1. mkstemp 临时文件
    2. 复制 production DB → 临时文件（含 schema + 数据）
    3. Patch 所有 service / loader 的 _conn / get_conn / sqlite3.connect 走临时文件
    4. teardown 删临时文件
    """
    # 1. 创建临时文件
    fd, tmppath = tempfile.mkstemp(suffix=".db", prefix="stockquant_test_")
    os.close(fd)
    db_path = Path(tmppath)

    # 2. 复制 production DB
    shutil.copy(str(PROD_DB_PATH), str(db_path))

    # 3. 定义 patched conn
    def patched_conn():
        """统一的连接工厂"""
        c = sqlite3.connect(str(db_path))
        c.execute("PRAGMA foreign_keys = ON")
        c.row_factory = sqlite3.Row
        return c

    # 4. Patch 所有 service 的 _conn
    from api.services import sim_engine, session_lifecycle, line_calculator, event_logger
    from strategies import trade_process_logger as tpl
    from backtest import backtest_engine

    # sim_engine 用的 _conn 不带 row_factory（用了 cur.fetchone() 取 tuple）
    def sim_conn():
        c = sqlite3.connect(str(db_path))
        c.execute("PRAGMA foreign_keys = ON")
        return c

    monkeypatch.setattr(sim_engine, "_conn", sim_conn)
    monkeypatch.setattr(session_lifecycle, "_conn", patched_conn)
    monkeypatch.setattr(line_calculator, "_conn", patched_conn)
    monkeypatch.setattr(event_logger, "_conn", patched_conn)
    monkeypatch.setattr(tpl, "_conn", patched_conn)
    monkeypatch.setattr(backtest_engine, "_conn", patched_conn)

    # 5. Patch strategies/loader.py 的 sqlite3.connect（动态 import，需要 module-level patch）
    import strategies.loader
    import strategies.executor
    from strategies.trade_process_logger import log_turtle_event as _orig_log
    import strategies.trade_process_logger as tpl_mod

    # loader.executor.trade_process_logger 都用各自的 sqlite3.connect + DB_PATH
    # 简单做法：patch DB_PATH 指向临时文件
    monkeypatch.setattr(strategies.loader, "DB_PATH", db_path)
    monkeypatch.setattr(strategies.executor, "DB_PATH", db_path)
    monkeypatch.setattr(tpl_mod, "DB_PATH", db_path)

    # 6. Patch data.data_loader (如果有引用)
    try:
        import data.data_loader as dl
        if hasattr(dl, "DB_PATH"):
            monkeypatch.setattr(dl, "DB_PATH", db_path)
        if hasattr(dl, "get_conn"):
            monkeypatch.setattr(dl, "get_conn", patched_conn)
    except Exception:
        pass

    # 清 line_calculator / event_logger 的 in-memory 缓存（避免跨测试污染）
    try:
        line_calculator.clear_cache()
    except Exception:
        pass

    yield db_path

    # 7. Teardown
    try:
        os.unlink(tmppath)
    except OSError:
        pass


# ============================================================
# 账户 / 策略 fixture
# ============================================================
@pytest.fixture
def sim_default():
    return "sim_default"


@pytest.fixture
def sim_user1():
    return "sim_user1"


@pytest.fixture
def sim_user2():
    return "sim_user2"


@pytest.fixture
def turtle_strategy():
    return "turtle_v1"
