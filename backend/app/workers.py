import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.reserve import ReserveInterestService
from app.services.scheduler import NodeHeartbeatService, TaskRetryHandler, TaskScheduler

settings = get_settings()
logger = logging.getLogger("app")

scheduler = AsyncIOScheduler()


async def run_task_scheduler():
    """任务调度器作业"""
    async with AsyncSessionLocal() as session:
        try:
            task_scheduler = TaskScheduler(session)
            count = await task_scheduler.schedule_pending_tasks()
            if count > 0:
                logger.info("[Scheduler] Scheduled %d tasks", count)
        except Exception:
            logger.exception("[Scheduler] Error")


async def run_elastic_scaling():
    """弹性扩容评估作业"""
    async with AsyncSessionLocal() as session:
        try:
            task_scheduler = TaskScheduler(session)
            count = await task_scheduler.scale_out_running_tasks()
            if count > 0:
                logger.info("[Elastic] Scaled out %d tasks", count)
        except Exception:
            logger.exception("[Elastic] Error")


async def run_scale_in():
    """弹性缩容评估作业"""
    async with AsyncSessionLocal() as session:
        try:
            task_scheduler = TaskScheduler(session)
            count = await task_scheduler.scale_in_lagging_tasks()
            if count > 0:
                logger.info("[Elastic] Scaled in %d lagging slices", count)
        except Exception:
            logger.exception("[Elastic] Error")


async def run_heartbeat_check():
    """节点心跳检查作业"""
    async with AsyncSessionLocal() as session:
        try:
            heartbeat_service = NodeHeartbeatService(session)
            count = await heartbeat_service.check_offline_nodes()
            if count > 0:
                logger.info("[Heartbeat] Marked %d nodes offline", count)
        except Exception:
            logger.exception("[Heartbeat] Error")


async def run_retry_handler():
    """任务失败重试处理作业"""
    async with AsyncSessionLocal() as session:
        try:
            retry_handler = TaskRetryHandler(session)
            count = await retry_handler.handle_failed_executions()
            if count > 0:
                logger.info("[Retry] Handled %d failed executions", count)
        except Exception:
            logger.exception("[Retry] Error")


async def run_reserve_interest():
    """储备利息分配作业"""
    async with AsyncSessionLocal() as session:
        try:
            reserve_service = ReserveInterestService(session)
            count = await reserve_service.distribute()
            if count > 0:
                logger.info("[Reserve] Distributed interest to %d accounts", count)
        except Exception:
            logger.exception("[Reserve] Error")


async def run_resume_paused_tasks():
    """暂停任务恢复扫描作业"""
    async with AsyncSessionLocal() as session:
        try:
            task_scheduler = TaskScheduler(session)
            count = await task_scheduler.resume_paused_tasks()
            if count > 0:
                logger.info("[Resume] Resumed %d paused tasks", count)
        except Exception:
            logger.exception("[Resume] Error")


def start_scheduler():
    """启动定时任务调度器"""
    scheduler.add_job(
        run_task_scheduler,
        IntervalTrigger(seconds=settings.SCHEDULER_INTERVAL_SECONDS),
        id="task_scheduler",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_elastic_scaling,
        IntervalTrigger(seconds=settings.ELASTIC_SCALING_INTERVAL_SECONDS),
        id="elastic_scaling",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_scale_in,
        IntervalTrigger(seconds=settings.ELASTIC_SCALING_INTERVAL_SECONDS),
        id="elastic_scale_in",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_heartbeat_check,
        IntervalTrigger(seconds=settings.HEARTBEAT_CHECK_INTERVAL_SECONDS),
        id="heartbeat_check",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_retry_handler,
        IntervalTrigger(seconds=settings.RETRY_CHECK_INTERVAL_SECONDS),
        id="retry_handler",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_reserve_interest,
        IntervalTrigger(seconds=settings.RESERVE_INTEREST_INTERVAL_SECONDS),
        id="reserve_interest",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_resume_paused_tasks,
        IntervalTrigger(seconds=settings.RESUME_CHECK_INTERVAL_SECONDS),
        id="resume_paused_tasks",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Background workers started")


def stop_scheduler():
    """停止定时任务调度器"""
    scheduler.shutdown(wait=True)
    logger.info("Background workers stopped")


# 信号处理
def setup_signal_handlers():
    def signal_handler(signum, _frame):
        logger.info("Received signal %s, stopping scheduler...", signum)
        stop_scheduler()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
