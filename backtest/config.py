# stock-quant/backtest/config.py
import os

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据目录
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 数据库路径
DB_PATH = os.path.join(DATA_DIR, 'stock_quant.db')

# 默认参数
DEFAULT_CONFIG = {
    'initial_cash': 1000000,      # 初始资金 100 万
    'commission': 0.0003,         # 手续费万三
    'stamp_tax': 0.001,           # 印花税千一
    'slippage': 0.0001,           # 滑点万一
}

# 数据源配置
DATA_SOURCES = {
    'akshare': {
        'enabled': True,
        'priority': 0,
    },
    'baostock': {
        'enabled': True,
        'priority': 1,
    },
}
