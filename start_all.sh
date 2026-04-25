#!/usr/bin/env bash
#
# ACN Agent Monitor WebUI 一键启动脚本
# 用法: ./start_all.sh [start|stop|restart|status]
#

if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PORT="${BACKEND_PORT:-9005}"
WEBUI_SCHEME="${WEBUI_SCHEME:-https}"
export WEBUI_SCHEME
LOG_DIR="$ROOT_DIR/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_BUILD_LOG="$LOG_DIR/frontend_build.log"
PID_FILE="$LOG_DIR/webui.pid"
HTTPS_CERT_FILE="${WEBUI_HTTPS_CERT_FILE:-$LOG_DIR/webui_https_cert.pem}"
HTTPS_KEY_FILE="${WEBUI_HTTPS_KEY_FILE:-$LOG_DIR/webui_https_key.pem}"

# 创建日志目录
mkdir -p "$LOG_DIR"

echo_color() {
    printf "%b\n" "$1"
}

find_backend_python() {
    local candidate

    if [ -n "${VENV_DIR:-}" ]; then
        candidate="$VENV_DIR"
        if [ -x "$candidate/bin/python3" ]; then
            printf "%s\n" "$candidate/bin/python3"
            return 0
        fi
        if [ -x "$candidate/bin/python" ]; then
            printf "%s\n" "$candidate/bin/python"
            return 0
        fi
        echo_color "${RED}  ✗ VENV_DIR 不可用: $VENV_DIR${NC}" >&2
        return 1
    fi

    for candidate in "$ROOT_DIR/.venv" "$ROOT_DIR/venv" "/root/lpx/acn_gw/venv"; do
        if [ -x "$candidate/bin/python3" ]; then
            printf "%s\n" "$candidate/bin/python3"
            return 0
        fi
        if [ -x "$candidate/bin/python" ]; then
            printf "%s\n" "$candidate/bin/python"
            return 0
        fi
    done

    echo_color "${YELLOW}  未找到可用虚拟环境，创建 $ROOT_DIR/.venv ...${NC}" >&2
    python3 -m venv "$ROOT_DIR/.venv"
    printf "%s\n" "$ROOT_DIR/.venv/bin/python3"
}

ensure_backend_deps() {
    local python_bin="$1"

    if "$python_bin" - <<'PY' >/dev/null 2>&1
import fastapi
import httpx
import pydantic
import uvicorn
import websockets
import multipart
PY
    then
        return 0
    fi

    echo_color "${YELLOW}  Python 依赖缺失，安装 backend/requirements.txt ...${NC}"
    "$python_bin" -m pip install -r "$BACKEND_DIR/requirements.txt"
}

ensure_https_cert() {
    local python_bin="$1"

    if [ "$WEBUI_SCHEME" != "https" ]; then
        return 0
    fi

    if [ -s "$HTTPS_CERT_FILE" ] && [ -s "$HTTPS_KEY_FILE" ]; then
        return 0
    fi

    echo_color "${YELLOW}  生成 HTTPS 自签名证书...${NC}"
    "$python_bin" - "$HTTPS_CERT_FILE" "$HTTPS_KEY_FILE" <<'PY'
import ipaddress
import socket
import sys
from datetime import datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

cert_path = Path(sys.argv[1])
key_path = Path(sys.argv[2])
cert_path.parent.mkdir(parents=True, exist_ok=True)

hosts = {"localhost", "127.0.0.1", socket.gethostname(), socket.getfqdn()}
try:
    hosts.update(socket.gethostbyname_ex(socket.gethostname())[2])
except OSError:
    pass

key = ec.generate_private_key(ec.SECP256R1())
subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ACN WebUI")])
san_values = []
for host in sorted(item for item in hosts if item):
    try:
        san_values.append(x509.IPAddress(ipaddress.ip_address(host)))
    except ValueError:
        san_values.append(x509.DNSName(host))

cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
    .not_valid_after(datetime.utcnow() + timedelta(days=30))
    .add_extension(x509.SubjectAlternativeName(san_values), critical=False)
    .sign(key, hashes.SHA256())
)

cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
key_path.write_bytes(
    key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
)
PY
}

is_port_open() {
    python3 - "$BACKEND_PORT" <<'PY' >/dev/null 2>&1
import socket
import sys

with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=1):
    pass
PY
}

