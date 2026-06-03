"""
策略动态加载器

通过 strategies 表的 type/version 字段动态加载对应实现
例：type='turtle', version=1 → 加载 strategies/turtle/V1/strategy.py
"""
import importlib
import json
import sqlite3
from pathlib import Path
from typing import Dict, List

from .base import BaseStrategy

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "futures_akshare.db"


def _load_strategy_class(type_name: str, version: int) -> type:
    """
    动态加载策略类
    例：_load_strategy_class('turtle', 1) → strategies.turtle.V1.strategy.TurtleStrategy
    """
    module_path = f"strategies.{type_name}.V{version}.strategy"
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ImportError(f"无法加载策略模块 {module_path}: {e}")

    # 找 BaseStrategy 子类
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, BaseStrategy) and attr is not BaseStrategy:
            return attr
    raise ImportError(f"模块 {module_path} 中无 BaseStrategy 子类")


def get_strategy(strategy_id: str) -> BaseStrategy:
    """
    根据 strategy_id 加载策略实例
    例：get_strategy('turtle_v1') → TurtleStrategy(params=...) 实例
    """
    # 1. 从 DB 查 strategies 表
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT strategy_id, name, type, version, params_json
        FROM strategies
        WHERE strategy_id = ?
        """,
        (strategy_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        raise ValueError(f"策略 {strategy_id} 不存在")

    # 2. 解析 params_json
    params = json.loads(row["params_json"]) if row["params_json"] else {}

    # 3. 动态加载类
    cls = _load_strategy_class(row["type"], row["version"])

    # 4. 实例化
    return cls(params=params)


def list_available_strategies() -> List[Dict]:
    """
    列出所有可用策略（从 DB 查 + 验证模块可加载）
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT strategy_id, name, type, version, is_active FROM strategies ORDER BY strategy_id"
    )
    rows = cur.fetchall()
    conn.close()

    available: List[Dict] = []
    for row in rows:
        info: Dict = dict(row)
        info["loadable"] = True
        info["error"] = None
        try:
            _load_strategy_class(row["type"], row["version"])
        except ImportError as e:
            info["loadable"] = False
            info["error"] = str(e)
        available.append(info)
    return available
