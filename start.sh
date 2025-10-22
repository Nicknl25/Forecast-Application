#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] container boot at FT07:04:41Z"
python - <<'PY'
try:
    import gunicorn
    print(f"[entrypoint] gunicorn {getattr(gunicorn, '__version__', 'unknown')}")
except Exception:
    print("[entrypoint] gunicorn version unknown")
PY

export PYTHONUNBUFFERED=1
exec gunicorn \
  --bind=0.0.0.0:8000 \
  --timeout=600 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  --capture-output \
  wsgi:app