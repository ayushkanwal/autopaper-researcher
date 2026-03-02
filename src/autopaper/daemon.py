from __future__ import annotations

import threading
from typing import Any, Dict

from autopaper.config import RuntimeConfig
from autopaper.job_runner import execute_run
from autopaper.logging import configure_logger

_RUN_LOCK = threading.Lock()



def run_daemon(config: RuntimeConfig) -> int:
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError as exc:  # pragma: no cover - dependency/install guard
        raise RuntimeError("APScheduler is required for `autopaper daemon`. Install dependencies with `pip install -e .`.") from exc
    from zoneinfo import ZoneInfo

    logger = configure_logger(config.profile_name, config.state_dir)
    tz = ZoneInfo(config.timezone) if config.timezone else None
    scheduler = BlockingScheduler(timezone=tz)

    def scheduled_job(trigger_reason: str) -> None:
        if not _RUN_LOCK.acquire(blocking=False):
            logger.warning("previous run still active; skipping trigger=%s", trigger_reason)
            return
        try:
            execute_run(
                config,
                logger=logger,
                scheduler_context={
                    "mode": "daemon",
                    "trigger": trigger_reason,
                    "cron": config.schedule_cron,
                    "profile_name": config.profile_name,
                },
            )
        finally:
            _RUN_LOCK.release()

    if config.run_on_start:
        scheduled_job("run-on-start")

    trigger = CronTrigger.from_crontab(config.schedule_cron, timezone=tz)
    scheduler.add_job(lambda: scheduled_job("scheduled"), trigger=trigger, id=f"autopaper:{config.profile_name}", max_instances=1)
    logger.info("Daemon started profile=%s cron=%s timezone=%s", config.profile_name, config.schedule_cron, config.timezone or "system")
    scheduler.start()
    return 0
