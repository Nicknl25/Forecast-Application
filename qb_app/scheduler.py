import os
import traceback
import datetime
from datetime import datetime, timezone
import time

from apscheduler.schedulers.background import BackgroundScheduler
from qb_app import qb_token_refresh, daily_qb_sync


def _log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except Exception:
        pass


def _run_with_retries(fn, name: str, tries: int = 5, backoff_sec: int = 20) -> None:
    """Run fn with retries so cold starts or transient failures don't skip jobs."""
    for attempt in range(1, tries + 1):
        try:
            fn()
            _log(f"[scheduler][{name}] done (attempt {attempt})")
            try:
                print(f"[scheduler][{name}] done (attempt {attempt})", flush=True)
            except Exception:
                pass
            return
        except Exception as e:  # noqa: BLE001
            _log(f"[scheduler][{name}] error on attempt {attempt}: {e}\n{traceback.format_exc()}")
            if attempt < tries:
                delay = backoff_sec * attempt
                try:
                    print(f"[scheduler][{name}] retrying in {delay}s", flush=True)
                except Exception:
                    pass
                time.sleep(delay)
            else:
                _log(f"[scheduler][{name}] giving up after {tries} attempts")


def job_token_refresh() -> None:
    start = datetime.now(timezone.utc).isoformat()
    _log(f"[scheduler][token_refresh] start {start}")
    # Explicit visibility in container logs
    try:
        print("[scheduler][token_refresh] start", flush=True)
    except Exception:
        pass
    _run_with_retries(lambda: qb_token_refresh.main(None), "token_refresh")


def job_daily_sync() -> None:
    start = datetime.now(timezone.utc).isoformat()
    _log(f"[scheduler][daily_sync] start {start}")
    # Explicit visibility in container logs
    try:
        print("[scheduler][daily_sync] start", flush=True)
    except Exception:
        pass
    _run_with_retries(lambda: daily_qb_sync.main(None), "daily_sync")


def _start_scheduler() -> None:
    if os.getenv("SCHEDULER_DISABLED", "0") == "1":
        _log("[scheduler] disabled by env")
        return

    # Only start one scheduler per process; configure misfire handling so jobs
    # still run shortly after container cold start. Coalesce avoids bursts.
    sched = BackgroundScheduler(
        timezone="UTC",
        job_defaults={
            "misfire_grace_time": int(os.getenv("MISFIRE_GRACE_SECONDS", "3600") or 3600),
            "coalesce": True,
            "max_instances": 1,
        },
    )
    # Hourly token refresh
    j_refresh = sched.add_job(
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
    j_daily = sched.add_job(
        job_daily_sync,
        trigger="cron",
        hour=hour,
        minute=minute,
        id="daily_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    # Heartbeat every 30 minutes for visibility in Log Stream
    def heartbeat():
        try:
            print(f"[heartbeat] Scheduler running - {datetime.datetime.utcnow().isoformat()} UTC", flush=True)
        except Exception:
            pass
    j_heartbeat = sched.add_job(heartbeat, "interval", minutes=30, id="heartbeat", replace_existing=True)
    sched.start()
    # Log next planned runs for visibility
    try:
        if j_refresh and j_refresh.next_run_time:
            print(f"[scheduler] token_refresh next: {j_refresh.next_run_time.isoformat()}", flush=True)
        if j_daily and j_daily.next_run_time:
            print(f"[scheduler] daily_sync  next: {j_daily.next_run_time.isoformat()}", flush=True)
    except Exception:
        pass
    _log("[scheduler] started (token_refresh interval, daily_sync cron, heartbeat interval)")
    try:
        print("[scheduler] started (token_refresh interval, daily_sync cron, heartbeat interval)", flush=True)
    except Exception:
        pass


# Start scheduler on import
try:
    _start_scheduler()
except Exception as e:  # noqa: BLE001
    _log(f"[scheduler] failed to start: {e}\n{traceback.format_exc()}")



