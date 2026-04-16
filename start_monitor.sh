#!/usr/bin/env bash
cd /root/lpx/webui/backend
VENV_PYTHON="${VENV_PYTHON:-/root/lpx/acn_gw/venv/bin/python3}"
exec "$VENV_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 9050
