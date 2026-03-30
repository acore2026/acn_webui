#!/bin/bash
# Start backend server

cd /root/lpx/webui/backend
source /root/lpx/acn_gw/venv/bin/activate

echo "Starting ACN Agent Monitor Backend..."
echo "API: http://0.0.0.0:9050"
echo "WebSocket: ws://0.0.0.0:9050/ws"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 9050 --reload
