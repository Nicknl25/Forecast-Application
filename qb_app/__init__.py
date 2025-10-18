import os
import sys
import logging
from flask import Flask

# Configure root logging to stdout once (INFO level)
_root_logger = logging.getLogger()
if not _root_logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    _handler.setFormatter(_formatter)
    _root_logger.addHandler(_handler)
_root_logger.setLevel(logging.INFO)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "fallback_key")
# Let Flask app logs propagate to root (handled above)
app.logger.propagate = True
