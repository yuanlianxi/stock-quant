# stock-quant/backtest/data_loader.py
import pandas as pd
import sqlite3
from datetime import datetime
from typing import Optional


class DataLoader:
    """统一的数据获取接口"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS stock_daily (
                code TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (code, date)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS etf_daily (
                code TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (code, date)
            )
        ''')
        conn.commit()
        conn.close()

    def get_stock_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        """
        获取股票日线数据
        code: 股票代码，如 '000001'（平安银行）
        start: 开始日期，如 '2018-01-01'
        end: 结束日期，如 '2023-12-31'
        """
        # 尝试从 SQLite 加载
        df = self.load_from_sqlite('stock_daily', code)
        if df is not None and len(df) > 0:
            df = df[(df['date'] >= start) & (df['date'] <= end)]
            if len(df) > 0:
                return df

        # 从 akshare 获取
        try:
            import akshare as ak
            symbol = code.zfill(6)  # 补齐 6 位
            df = ak.stock_zh_a_hist(symbol=symbol, start_date=start.replace('-', ''), end_date=end.replace('-', ''), adjust="qfq")
            df = df.rename(columns={
                '日期': 'date',
                '股票代码': 'code',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume'
            })
            df = df[['code', 'date', 'open', 'high', 'low', 'close', 'volume']]
            self.save_to_sqlite(df, 'stock_daily')
            return df
        except Exception as e:
            print(f"akshare 获取失败: {e}")
            return pd.DataFrame()

    def get_etf_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        """
        获取 ETF 日线数据
        code: ETF 代码，如 '510300'（沪深 300ETF）
        """
        # 尝试从 SQLite 加载
        df = self.load_from_sqlite('etf_daily', code)
        if df is not None and len(df) > 0:
            df = df[(df['date'] >= start) & (df['date'] <= end)]
            if len(df) > 0:
                return df

        # 从 akshare 获取
        try:
            import akshare as ak
            df = ak.fund_etf_hist(symbol=code, start_date=start.replace('-', ''), end_date=end.replace('-', ''))
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '最高': 'high',
                '最低': 'low',
                '收盘': 'close',
                '成交量': 'volume'
            })
            df['code'] = code
            df = df[['code', 'date', 'open', 'high', 'low', 'close', 'volume']]
            self.save_to_sqlite(df, 'etf_daily')
            return df
        except Exception as e:
            print(f"akshare 获取失败: {e}")
            return pd.DataFrame()

    def save_to_sqlite(self, df: pd.DataFrame, table: str):
        """保存到 SQLite"""
        if df.empty:
            return
        conn = sqlite3.connect(self.db_path)
        df.to_sql(table, conn, if_exists='append', index=False)
        conn.close()

    def load_from_sqlite(self, table: str, code: str) -> Optional[pd.DataFrame]:
        """从 SQLite 加载"""
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql_query(f"SELECT * FROM {table} WHERE code='{code}'", conn)
            conn.close()
            return df
        except:
            return None


# 便捷函数
def get_data_loader() -> DataLoader:
    """获取 DataLoader 实例"""
    from .config import DB_PATH
    return DataLoader(DB_PATH)
