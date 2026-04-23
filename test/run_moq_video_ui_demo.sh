#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$REPO_ROOT/logs/moq_video_ui_demo.pid"
LOG_FILE="$REPO_ROOT/logs/moq_video_ui_demo.log"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

is_running() {
    if [[ ! -f "$PID_FILE" ]]; then
        return 1
    fi

    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

start_demo() {
    if is_running; then
        echo -e "${YELLOW}[Warn]${NC} moq_video_ui_demo.py is already running (PID: $(cat "$PID_FILE"))"
        exit 0
    fi

    mkdir -p "$REPO_ROOT/logs"

    echo -e "${BLUE}Starting MOQ video UI demo...${NC}"
    cd "$REPO_ROOT"
    nohup python3 test/moq_video_ui_demo.py >"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
    sleep 1

    if is_running; then
        echo -e "${GREEN}[OK]${NC} Started moq_video_ui_demo.py (PID: $(cat "$PID_FILE"))"
        echo "Log: $LOG_FILE"
    else
        echo -e "${RED}[Error]${NC} Failed to start moq_video_ui_demo.py"
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop_demo() {
    if ! is_running; then
        echo -e "${YELLOW}[Warn]${NC} moq_video_ui_demo.py is not running"
        rm -f "$PID_FILE"
        exit 0
    fi

    local pid
    pid="$(cat "$PID_FILE")"
    echo -e "${BLUE}Stopping MOQ video UI demo (PID: $pid)...${NC}"
    kill "$pid" 2>/dev/null || true

    for _ in {1..10}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$PID_FILE"
            echo -e "${GREEN}[OK]${NC} Stopped moq_video_ui_demo.py"
            exit 0
        fi
        sleep 1
    done

    echo -e "${YELLOW}[Warn]${NC} Process did not exit after SIGTERM, sending SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo -e "${GREEN}[OK]${NC} Stopped moq_video_ui_demo.py"
}

status_demo() {
    if is_running; then
        echo -e "${GREEN}[OK]${NC} moq_video_ui_demo.py is running (PID: $(cat "$PID_FILE"))"
        echo "Log: $LOG_FILE"
    else
        echo -e "${YELLOW}[Info]${NC} moq_video_ui_demo.py is not running"
        rm -f "$PID_FILE"
    fi
}

case "${1:-start}" in
    start)
        start_demo
        ;;
    stop)
        stop_demo
        ;;
    restart)
        stop_demo || true
        start_demo
        ;;
    status)
        status_demo
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