# 启动后端
start_backend() {
    echo_color "${BLUE}[2/2] 启动后端服务...${NC}"
    
    # 检查是否已运行
    if pgrep -f "uvicorn.*app.main:app.*$BACKEND_PORT" > /dev/null; then
        echo_color "${YELLOW}  后端服务已在运行${NC}"
        return 0
    fi
    
    cd "$BACKEND_DIR"
    
    # 使用 venv 的 python 直接启动，不依赖 source activate。
    VENV_PYTHON="$(find_backend_python)"
    ensure_backend_deps "$VENV_PYTHON"
    ensure_https_cert "$VENV_PYTHON"

    local uvicorn_args=(
        -m uvicorn app.main:app
        --host 0.0.0.0
        --port "$BACKEND_PORT"
        --log-level info
    )
    if [ "$WEBUI_SCHEME" = "https" ]; then
        uvicorn_args+=(--ssl-certfile "$HTTPS_CERT_FILE" --ssl-keyfile "$HTTPS_KEY_FILE")
    fi
    
    # 启动后端（使用 setsid 确保脱离终端）
    setsid "$VENV_PYTHON" "${uvicorn_args[@]}" > "$BACKEND_LOG" 2>&1 &
    
    BACKEND_PID=$!
    
    # 等待服务启动
    for i in {1..10}; do
        sleep 1
        if curl -kfsS "$WEBUI_SCHEME://localhost:$BACKEND_PORT/api/health" > /dev/null 2>&1; then
            echo_color "${GREEN}  ✓ 后端服务已启动 (PID: $BACKEND_PID)${NC}"
            echo_color "${GREEN}  ✓ API: $WEBUI_SCHEME://localhost:$BACKEND_PORT${NC}"
            if [ "$WEBUI_SCHEME" = "https" ]; then
                echo_color "${GREEN}  ✓ WebSocket: wss://localhost:$BACKEND_PORT/ws${NC}"
            else
                echo_color "${GREEN}  ✓ WebSocket: ws://localhost:$BACKEND_PORT/ws${NC}"
            fi
            echo $BACKEND_PID >> "$PID_FILE"
            return 0
        fi
    done
    
    echo_color "${RED}  ✗ 后端服务启动失败${NC}"
    echo_color "${RED}  查看日志: $BACKEND_LOG${NC}"
    return 1
}

# 构建前端
build_frontend() {
    echo_color "${BLUE}[1/2] 构建前端...${NC}"
    
    cd "$FRONTEND_DIR"

    if [ ! -d node_modules ]; then
        echo_color "${YELLOW}  node_modules 不存在，请先执行: cd $FRONTEND_DIR && npm install${NC}"
        return 1
    fi
    
    # 构建前端
    if npm run build > "$FRONTEND_BUILD_LOG" 2>&1; then
        echo_color "${GREEN}  ✓ 前端构建完成${NC}"
        return 0
    else
        echo_color "${RED}  ✗ 前端构建失败${NC}"
        echo_color "${RED}  查看日志: $FRONTEND_BUILD_LOG${NC}"
        return 1
    fi
}

# 检查服务状态
check_status() {
    echo_color "${BLUE}服务状态检查:${NC}"
    local venv_python
    
    # 检查后端
    if pgrep -f "uvicorn.*app.main:app.*$BACKEND_PORT" > /dev/null; then
        echo_color "${GREEN}  ✓ 后端服务: 运行中${NC}"
        if curl -kfsS "$WEBUI_SCHEME://localhost:$BACKEND_PORT/api/health" > /dev/null 2>&1; then
            echo_color "${GREEN}    - API 正常${NC}"
        else
            echo_color "${RED}    - API 无响应${NC}"
        fi
    else
        echo_color "${RED}  ✗ 后端服务: 未运行${NC}"
    fi
    
    # 检查端口
    if is_port_open; then
        echo_color "${GREEN}  ✓ 端口 $BACKEND_PORT: 监听中${NC}"
    else
        echo_color "${RED}  ✗ 端口 $BACKEND_PORT: 未监听${NC}"
    fi
    
    # 显示日志位置
    echo ""
    echo_color "${BLUE}Python 虚拟环境:${NC}"
    if venv_python="$(find_backend_python 2>/dev/null)"; then
        echo "  Python: $venv_python"
    else
        echo_color "${RED}  ✗ 未找到可用 Python 虚拟环境${NC}"
    fi
    echo ""
    echo_color "${BLUE}日志文件位置:${NC}"
    echo "  后端日志: $BACKEND_LOG"
    echo "  前端构建日志: $FRONTEND_BUILD_LOG"
}

# 停止服务
stop_services() {
    echo_color "${BLUE}停止服务...${NC}"
    
    # 停止后端
    BACKEND_PIDS=$(pgrep -f "uvicorn.*app.main:app.*$BACKEND_PORT" || true)
    if [ -n "$BACKEND_PIDS" ]; then
        echo "  停止后端服务 (PIDs: $BACKEND_PIDS)"
        kill $BACKEND_PIDS 2>/dev/null || true
        sleep 1
        BACKEND_PIDS=$(pgrep -f "uvicorn.*app.main:app.*$BACKEND_PORT" || true)
        if [ -n "$BACKEND_PIDS" ]; then
            kill -9 $BACKEND_PIDS 2>/dev/null || true
        fi
    fi
    
    # 清理 PID 文件
    rm -f "$PID_FILE"
    
    echo_color "${GREEN}  ✓ 所有服务已停止${NC}"
}

# 实时查看日志
tail_logs() {
    echo_color "${BLUE}查看日志 (按 Ctrl+C 退出)...${NC}"
    echo ""
    
    if [ -f "$BACKEND_LOG" ]; then
        echo_color "${GREEN}=== 后端日志 ===${NC}"
        tail -f "$BACKEND_LOG"
    else
        echo_color "${RED}后端日志不存在${NC}"
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
            echo_color "${GREEN}  所有服务启动成功!${NC}"
            echo "========================================"
            echo ""
            echo "访问地址:"
            echo "  $WEBUI_SCHEME://<服务器IP>:$BACKEND_PORT"
            echo "  $WEBUI_SCHEME://localhost:$BACKEND_PORT"
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
            echo_color "${RED}  服务启动失败!${NC}"
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
