#!/bin/bash
# 1080p MOQ Pipeline Test
# Publisher + Subscriber/WebServer

WEBUI_ROOT="/root/lpx/webui"
TEST_DIR="$WEBUI_ROOT/test"
LOG_DIR="/tmp/moq_1080p_test"

mkdir -p $LOG_DIR

echo "=============================================="
echo "1080p MOQ Video Pipeline Test"
echo "=============================================="
echo ""
echo "Components:"
echo "  - Publisher: Reads test_1080p.h264 -> MOQ Relay (9003)"
echo "  - Subscriber: Receives from MOQ -> Transcode -> HTTP (9006)"
echo ""

# Kill any existing processes
echo "[1] Cleaning up old processes..."
pkill -9 -f "publish_1080p.py" 2>/dev/null
pkill -9 -f "moq_video_server_9006.py" 2>/dev/null
sleep 2
echo "    Done"

# Start Publisher
echo ""
echo "[2] Starting Publisher..."
cd $WEBUI_ROOT
python3 $TEST_DIR/publish_1080p.py > $LOG_DIR/publisher.log 2>&1 &
PUB_PID=$!
echo "    Publisher PID: $PUB_PID"
sleep 3
tail -10 $LOG_DIR/publisher.log

# Start Subscriber/Web Server
echo ""
echo "[3] Starting Subscriber/Web Server on port 9006..."
python3 $TEST_DIR/moq_video_server_9006.py > $LOG_DIR/server.log 2>&1 &
SRV_PID=$!
echo "    Server PID: $SRV_PID"
sleep 5
tail -20 $LOG_DIR/server.log

echo ""
echo "=============================================="
echo "Pipeline started!"
echo "=============================================="
echo ""
echo "Access the video stream at:"
echo "  http://localhost:9006"
echo ""
echo "Monitor logs:"
echo "  Publisher: tail -f $LOG_DIR/publisher.log"
echo "  Server:    tail -f $LOG_DIR/server.log"
echo ""
echo "Stop all:"
echo "  kill $PUB_PID $SRV_PID"
echo ""

# Show status every 5 seconds
echo "Monitoring (Ctrl+C to stop monitoring)..."
while true; do
    sleep 5
    echo ""
    echo "--- Status Check ---"
    echo "Publisher running: $(kill -0 $PUB_PID 2>/dev/null && echo 'YES' || echo 'NO')"
    echo "Server running:    $(kill -0 $SRV_PID 2>/dev/null && echo 'YES' || echo 'NO')"
    tail -5 $LOG_DIR/publisher.log 2>/dev/null | grep -E "Published|frames" | tail -1
    tail -5 $LOG_DIR/server.log 2>/dev/null | grep -E "Received|frame" | tail -1
done
