import os
import sys
import logging
from flask import Flask

# Send logs to stdout for Azure Log Stream
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "fallback_key")
# Let Flask app logs propagate to root (handled above)
app.logger.propagate = True
