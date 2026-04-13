#!/bin/bash
#
# 快速测试脚本 - 发送测试消息到 WebUI
# 用法: ./test_webui.sh [pipeline|element|moq|all]
#

BACKEND_URL="http://localhost:9005"

echo "========================================"
echo "  WebUI 快速测试"
echo "========================================"
echo ""

# 测试 pipeline-logs
test_pipeline() {
    echo "[测试] 发送 Pipeline Log..."
    curl -s -X POST "$BACKEND_URL/acn/v3/pipeline-logs" \
        -H "Content-Type: application/json" \
        -d '{
            "method": "POST",
            "url": "/acn/v3/pipeline-logs",
            "headers": {"Content-Type": "application/json"},
            "body": {
                "source": "Agent GW",
                "destination": "IDM",
                "timestamp": "2025-07-29T18:35:40Z",
                "protocol": "HTTP/2",
                "abstract": "Agent registration request",
                "content": "Requesting digital identity"
            }
        }' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  结果: {d[\"status\"]}')"
}

# 测试 element-logs
test_element() {
    echo "[测试] 发送 Element Log (ApplyProfile)..."
    curl -s -X POST "$BACKEND_URL/acn/v3/element-logs" \
        -H "Content-Type: application/json" \
        -d '{
            "method": "POST",
            "url": "/acn/v3/element-logs",
            "headers": {"Content-Type": "application/json"},
            "body": {
                "element_id": "IDM",
                "log_type": "ApplyProfile",
                "timestamp": "2025-07-29T18:35:40Z",
                "content": {
                    "agent_id": "did:acn:agent:test001",
                    "agent_name": "Test Drone",
                    "owner": "user-001"
                }
            }
        }' | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  结果: {d[\"status\"]}')"
}

# 测试 MOQ 订阅
test_moq() {
    echo "[测试] MOQ 自动订阅..."
    curl -s -X POST "$BACKEND_URL/api/moq/auto-subscribe/test_agent" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  结果: {d[\"status\"]}, tracks: {len(d.get(\"results\", []))}')"
    
    echo "[测试] MOQ 状态..."
    curl -s "$BACKEND_URL/api/moq/status" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  MOQ: {d[\"status\"]}, 已连接: {d[\"connected\"]}, tracks: {d[\"subscribed_tracks\"]}')"
}

# 测试 API 健康
test_health() {
    echo "[测试] API 健康检查..."
    curl -s "$BACKEND_URL/api/health" \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  状态: {d[\"status\"]}, WebSocket客户端: {d[\"websocket_clients\"]}')"
}

# 根据参数执行测试
case "${1:-all}" in
    pipeline)
        test_health
        test_pipeline
        ;;
    element)
        test_health
        test_element
        ;;
    moq)
        test_health
        test_moq
        ;;
    all)
        test_health
        test_pipeline
        test_element
        test_moq
        ;;
    *)
        echo "用法: $0 [pipeline|element|moq|all]"
        exit 1
        ;;
esac

echo ""
echo "========================================"
echo "  测试完成"
echo "========================================"
