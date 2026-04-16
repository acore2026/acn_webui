#!/bin/bash
# Rebuild Frontend with Video Display Fix

echo "=========================================="
echo "  Rebuilding Frontend"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

cd /root/lpx/webui/frontend

echo -e "${YELLOW}[Step 1]${NC} Installing dependencies..."
npm install

echo ""
echo -e "${YELLOW}[Step 2]${NC} Building frontend..."
npm run build

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}[OK]${NC} Frontend build successful!"
    echo ""
    echo "The fix has been applied:"
    echo "  - payload_base64 is now passed from App.jsx to MOQVideoCard"
    echo "  - H264VideoCard can now decode frames using WebCodecs API"
    echo ""
    echo "Next steps:"
    echo "  1. Refresh browser at http://localhost:9005"
    echo "  2. Run H.264 test: python3 /root/lpx/webui/test/test_h264_video.py"
    echo "  3. Check if video displays correctly"
else
    echo ""
    echo -e "${RED}[Error]${NC} Frontend build failed!"
    exit 1
fi
