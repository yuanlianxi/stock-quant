"""后台调度器（sq-0009-p5 + sq-0009-round-3 commit 7）
===========================
技术选型：APScheduler 3.x + BackgroundScheduler
- 进程内调度，零外部依赖
- 内存 JobStore（重启后从 cache_schedule_state 读 last_run_at 重算）
- 3 个常驻 cron 任务：
  - daily_sync                  每天 17:00（周一至周五）—— 日线全量
  - minute_sync_5min            每 5 分钟 9-15 点（周一至周五）—— 实时增量
  - daily_full_minute_backfill  每天 17:05（周一至周五）—— 分时完整兜底

启动方式（api/main.py）：
    from api.scheduler import start_scheduler
    @app.on_event("startup")
    async def startup_event():
        start_scheduler()
"""
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from api.cache_sync import (
    sync_daily_all,
    sync_minute_all,
    update_schedule_after_run,
)


logger = logging.getLogger(__name__)

# 全局单例（避免多次启动）
_scheduler_instance: Optional[BackgroundScheduler] = None


# ============================================================
# 调度任务包装层
# ============================================================

def _run_daily_sync():
    """包装层：更新 cache_schedule_state + 调 sync_daily_all + 错误处理"""
    logger.info("[scheduler] daily_sync 启动")
    try:
        result = sync_daily_all(trigger_source="cron:daily_sync")
        status = "success" if result.get("status") == "success" else "partial"
        update_schedule_after_run("daily_sync", status)
        logger.info(f"[scheduler] daily_sync 完成：{result.get('rows_new', 0)} 新行, status={status}")
    except Exception as e:
        update_schedule_after_run("daily_sync", "failed")
        logger.error(f"[scheduler] daily_sync 失败: {e}", exc_info=True)


def _run_minute_5min():
    """包装层：更新 cache_schedule_state + 调 sync_minute_all + 错误处理"""
    logger.info("[scheduler] minute_sync_5min 启动")
    try:
        result = sync_minute_all(period="5min", trigger_source="cron:minute_sync_5min")
        status = "success" if result.get("status") == "success" else "partial"
        update_schedule_after_run("minute_sync_5min", status)
        logger.info(f"[scheduler] minute_sync_5min 完成：{result.get('rows_new', 0)} 新行, status={status}")
    except Exception as e:
        update_schedule_after_run("minute_sync_5min", "failed")
        logger.error(f"[scheduler] minute_sync_5min 失败: {e}", exc_info=True)


def _run_daily_full_minute_backfill():
    """sq-0009-round-3 commit 7：每日 17:05 完整回填分时 5min 数据

    目的：把 akshare 5min 数据源窗口（~10 天）内的所有数据完整拉到本地。
    - 17:00 daily_sync 完成后立即触发（5 分钟后）
    - 全 38 品种 × 5min 完整回填
    - 实际拉到条数受 akshare 限制（10 天 ≈ 4800 条/品种）

    与 minute_sync_5min 5min 频率互补：
    - minute_sync_5min: 实时增量（单次 ~48 条）
    - daily_full_minute_backfill: 完整兜底（10 天 ~4800 条/品种）
    """
    logger.info("[scheduler] daily_full_minute_backfill 启动")
    try:
        result = sync_minute_all(period="5min", trigger_source="cron:daily_full_minute_backfill")
        rows_new = result.get("rows_new", 0)
        update_schedule_after_run("daily_full_minute_backfill", "success")
        logger.info(f"[scheduler] daily_full_minute_backfill 完成：{rows_new} 新行")
    except Exception as e:
        update_schedule_after_run("daily_full_minute_backfill", "failed")
        logger.error(f"[scheduler] daily_full_minute_backfill 失败: {e}", exc_info=True)


# ============================================================
# 工厂
# ============================================================

def create_scheduler() -> BackgroundScheduler:
    """创建并配置 BackgroundScheduler（不启动）

    2 cron 任务：
    - daily_sync: 周一至周五 17:00
    - minute_sync_5min: 周一至周五 9-15 点每 5 分钟
    """
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # 任务 1：日线同步
    scheduler.add_job(
        func=_run_daily_sync,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=17,
            minute=0,
            timezone="Asia/Shanghai",
        ),
        id="daily_sync",
        name="日线全量增量同步",
        replace_existing=True,
        misfire_grace_time=300,  # 5 分钟内补跑
    )

    # 任务 2：5min 分时同步
    scheduler.add_job(
        func=_run_minute_5min,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour="9-15",
            minute="*/5",
            timezone="Asia/Shanghai",
        ),
        id="minute_sync_5min",
        name="5min 分时增量同步",
        replace_existing=True,
        misfire_grace_time=120,  # 2 分钟内补跑
    )

    # 任务 3（sq-0009-round-3 commit 7）：每日 17:05 完整回填分时 5min
    scheduler.add_job(
        func=_run_daily_full_minute_backfill,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=17,
            minute=5,
            timezone="Asia/Shanghai",
        ),
        id="daily_full_minute_backfill",
        name="日盘收盘后分时完整回填（5min 兜底）",
        replace_existing=True,
        misfire_grace_time=600,  # 10 分钟内补跑
    )

    return scheduler


def start_scheduler() -> BackgroundScheduler:
    """启动 scheduler（单例，重复调用返回同一实例）"""
    global _scheduler_instance
    if _scheduler_instance is not None and _scheduler_instance.running:
        return _scheduler_instance

    if _scheduler_instance is None:
        _scheduler_instance = create_scheduler()

    if not _scheduler_instance.running:
        _scheduler_instance.start()
        logger.info(
            f"[scheduler] 启动：{len(_scheduler_instance.get_jobs())} 任务"
        )
        for job in _scheduler_instance.get_jobs():
            logger.info(
                f"  - {job.id}: {job.name} (next_run: {job.next_run_time})"
            )

    return _scheduler_instance


def stop_scheduler():
    """停止 scheduler（用于测试 / 优雅退出）"""
    global _scheduler_instance
    if _scheduler_instance is not None and _scheduler_instance.running:
        _scheduler_instance.shutdown(wait=False)
        logger.info("[scheduler] 停止")
    _scheduler_instance = None


def get_scheduler() -> Optional[BackgroundScheduler]:
    """获取当前 scheduler 实例（供 toggle 端点用）"""
    return _scheduler_instance


def toggle_task(task_name: str, enabled: bool) -> bool:
    """联动 APScheduler 启停单个任务

    Returns:
        True if 切换成功
    """
    scheduler = get_scheduler()
    if scheduler is None or not scheduler.running:
        return False

    job = scheduler.get_job(task_name)
    if job is None:
        return False

    if enabled:
        scheduler.resume_job(task_name)
    else:
        scheduler.pause_job(task_name)
    return True
