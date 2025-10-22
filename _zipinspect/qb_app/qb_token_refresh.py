"""Wrapper to expose qb_token_refresh package via qb_app namespace.

Allows imports like `from qb_app import qb_token_refresh` and calling
`qb_token_refresh.main(None)` from the web app scheduler.
"""

from qb_token_refresh import main  # re-export
