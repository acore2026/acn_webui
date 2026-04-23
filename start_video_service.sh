#!/bin/bash
# Start Video Service on port 9006

cd /root/lpx/webui/backend

# Check if already running
if lsof -ti:9006 > /dev/null 2>&1; then
    echo "Video service already running on port 9006"
    echo "Health check:"
    curl -s http://localhost:9006/health
    echo ""
    exit 0
fi

echo "Starting Video Service on port 9006..."
python3 -m app.video_9006.service &

sleep 2

echo ""
echo "✅ Video Service started!"
echo ""
echo "Health check:"
curl -s http://localhost:9006/health | python3 -m json.tool
echo ""
echo "Available endpoints:"
echo "  - http://localhost:9006/"
echo "  - http://localhost:9006/health"
echo "  - http://localhost:9006/video/streams"
echo "  - http://localhost:9006/video/stream/{track_id}/mjpeg"
echo "  - http://localhost:9006/video/stream/{track_id}/latest"
echo "  - http://localhost:9006/video/stream/{track_id}/info"
echo "  - http://localhost:9006/video/player/{track_id}"
echo ""
