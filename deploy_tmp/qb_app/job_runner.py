import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional


# A small, in-process job runner for background tasks.
_MAX_WORKERS = int(os.getenv("JOB_MAX_WORKERS", "2") or 2)
_EXECUTOR: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=_MAX_WORKERS)


def submit_onboarding(client_id: int, logger: Optional[Callable[[str], None]] = None) -> None:
    """Queue an onboarding job to run in the background.

    The job logs start/finish to the provided logger (defaults to print).
    """
    if logger is None:
        logger = print

    cid = int(client_id)

    def _job() -> None:
        try:
            logger(f"[onboarding] start client_id={cid}")
            from qb_app.onboard_loader import run_onboarding

            run_onboarding(cid)
            logger(f"[onboarding] done client_id={cid}")
        except Exception as e:  # noqa: BLE001
            logger(f"[onboarding] error client_id={cid}: {e}")

    logger(f"[onboarding] queued client_id={cid}")
    _EXECUTOR.submit(_job)

