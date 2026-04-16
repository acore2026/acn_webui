#!/bin/bash
# MOQ Video Pipeline Test Script
# Runs relay, publisher, and subscriber to test video transmission

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "MOQ Video Pipeline Test"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to cleanup processes
cleanup() {
    echo ""
    echo "Cleaning up..."
    if [ -n "$RELAY_PID" ]; then
        kill $RELAY_PID 2>/dev/null || true
    fi
    if [ -n "$PUB_PID" ]; then
        kill $PUB_PID 2>/dev/null || true
    fi
    if [ -n "$SUB_PID" ]; then
        kill $SUB_PID 2>/dev/null || true
    fi
    echo "Done."
}

trap cleanup EXIT

# Step 1: Start Relay
echo -e "${YELLOW}[Step 1]${NC} Starting MOQ Relay..."
python3 moq_relay.py &
RELAY_PID=$!
sleep 2

# Check if relay is running
if ! kill -0 $RELAY_PID 2>/dev/null; then
    echo -e "${RED}[Error]${NC} Failed to start relay"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Relay started (PID: $RELAY_PID)"
echo ""

# Step 2: Start Subscriber
echo -e "${YELLOW}[Step 2]${NC} Starting MOQ Subscriber..."
python3 moq_subscriber.py &
SUB_PID=$!
sleep 2

# Check if subscriber is running
if ! kill -0 $SUB_PID 2>/dev/null; then
    echo -e "${RED}[Error]${NC} Failed to start subscriber"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Subscriber started (PID: $SUB_PID)"
echo ""

# Step 3: Start Publisher
echo -e "${YELLOW}[Step 3]${NC} Starting MOQ Publisher..."
python3 moq_publisher.py &
PUB_PID=$!

# Wait for publisher to complete
wait $PUB_PID
PUB_RESULT=$?

echo ""
if [ $PUB_RESULT -eq 0 ]; then
    echo -e "${GREEN}[OK]${NC} Publisher completed successfully"
else
    echo -e "${RED}[Error]${NC} Publisher failed"
    exit 1
fi

# Give subscriber time to receive remaining data
echo ""
echo "Waiting for subscriber to finish..."
sleep 5

echo ""
echo "=========================================="
echo -e "${GREEN}Test Complete!${NC}"
echo "=========================================="
