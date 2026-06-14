"""
Stock Quant - FastAPI 服务
==============================
提供回测、信号、仓位查询接口
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException

from strategies.turtle.position import PositionManager

# Phase 4 (sq-0008-p4-routers): 9 个域 router 全部从 main.py 抽出
# Batch-1 (sq-0008-p4-batch1): 拆 signal router（Pilot 试水）
from api.routers.signal import router as signal_router
# Batch-2 (sq-0008-p4-batch2): 拆 cache / position / account 3 个域
from api.routers.cache import router as cache_router
from api.routers.position import router as position_router
from api.routers.account import router as account_router
# Batch-3 (sq-0008-p4-batch3): 拆 market / backtest / turtle 3 个域
from api.routers.market import router as market_router
from api.routers.backtest import router as backtest_router
from api.routers.turtle import router as turtle_router
# Batch-4 (sq-0008-p4-batch4): 拆 session / strategy 2 个域（最后一批）
from api.routers.session import router as session_router
from api.routers.strategy import router as strategy_router

# sq-0009-p5: APScheduler 集成（2 cron 任务）
try:
    from api.scheduler import start_scheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

app = FastAPI(
    title="Stock Quant API",
    description="海龟交易系统回测与服务接口",
    version="0.18.4"
)

# 注册域 router（Phase 4 sq-0008-p4-routers）
app.include_router(signal_router)
app.include_router(cache_router)
app.include_router(position_router)
app.include_router(account_router)
app.include_router(market_router)
app.include_router(backtest_router)
app.include_router(turtle_router)
app.include_router(session_router)
app.include_router(strategy_router)

# ============================================================
# 全局状态
# ============================================================
#
# P5 收尾迁移记录：
# - _cached_prices 已迁到 api.state（Phase 2 抽 _calc_signal 时一并迁出，避免循环导入）
# - backtest_jobs 已迁到 api.routers.backtest（Phase 4 Batch-3，本 router 内部实例化）

position_manager = PositionManager()

# ============================================================
# API 端点
# ============================================================

WWW_DIR = PROJECT_ROOT / "www_legacy_v1.5"
WEBAPP_DIST = PROJECT_ROOT / "webapp" / "dist"
WEBAPP_INDEX = WEBAPP_DIST / "index.html"
WEBAPP_ASSETS = WEBAPP_DIST / "assets"

# 旧版 v1.5 挂到 /legacy（保留作为灰度对照）
app.mount("/legacy", StaticFiles(directory=str(WWW_DIR), html=True), name="legacy")

# 新版 webapp 静态资源（CSS / JS / favicon 等）
if WEBAPP_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=str(WEBAPP_ASSETS)), name="webapp-assets")

# 根路径 → 新版 webapp index.html
@app.get("/")
async def root():
    """主页看板（v1.6 新版 webapp）"""
    if WEBAPP_INDEX.is_file():
        return FileResponse(str(WEBAPP_INDEX))
    # 新版未构建时降级到旧版，避免服务不可用
    return FileResponse(str(WWW_DIR / "index.html"))

# 健康检查（必须在 SPA fallback 之前定义，否则被 /{full_path:path} 抢走）
@app.get("/health")
async def health():
    return {"status": "healthy"}

# SPA fallback：所有未匹配的 UI 路径都返回新版 index.html（Vue 接管）
_SPA_EXCLUDED_PREFIXES = (
    "api", "assets", "legacy", "docs", "openapi.json", "redoc"
)

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """v1.6 SPA fallback：让 Vue 接管前端路由"""
    first = full_path.split("/", 1)[0]
    if first in _SPA_EXCLUDED_PREFIXES:
        raise HTTPException(status_code=404, detail="Not Found")
    if WEBAPP_INDEX.is_file():
        return FileResponse(str(WEBAPP_INDEX))
    raise HTTPException(status_code=404, detail="webapp not built")


# ============================================================
# sq-0009-p5: 启动钩子
# ============================================================
if SCHEDULER_AVAILABLE:
    @app.on_event("startup")
    async def startup_event():
        """FastAPI 启动时启动 APScheduler + 应用 cache_schedule_state.enabled"""
        start_scheduler()
        # 联动：从 cache_schedule_state 读 enabled 状态，disabled 的 pause
        from api.cache_sync import get_schedule_state
        from api.scheduler import toggle_task
        for s in get_schedule_state():
            enabled = bool(s["enabled"])
            if not enabled:
                toggle_task(s["task_name"], False)
                print(f"[main] {s['task_name']} enabled=0，pause")
        print("[main] APScheduler 启动，2 cron 任务已注册")

    @app.on_event("shutdown")
    async def shutdown_event():
        """FastAPI 关闭时停止 APScheduler"""
        from api.scheduler import stop_scheduler
        stop_scheduler()
        print("[main] APScheduler 停止")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
