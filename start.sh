#!/bin/bash
# ACN Agent Monitor - React + Python Full Stack
# Start script

cd /root/lpx/webui

echo "=================================================="
echo "  ACN Agent Monitor"
echo "  React Frontend + Python Backend"
echo "=================================================="
echo ""

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Activating virtual environment..."
    source /root/lpx/acn_gw/venv/bin/activate
fi

# Start Backend
echo "Starting Backend Server..."
echo "  API: http://0.0.0.0:9050"
echo "  WebSocket: ws://0.0.0.0:9050/ws"
echo ""

cd backend
pip install -q -r requirements.txt 2>/dev/null

# Start backend in background
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9050 --reload > /tmp/webui_backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to start
sleep 2

# Check if backend is running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "ERROR: Backend failed to start"
    exit 1
fi

echo "Backend started successfully!"
echo ""
echo "Log file: /tmp/webui_backend.log"
echo ""
echo "=================================================="
echo "  Backend is running on http://0.0.0.0:9050"
echo "=================================================="
echo ""
echo "Note: Frontend needs to be built manually:"
echo "  cd /root/lpx/webui/frontend"
echo "  npm install"
echo "  npm start    # for development"
echo "  npm run build # for production"
echo ""
echo "Press Ctrl+C to stop the backend"
echo "=================================================="

# Keep script running
trap "echo 'Stopping backend...'; kill $BACKEND_PID 2>/dev/null; exit 0" INT
tail -f /tmp/webui_backend.log
