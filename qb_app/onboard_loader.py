"""
Lightweight onboarding runner for the Web App.

Moves onboarding out of ad-hoc HTTP triggers and into a direct call
from the OAuth callback flow. This invokes the existing
load_all_transactions.main(client_id) to kick off the initial load.
"""

from typing import Optional


def run_onboarding(client_id: int) -> None:
    """Run onboarding for the given client_id.

    This function intentionally imports inside the body to avoid
    import-time side-effects when the module is loaded.
    """
    from qb_app import load_all_transactions

    # Ensure integer client id
    cid: int = int(client_id)
    load_all_transactions.main(client_id=cid)

