#!/bin/bash
#
# ACN Agent Monitor WebUI 一键启动脚本
# 用法: ./start_all.sh [start|stop|restart|status]
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
BACKEND_PORT=9005
LOG_DIR="/root/lpx/webui/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_BUILD_LOG="$LOG_DIR/frontend_build.log"
PID_FILE="$LOG_DIR/webui.pid"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 启动后端
start_backend() {
    echo -e "${BLUE}[1/3] 启动后端服务...${NC}"
    
    # 检查是否已运行
    if pgrep -f "uvicorn.*app.main:app.*$BACKEND_PORT" > /dev/null; then
        echo -e "${YELLOW}  后端服务已在运行${NC}"
        return 0
    fi
    
    cd /root/lpx/webui/backend
    source /root/lpx/acn_gw/venv/bin/activate
    
    # 启动后端（使用 setsid 确保脱离终端）
    setsid python3 -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port $BACKEND_PORT \
        --log-level info \
        > "$BACKEND_LOG" 2>&1 &
    
    BACKEND_PID=$!
    
    # 等待服务启动
    for i in {1..10}; do
        sleep 1
        if curl -s http://localhost:$BACKEND_PORT/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}  ✓ 后端服务已启动 (PID: $BACKEND_PID)${NC}"
            echo -e "${GREEN}  ✓ API: http://localhost:$BACKEND_PORT${NC}"
            echo -e "${GREEN}  ✓ WebSocket: ws://localhost:$BACKEND_PORT/ws${NC}"
            echo $BACKEND_PID >> "$PID_FILE"
            return 0
        fi
    done
    
    echo -e "${RED}  ✗ 后端服务启动失败${NC}"
    return 1
}

# 构建前端
build_frontend() {
    echo -e "${BLUE}[2/3] 构建前端...${NC}"
    
    cd /root/lpx/webui/frontend
    
    # 构建前端
    if npm run build > "$FRONTEND_BUILD_LOG" 2>&1; then
        echo -e "${GREEN}  ✓ 前端构建完成${NC}"
        return 0
    else
        echo -e "${RED}  ✗ 前端构建失败${NC}"
        echo -e "${RED}  查看日志: $FRONTEND_BUILD_LOG${NC}"
        return 1
    fi
}

# 检查服务状态
check_status() {
    echo -e "${BLUE}服务状态检查:${NC}"
    
    # 检查后端
    if pgrep -f "uvicorn.*app.main:app.*$BACKEND_PORT" > /dev/null; then
        echo -e "${GREEN}  ✓ 后端服务: 运行中${NC}"
        if curl -s http://localhost:$BACKEND_PORT/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}    - API 正常${NC}"
        else
            echo -e "${RED}    - API 无响应${NC}"
        fi
    else
        echo -e "${RED}  ✗ 后端服务: 未运行${NC}"
    fi
    
    # 检查端口
    if ss -tlnp | grep -q ":$BACKEND_PORT"; then
        echo -e "${GREEN}  ✓ 端口 $BACKEND_PORT: 监听中${NC}"
    else
        echo -e "${RED}  ✗ 端口 $BACKEND_PORT: 未监听${NC}"
    fi
    
    # 显示日志位置
    echo ""
    echo -e "${BLUE}日志文件位置:${NC}"
    echo "  后端日志: $BACKEND_LOG"
    echo "  前端构建日志: $FRONTEND_BUILD_LOG"
}

# 停止服务
stop_services() {
    echo -e "${BLUE}停止服务...${NC}"
    
    # 停止后端
    BACKEND_PIDS=$(pgrep -f "uvicorn.*app.main:app.*$BACKEND_PORT" || true)
    if [ -n "$BACKEND_PIDS" ]; then
        echo "  停止后端服务 (PIDs: $BACKEND_PIDS)"
        kill -9 $BACKEND_PIDS 2>/dev/null || true
        sleep 1
    fi
    
    # 清理 PID 文件
    rm -f "$PID_FILE"
    
    echo -e "${GREEN}  ✓ 所有服务已停止${NC}"
}

# 实时查看日志
tail_logs() {
    echo -e "${BLUE}查看日志 (按 Ctrl+C 退出)...${NC}"
    echo ""
    
    if [ -f "$BACKEND_LOG" ]; then
        echo -e "${GREEN}=== 后端日志 ===${NC}"
        tail -50 "$BACKEND_LOG"
    else
        echo -e "${RED}后端日志不存在${NC}"
    fi
}

# 主函数
case "${1:-start}" in
    start)
        echo "========================================"
        echo "  ACN Agent Monitor WebUI 启动"
        echo "========================================"
        echo ""
        
        stop_services 2>/dev/null || true
        sleep 1
        
        if build_frontend && start_backend; then
            echo ""
            echo "========================================"
            echo -e "${GREEN}  所有服务启动成功!${NC}"
            echo "========================================"
            echo ""
            echo "访问地址:"
            echo "  http://<服务器IP>:$BACKEND_PORT"
            echo ""
            echo "查看日志:"
            echo "  tail -f $BACKEND_LOG"
            echo ""
            echo "常用命令:"
            echo "  ./start_all.sh stop     # 停止服务"
            echo "  ./start_all.sh status   # 查看状态"
            echo "  ./start_all.sh logs     # 查看日志"
            echo "========================================"
        else
            echo ""
            echo "========================================"
            echo -e "${RED}  服务启动失败!${NC}"
            echo "========================================"
            exit 1
        fi
        ;;
    
    stop)
        stop_services
        ;;
    
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    
    status)
        check_status
        ;;
    
    logs)
        tail_logs
        ;;
    
    *)
        echo "用法: $0 [start|stop|restart|status|logs]"
        echo ""
        echo "命令:"
        echo "  start    - 启动所有服务 (默认)"
        echo "  stop     - 停止所有服务"
        echo "  restart  - 重启所有服务"
        echo "  status   - 查看服务状态"
        echo "  logs     - 查看日志"
        exit 1
        ;;
esac
