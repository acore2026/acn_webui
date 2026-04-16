#!/usr/bin/env bash
# Start backend server

cd /root/lpx/webui/backend
VENV_PYTHON="${VENV_PYTHON:-/root/lpx/acn_gw/venv/bin/python3}"

echo "Starting ACN Agent Monitor Backend..."
echo "API: http://0.0.0.0:9050"
echo "WebSocket: ws://0.0.0.0:9050/ws"
echo ""

exec "$VENV_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 9050 --reload
