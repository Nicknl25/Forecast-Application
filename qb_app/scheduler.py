import os
import traceback
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from qb_app import qb_token_refresh, daily_qb_sync


def _log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except Exception:
        pass


def job_token_refresh() -> None:
    start = datetime.now(timezone.utc).isoformat()
    _log(f"[scheduler][token_refresh] start {start}")
    try:
        qb_token_refresh.main(None)  # Azure Function style, timer arg unused in our code
        _log("[scheduler][token_refresh] done")
    except Exception as e:  # noqa: BLE001
        _log(f"[scheduler][token_refresh] error: {e}\n{traceback.format_exc()}")


def job_daily_sync() -> None:
    start = datetime.now(timezone.utc).isoformat()
    _log(f"[scheduler][daily_sync] start {start}")
    try:
        daily_qb_sync.main(None)  # Azure Function style, timer arg unused in our code
        _log("[scheduler][daily_sync] done")
    except Exception as e:  # noqa: BLE001
        _log(f"[scheduler][daily_sync] error: {e}\n{traceback.format_exc()}")


def _start_scheduler() -> None:
    if os.getenv("SCHEDULER_DISABLED", "0") == "1":
        _log("[scheduler] disabled by env")
        return

    # Only start one scheduler per process
    sched = BackgroundScheduler(timezone="UTC")
    # Hourly token refresh
    sched.add_job(
        job_token_refresh,
        trigger="interval",
        minutes=int(os.getenv("TOKEN_REFRESH_INTERVAL_MIN", "60") or 60),
        id="token_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    # Daily sync at 03:00 UTC by default
    hour = int(os.getenv("DAILY_SYNC_HOUR_UTC", "3") or 3)
    minute = int(os.getenv("DAILY_SYNC_MINUTE_UTC", "0") or 0)
    sched.add_job(
        job_daily_sync,
        trigger="cron",
        hour=hour,
        minute=minute,
        id="daily_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _log("[scheduler] started (token_refresh interval, daily_sync cron)")


# Start scheduler on import
try:
    _start_scheduler()
except Exception as e:  # noqa: BLE001
    _log(f"[scheduler] failed to start: {e}\n{traceback.format_exc()}")
