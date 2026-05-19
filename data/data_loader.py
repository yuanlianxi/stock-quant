"""
T1 海龟交易系统 - 数据层（akshare 版）
=======================================
从 akshare 获取期货行情数据，对接 factors.py 的因子计算

数据源：
  - akshare 期货日线（主力连续）
  - akshare 期货分钟线
  - 缓存到 SQLite

用途：
  - P1 回测引擎数据供给
  - P5 全品种回测数据获取
"""

import sqlite3
from pathlib import Path
from typing import Optional
import pandas as pd
import numpy as np

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("Warning: akshare not installed. Run: pip install akshare")

# ATR calculation (inline to avoid import issues)
def calc_atr_ema(tr_list: list, n_period: int = 20) -> float:
    if len(tr_list) < n_period:
        raise ValueError(f"TR 序列长度不足 {n_period}")
    n = tr_list[:n_period]
    atr = sum(n) / n_period
    for tr in tr_list[n_period:]:
        atr = (19 * atr + tr) / 20
    return atr


# ============================================================
# 数据缓存层
# ============================================================

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "futures_akshare.db"


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    """初始化数据库表"""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS futures_daily (
            symbol TEXT,
            date TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            hold REAL, settle REAL,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS futures_min (
            symbol TEXT,
            datetime TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY (symbol, datetime)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS futures_atr (
            symbol TEXT,
            date TEXT,
            tr REAL,
            atr REAL,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.commit()
    return conn


# ============================================================
# 日线数据获取
# ============================================================

def get_futures_daily(
    symbol: str,
    start_date: str = "20180101",
    end_date: str = "20251231",
    use_cache: bool = True
) -> pd.DataFrame:
    """
    获取期货日线数据（主力连续合约）
    symbol 示例：AG（白银）、RB（螺纹钢）

    返回 DataFrame，含列：date, open, high, low, close, volume
    """
    if not AKSHARE_AVAILABLE:
        raise ImportError("akshare not installed")

    cache_key = symbol.upper()
    conn = get_conn()

    # 1. 尝试从缓存读
    if use_cache:
        df_cached = pd.read_sql(
            f"SELECT * FROM futures_daily WHERE symbol='{cache_key}' "
            f"AND date>='{start_date}' AND date<='{end_date}' ORDER BY date",
            conn, index_col="date", parse_dates=["date"]
        )
        if len(df_cached) > 50:
            print(f"[数据] {symbol} 从缓存读取 {len(df_cached)} 条")
            return df_cached

    # 2. akshare 获取（符号格式：AG0/RB0/HC0 等）
    try:
        symbol_code = symbol.upper() + "0"   # AG0, RB0, HC0...
        df = ak.futures_zh_daily_sina(symbol=symbol_code)
        if df is None or len(df) == 0:
            print(f"[数据] {symbol} 无数据")
            return pd.DataFrame()
    except Exception as e:
        print(f"[数据] {symbol} 获取失败: {e}")
        return pd.DataFrame()

    if df is None or len(df) == 0:
        return pd.DataFrame()

    # 3. 标准化列名
    df = df.rename(columns={
        "日期": "date", "开盘价": "open",
        "最高价": "high", "最低价": "low",
        "收盘价": "close", "成交量": "volume"
    })
    df["symbol"] = cache_key
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # 4. 存入缓存（仅保留核心列）
    df_cache = df[["symbol", "date", "open", "high", "low", "close", "volume"]].copy()
    if use_cache and len(df_cache) > 0:
        conn.execute(
            f"DELETE FROM futures_daily WHERE symbol='{cache_key}'"
        )
        df_cache.to_sql("futures_daily", conn, if_exists="append", index=False)
        conn.commit()
        print(f"[数据] {symbol} 缓存 {len(df_cache)} 条到 SQLite")

    conn.close()
    return df


# ============================================================
# 分钟线数据获取
# ============================================================

def get_futures_min(
    symbol: str,
    period: str = "5",
    start_date: str = "20230101",
    end_date: str = "20251231"
) -> pd.DataFrame:
    """
    获取期货分钟线数据
    period: "1"/"5"/"15"/"30"/"60"（分钟）
    """
    if not AKSHARE_AVAILABLE:
        raise ImportError("akshare not installed")

    symbol_map = {
        "AG": "ag", "AU": "au", "CU": "cu", "AL": "al",
        "RB": "rb", "HC": "hc", "I": "i",
        "TA": "ta", "MA": "ma", "RU": "ru",
    }
    akshare_symbol = symbol_map.get(symbol.upper(), symbol.lower())

    try:
        df = ak.futures_zh_min_sina(symbol=akshare_symbol, period=period)
    except Exception as e:
        print(f"[数据] {symbol} 分钟线获取失败: {e}")
        return pd.DataFrame()

    if df is None or len(df) == 0:
        return pd.DataFrame()

    df = df.rename(columns={
        "日期时间": "datetime", "开盘价": "open",
        "最高价": "high", "最低价": "low",
        "收盘价": "close", "成交量": "volume"
    })
    df["symbol"] = symbol.upper()
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime")

    return df


# ============================================================
# ATR（N值）计算
# ============================================================

def calc_atr_series(
    df: pd.DataFrame,
    n_period: int = 20,
    use_cache: bool = True
) -> pd.DataFrame:
    """
    计算日线 ATR 序列
    df: 含 date, high, low, close 列

    返回：在原 df 基础上增加 tr, atr 列
    """
    df = df.copy()
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)

    # True Range
    prev_close = df["close"].shift(1).fillna(df["close"])
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.abs(df["high"] - prev_close),
        np.abs(df["low"] - prev_close)
    )

    # ATR EMA 递推
    tr_series = df["tr"].tolist()
    df["atr"] = calc_atr_ema(tr_series, n_period)

    return df


# ============================================================
# 55 日突破信号
# ============================================================

def calc_breakout_55(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 55 日突破信号
    在 df 上增加 high_55, low_55 列
    """
    df = df.copy()
    df["high_55"] = df["high"].rolling(55).max().shift(1)  # 前55日最高（入市用）
    df["low_55"] = df["low"].rolling(55).min().shift(1)   # 前55日最低（做空用）
    return df


# ============================================================
# 20 日离市信号
# ============================================================

def calc_exit_20(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算 20 日反向突破离市信号
    在 df 上增加 low_20, high_20 列
    """
    df = df.copy()
    df["low_20"] = df["low"].rolling(20).min().shift(1)  # 多头离市触发
    df["high_20"] = df["high"].rolling(20).max().shift(1)  # 空头离市触发
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
    获取品种数据，并计算所有海龟因子：
    - TR, ATR(N=20)
    - 55日突破价（high_55 / low_55）
    - 20日离市价（low_20 / high_20）

    返回：含完整因子列的 DataFrame
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
    """
    批量获取多个品种的因子数据
    返回 {symbol: df_with_factors}
    """
    results = {}
    for sym in symbols:
        df = get_futures_with_factors(sym, start_date, end_date, use_cache)
        if len(df) > 60:
            results[sym] = df
        else:
            print(f"[数据] {sym} 数据不足，跳过")
    return results


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    init_db()

    print("=== AKShare 数据接口测试 ===\n")

    # 测试 1：白银 AG 日线
    df_ag = get_futures_with_factors("AG", "20230101", "20251231")
    if len(df_ag) > 0:
        print(f"\n[1] AG 数据：{len(df_ag)} 条")
        print(f"     最新行: date={df_ag['date'].iloc[-1]}, "
              f"close={df_ag['close'].iloc[-1]:.0f}, "
              f"ATR={df_ag['atr'].iloc[-1]:.2f}, "
              f"55日最高={df_ag['high_55'].iloc[-1]:.0f}")
    else:
        print("[1] AG 数据获取失败")

    # 测试 2：螺纹钢 RB
    df_rb = get_futures_with_factors("RB", "20230101", "20251231")
    if len(df_rb) > 0:
        print(f"\n[2] RB 数据：{len(df_rb)} 条")
        print(f"     最新行: date={df_rb['date'].iloc[-1]}, "
              f"close={df_rb['close'].iloc[-1]:.0f}, "
              f"ATR={df_rb['atr'].iloc[-1]:.2f}")
    else:
        print("[2] RB 数据获取失败")

    # 测试 3：PTA 空头
    df_ta = get_futures_with_factors("TA", "20230101", "20251231")
    if len(df_ta) > 0:
        last = df_ta.iloc[-1]
        print(f"\n[3] PTA 数据：{len(df_ta)} 条")
        print(f"     最新: ATR={last['atr']:.2f}, "
              f"55日高低={last['high_55']:.0f}/{last['low_55']:.0f}")

    print("\n=== 测试完成 ===")
    print(f"缓存位置: {DB_PATH}")