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
echo "[entrypoint] reached before exec at $(date -u +%FT%TZ)"\nwhich gunicorn || true\necho "[entrypoint] which python: $(which python || true)"\nexec gunicorn \
  --bind=0.0.0.0:8000 \
  --timeout=600 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  --capture-output \
  wsgi:app