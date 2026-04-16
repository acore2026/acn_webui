#!/bin/bash
# H.264 Video Test Runner
# Automated test for MOQ video transmission

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  MOQ H.264 Video Test Runner${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check dependencies
echo -e "${YELLOW}[1/5]${NC} Checking dependencies..."

if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}[Error]${NC} FFmpeg not found. Installing..."
    apt-get update && apt-get install -y ffmpeg
fi
echo -e "${GREEN}[OK]${NC} FFmpeg available"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[Error]${NC} Python3 not found"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Python3 available"

echo ""

# Check relay connection
echo -e "${YELLOW}[2/5]${NC} Checking MOQ Relay..."

RELAY_HOST="localhost"
RELAY_PORT="9003"

# Check if relay is responding (QUIC)
if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$RELAY_HOST/$RELAY_PORT" 2>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Relay at $RELAY_HOST:$RELAY_PORT is reachable (TCP)"
else
    echo -e "${YELLOW}[Warn]${NC} Cannot check UDP port, assuming relay is running"
    echo "        Make sure agent_gw is running on port 9003"
fi

# Check WebUI status
WEBUI_STATUS=$(curl -s http://localhost:9005/api/moq/status 2>/dev/null || echo "{}")
if echo "$WEBUI_STATUS" | grep -q '"connected": true'; then
    echo -e "${GREEN}[OK]${NC} WebUI connected to relay"
    
    # Show subscribed tracks
    echo ""
    echo -e "${BLUE}Currently subscribed tracks:${NC}"
    echo "$WEBUI_STATUS" | python3 -c "
import json,sys
d = json.load(sys.stdin)
for i, track in enumerate(d.get('subscribed_tracks', [])):
    print(f'  {i+1}. {track}')
" 2>/dev/null || echo "  (Unable to parse)"
else
    echo -e "${RED}[Error]${NC} WebUI not connected to relay"
    echo "        Please start WebUI backend first:"
    echo "        cd /root/lpx/webui/backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9005"
    exit 1
fi

echo ""

# Run H.264 test
echo -e "${YELLOW}[3/5]${NC} Running H.264 video test..."
echo "        This will take about 60 seconds"
echo ""

cd "$SCRIPT_DIR/.."
python3 test/test_h264_video.py

TEST_RESULT=$?
echo ""

if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}[OK]${NC} Test completed successfully"
else
    echo -e "${RED}[Error]${NC} Test failed"
    exit 1
fi

echo ""

# Verify results
echo -e "${YELLOW}[4/5]${NC} Verifying results..."

sleep 2

RESULT=$(curl -s http://localhost:9005/api/moq/status 2>/dev/null | python3 -c "
import json,sys
d = json.load(sys.stdin)
for sub in d.get('subscription_debug', []):
    if sub.get('object_count', 0) > 0:
        print(f'{sub[\"track_id\"]}:{sub[\"object_count\"]}:{sub[\"buffered_frames\"]}')
" 2>/dev/null)

if [ -n "$RESULT" ]; then
    TRACK_ID=$(echo "$RESULT" | cut -d':' -f1)
    OBJ_COUNT=$(echo "$RESULT" | cut -d':' -f2)
    BUF_FRAMES=$(echo "$RESULT" | cut -d':' -f3)
    
    echo -e "${GREEN}[OK]${NC} Data received:"
    echo "        Track: $TRACK_ID"
    echo "        Objects: $OBJ_COUNT"
    echo "        Buffered Frames: $BUF_FRAMES"
else
    echo -e "${RED}[Error]${NC} No data received"
    exit 1
fi

echo ""

# Show frame samples
echo -e "${YELLOW}[5/5]${NC} Sample frames:"

TRACK_ID_URL=$(echo "$TRACK_ID" | sed 's/ /%20/g')
FRAME_DATA=$(curl -s "http://localhost:9005/api/moq/tracks/$TRACK_ID_URL/frames" 2>/dev/null | python3 -c "
import json,sys
data = json.load(sys.stdin)
frames = data.get('frames', [])
print(f'Total frames: {len(frames)}')
print('')
print('First 5 frames:')
for f in frames[:5]:
    print(f'  ID={f[\"object_id\"]}, Size={f[\"payload_size\"]} bytes, Type={f[\"frame_type\"]}')
" 2>/dev/null)

if [ -n "$FRAME_DATA" ]; then
    echo "$FRAME_DATA"
else
    echo "  (Unable to fetch frame data)"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Test Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Open browser at http://$(hostname -I | awk '{print $1}'):9005"
echo "  2. Login and navigate to video monitoring page"
echo "  3. Check if video is displayed"
echo ""
echo "Debug:"
echo "  - Backend logs: tail -f /root/lpx/webui/logs/backend.log"
echo "  - Browser DevTools: F12 -> Console/Network"
echo ""
