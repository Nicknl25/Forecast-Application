"""Wrapper to expose daily_qb_sync package via qb_app namespace.

Used by the in-process scheduler to import as
`from qb_app import daily_qb_sync` then call `daily_qb_sync.main(None)`.
"""

from daily_qb_sync import main  # re-export

