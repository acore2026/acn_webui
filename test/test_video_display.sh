#!/bin/bash
# Test Video Display Fix
# Run H.264 test and verify frontend receives data

echo "=========================================="
echo "  Video Display Fix Test"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${YELLOW}[Step 1]${NC} Running H.264 publisher test..."
echo "        This will send H.264 video for 60 seconds"
echo ""

# Run publisher in background
python3 /root/lpx/webui/test/test_h264_video.py &
PUB_PID=$!

# Wait for publisher to start sending
echo "        Waiting for publisher to start..."
sleep 5

echo ""
echo -e "${YELLOW}[Step 2]${NC} Checking WebUI backend..."

# Check if backend is receiving data
for i in {1..10}; do
    sleep 2
    
    # Check WebUI status
    RESULT=$(curl -s http://localhost:9005/api/moq/status 2>/dev/null | python3 -c "
import json,sys
d = json.load(sys.stdin)
for sub in d.get('subscription_debug', []):
    if sub.get('object_count', 0) > 0:
        print(f'{sub[\"object_count\"]}:{sub[\"buffered_frames\"]}')
        break
" 2>/dev/null)
    
    if [ -n "$RESULT" ]; then
        OBJ_COUNT=$(echo "$RESULT" | cut -d':' -f1)
        BUF_FRAMES=$(echo "$RESULT" | cut -d':' -f2)
        
        echo -e "${GREEN}[OK]${NC} Backend receiving data:"
        echo "        Objects: $OBJ_COUNT"
        echo "        Buffered Frames: $BUF_FRAMES"
        break
    fi
    
    echo "        Attempt $i/10: No data yet..."
done

if [ -z "$RESULT" ]; then
    echo -e "${RED}[Error]${NC} Backend not receiving data"
    kill $PUB_PID 2>/dev/null
    exit 1
fi

echo ""
echo -e "${YELLOW}[Step 3]${NC} Instructions for frontend verification:"
echo ""
echo "  1. Open browser at http://$(hostname -I | awk '{print $1}'):9005"
echo "  2. Login to WebUI"
echo "  3. Look for video cards in the sidebar"
echo "  4. Check browser console (F12) for:"
echo "     - [WebSocket] Received messages with VIDEO_FRAME"
echo "     - [MOQ H264] Decoder status messages"
echo ""
echo "  Expected behavior:"
echo "     - Video card shows 'Decoding' or 'LIVE H264'"
echo "     - Canvas displays decoded video frames"
echo "     - No 'Waiting for data...' message"
echo ""

# Wait for publisher to finish or user to interrupt
echo -e "${BLUE}[Info]${NC} Publisher running (PID: $PUB_PID)"
echo "        Press Ctrl+C to stop"
wait $PUB_PID

echo ""
echo "=========================================="
echo "  Test Complete"
echo "=========================================="
