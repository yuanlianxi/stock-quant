"""
T1 海龟交易系统 - 数据层（akshare 版）
=======================================
增量更新 + 分时数据 + 缓存自动清理

缓存策略：
  - 日线：最多保留 14 天，每次增量更新只拉比缓存最新的日期更晚的数据
  - 分时（分钟/小时）：最多保留 7 天，每天收盘后增量拉当天数据
  - 缓存过期自动清理（每次写入前执行）

用途：
  - P1 回测引擎数据供给
  - P5 全品种回测数据获取
  - FastAPI 实时信号计算
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import numpy as np
import yaml

# 加载品种中文名
INSTRUMENTS_PATH = Path(__file__).parent.parent / "config" / "instruments.yaml"
SYMBOL_NAME = {}
try:
    with open(INSTRUMENTS_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
        for sym, info in cfg.get("instruments", {}).items():
            SYMBOL_NAME[sym.upper()] = info.get("name", sym)
except Exception as e:
    print(f"Warning: failed to load instruments.yaml: {e}")

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("Warning: akshare not installed. Run: pip install akshare")

# ============================================================
# 常量配置
# ============================================================

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "futures_akshare.db"

DAILY_RETENTION_DAYS = 1095  # 日线保留 3 年（策略回测需长期历史；v1.5 从 62 调至 1095）
MIN_RETENTION_DAYS = 180     # 分时保留半年（半年历史够回测；v1.5 从 7 调至 180）

# ============================================================
# 数据库初始化
# ============================================================

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    # SQLite 默认不启用 FK，连接后必须显式打开（PRAGMA 仅对当前连接有效）
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _add_column_if_not_exists(cur, table: str, column: str, col_type: str):
    """幂等加列（SQLite 没有 IF NOT EXISTS for column）"""
    cur.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        print(f"[DB] Added column {table}.{column} ({col_type})")


def init_db():
    """初始化/升级数据库表（v1.5 幂等自动迁移）

    每次启动都会跑这个函数，自动完成：
    - 新表创建（futures_contracts / futures_quotes / strategies /
      strategy_param_history / strategy_signals / strategy_event_log /
      turtle_trade_process）
    - Phase 3.1 新增：sim_account / trade_sessions / sim_orders / sim_trades /
      sim_positions / position_units / turtle_session_data / session_event_log /
      live_orders / live_trades / live_positions（11 张表 + 7 索引 + 3 种子账户）
    - Phase 3.1 修复：turtle_trade_process 重建带 FK → trade_sessions
    - 现有表加列（futures_daily.atr / main_contract_code, futures_min.date）
    - ATR 数据从 futures_atr 迁移到 futures_daily.atr（幂等）
    - 删除已废弃的 futures_atr 表
    - 创建索引
    - 启用 PRAGMA foreign_keys = ON（让 FK 约束生效）
    - 清理过期缓存数据
    """
    conn = get_conn()
    cur = conn.cursor()

    # ===== 新表 1：futures_contracts（合约静态信息）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS futures_contracts (
            contract_code TEXT PRIMARY KEY,
            symbol        TEXT NOT NULL,
            name          TEXT,
            exchange      TEXT NOT NULL,
            list_date     TEXT,
            expire_date   TEXT,
            is_main       INTEGER DEFAULT 0,
            main_rank     INTEGER DEFAULT 99,
            contract_size REAL,
            point_value   REAL,
            tick          REAL,
            margin_ratio  REAL,
            last_volume   REAL,
            last_oi       REAL,
            updated_at    TEXT,
            status        TEXT DEFAULT 'active'
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fc_symbol ON futures_contracts(symbol)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fc_main ON futures_contracts(symbol, is_main)")

    # ===== 新表 2：futures_quotes（合约实时行情，30s 刷新）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS futures_quotes (
            contract_code TEXT PRIMARY KEY,
            symbol        TEXT NOT NULL,
            trade         REAL, change_abs REAL, change_pct REAL,
            open          REAL, high REAL, low REAL,
            preclose      REAL, presettlement REAL, settlement REAL,
            volume        REAL, position REAL,
            bidprice1     REAL, askprice1 REAL,
            bidvol1       REAL, askvol1 REAL,
            ticktime      TEXT, updated_at TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fq_update_time ON futures_quotes(updated_at)")

    # ===== 现有表：futures_daily（确保存在 + 加列）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS futures_daily (
            symbol TEXT,
            date TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            hold REAL, settle REAL,
            cached_at TEXT,
            PRIMARY KEY (symbol, date)
        )
    """)
    _add_column_if_not_exists(cur, "futures_daily", "atr", "REAL")
    _add_column_if_not_exists(cur, "futures_daily", "main_contract_code", "TEXT")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fd_main_contract ON futures_daily(main_contract_code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fd_symbol ON futures_daily(symbol, date)")

    # ===== 现有表：futures_min（确保存在 + 加列）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS futures_min (
            symbol TEXT,
            period TEXT,
            datetime TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            cached_at TEXT,
            PRIMARY KEY (symbol, period, datetime)
        )
    """)
    _add_column_if_not_exists(cur, "futures_min", "date", "TEXT")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fm_symbol_date ON futures_min(symbol, date)")

    # ===== turtle_signals（确保存在，不动结构）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS turtle_signals (
            symbol TEXT,
            date TEXT,
            signal_type TEXT,
            price REAL,
            atr REAL,
            notes TEXT,
            created_at TEXT,
            PRIMARY KEY (symbol, date, signal_type)
        )
    """)

    # ===== 数据迁移：futures_atr → futures_daily.atr（幂等）=====
    # 只迁移 futures_daily.atr 为 NULL 的行，多次跑不破坏
    # 检查 futures_atr 是否还存在（首次跑存在，二次跑已被删除）
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='futures_atr'"
    )
    if cur.fetchone() is not None:
        cur.execute("""
            UPDATE futures_daily
            SET atr = (
                SELECT atr FROM futures_atr
                WHERE futures_atr.symbol = futures_daily.symbol
                AND futures_atr.date = futures_daily.date
            )
            WHERE atr IS NULL
        """)
        n_migrated = cur.rowcount
        if n_migrated > 0:
            print(f"[DB] ATR 数据迁移完成：{n_migrated} 行")

    # ===== 删除已废弃的 futures_atr 表 =====
    cur.execute("DROP TABLE IF EXISTS futures_atr")

    # ============================================================
    # 策略领域表（Phase 2.1 新增，5 张表 + 7 索引 + 2 种子策略）
    # ============================================================

    # ===== 新表 1：strategies（策略元信息 + 种子数据）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            strategy_id  TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            version      INTEGER NOT NULL DEFAULT 1,
            type         TEXT NOT NULL,
            description  TEXT,
            params_json  TEXT,
            is_active    INTEGER DEFAULT 1,
            is_paper     INTEGER DEFAULT 1,
            created_at   TEXT,
            updated_at   TEXT,
            UNIQUE (name, version)
        )
    """)
    # 种子数据：turtle_v1（激活）和 dual_ma_v1（未激活）
    # 幂等：INSERT OR IGNORE，重复跑不报错
    # 注：datetime('now') 是 SQLite 函数，但 .isoformat() 是 Python 方法
    #    所以必须先在 Python 端计算好 ISO 字符串，再插入。
    _now_iso = datetime.now().isoformat()
    cur.execute("""
        INSERT OR IGNORE INTO strategies VALUES
            ('turtle_v1', '海龟T1', 1, 'turtle',
             '经典海龟系统二，55日突破/20日反向/0.5N加仓/2N止损',
             '{"entry_n":55,"exit_n":20,"add_interval":0.5,"stop_loss":2,"atr_n":20,"max_units":4,"risk_per_trade":2000}',
             1, 1, ?, ?),
            ('dual_ma_v1', '双均线', 1, 'dual_ma',
             '快慢均线交叉信号',
             '{"fast":10,"slow":20}',
             0, 1, ?, ?)
    """, (_now_iso, _now_iso, _now_iso, _now_iso))

    # ===== 新表 2：strategy_param_history（参数变更历史）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategy_param_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id   TEXT NOT NULL,
            name          TEXT NOT NULL,
            version       INTEGER NOT NULL,
            params_json   TEXT NOT NULL,
            changed_at    TEXT NOT NULL,
            changed_by    TEXT,
            change_reason TEXT,
            notes         TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sph_strategy ON strategy_param_history(strategy_id, version)")

    # ===== 新表 3：strategy_signals（v1.3 精简，信号记录）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategy_signals (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id       TEXT NOT NULL,
            symbol            TEXT NOT NULL,
            name              TEXT,
            contract_code     TEXT,
            signal_type       TEXT NOT NULL,         -- entry_long / entry_short
            direction         TEXT NOT NULL,
            trigger_price     REAL NOT NULL,
            reference_price   REAL NOT NULL,
            reference_n       REAL,
            bar_time          TEXT NOT NULL,
            period            TEXT DEFAULT '5min',
            alert_level       TEXT DEFAULT 'normal',
            created_at        TEXT DEFAULT (datetime('now')),
            UNIQUE(strategy_id, symbol, signal_type, bar_time)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ss_strategy ON strategy_signals(strategy_id, bar_time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ss_active ON strategy_signals(strategy_id, symbol, direction, alert_level)")

    # ===== 新表 4：strategy_event_log（v1.4，事件日志）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategy_event_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id   TEXT NOT NULL,
            event_type    TEXT NOT NULL,            -- signal_detected / signal_skipped / param_updated / engine_started / engine_stopped
            event_at      TEXT NOT NULL,
            symbol        TEXT,
            context_json  TEXT,
            created_at    TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sel_strategy_at ON strategy_event_log(strategy_id, event_at)")

    # ===== 新表 5：turtle_trade_process（v1.5，海龟交易过程，10 枚举事件）=====
    # 注意：session_id 没有 FOREIGN KEY 约束，因为 trade_sessions 是 Phase 3 才建。
    # 届时用 ALTER TABLE 或迁移脚本加上 FK。
    # event_type 枚举（10 个）：
    #   entry_signal / entry_filled
    #   add_signal / add_filled / add_skipped_gap
    #   stop_loss_check / stop_loss_triggered
    #   check_exit / exit_20_triggered
    #   unit_closed
    cur.execute("""
        CREATE TABLE IF NOT EXISTS turtle_trade_process (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT NOT NULL,           -- FK to trade_sessions (Phase 3 会加)
            account_id      TEXT NOT NULL,
            event_type      TEXT NOT NULL,           -- 10 枚举：entry_signal / entry_filled / add_signal / add_filled / add_skipped_gap / stop_loss_check / stop_loss_triggered / check_exit / exit_20_triggered / unit_closed
            bar_time        TEXT NOT NULL,
            bar_open        REAL, bar_high REAL, bar_low REAL, bar_close REAL,
            signal_type     TEXT,
            signal_price    REAL,
            reference_price REAL,
            n_value         REAL,
            unit_id         INTEGER,
            exec_status     TEXT,                    -- pending / filled / skipped / failed
            exec_price      REAL,
            exec_hand_count INTEGER,
            exec_time       TEXT,
            slippage        REAL,
            is_gap          INTEGER DEFAULT 0,
            gap_size        REAL,
            decision_reason TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ttp_session ON turtle_trade_process(session_id, bar_time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ttp_type ON turtle_trade_process(event_type, bar_time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ttp_bar ON turtle_trade_process(bar_time)")

    # ============================================================
    # 交易/账户领域表（Phase 3.1 新增，11 张表 + 7 索引 + 3 种子账户）
    # ============================================================

    # ===== 修复 1：turtle_trade_process 重建带 FK → trade_sessions =====
    # Phase 2.1 时 turtle_trade_process 不带 FK（trade_sessions 不存在）。
    # SQLite 不支持 ALTER TABLE ADD FOREIGN KEY，必须重建表。
    # 策略：若 0 行 → DROP + CREATE（带 FK）；若有数据 → 警告后续 12 步重建。
    cur.execute("SELECT COUNT(*) FROM turtle_trade_process")
    ttp_count = cur.fetchone()[0]
    if ttp_count == 0:
        # 0 行：直接 DROP + CREATE（带 FK）
        cur.execute("DROP TABLE IF EXISTS turtle_trade_process")
        cur.execute("""
            CREATE TABLE turtle_trade_process (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id      TEXT NOT NULL,
                account_id      TEXT NOT NULL,
                event_type      TEXT NOT NULL,
                bar_time        TEXT NOT NULL,
                bar_open        REAL, bar_high REAL, bar_low REAL, bar_close REAL,
                signal_type     TEXT,
                signal_price    REAL,
                reference_price REAL,
                n_value         REAL,
                unit_id         INTEGER,
                exec_status     TEXT,
                exec_price      REAL,
                exec_hand_count INTEGER,
                exec_time       TEXT,
                slippage        REAL,
                is_gap          INTEGER DEFAULT 0,
                gap_size        REAL,
                decision_reason TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES trade_sessions(session_id) ON DELETE CASCADE
            )
        """)
        # 重建后重新创建 idx_ttp_* 索引
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ttp_session ON turtle_trade_process(session_id, bar_time)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ttp_type ON turtle_trade_process(event_type, bar_time)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ttp_bar ON turtle_trade_process(bar_time)")
    else:
        # 有数据：需 12 步重建流程（不在 Phase 3.1 范围）
        # 12 步流程：重命名 → 重新创建 → 复制数据 → 删除旧表 → 重命名新表
        print(f"[DB] WARNING: turtle_trade_process 已有 {ttp_count} 行，需 12 步重建流程加 FK")

    # ===== 新表 1：sim_account（模拟账户）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sim_account (
            account_id     TEXT PRIMARY KEY,
            user_id        TEXT,
            display_name   TEXT,
            name           TEXT,
            balance        REAL DEFAULT 1000000.0,
            available      REAL DEFAULT 1000000.0,
            margin_used    REAL DEFAULT 0.0,
            realized_pnl   REAL DEFAULT 0.0,
            unrealized_pnl REAL DEFAULT 0.0,
            platform_name  TEXT DEFAULT 'sim',
            created_at     TEXT,
            updated_at     TEXT
        )
    """)
    # 种子数据：3 个默认账户（sim_default / sim_user1 / sim_user2）
    _now_iso_p3 = datetime.now().isoformat()
    cur.execute("""
        INSERT OR IGNORE INTO sim_account(account_id, user_id, display_name, name, balance, available, created_at, updated_at) VALUES
            ('sim_default', 'alex', '默认模拟账户', 'sim_default', 1000000.0, 1000000.0, ?, ?),
            ('sim_user1',   'user1', '用户1',         'sim_user1',   1000000.0, 1000000.0, ?, ?),
            ('sim_user2',   'user2', '用户2',         'sim_user2',   1000000.0, 1000000.0, ?, ?)
    """, (_now_iso_p3, _now_iso_p3, _now_iso_p3, _now_iso_p3, _now_iso_p3, _now_iso_p3))

    # ===== 新表 2：trade_sessions（交易会话，含 FK → strategies）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trade_sessions (
            session_id          TEXT PRIMARY KEY,
            account_id          TEXT NOT NULL,
            strategy_id         TEXT NOT NULL,
            symbol              TEXT NOT NULL,
            contract_code       TEXT,
            direction           TEXT NOT NULL,
            status              TEXT NOT NULL,
            entry_time          TEXT NOT NULL,
            exit_time           TEXT,
            first_entry_price   REAL,
            current_units       INTEGER DEFAULT 0,
            total_units         INTEGER DEFAULT 0,
            entry_basis_price   REAL,
            entry_locked_atr    REAL,
            price_overrides_json TEXT DEFAULT '{}',
            exit_reason         TEXT,
            realized_pnl        REAL,
            user_note           TEXT,
            created_at          TEXT,
            updated_at          TEXT,
            UNIQUE (account_id, strategy_id, direction, entry_time),
            FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id) ON DELETE RESTRICT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ts_account_status ON trade_sessions(account_id, status)")

    # ===== 新表 3：sim_orders（模拟订单，session_id 可空，FK 在 Phase 3.6 加）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sim_orders (
            order_id          TEXT PRIMARY KEY,
            account_id        TEXT NOT NULL,
            session_id        TEXT,
            symbol            TEXT NOT NULL,
            contract_code     TEXT,
            direction         TEXT NOT NULL,
            order_type        TEXT NOT NULL,
            quantity          INTEGER NOT NULL,
            price             REAL,
            status            TEXT NOT NULL,
            filled_quantity   INTEGER DEFAULT 0,
            avg_filled_price  REAL,
            platform_name     TEXT DEFAULT 'sim',
            external_order_id TEXT,
            created_at        TEXT,
            updated_at        TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_so_account_time ON sim_orders(account_id, created_at)")

    # ===== 新表 4：sim_trades（模拟成交）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sim_trades (
            trade_id          TEXT PRIMARY KEY,
            order_id          TEXT NOT NULL,
            account_id        TEXT NOT NULL,
            session_id        TEXT,
            symbol            TEXT NOT NULL,
            contract_code     TEXT,
            direction         TEXT NOT NULL,
            filled_price      REAL NOT NULL,
            filled_quantity   INTEGER NOT NULL,
            commission        REAL DEFAULT 0.0,
            platform_name     TEXT DEFAULT 'sim',
            external_trade_id TEXT,
            filled_at         TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_st_account_time ON sim_trades(account_id, filled_at)")

    # ===== 新表 5：sim_positions（模拟持仓，无 FK）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sim_positions (
            account_id      TEXT NOT NULL,
            symbol          TEXT NOT NULL,
            contract_code   TEXT,
            quantity        INTEGER DEFAULT 0,
            avg_cost        REAL DEFAULT 0.0,
            realized_pnl    REAL DEFAULT 0.0,
            unrealized_pnl  REAL DEFAULT 0.0,
            last_price      REAL,
            updated_at      TEXT,
            PRIMARY KEY (account_id, symbol)
        )
    """)

    # ===== 新表 6：position_units（仓海龟单位，FK → trade_sessions）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS position_units (
            unit_id           TEXT PRIMARY KEY,
            session_id        TEXT NOT NULL,
            account_id        TEXT NOT NULL,
            unit_index        INTEGER NOT NULL,
            open_price        REAL NOT NULL,
            current_price     REAL,
            stop_price        REAL,
            entry_basis_price REAL,
            entry_atr         REAL,
            open_hand_count   INTEGER NOT NULL,
            close_price       REAL,
            close_time        TEXT,
            close_hand_count  INTEGER,
            status            TEXT NOT NULL,
            is_gap            INTEGER DEFAULT 0,
            created_at        TEXT,
            updated_at        TEXT,
            FOREIGN KEY (session_id) REFERENCES trade_sessions(session_id) ON DELETE CASCADE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pu_session ON position_units(session_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pu_account ON position_units(account_id)")

    # ===== 新表 7：turtle_session_data（v1.4，PK+FK → trade_sessions）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS turtle_session_data (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id          TEXT NOT NULL UNIQUE,
            entry_55d_high      REAL,
            entry_55d_low       REAL,
            entry_atr_20        REAL,
            add_count           INTEGER DEFAULT 0,
            skip_add_count      INTEGER DEFAULT 0,
            is_gap_entry        INTEGER DEFAULT 0,
            is_breakout_confirm INTEGER DEFAULT 0,
            created_at          TEXT DEFAULT (datetime('now')),
            updated_at          TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES trade_sessions(session_id) ON DELETE CASCADE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tsd_session ON turtle_session_data(session_id)")

    # ===== 新表 8：session_event_log（v1.4，FK → trade_sessions）=====
    # event_type 枚举（8 个）：session_created / order_submitted / order_filled /
    #   units_changed / line_overridden / status_changed /
    #   stop_loss_triggered / exit_20_triggered
    cur.execute("""
        CREATE TABLE IF NOT EXISTS session_event_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    TEXT NOT NULL,
            account_id    TEXT NOT NULL,
            event_type    TEXT NOT NULL,
            event_at      TEXT NOT NULL,
            unit_id       TEXT,
            trade_id      TEXT,
            context_json  TEXT,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES trade_sessions(session_id) ON DELETE CASCADE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sesl_session_at ON session_event_log(session_id, event_at)")

    # ===== 新表 9：live_orders（预留，实盘订单）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS live_orders (
            order_id          TEXT PRIMARY KEY,
            account_id        TEXT NOT NULL,
            session_id        TEXT,
            symbol            TEXT NOT NULL,
            contract_code     TEXT,
            direction         TEXT NOT NULL,
            order_type        TEXT NOT NULL,
            quantity          INTEGER NOT NULL,
            price             REAL,
            status            TEXT NOT NULL,
            filled_quantity   INTEGER DEFAULT 0,
            avg_filled_price  REAL,
            platform_name     TEXT DEFAULT 'ctp',
            external_order_id TEXT,
            ctp_order_ref     TEXT,
            ctp_front_id      TEXT,
            ctp_session_id    TEXT,
            created_at        TEXT,
            updated_at        TEXT
        )
    """)

    # ===== 新表 10：live_trades（预留，实盘成交）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS live_trades (
            trade_id          TEXT PRIMARY KEY,
            order_id          TEXT NOT NULL,
            account_id        TEXT NOT NULL,
            session_id        TEXT,
            symbol            TEXT NOT NULL,
            contract_code     TEXT,
            direction         TEXT NOT NULL,
            filled_price      REAL NOT NULL,
            filled_quantity   INTEGER NOT NULL,
            commission        REAL DEFAULT 0.0,
            platform_name     TEXT DEFAULT 'ctp',
            external_trade_id TEXT,
            ctp_trade_id      TEXT,
            filled_at         TEXT
        )
    """)

    # ===== 新表 11：live_positions（预留，实盘持仓）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS live_positions (
            account_id      TEXT NOT NULL,
            symbol          TEXT NOT NULL,
            contract_code   TEXT,
            quantity        INTEGER DEFAULT 0,
            avg_cost        REAL DEFAULT 0.0,
            realized_pnl    REAL DEFAULT 0.0,
            unrealized_pnl  REAL DEFAULT 0.0,
            last_price      REAL,
            updated_at      TEXT,
            PRIMARY KEY (account_id, symbol)
        )
    """)

    # ===== 启用 FK 约束（SQLite 默认是 OFF）=====
    # PRAGMA foreign_keys = ON 仅对当前连接有效，每次连接都需设置
    conn.execute("PRAGMA foreign_keys = ON")

    # ===== 清理过期数据 =====
    _cleanup_expired(conn)

    # ============================================================
    # sq-0009-p1：缓存拉取记录 + 调度任务状态（2 张新表）
    # ============================================================

    # ===== 新表 1：cache_sync_log（拉取记录）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cache_sync_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol          TEXT NOT NULL,           -- 'AG' / 'ALL' / 'ag2608'
            period          TEXT NOT NULL,           -- 'daily' / '5min' / '15min' / '30min' / '60min'
            sync_type       TEXT NOT NULL,           -- 'scheduled' / 'manual' / 'backfill'
            status          TEXT NOT NULL,           -- 'running' / 'success' / 'failed' / 'partial'
            start_at        TEXT NOT NULL,
            end_at          TEXT,
            rows_existing   INTEGER DEFAULT 0,
            rows_new        INTEGER DEFAULT 0,
            rows_total      INTEGER DEFAULT 0,
            error_message   TEXT,
            trigger_source  TEXT,                    -- 'cron' / 'api:POST /minute/sync' / 'webapp:manual'
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    _add_column_if_not_exists(cur, "cache_sync_log", "start_date", "TEXT")   # sq-0009-round-4 commit 9
    _add_column_if_not_exists(cur, "cache_sync_log", "end_date", "TEXT")     # sq-0009-round-4 commit 9
    cur.execute("CREATE INDEX IF NOT EXISTS idx_csl_symbol_at   ON cache_sync_log(symbol, start_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_csl_type_status ON cache_sync_log(sync_type, status, start_at DESC)")

    # ===== 新表 2：cache_schedule_state（调度任务状态）=====
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cache_schedule_state (
            task_name    TEXT PRIMARY KEY,           -- 'daily_sync' / 'minute_sync_5min'
            last_run_at  TEXT,
            next_run_at  TEXT,
            last_status  TEXT,                       -- 'success' / 'failed' / 'skipped'
            run_count    INTEGER DEFAULT 0,
            fail_count   INTEGER DEFAULT 0,
            enabled      INTEGER DEFAULT 1,
            updated_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    # 种子数据：2 个调度任务（daily_sync + minute_sync_5min）
    cur.execute("""
        INSERT OR IGNORE INTO cache_schedule_state(task_name, enabled) VALUES
            ('daily_sync', 1),
            ('minute_sync_5min', 1)
    """)

    # ============================================================
    # 跨领域：backtest_runs（Phase 4.1）
    # ============================================================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS backtest_runs (
            run_id              TEXT PRIMARY KEY,
            strategy_id         TEXT NOT NULL,
            symbol              TEXT NOT NULL,
            start_date          TEXT NOT NULL,
            end_date            TEXT NOT NULL,
            params_json         TEXT,
            result_metrics_json TEXT,
            status              TEXT NOT NULL,
            initial_capital     REAL,
            final_capital       REAL,
            total_return_pct    REAL,
            max_drawdown_pct    REAL,
            total_trades        INTEGER DEFAULT 0,
            error_message       TEXT,
            created_at          TEXT,
            updated_at          TEXT,
            completed_at        TEXT,
            FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id) ON DELETE RESTRICT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_br_strategy_at ON backtest_runs(strategy_id, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_br_symbol ON backtest_runs(symbol, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_br_status ON backtest_runs(status)")

    conn.commit()
    conn.close()


def _cleanup_expired(conn: sqlite3.Connection):
    """清理过期缓存数据（包括 cached_at 为 NULL 的旧数据）"""
    daily_cutoff = (datetime.now() - timedelta(days=DAILY_RETENTION_DAYS)).strftime("%Y-%m-%d")
    min_cutoff = (datetime.now() - timedelta(days=MIN_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")

    cur = conn.cursor()

    # 清理过期日线（cached_at 过期 或 为 NULL）
    cur.execute(
        "DELETE FROM futures_daily WHERE cached_at < ? OR cached_at IS NULL",
        (daily_cutoff,)
    )
    n_daily = cur.rowcount

    # 清理过期分时
    cur.execute(
        "DELETE FROM futures_min WHERE cached_at < ? OR cached_at IS NULL",
        (min_cutoff,)
    )
    n_min = cur.rowcount

    if n_daily > 0 or n_min > 0:
        print(f"[缓存] 清理过期数据：日线 {n_daily} 条，分时 {n_min} 条")

    return n_daily, n_min


# ============================================================
# 工具函数
# ============================================================

def _str_to_date(s: str) -> datetime:
    """解析日期字符串为 datetime"""
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(s)[:10], fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {s}")


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _ensure_date_str(date_val) -> str:
    """统一转为 YYYY-MM-DD 字符串"""
    if isinstance(date_val, str):
        return date_val[:10]
    if hasattr(date_val, "strftime"):
        return date_val.strftime("%Y-%m-%d")
    return str(date_val)[:10]


# ============================================================
# 日线：增量更新
# ============================================================

def get_latest_cached_date(symbol: str) -> Optional[str]:
    """查询 SQLite 中某品种缓存的最新日期"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT MAX(date) as max_date FROM futures_daily WHERE symbol=?",
            (symbol.upper(),)
        ).fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def incremental_update_daily(symbol: str, lookback_days: int = 7) -> pd.DataFrame:
    """
    增量更新日线数据
    - 如果缓存中有最新日期，只拉该日期之后的数据（最多回溯 lookback_days 天）
    - 如果缓存为空或过期，拉最近 lookback_days 天数据
    - 写入前清理过期缓存（>14天）
    """
    if not AKSHARE_AVAILABLE:
        raise ImportError("akshare not installed")

    sym = symbol.upper()
    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    # 1. 确定起始日期
    latest_cached = get_latest_cached_date(sym)
    if latest_cached and latest_cached >= cutoff:
        # 缓存够新，不需要额外拉取
        print(f"[增量日线] {sym} 缓存已最新: {latest_cached}")
        return pd.DataFrame()

    # 2. akshare 获取（只拿最近 lookback_days 天，减少重复请求）
    try:
        symbol_code = sym + "0"
        df = ak.futures_zh_daily_sina(symbol=symbol_code)
        if df is None or len(df) == 0:
            return pd.DataFrame()
    except Exception as e:
        print(f"[增量日线] {sym} 获取失败: {e}")
        return pd.DataFrame()

    # 3. 标准化
    df = df.rename(columns={
        "日期": "date", "开盘价": "open",
        "最高价": "high", "最低价": "low",
        "收盘价": "close", "成交量": "volume"
    })
    df["symbol"] = sym
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values("date")

    # 4. 过滤：只保留比缓存更新且在回溯窗口内的数据
    if latest_cached:
        df = df[df["date"] > latest_cached]
    else:
        df = df[df["date"] >= cutoff]

    if len(df) == 0:
        print(f"[增量日线] {sym} 无新数据需更新")
        return pd.DataFrame()

    # 5. 写入缓存（带 cached_at）
    df["cached_at"] = today
    conn = get_conn()
    try:
        _cleanup_expired(conn)  # 先清理

        # Insert or replace（兼容已有数据）
        cols = ["symbol", "date", "open", "high", "low", "close", "volume", "hold", "settle", "cached_at"]
        for _, row in df.iterrows():
            conn.execute(f"""
                INSERT OR REPLACE INTO futures_daily
                ({', '.join(cols)})
                VALUES ({', '.join(['?']*len(cols))})
            """, [row.get(c) if c in row.index else None for c in cols])
        conn.commit()
        print(f"[增量日线] {sym} 新增 {len(df)} 条 ({df['date'].iloc[0]} ~ {df['date'].iloc[-1]})")
    finally:
        conn.close()

    return df


def get_futures_daily(
    symbol: str,
    start_date: str = "20180101",
    end_date: str = "20251231",
    use_cache: bool = True
) -> pd.DataFrame:
    """
    获取期货日线数据（主力连续合约）
    优先从缓存读取，缓存不足 60 条时自动回填 3 年历史
    """
    if not AKSHARE_AVAILABLE:
        raise ImportError("akshare not installed")

    sym = symbol.upper()
    start_str = str(start_date)[:10].replace("/", "-")
    end_str = str(end_date)[:10].replace("/", "-")

    conn = get_conn()

    if use_cache:
        df_cached = pd.read_sql(
            f"SELECT * FROM futures_daily WHERE symbol='{sym}' "
            f"AND date>='{start_str}' AND date<='{end_str}' ORDER BY date",
            conn, index_col="date", parse_dates=["date"]
        )
        conn.close()

        # 缓存够用（>60条）且最新日期距今 ≤ 1 天，直接返回
        if len(df_cached) >= 60:
            latest_cached = get_latest_cached_date(sym)
            if latest_cached:
                latest_dt = _str_to_date(latest_cached)
                if (datetime.now() - latest_dt).days <= 1:
                    print(f"[日线] {sym} 缓存命中 {len(df_cached)} 条，最新 {latest_cached}")
                    return df_cached
            print(f"[日线] {sym} 缓存 {len(df_cached)} 条（偏旧，触发增量）")
            incremental_update_daily(sym)
            # 重新读
            conn2 = get_conn()
            df_cached = pd.read_sql(
                f"SELECT * FROM futures_daily WHERE symbol='{sym}' "
                f"AND date>='{start_str}' AND date<='{end_str}' ORDER BY date",
                conn2, index_col="date", parse_dates=["date"]
            )
            conn2.close()
            if len(df_cached) >= 60:
                return df_cached
        elif len(df_cached) > 0:
            print(f"[日线] {sym} 缓存仅 {len(df_cached)} 条（不足 60），回填历史")
            # 缓存有一些但不够，回填 3 年历史
            _fetch_full_daily(sym, years=3)
        else:
            print(f"[日线] {sym} 缓存为空，回填 3 年历史")
            _fetch_full_daily(sym, years=3)
    else:
        conn.close()

    # 最终读取
    conn = get_conn()
    df_cached = pd.read_sql(
        f"SELECT * FROM futures_daily WHERE symbol='{sym}' "
        f"AND date>='{start_str}' AND date<='{end_str}' ORDER BY date",
        conn, index_col="date", parse_dates=["date"]
    )
    conn.close()
    return df_cached


def _fetch_full_daily(symbol: str, years: int = 1) -> pd.DataFrame:
    """强制全量获取历史日线数据（用于缓存为空或不足时回填）"""
    try:
        sym = symbol.upper()
        df = ak.futures_zh_daily_sina(symbol=sym + "0")
        if df is None or len(df) == 0:
            return pd.DataFrame()

        # 标准化列名（akshare 返回的列名）
        df = df.rename(columns={
            "日期": "date", "开盘价": "open",
            "最高价": "high", "最低价": "low",
            "收盘价": "close", "成交量": "volume"
        })
        if "hold" not in df.columns:
            df["hold"] = None
        if "settle" not in df.columns:
            df["settle"] = None

        # 日期标准化
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

        # 只保留最近 N 年数据
        if years > 0:
            cutoff = (datetime.now() - timedelta(days=365 * years)).strftime("%Y-%m-%d")
            df = df[df["date"] >= cutoff]

        df = df.sort_values("date")
        df["symbol"] = sym
        today = _today_str()
        df["cached_at"] = today

        conn = get_conn()
        conn.execute(f"DELETE FROM futures_daily WHERE symbol='{sym}'")
        cols = ["symbol", "date", "open", "high", "low", "close", "volume", "hold", "settle", "cached_at"]
        for _, row in df.iterrows():
            vals = [row.get(c) if c in row.index else None for c in cols]
            conn.execute(f"""
                INSERT OR REPLACE INTO futures_daily
                ({', '.join(cols)})
                VALUES ({', '.join(['?']*len(cols))})
            """, vals)
        conn.commit()
        conn.close()

        print(f"[日线] {sym} 全量回填 {len(df)} 条（~{years}年）")
        return df.set_index("date")[["symbol", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        import traceback
        print(f"[日线] {sym} 全量获取失败: {e}")
        traceback.print_exc()
        return pd.DataFrame()


# ============================================================
# 分时数据
# ============================================================

def get_latest_cached_min_datetime(symbol: str, period: str = "5min") -> Optional[str]:
    """查询某品种某周期的分时缓存最新时间"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT MAX(datetime) FROM futures_min WHERE symbol=? AND period=?",
            (symbol.upper(), period)
        ).fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


def fetch_minute_data(
    symbol: str,
    period: str = "5min",
    days: int = 7
) -> pd.DataFrame:
    """
    获取分时数据（增量更新，自动识别当前主力合约）
    period: "1min" / "5min" / "15min" / "30min" / "60min"
    days: 最多回溯天数（用于首次无缓存时）
    """
    if not AKSHARE_AVAILABLE:
        raise ImportError("akshare not installed")

    sym = symbol.upper()
    today = _today_str()
    period_map = {"1min": "1", "5min": "5", "15min": "15", "30min": "30", "60min": "60"}

    # 1. 缓存优先：已有数据时直接返回缓存
    latest_cached = get_latest_cached_min_datetime(sym, period)
    cutoff = (datetime.now() - timedelta(days=MIN_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    df_cached = pd.read_sql(
        f"SELECT * FROM futures_min WHERE symbol='{sym}' AND period='{period}' AND datetime>='{cutoff}' ORDER BY datetime",
        conn, index_col="datetime", parse_dates=["datetime"]
    )
    conn.close()
    if len(df_cached) > 0:
        print(f"[分时] {sym} {period} 缓存命中 {len(df_cached)} 条，最新 {df_cached.index[-1]}")
        # 尝试增量更新（被限流时直接返回缓存）
        try:
            contract_codes = _make_contract_codes(sym, n=4)
            best_df = None
            best_code = None
            best_latest = None
            for code in contract_codes:
                try:
                    df = ak.futures_zh_minute_sina(symbol=code, period=period_map.get(period, "5"))
                    if df is not None and len(df) > 0:
                        latest = df.iloc[-1]["datetime"]
                        if best_latest is None or latest > best_latest:
                            best_df = df
                            best_code = code
                            best_latest = latest
                except Exception:
                    pass
            if best_df is not None:
                df = best_df.rename(columns={"datetime": "datetime", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"})
                df["symbol"] = sym
                df["period"] = period
                df["datetime"] = pd.to_datetime(df["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
                df = df[df["datetime"] > latest_cached]
                if len(df) > 0:
                    df["cached_at"] = today
                    conn2 = get_conn()
                    cols = ["symbol", "period", "datetime", "open", "high", "low", "close", "volume", "cached_at"]
                    for _, row in df.iterrows():
                        vals = [row.get(c) if c in row.index else None for c in cols]
                        conn2.execute(f"INSERT OR REPLACE INTO futures_min ({', '.join(cols)}) VALUES ({', '.join(['?']*len(cols))})", vals)
                    conn2.commit()
                    conn2.close()
                    df_cached2 = pd.read_sql(f"SELECT * FROM futures_min WHERE symbol='{sym}' AND period='{period}' ORDER BY datetime", conn, index_col="datetime", parse_dates=["datetime"])
                    return df_cached2
        except Exception:
            pass
        return df_cached

    # 2. 缓存为空：从 Sina 拉取
    contract_codes = _make_contract_codes(sym, n=4)
    best_df = None
    best_code = None
    best_latest = None
    for code in contract_codes:
        try:
            df = ak.futures_zh_minute_sina(symbol=code, period=period_map.get(period, "5"))
            if df is not None and len(df) > 0:
                latest = df.iloc[-1]["datetime"]
                if best_latest is None or latest > best_latest:
                    best_df = df
                    best_code = code
                    best_latest = latest
        except Exception:
            pass

    if best_df is None:
        print(f"[分时] {sym} {period} 无可用合约数据")
        return pd.DataFrame()

    df = best_df

    # 标准化列名
    rename_cols = {
        "datetime": "datetime", "open": "open",
        "high": "high", "low": "low", "close": "close", "volume": "volume"
    }
    df = df.rename(columns=rename_cols)
    if "datetime" not in df.columns:
        return pd.DataFrame()

    df["symbol"] = sym
    df["period"] = period
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    df = df.sort_values("datetime")

    # 3. 过滤：只保留比缓存更新的数据
    if latest_cached:
        df = df[df["datetime"] > latest_cached]

    if len(df) == 0:
        print(f"[分时] {sym} {period} 无新数据")
        return pd.DataFrame()

    # 4. 写入缓存
    df["cached_at"] = today
    conn = get_conn()
    try:
        cutoff = (datetime.now() - timedelta(days=MIN_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "DELETE FROM futures_min WHERE (cached_at < ? OR cached_at IS NULL) AND symbol=? AND period=?",
            (cutoff, sym, period)
        )
        cols = ["symbol", "period", "datetime", "open", "high", "low", "close", "volume", "cached_at"]
        for _, row in df.iterrows():
            conn.execute(f"""
                INSERT OR REPLACE INTO futures_min
                ({', '.join(cols)})
                VALUES ({', '.join(['?']*len(cols))})
            """, [row.get(c) if c in row.index else None for c in cols])
        conn.commit()
        print(f"[分时] {sym} {period} 新增 {len(df)} 条 ({df['datetime'].iloc[0]} ~ {df['datetime'].iloc[-1]})")
    finally:
        conn.close()

    return df


# ============================================================
# 全量分时同步（所有品种）
# ============================================================

# 所有交易品种（来自 instruments.yaml）
ALL_PRODUCTS = [
    "AG", "AU", "CU", "AL", "ZN", "PB", "NI", "SN",   # 贵金属/有色
    "RB", "HC", "I", "J", "JM",                               # 黑色金属
    "FG",                                                          # 建材
    "TA", "MA", "BU", "EG", "V", "L", "PP", "RU",         # 能源化工
    "M", "Y", "RM", "OI", "P", "SR", "CF",                 # 农产品
    "A", "C", "JD", "CS",                                      # 农产品
]

# Sina 品种代码映射（产品代码 -> Sina 小写代码）
SINA_PRODUCT_MAP = {
    "AG": "ag", "AU": "au", "CU": "cu", "AL": "al",
    "RB": "rb", "HC": "hc", "I": "i", "J": "j", "JM": "jm",
    "TA": "ta", "MA": "ma", "RU": "ru", "NI": "ni",
    "ZN": "zn", "PB": "pb", "SN": "sn",
    "FG": "fg", "BU": "bu", "EG": "eg", "V": "v",
    "L": "l", "PP": "pp",
    "M": "m", "Y": "y", "RM": "rm", "OI": "oi", "P": "p",
    "SR": "sr", "CF": "cf", "A": "a", "C": "c",
    "JD": "jd", "CS": "cs",
}

# 各品种交割月（奇数月：1,3,5,7,9,11）  
# 用于构造近月合约代码
PRODUCT_DELIVERY_MONTHS = {
    "AG": [1,3,5,7,9,11], "AU": [6,12], "CU": [1,2,3,4,5,6,7,8,9,10,11,12],
    "AL": [1,2,3,4,5,6,7,8,9,10,11,12], "ZN": [1,2,3,4,5,6,7,8,9,10,11,12],
    "PB": [1,2,3,4,5,6,7,8,9,10,11,12], "NI": [1,2,3,4,5,6,7,8,9,10,11,12],
    "SN": [1,2,3,4,5,6,7,8,9,10,11,12],
    "RB": [1,5,10], "HC": [1,5,10], "I": [1,5,9,11],
    "J": [1,3,5,7,9,11], "JM": [1,3,5,7,9,11],
    "FG": [1,5,9],
    "TA": [1,5,9,11], "MA": [1,3,7,9,11], "BU": [1,6,9,12],
    "EG": [1,5,9], "V": [1,5,9], "L": [1,5,9], "PP": [1,5,9],
    "RU": [1,3,4,5,6,7,8,9,10,11,12],
    "M": [1,3,5,7,8,9,11], "Y": [1,3,5,7,8,9,11],
    "RM": [1,3,5,7,8,9,11], "OI": [1,3,5,7,8,9,11],
    "P": [1,3,5,7,8,9,11,12], "SR": [1,3,5,7,9,11],
    "CF": [1,3,5,7,9,11], "A": [1,3,5,7,9,11],
    "C": [1,3,5,7,9,11], "JD": list(range(1,13)), "CS": [1,3,5,7,9,11],
}


def _make_contract_codes(sym: str, n: int = 4) -> list[str]:
    """为某品种构造近月合约代码列表（v1.5 修复：去重 + 按交割月顺序递进）"""
    sina_code = SINA_PRODUCT_MAP.get(sym, sym.lower())
    now = datetime.now()
    year = now.year
    month = now.month
    delivery_months = sorted(PRODUCT_DELIVERY_MONTHS.get(sym, [1,3,5,7,9,11]))

    # 找到第一个 >= month 的交割月索引
    start_idx = 0
    for i, m in enumerate(delivery_months):
        if m >= month:
            start_idx = i
            break
    else:
        # month 比所有交割月都大，使用下一年第一个交割月
        start_idx = 0
        year += 1

    codes = []
    for offset in range(n):
        idx = (start_idx + offset) % len(delivery_months)
        y = year + (start_idx + offset) // len(delivery_months)
        m = delivery_months[idx]
        codes.append(f"{sina_code}{str(y)[2:]}{m:02d}")
    return codes


def sync_all_minute_data(period: str = "5min", progress: bool = True) -> dict:
    """
    全量分时同步：枚举所有品种，自动找出当前主力合约，写入 SQLite
    
    策略：
    1. 对每个品种，尝试 4 个近月合约代码
    2. 取数据最新（datetime 最大）且非空的那个作为当前主力合约
    3. 增量写入 futures_min 表
    4. 返回同步结果汇总
    """
    if not AKSHARE_AVAILABLE:
        return {"error": "akshare not available"}

    period_map = {"1min": "1", "5min": "5", "15min": "15", "30min": "30", "60min": "60"}
    akshare_period = period_map.get(period, "5")
    today = _today_str()

    results = {"success": [], "fail": [], "total_new": 0}

    for sym in ALL_PRODUCTS:
        contract_codes = _make_contract_codes(sym, n=4)
        best_code = None
        best_df = None
        best_latest = None

        for code in contract_codes:
            try:
                df = ak.futures_zh_minute_sina(symbol=code, period=akshare_period)
                if df is not None and len(df) > 0:
                    latest = df.iloc[-1]["datetime"]
                    if best_latest is None or latest > best_latest:
                        best_code = code
                        best_df = df
                        best_latest = latest
            except Exception:
                pass

        if best_df is not None and best_code is not None:
            # 标准化
            best_df = best_df.rename(columns={
                "datetime": "datetime", "open": "open",
                "high": "high", "low": "low",
                "close": "close", "volume": "volume"
            })
            best_df["symbol"] = sym
            best_df["period"] = period
            best_df["datetime"] = pd.to_datetime(best_df["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            best_df = best_df.sort_values("datetime")
            best_df["cached_at"] = today
            best_df["contract_code"] = best_code
            best_df["name"] = SYMBOL_NAME.get(sym.upper(), sym)

            # 写入 SQLite（增量：只写比缓存更新的）
            latest_cached = get_latest_cached_min_datetime(sym, period)
            if latest_cached:
                best_df = best_df[best_df["datetime"] > latest_cached]

            if len(best_df) > 0:
                conn = get_conn()
                try:
                    cutoff = (datetime.now() - timedelta(days=MIN_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute(
                        "DELETE FROM futures_min WHERE (cached_at < ? OR cached_at IS NULL) AND symbol=? AND period=?",
                        (cutoff, sym, period)
                    )
                    cols = ["symbol", "period", "datetime", "open", "high", "low", "close", "volume", "cached_at", "contract_code", "name"]
                    for _, row in best_df.iterrows():
                        vals = [row.get(c) if c in row.index else None for c in cols]
                        conn.execute(f"""
                            INSERT OR REPLACE INTO futures_min
                            ({', '.join(cols)})
                            VALUES ({', '.join(['?']*len(cols))})
                        """, vals)
                    conn.commit()
                    results["success"].append((sym, best_code, len(best_df), str(best_latest)[:16]))
                    results["total_new"] += len(best_df)
                finally:
                    conn.close()
            else:
                results["success"].append((sym, best_code, 0, str(best_latest)[:16]))
        else:
            results["fail"].append(sym)

        if progress:
            status = f"✅ {sym} ({best_code}, {len(best_df) if best_df is not None else 0} 新条)" if best_code else f"❌ {sym}"
            print(status)

    if progress:
        print(f"\n同步完成: {len(results['success'])}/{len(ALL_PRODUCTS)} 品种成功, {len(results['fail'])} 失败, 共 {results['total_new']} 条新数据")
    return results


def get_minute_data(
    symbol: str,
    period: str = "5min",
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    use_cache: bool = True
) -> pd.DataFrame:
    """
    查询分时数据
    - 优先从缓存读，缓存不足时增量更新
    - start_datetime / end_datetime 为 YYYY-MM-DD HH:MM:SS 格式
    """
    sym = symbol.upper()

    if use_cache:
        # 触发增量更新（拉取最新分时）
        fetch_minute_data(sym, period)

    conn = get_conn()
    query = f"SELECT * FROM futures_min WHERE symbol='{sym}' AND period='{period}'"
    if start_datetime:
        query += f" AND datetime>='{start_datetime}'"
    if end_datetime:
        query += f" AND datetime<='{end_datetime}'"
    query += " ORDER BY datetime"

    df = pd.read_sql(query, conn, index_col="datetime", parse_dates=["datetime"])
    conn.close()
    return df


# ============================================================
# ATR（N值）计算
# ============================================================

def calc_atr_ema(tr_list: list, n_period: int = 20) -> float:
    if len(tr_list) < n_period:
        raise ValueError(f"TR 序列长度不足 {n_period}")
    n = tr_list[:n_period]
    atr = sum(n) / n_period
    for tr in tr_list[n_period:]:
        atr = (19 * atr + tr) / 20
    return atr


def calc_atr_series(
    df: pd.DataFrame,
    n_period: int = 20,
) -> pd.DataFrame:
    """计算 ATR 序列（TR + ATR EMA）"""
    df = df.copy()
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)

    prev_close = df["close"].shift(1).fillna(df["close"])
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.abs(df["high"] - prev_close),
        np.abs(df["low"] - prev_close)
    )

    tr_series = df["tr"].tolist()
    df["atr"] = calc_atr_ema(tr_series, n_period)
    return df


# ============================================================
# 海龟信号因子
# ============================================================

def calc_breakout_55(df: pd.DataFrame) -> pd.DataFrame:
    """55 日突破价"""
    df = df.copy()
    df["high_55"] = df["high"].rolling(55).max().shift(1)
    df["low_55"] = df["low"].rolling(55).min().shift(1)
    return df


def calc_exit_20(df: pd.DataFrame) -> pd.DataFrame:
    """20 日离市价"""
    df = df.copy()
    df["low_20"] = df["low"].rolling(20).min().shift(1)
    df["high_20"] = df["high"].rolling(20).max().shift(1)
    return df


# ============================================================
# 主数据接口：获取已计算好因子的 DataFrame
# ============================================================

def get_futures_with_factors(
    symbol: str,
    start_date: str = "20200101",
    end_date: str = "20251231",
    use_cache: bool = True
) -> pd.DataFrame:
    """
    获取品种数据，并计算所有海龟因子
    """
    df = get_futures_daily(symbol, start_date, end_date, use_cache)
    if len(df) < 60:
        return pd.DataFrame()

    df = calc_atr_series(df)
    df = calc_breakout_55(df)
    df = calc_exit_20(df)

    return df.dropna(subset=["atr", "high_55", "low_55"])


# ============================================================
# 全品种批量获取（用于 P5 回测）
# ============================================================

def get_all_instruments_factors(
    symbols: list[str],
    start_date: str = "20200101",
    end_date: str = "20251231",
    use_cache: bool = True
) -> dict[str, pd.DataFrame]:
    results = {}
    for sym in symbols:
        df = get_futures_with_factors(sym, start_date, end_date, use_cache)
        if len(df) > 60:
            results[sym] = df
        else:
            print(f"[数据] {sym} 数据不足，跳过")
    return results


# ============================================================
# 缓存状态诊断
# ============================================================

def cache_status(symbol: Optional[str] = None) -> dict:
    """返回缓存状态诊断信息"""
    conn = get_conn()
    try:
        if symbol:
            sym = symbol.upper()
            daily_count = conn.execute(
                "SELECT COUNT(*) FROM futures_daily WHERE symbol=?", (sym,)
            ).fetchone()[0]
            daily_latest = get_latest_cached_date(sym)
            min_periods = conn.execute(
                "SELECT DISTINCT period FROM futures_min WHERE symbol=?", (sym,)
            ).fetchall()
            return {
                "symbol": sym,
                "daily_count": daily_count,
                "daily_latest": daily_latest,
                "minute_periods": [r[0] for r in min_periods],
            }
        else:
            total_daily = conn.execute("SELECT COUNT(*) FROM futures_daily").fetchone()[0]
            total_min = conn.execute("SELECT COUNT(*) FROM futures_min").fetchone()[0]
            symbols = [r[0] for r in conn.execute(
                "SELECT DISTINCT symbol FROM futures_daily"
            ).fetchall()]
            return {
                "total_daily": total_daily,
                "total_minute": total_min,
                "symbols": symbols,
            }
    finally:
        conn.close()


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    init_db()

    print("=== 增量数据接口测试 ===\n")

    # 测试 1：增量更新日线
    print("[1] 增量更新日线")
    inc_df = incremental_update_daily("AG")
    print(f"    新增条数: {len(inc_df)}")

    # 测试 2：缓存状态
    print("\n[2] 缓存状态")
    status = cache_status("AG")
    print(f"    AG 日线: {status['daily_count']} 条, 最新 {status['daily_latest']}")

    # 测试 3：因子计算
    print("\n[3] AG 因子")
    df_ag = get_futures_with_factors("AG", "20260101", "20261231")
    if len(df_ag) > 0:
        row = df_ag.iloc[-1]
        print(f"    最新: {row.name}, close={row['close']:.0f}, ATR={row['atr']:.2f}, "
              f"55日高={row['high_55']:.0f}, 低={row['low_55']:.0f}")
    else:
        print("    无数据")

    # 测试 4：分时数据
    print("\n[4] AG 5分钟分时")
    min_df = fetch_minute_data("AG", "5min")
    print(f"    新增条数: {len(min_df)}")

    print("\n=== 测试完成 ===")
    print(f"缓存位置: {DB_PATH}")


# =============================================================================
# 缓存只读查询（供 API 接口使用，不请求外部）
# =============================================================================

def get_daily_signal_from_cache(symbol: str) -> dict | None:
    """
    纯缓存读取：从 futures_daily 表读取最近 N 条数据，
    计算 ATR / 55日高 / 55日低，不请求任何外部接口。
    """
    conn = get_conn()
    df = pd.read_sql(
        f"SELECT * FROM futures_daily WHERE symbol='{symbol.upper()}' ORDER BY date DESC LIMIT 120",
        conn, index_col="date", parse_dates=["date"]
    )
    conn.close()
    if len(df) < 5:
        return None
    df = df.sort_index()
    tr1 = df["high"] - df["low"]
    tr2 = abs(df["high"] - df["close"].shift(1))
    tr3 = abs(df["low"] - df["close"].shift(1))
    df["tr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = df["tr"].ewm(span=14, adjust=False).mean()
    df["high_55"] = df["high"].rolling(55).max().shift(1)
    df["low_55"] = df["low"].rolling(55).min().shift(1)
    row = df.iloc[-1]
    if pd.isna(row["atr"]) or pd.isna(row["high_55"]):
        return None
    return {
        "close": float(row["close"]),
        "atr": float(row["atr"]),
        "high_55": float(row["high_55"]),
        "low_55": float(row["low_55"]),
        "date": str(row.name.date()),
    }


def _make_contract_code(sym: str) -> str:
    """根据当前日期生成主力合约代码（用于缓存为空时）"""
    sina_code = SINA_PRODUCT_MAP.get(sym.upper(), sym.lower())
    delivery_months = PRODUCT_DELIVERY_MONTHS.get(sym.upper(), [1,3,5,7,9,11])
    now = datetime.now()
    y, m = now.year, now.month
    future = [x for x in sorted(delivery_months) if x >= m]
    if future:
        m = future[0]
    else:
        m = sorted(delivery_months)[0]
        y += 1
    return f"{sina_code}{str(y)[2:]}{m:02d}"


def get_contract_info(symbol: str) -> dict:
    """获取某品种的主力合约代码和中文名（优先从缓存，无则按当前日期生成）"""
    sym = symbol.upper()
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT contract_code, name FROM futures_min WHERE symbol=? ORDER BY datetime DESC LIMIT 1",
            (sym,)
        ).fetchone()
        if row and row[0]:
            return {"contract_code": row[0], "name": row[1] or SYMBOL_NAME.get(sym, sym)}
        return {"contract_code": _make_contract_code(sym), "name": SYMBOL_NAME.get(sym, sym)}
    finally:
        conn.close()


def get_minute_from_cache(symbol: str, period: str = "5min", limit: int = 500, date: str = "", days: int = 0) -> pd.DataFrame:
    """
    纯缓存读取分时数据（不请求 Sina）。
    date 非空：返回该日期全天数据（如 2026-05-28）
    days > 0：返回最近 N 天数据（如 days=3 返回近3天）
    两者都为空：返回当天（today）数据
    """
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=MIN_RETENTION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y-%m-%d")

    if date:
        # 指定日期全天数据
        query = (
            f"SELECT * FROM futures_min WHERE symbol='{symbol.upper()}' "
            f"AND period='{period}' AND datetime>='{date} 00:00:00' "
            f"AND datetime<='{date} 23:59:59' ORDER BY datetime"
        )
    elif days > 0:
        # 最近 N 天
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        query = (
            f"SELECT * FROM futures_min WHERE symbol='{symbol.upper()}' "
            f"AND period='{period}' AND datetime>='{start} 00:00:00' "
            f"AND datetime<='{today_str} 23:59:59' ORDER BY datetime"
        )
    else:
        # 默认今天
        query = (
            f"SELECT * FROM futures_min WHERE symbol='{symbol.upper()}' "
            f"AND period='{period}' AND datetime>='{today_str} 00:00:00' "
            f"AND datetime<='{today_str} 23:59:59' ORDER BY datetime"
        )

    df = pd.read_sql(query, conn, index_col="datetime", parse_dates=["datetime"])
    conn.close()
    return df.sort_index()


def get_daily_data_from_cache(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    纯缓存读取日线数据（不请求 Sina）。
    start_date / end_date 格式：YYYY-MM-DD
    """
    conn = get_conn()
    df = pd.read_sql(
        f"SELECT * FROM futures_daily WHERE symbol='{symbol.upper()}' AND date>='{start_date}' AND date<='{end_date}' ORDER BY date",
        conn, index_col="date", parse_dates=["date"]
    )
    conn.close()
    if len(df) == 0:
        return df
    # 补算因子
    df = df.sort_index()
    tr1 = df["high"] - df["low"]
    tr2 = abs(df["high"] - df["close"].shift(1))
    tr3 = abs(df["low"] - df["close"].shift(1))
    df["tr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = df["tr"].ewm(span=14, adjust=False).mean()
    df["high_55"] = df["high"].rolling(55).max().shift(1)
    df["low_55"] = df["low"].rolling(55).min().shift(1)
    return df


# =============================================================================
# 海龟信号检测层
# =============================================================================

def get_daily_ref_levels(symbol: str) -> dict | None:
    """
    获取品种的当日参考价位（55日/20日高低价 + ATR）
    用于分钟K线信号检测，当日固定不变
    """
    conn = get_conn()
    df = pd.read_sql(
        f"SELECT * FROM futures_daily WHERE symbol='{symbol.upper()}' ORDER BY date DESC LIMIT 120",
        conn, index_col="date", parse_dates=["date"]
    )
    conn.close()
    if len(df) < 60:
        return None
    df = df.sort_index()
    tr1 = df["high"] - df["low"]
    tr2 = abs(df["high"] - df["close"].shift(1))
    tr3 = abs(df["low"] - df["close"].shift(1))
    df["tr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = df["tr"].ewm(span=14, adjust=False).mean()
    df["high_55"] = df["high"].rolling(55).max().shift(1)
    df["low_55"] = df["low"].rolling(55).min().shift(1)
    df["high_20"] = df["high"].rolling(20).max().shift(1)
    df["low_20"] = df["low"].rolling(20).min().shift(1)
    row = df.iloc[-1]
    if pd.isna(row["atr"]) or pd.isna(row["high_55"]):
        return None
    return {
        "atr": float(row["atr"]),
        "high_55": float(row["high_55"]),
        "low_55": float(row["low_55"]),
        "high_20": float(row["high_20"]) if not pd.isna(row["high_20"]) else None,
        "low_20": float(row["low_20"]) if not pd.isna(row["low_20"]) else None,
        "date": str(row.name.date()),
    }


def save_turtle_signal(
    symbol: str,
    signal_type: str,
    trigger_price: float,
    reference_price: float,
    reference_n: float,
    direction: str,
    bar_time: str,
    period: str = "5min",
    name: str = "",
    contract_code: str = "",
    alert_level: str = "normal",
) -> bool:
    """
    写入海龟信号，返回是否成功（已存在则返回 False）
    """
    conn = get_conn()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO turtle_signals
            (symbol, name, contract_code, signal_type, trigger_price, reference_price,
             reference_n, direction, bar_time, period, alert_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (symbol.upper(), name, contract_code, signal_type, trigger_price,
              reference_price, reference_n, direction, bar_time, period, alert_level))
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def get_turtle_signals(symbol: str, days: int = 30) -> list[dict]:
    """
    查询某品种近 N 天的所有信号
    """
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT id, symbol, name, contract_code, signal_type, trigger_price,
               reference_price, reference_n, direction, bar_time, period,
               alert_level, created_at
        FROM turtle_signals
        WHERE symbol=? AND bar_time >= ? ORDER BY bar_time DESC
    """, (symbol.upper(), cutoff)).fetchall()
    conn.close()
    cols = ["id", "symbol", "name", "contract_code", "signal_type", "trigger_price",
            "reference_price", "reference_n", "direction", "bar_time", "period",
            "alert_level", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


def get_active_signals() -> list[dict]:
    """
    查询当前所有未离市的信号（entry 信号且未触发对应 exit）
    返回每个品种的最新入场信号
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT t1.id, t1.symbol, t1.name, t1.contract_code, t1.signal_type,
               t1.trigger_price, t1.reference_price, t1.reference_n,
               t1.direction, t1.bar_time, t1.period, t1.alert_level, t1.created_at
        FROM turtle_signals t1
        INNER JOIN (
            SELECT symbol, signal_type, MAX(bar_time) as max_bar
            FROM turtle_signals
            WHERE signal_type IN ('entry_long', 'entry_short')
            GROUP BY symbol, signal_type
        ) t2
        ON t1.symbol = t2.symbol AND t1.signal_type = t2.signal_type
           AND t1.bar_time = t2.max_bar
        ORDER BY t1.bar_time DESC
    """).fetchall()
    conn.close()
    cols = ["id", "symbol", "name", "contract_code", "signal_type", "trigger_price",
            "reference_price", "reference_n", "direction", "bar_time", "period",
            "alert_level", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


def get_turtle_alerts(since_minutes: int = 30) -> list[dict]:
    """
    查询最近 N 分钟内的新信号（用于推送提醒）
    """
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(minutes=since_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute("""
        SELECT symbol, name, contract_code, signal_type, trigger_price,
               reference_price, reference_n, direction, bar_time, alert_level
        FROM turtle_signals
        WHERE created_at >= ? ORDER BY created_at DESC
    """, (cutoff,)).fetchall()
    conn.close()
    cols = ["symbol", "name", "contract_code", "signal_type", "trigger_price",
            "reference_price", "reference_n", "direction", "bar_time", "alert_level"]
    return [dict(zip(cols, r)) for r in rows]


def check_bar_signal(
    symbol: str,
    bar_close: float,
    bar_high: float,
    bar_low: float,
    bar_time: str,
    period: str = "5min",
    direction: str = "flat",
    has_position: bool = False,
    name: str = "",
    contract_code: str = "",
) -> list[dict]:
    """
    检测单根 K 线是否触发海龟信号，返回信号列表

    direction: 'long' | 'short' | 'flat'（当前持仓方向，flat=无持仓）
    has_position: 当前是否有该品种持仓
    """
    levels = get_daily_ref_levels(symbol)
    if not levels:
        return []

    signals = []
    atr = levels["atr"]
    high_55 = levels["high_55"]
    low_55 = levels["low_55"]
    high_20 = levels.get("high_20")
    low_20 = levels.get("low_20")

    # 55日突破入场
    if bar_close >= high_55:
        sig = {
            "symbol": symbol.upper(),
            "name": name or SYMBOL_NAME.get(symbol.upper(), symbol.upper()),
            "contract_code": contract_code,
            "signal_type": "entry_long",
            "trigger_price": bar_close,
            "reference_price": high_55,
            "reference_n": atr,
            "direction": "long",
            "bar_time": bar_time,
            "period": period,
            "alert_level": "normal",
        }
        if save_turtle_signal(**sig):
            signals.append(sig)

    if bar_close <= low_55:
        sig = {
            "symbol": symbol.upper(),
            "name": name or SYMBOL_NAME.get(symbol.upper(), symbol.upper()),
            "contract_code": contract_code,
            "signal_type": "entry_short",
            "trigger_price": bar_close,
            "reference_price": low_55,
            "reference_n": atr,
            "direction": "short",
            "bar_time": bar_time,
            "period": period,
            "alert_level": "normal",
        }
        if save_turtle_signal(**sig):
            signals.append(sig)

    # 20日反向离市（仅在有持仓时检测）
    if has_position and direction != "flat":
        if direction == "long" and low_20 and bar_close <= low_20:
            sig = {
                "symbol": symbol.upper(),
                "name": name or SYMBOL_NAME.get(symbol.upper(), symbol.upper()),
                "contract_code": contract_code,
                "signal_type": "exit_long",
                "trigger_price": bar_close,
                "reference_price": low_20,
                "reference_n": atr,
                "direction": "flat",
                "bar_time": bar_time,
                "period": period,
                "alert_level": "strong",
            }
            if save_turtle_signal(**sig):
                signals.append(sig)
        if direction == "short" and high_20 and bar_close >= high_20:
            sig = {
                "symbol": symbol.upper(),
                "name": name or SYMBOL_NAME.get(symbol.upper(), symbol.upper()),
                "contract_code": contract_code,
                "signal_type": "exit_short",
                "trigger_price": bar_close,
                "reference_price": high_20,
                "reference_n": atr,
                "direction": "flat",
                "bar_time": bar_time,
                "period": period,
                "alert_level": "strong",
            }
            if save_turtle_signal(**sig):
                signals.append(sig)

    return signals


def detect_signals_for_symbol(symbol: str, period: str = "5min", days: int = 365) -> list[dict]:
    """
    对某品种近 N 天分钟数据全量扫描（用于历史回溯）
    每次只检测最后一根新 K 线，增量调用
    days: 扫描窗口（v0.18.16 由 7 改默认 365，让历史信号都能找到）
    """
    levels = get_daily_ref_levels(symbol)
    if not levels:
        return []

    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    df = pd.read_sql(
        f"SELECT * FROM futures_min WHERE symbol='{symbol.upper()}' "
        f"AND period='{period}' AND datetime>='{cutoff} 00:00:00' ORDER BY datetime",
        conn, index_col="datetime", parse_dates=["datetime"]
    )
    conn.close()
    if len(df) == 0:
        return []

    all_signals = []
    name = SYMBOL_NAME.get(symbol.upper(), symbol.upper())
    contract_info = get_contract_info(symbol.upper())
    contract_code = contract_info.get("contract_code", "")

    for _, row in df.iterrows():
        bar_close = float(row["close"])
        bar_high = float(row["high"])
        bar_low = float(row["low"])
        bar_time = row.name.strftime("%Y-%m-%d %H:%M:%S")
        sigs = check_bar_signal(
            symbol=symbol, bar_close=bar_close, bar_high=bar_high, bar_low=bar_low,
            bar_time=bar_time, period=period,
            name=name, contract_code=contract_code,
        )
        all_signals.extend(sigs)

    return all_signals


# =============================================================================
# v1.5 新增：数据回填 + 主力合约识别
# =============================================================================

# 品种 → 交易所 映射（上期所/大商所/郑商所/上期能源/广期所）
SYMBOL_EXCHANGE = {
    "AG": "shfe", "AU": "shfe", "CU": "shfe", "AL": "shfe", "ZN": "shfe",
    "PB": "shfe", "NI": "shfe", "SN": "shfe", "RB": "shfe", "HC": "shfe",
    "BU": "shfe", "RU": "shfe", "FU": "shfe", "SP": "shfe", "SS": "shfe",
    "SC": "ine", "NR": "ine", "LU": "ine", "BC": "ine", "EC": "ine",
    "I": "dce", "J": "dce", "JM": "dce", "A": "dce", "C": "dce",
    "M": "dce", "Y": "dce", "P": "dce", "L": "dce", "PP": "dce",
    "V": "dce", "EG": "dce", "JD": "dce", "CS": "dce", "LH": "dce", "PG": "dce",
    "TA": "czce", "MA": "czce", "CF": "czce", "SR": "czce", "RM": "czce",
    "OI": "czce", "FG": "czce", "ZC": "czce", "SM": "czce", "SF": "czce",
    "SA": "czce", "UR": "czce", "AP": "czce", "CJ": "czce", "PK": "czce",
    "PF": "czce", "PX": "czce",
    "SI": "gfex", "LC": "gfex", "PS": "gfex", "PT": "gfex", "PD": "gfex",
}

# 品种 → instruments.yaml 配置（v1.5 复用 SYMBOL_NAME 加载时存的信息）
_INSTRUMENT_CFG = {}
try:
    with open(INSTRUMENTS_PATH, encoding="utf-8") as _f:
        _cfg_yaml = yaml.safe_load(_f)
        for _sym, _info in _cfg_yaml.get("instruments", {}).items():
            _INSTRUMENT_CFG[_sym.upper()] = _info
except Exception:
    pass


def _get_instrument_info(sym: str) -> dict:
    """从 instruments.yaml 读取某品种静态信息（contract_size / tick / margin_ratio 等）"""
    return _INSTRUMENT_CFG.get(sym.upper(), {})


def backfill_daily_history(symbol: str, years: int = 3) -> int:
    """
    回填指定品种近 N 年日线数据（v1.5 新增）

    - 数据源：ak.futures_zh_daily_sina(symbol=sym+"0")（主力连续合约历史）
    - 只写比缓存更新的行（避免重复写入）
    - 幂等：INSERT OR REPLACE
    - 单次拉取失败不抛异常，返回 0

    Returns:
        新增行数（不含已存在）
    """
    if not AKSHARE_AVAILABLE:
        raise ImportError("akshare not installed")

    sym = symbol.upper()
    today = _today_str()
    cutoff = (datetime.now() - timedelta(days=365 * years)).strftime("%Y-%m-%d")

    # 1. 拉数据
    try:
        df = ak.futures_zh_daily_sina(symbol=sym + "0")
        if df is None or len(df) == 0:
            print(f"[日线回填] {sym} akshare 返回空数据")
            return 0
    except Exception as e:
        print(f"[日线回填] {sym} akshare 拉取失败: {e}")
        return 0

    # 2. 标准化列名
    df = df.rename(columns={
        "日期": "date", "开盘价": "open", "最高价": "high",
        "最低价": "low", "收盘价": "close", "成交量": "volume",
    })
    if "hold" not in df.columns:
        df["hold"] = None
    if "settle" not in df.columns:
        df["settle"] = None

    # 3. 日期标准化 + 过滤最近 N 年
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df[df["date"] >= cutoff]
    df = df.sort_values("date")
    if len(df) == 0:
        print(f"[日线回填] {sym} 过滤后无数据")
        return 0

    # 4. 只保留比缓存更新的行（避免大量重复写入）
    conn = get_conn()
    try:
        existing_dates = {
            r[0] for r in conn.execute(
                "SELECT date FROM futures_daily WHERE symbol=?", (sym,)
            ).fetchall()
        }
        df_new = df[~df["date"].isin(existing_dates)].copy()
        if len(df_new) == 0:
            print(f"[日线回填] {sym} 缓存已最新（无新增）")
            return 0

        # 5. 写入
        df_new["symbol"] = sym
        df_new["cached_at"] = today
        cols = ["symbol", "date", "open", "high", "low", "close",
                "volume", "hold", "settle", "cached_at"]
        n_written = 0
        for i, (_, row) in enumerate(df_new.iterrows(), 1):
            vals = [row.get(c) if c in row.index else None for c in cols]
            conn.execute(f"""
                INSERT OR REPLACE INTO futures_daily
                ({', '.join(cols)})
                VALUES ({', '.join(['?']*len(cols))})
            """, vals)
            n_written += 1
            if i % 100 == 0:
                print(f"  [日线回填] {sym} 进度 {i}/{len(df_new)}")
        conn.commit()
        print(f"[日线回填] {sym} 新增 {n_written} 条 "
              f"({df_new['date'].iloc[0]} ~ {df_new['date'].iloc[-1]}, ~{years}年)")
        return n_written
    except Exception as e:
        print(f"[日线回填] {sym} 写入失败: {e}")
        return 0
    finally:
        conn.close()


def backfill_min_history(symbol: str, days: int = 180, period: str = "5min") -> int:
    """
    回填指定品种近 N 天分时数据（v1.5 新增）

    - 数据源：ak.futures_zh_minute_sina(symbol=contract_code, period=...)
    - 4 个近月合约，取数据最新且非空的那一个
    - 自动派生 date 字段（从 datetime 前 10 位）
    - 幂等：INSERT OR REPLACE
    - 单合约失败不影响其他合约

    Note: akshare.futures_zh_minute_sina 仅返回最近 ~5-10 天数据，days 参数用作过滤窗口。

    Returns:
        新增行数
    """
    if not AKSHARE_AVAILABLE:
        raise ImportError("akshare not installed")

    sym = symbol.upper()
    today = _today_str()
    cutoff_dt = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    period_map = {"1min": "1", "5min": "5", "15min": "15", "30min": "30", "60min": "60"}
    akshare_period = period_map.get(period, "5")

    # 1. 构造 4 个近月合约
    try:
        contract_codes = _make_contract_codes(sym, n=4)
    except Exception as e:
        print(f"[分时回填] {sym} 构造合约代码失败: {e}")
        return 0

    # 2. 4 合约遍历，取数据最新且非空的那个
    best_df = None
    best_code = None
    best_latest = None
    for code in contract_codes:
        try:
            df = ak.futures_zh_minute_sina(symbol=code, period=akshare_period)
            if df is not None and len(df) > 0:
                latest = df.iloc[-1]["datetime"]
                if best_latest is None or latest > best_latest:
                    best_df = df
                    best_code = code
                    best_latest = latest
        except Exception as e:
            print(f"  [分时回填] {sym} 合约 {code} 拉取失败: {e}")
            continue

    if best_df is None:
        print(f"[分时回填] {sym} 4 个合约均无数据")
        return 0

    # 3. 标准化列名
    rename_cols = {
        "datetime": "datetime", "open": "open",
        "high": "high", "low": "low", "close": "close", "volume": "volume"
    }
    best_df = best_df.rename(columns=rename_cols)
    if "datetime" not in best_df.columns:
        print(f"[分时回填] {sym} 缺 datetime 列")
        return 0

    best_df["symbol"] = sym
    best_df["period"] = period
    best_df["datetime"] = pd.to_datetime(best_df["datetime"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    best_df["date"] = best_df["datetime"].str[:10]  # ★ v1.5 派生 date 字段
    best_df = best_df.sort_values("datetime")

    # 4. 过滤到 days 窗口
    best_df = best_df[best_df["datetime"] >= cutoff_dt]
    if len(best_df) == 0:
        print(f"[分时回填] {sym} 窗口内无数据")
        return 0

    # 5. 过滤已有数据（只写新行）
    conn = get_conn()
    try:
        existing_dt = {
            r[0] for r in conn.execute(
                "SELECT datetime FROM futures_min WHERE symbol=? AND period=?",
                (sym, period)
            ).fetchall()
        }
        df_new = best_df[~best_df["datetime"].isin(existing_dt)].copy()
        if len(df_new) == 0:
            print(f"[分时回填] {sym} {period} 缓存已最新（无新增）")
            return 0

        # 6. 写入
        df_new["cached_at"] = today
        df_new["contract_code"] = best_code
        df_new["name"] = SYMBOL_NAME.get(sym, sym)
        cols = ["symbol", "period", "datetime", "date", "open", "high", "low",
                "close", "volume", "cached_at", "contract_code", "name"]
        n_written = 0
        for i, (_, row) in enumerate(df_new.iterrows(), 1):
            vals = [row.get(c) if c in row.index else None for c in cols]
            conn.execute(f"""
                INSERT OR REPLACE INTO futures_min
                ({', '.join(cols)})
                VALUES ({', '.join(['?']*len(cols))})
            """, vals)
            n_written += 1
            if i % 100 == 0:
                print(f"  [分时回填] {sym} {period} 进度 {i}/{len(df_new)}")
        conn.commit()
        print(f"[分时回填] {sym} {period} 新增 {n_written} 条 "
              f"({df_new['datetime'].iloc[0]} ~ {df_new['datetime'].iloc[-1]})")
        return n_written
    except Exception as e:
        print(f"[分时回填] {sym} 写入失败: {e}")
        return 0
    finally:
        conn.close()


def identify_main_contract(symbol: str) -> Optional[str]:
    """
    识别某品种主力合约，写入 futures_contracts 表（v1.5 新增）

    - 4 个近月合约，遍历拿 hold（持仓量）
    - 持仓量最大的 = 主力（is_main=1, main_rank=1）
    - 其余（is_main=0, main_rank=2/3/4）
    - 写入 futures_contracts（INSERT OR REPLACE）
    - 单合约失败不影响其他合约

    Returns:
        主力合约代码（如 'ag2608'），失败返回 None
    """
    if not AKSHARE_AVAILABLE:
        raise ImportError("akshare not installed")

    sym = symbol.upper()
    name = SYMBOL_NAME.get(sym, sym)
    exchange = SYMBOL_EXCHANGE.get(sym, "")

    # 1. 构造 4 个近月合约
    try:
        contract_codes = _make_contract_codes(sym, n=4)
    except Exception as e:
        print(f"[主力识别] {sym} 构造合约代码失败: {e}")
        return None

    # 2. 遍历拿每个合约的 hold（持仓量）
    # 优先用日线最后一行的 hold（稳定），日线失败时回退到分线最后一行的 hold
    oi_data = {}  # code -> hold
    for code in contract_codes:
        hold = None
        # 先试日线
        try:
            df = ak.futures_zh_daily_sina(symbol=code)
            if df is not None and len(df) > 0 and "hold" in df.columns:
                hold = float(df.iloc[-1]["hold"])
        except Exception as e:
            pass
        # 日线失败 / hold 空 时试分时
        if hold is None or hold <= 0:
            try:
                df = ak.futures_zh_minute_sina(symbol=code, period="5")
                if df is not None and len(df) > 0 and "hold" in df.columns:
                    hold = float(df.iloc[-1]["hold"])
            except Exception:
                pass
        oi_data[code] = hold if hold and hold > 0 else 0.0

    # 3. 按 hold 降序排序
    valid_items = [(c, h) for c, h in oi_data.items() if h is not None]
    valid_items.sort(key=lambda x: x[1], reverse=True)

    if not valid_items:
        print(f"[主力识别] {sym} 4 个合约均无 oi 数据")
        return None

    # 4. 写入 futures_contracts
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inst_info = _get_instrument_info(sym)
    conn = get_conn()
    try:
        for rank, (code, oi) in enumerate(valid_items, 1):
            # 解析合约到期月份（ag2608 -> 2026-08）
            # 合约代码格式：品种(2字母) + 年(2位) + 月(2位)
            try:
                yy = int(code[-4:-2])
                mm = int(code[-2:])
                year_full = 2000 + yy
                expire_date = f"{year_full}-{mm:02d}-15"  # 近似 15 日
            except Exception:
                expire_date = None

            is_main = 1 if rank == 1 else 0
            conn.execute("""
                INSERT OR REPLACE INTO futures_contracts
                (contract_code, symbol, name, exchange, expire_date,
                 is_main, main_rank, last_oi, updated_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """, (code, sym, name, exchange, expire_date,
                  is_main, rank, oi, now_str))
        conn.commit()

        main_code = valid_items[0][0]
        oi_summary = ", ".join(f"{c}={h:.0f}" for c, h in valid_items)
        print(f"[主力识别] {sym} 主力={main_code} (oi={valid_items[0][1]:.0f}); 全部: {oi_summary}")
        return main_code
    except Exception as e:
        print(f"[主力识别] {sym} 写入失败: {e}")
        return None
    finally:
        conn.close()


def sync_all_contracts_and_main() -> int:
    """
    同步所有品种的合约列表 + 主力识别（v1.5 新增）

    - 从 instruments.yaml 读取所有品种
    - 遍历每个品种：调用 identify_main_contract()（内部写 4 个合约 + is_main 标记）
    - 单品种失败不影响其他品种

    Returns:
        处理的合约总数（品种数 × 4）
    """
    if not _INSTRUMENT_CFG:
        print("[批量同步] instruments.yaml 未加载，无品种可处理")
        return 0

    symbols = sorted(_INSTRUMENT_CFG.keys())
    total_contracts = 0
    n_success = 0
    n_fail = 0

    print(f"[批量同步] 开始处理 {len(symbols)} 个品种 ...")
    for sym in symbols:
        try:
            main = identify_main_contract(sym)
            if main:
                total_contracts += 4
                n_success += 1
            else:
                n_fail += 1
        except Exception as e:
            print(f"  [批量同步] {sym} 异常: {e}")
            n_fail += 1

    print(f"\n[批量同步] 完成: 成功 {n_success}/{len(symbols)}, "
          f"失败 {n_fail}, 写入合约 {total_contracts} 条")
    return total_contracts
