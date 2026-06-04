"""API 进程内共享状态。

Phase 2 (sq-0008-p2-helpers) 引入。

设计动机：
- 原 main.py 维护 `_cached_prices: dict[str, float] = {}` 作为进程级缓存
- `_calc_signal`（现已抽到 `api.helpers.signal_calc`）写入它
- `get_position` 端点读取它
- 为避免 helpers↔main.py 的循环导入，把这个 dict 放到独立模块

行为不变：所有引用方都通过 `from api.state import cached_prices` 拿到同一份对象。
"""
from typing import Dict

# 进程内品种→最新收盘价缓存
# 原 api/main.py L172 `_cached_prices: dict[str, float] = {}`
cached_prices: Dict[str, float] = {}
