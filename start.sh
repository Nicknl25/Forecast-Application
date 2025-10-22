#!/bin/sh
set -eu

echo "[entrypoint] container boot at FT07:15:22Z"
python - <<'PY'
try:
    import gunicorn
    ver = getattr(gunicorn, '__version__', 'unknown')
    print(f"[entrypoint] gunicorn {ver}")
except Exception as e:
    print(f"[entrypoint] gunicorn version lookup failed: {e}")
PY

export PYTHONUNBUFFERED=1
echo "[entrypoint] reached before 
echo [entrypoint] launching gunicorn on 0.0.0.0:
exec gunicorn -b 0.0.0.0: qb_app:app --access-logfile - --error-logfile - --log-level info --capture-output