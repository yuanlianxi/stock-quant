"""Cache Router（sq-0008-p4-batch2）
================
拆自 api/main.py 的"缓存状态"段，含 1 个端点：
- GET /cache/status

cache_status 来源：data.data_loader（与 main.py 第 78 行 import 同一份 SSOT）。
"""
from fastapi import APIRouter

from data.data_loader import cache_status

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/status")
async def get_cache_status():
    """缓存状态诊断"""
    return cache_status()
