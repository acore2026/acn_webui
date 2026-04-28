#!/usr/bin/env python3
"""
前端显示效果测试脚本
发送各种类型的消息到后端，测试前端显示效果

使用方法:
    python3 test_messages.py [options]
    
选项:
    --pipeline    只发送 pipeline-logs 消息 (Message Flow)
    --element     只发送 element-logs 消息 (Agent Status)
    --all         发送所有类型的消息 (默认)
    --count N     发送 N 轮消息 (默认: 1)
    --delay S     每轮间隔 S 秒 (默认: 2)
    
示例:
    python3 test_messages.py                    # 发送所有消息类型一轮
    python3 test_messages.py --element --count 3  # 发送 element 消息3轮
    python3 test_messages.py --all --count 5 --delay 3  # 发送5轮，每轮间隔3秒
"""

import requests
import json
import time
import sys
import argparse
import socket
from datetime import datetime

# Backend API endpoints
DEFAULT_BACKEND_HOST = "127.0.0.1"
DEFAULT_BACKEND_PORT = 9005

# Test agent IDs
TEST_AGENTS = [
    "did:acn:agent:001",
    "did:acn:agent:002",
    "did:acn:agent:987654321"
]


def send_pipeline_log(backend_url, source, destination, protocol, abstract, content, task_id=None):
    """Send pipeline log message (for Message Flow)"""
    pipeline_logs_url = f"{backend_url}/acn/v3/pipeline-logs"
    payload = {
        "method": "POST",
        "url": "/acn/v3/pipeline-logs",
        "headers": {"Content-Type": "application/json"},
        "body": {
            "source": source,
            "destination": destination,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "task_id": task_id,
            "protocol": protocol,
            "headers": "",
            "abstract": abstract,
            "content": content
        }
    }
    
    try:
        resp = requests.post(pipeline_logs_url, json=payload, timeout=5)
        if resp.status_code == 200:
            print(f"  [Pipeline] {source} -> {destination}: {abstract[:40]}... ✓")
            return True
        else:
            print(f"  [Pipeline] Error: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  [Pipeline] Error: {e}")
        return False


def send_element_log(backend_url, element_id, log_type, agent_id, agent_name=None, **kwargs):
    """Send element log message (for Agent Status)"""
    element_logs_url = f"{backend_url}/acn/v3/element-logs"
    content = {"agent_id": agent_id}
    if agent_name:
        content["agent_name"] = agent_name
    
    # Add additional content based on log_type
    if log_type == "ApplyProfile":
        content.update({
            "owner": kwargs.get("owner", "user-001"),
            "network_capability": kwargs.get("capability", "6G业务开通")
        })
    elif log_type == "PublishAgent":
        content.update({
            "agent_name": agent_name or "Test Agent",
            "agent_capability": kwargs.get("capability", "通用能力"),
            "consent": {
                "need_consumer_ue_authorization": False,
                "need_producer_authorization": True,
                "support_producer_ue_authorization": False
            }
        })
    elif log_type == "SetupConnection":
        pass  # Only agent_id needed
    elif log_type == "LLMMessage":
        content.update({
            "thinking": kwargs.get("thinking", ""),
            "message": kwargs.get("message", "Processing request...")
        })
    
    payload = {
        "method": "POST",
        "url": "/acn/v3/element-logs",
        "headers": {"Content-Type": "application/json"},
        "body": {
            "element_id": element_id,
            "log_type": log_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "content": content
        }
    }
    
    try:
        resp = requests.post(element_logs_url, json=payload, timeout=5)
        if resp.status_code == 200:
            print(f"  [Element] {element_id} | {log_type} | {agent_id[:25]}... ✓")
            return True
        else:
            print(f"  [Element] Error: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  [Element] Error: {e}")
        return False


def test_pipeline_messages(backend_url):
    """Test pipeline logs (Message Flow)"""
    print("\n=== Testing Pipeline Logs (Message Flow) ===")
    
    messages = [
        ("Agent GW", "IDM", "GTP-U+", "Agent registration request", "Requesting digital identity for new agent", "task-001"),
        ("IDM", "Agent GW", "HTTP/2", "Identity verification completed", "VC issued successfully", "task-001"),
        ("Agent GW", "ARF", "HTTP/2", "Agent discovery request", "Requesting available agents for patrol task", "task-002"),
        ("ARF", "Agent GW", "HTTP/2", "Discovery results", "Found 3 matching agents", "task-002"),
        ("Drone Alpha", "ACF", "WebSocket", "Task channel setup", "Task telemetry channel established", None),
        ("ACF", "Drone Alpha", "WebSocket", "Task channel confirmed", "Telemetry channel active", None),
        ("Drone Beta", "ACF", "WebSocket", "Status update", "Target T-001 detected at coordinates [34.0522, -118.2437]", "task-003"),
        ("ACF", "Ground Unit 1", "GTP-U+", "Dispatch command", "Proceed to location for backup", "task-004"),
        ("Marine Unit A", "ACF", "WebSocket", "Sonar data", "Underwater scan completed, no anomalies", None),
        ("System", "ALL", "Internal", "Network check", "Latency check: 12ms, Packet loss: 0%", None),
    ]
    
    for src, dst, proto, abstract, content, task_id in messages:
        send_pipeline_log(backend_url, src, dst, proto, abstract, content, task_id)
        time.sleep(0.3)


def test_topology_demo(backend_url, step_delay=0.12):
    """Send a focused topology-map demo with canonical node names."""
    print("\n=== Testing Topology Map Demo ===")

    messages = [
        ("ACN SDK", "ACN Agent", "HTTP/2", "Register agent identity", "ACN SDK starts identity registration", "topology-001"),
        ("ACN Agent", "IDM", "HTTP/2", "/idm/v1/identity-applications已转发到IDM", "ACN Agent forwards the identity application to IDM", "topology-001"),
        ("IDM", "ACN SDK", "HTTP/2", "/idm/v1/identity-applications响应返回ACN SDK", "IDM returns the identity application response to ACN SDK", "topology-001"),
        ("ACN Agent", "AgentGW", "HTTP/2", "/arf/v1/agent-cards已转发到AgentGW", "ACN Agent forwards the agent card to AgentGW", "topology-002"),
        ("AgentGW", "ACN SDK", "HTTP/2", "/arf/v1/agent-cards响应返回ACN SDK", "AgentGW returns the agent-card response to ACN SDK", "topology-002"),
    ]

    for src, dst, proto, abstract, content, task_id in messages:
        send_pipeline_log(backend_url, src, dst, proto, abstract, content, task_id)
        time.sleep(step_delay)


def test_element_messages(backend_url):
    """Test element logs (Agent Work Status)"""
    print("\n=== Testing Element Logs (Agent Work Status) ===")
    
    # ApplyProfile - 申请数字身份
    print("\n  > ApplyProfile (申请数字身份):")
    send_element_log(backend_url, "IDM", "ApplyProfile", "did:acn:agent:987654321", "Alice的个人助手", 
                    owner="user-001", capability="6G业务开通")
    time.sleep(0.5)
    
    # PublishAgent - 能力注册
    print("\n  > PublishAgent (能力注册):")
    send_element_log(backend_url, "AgentGW", "PublishAgent", "did:acn:agent:987654321", "Alice的个人助手",
                    capability="跌倒监测-手环")
    time.sleep(0.5)
    
    # SetupConnection - 入网
    print("\n  > SetupConnection (入网):")
    send_element_log(backend_url, "AgentGW", "SetupConnection", "did:acn:agent:987654321")
    time.sleep(0.5)
    
    # LLMMessage - 路由/处理
    print("\n  > LLMMessage (LLM处理):")
    send_element_log(backend_url, "ACN Agent", "LLMMessage", "did:acn:agent:987654321",
                    message="Analyzing user request for health monitoring...")
    time.sleep(0.5)
    
    # 测试多个不同agent
    print("\n  > Multiple agents:")
    agents_data = [
        ("did:acn:agent:001", "Drone Alpha", "ApplyProfile"),
        ("did:acn:agent:002", "Drone Beta", "PublishAgent"),
        ("did:acn:agent:003", "Ground Unit 1", "SetupConnection"),
    ]
    for agent_id, name, log_type in agents_data:
        send_element_log(backend_url, "AgentGW", log_type, agent_id, name)
        time.sleep(0.3)


def test_mixed_scenario(backend_url):
    """Test a realistic mixed scenario"""
    print("\n=== Testing Mixed Scenario (Realistic Flow) ===")
    
    agent_id = "did:acn:agent:test001"
    agent_name = "Test Drone"
    
    # 1. Agent 申请数字身份
    print("\n  Step 1: Agent applying for identity...")
    send_element_log(backend_url, "IDM", "ApplyProfile", agent_id, agent_name, 
                    owner="test-user", capability="surveillance")
    send_pipeline_log(backend_url, "Agent GW", "IDM", "HTTP/2", "Apply for digital identity", 
                     f"Agent {agent_name} requesting identity", "task-init")
    time.sleep(1)
    
    # 2. IDM 返回验证结果
    print("\n  Step 2: IDM verification...")
    send_pipeline_log(backend_url, "IDM", "Agent GW", "HTTP/2", "Identity verification completed", 
                     "VC issued with surveillance capability", "task-init")
    time.sleep(1)
    
    # 3. Agent 注册能力
    print("\n  Step 3: Agent registering capabilities...")
    send_element_log(backend_url, "AgentGW", "PublishAgent", agent_id, agent_name,
                    capability="面部识别-追踪-驱逐")
    send_pipeline_log(backend_url, agent_name, "ARF", "HTTP/2", "Register capabilities", 
                     "Publishing agent capabilities to repository", "task-reg")
    time.sleep(1)
    
    # 4. 建立连接
    print("\n  Step 4: Setting up connection...")
    send_element_log(backend_url, "AgentGW", "SetupConnection", agent_id, agent_name)
    send_pipeline_log(backend_url, "ACF", agent_name, "WebSocket", "Connection established", 
                     "WebSocket connection active", None)
    time.sleep(1)
    
    # 5. 开始任务
    print("\n  Step 5: Agent starting task...")
    send_element_log(backend_url, "ACN Agent", "LLMMessage", agent_id, agent_name,
                    message="Task received: Patrol sector A")
    send_pipeline_log(backend_url, agent_name, "ACF", "WebSocket", "Task telemetry update", 
                     "Starting sector-a telemetry stream", "task-001")
    time.sleep(1)
    
    # 6. 任务执行中
    print("\n  Step 6: Task in progress...")
    send_pipeline_log(backend_url, agent_name, "System", "Internal", "Status update", 
                     "Patrol progress: 45% complete", "task-001")
    send_pipeline_log(backend_url, agent_name, "System", "Internal", "Detection alert", 
                     "Suspicious activity detected at checkpoint 3", "task-001")
    time.sleep(1)
    
    print("\n  Scenario completed!")


def test_full_system_demo(backend_url, step_delay=0.22):
    """Run the backend's full local demo so all dashboard surfaces update together."""
    print("\n=== Testing Local Full Demo ===")
    try:
        resp = requests.post(
            f"{backend_url}/api/control/test-messages/full-demo",
            json={"rounds": 1, "step_delay_seconds": step_delay},
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        print(f"  [Full Demo] Error: {e}")
        return False

    dashboard = payload.get("dashboard", {})
    metrics = dashboard.get("metrics", [])
    tasks = payload.get("tasks", [])
    print(f"  [Full Demo] {payload.get('message', 'Demo injected')} ✓")
    if metrics:
        active_agents = next((item.get("value") for item in metrics if item.get("id") == "agents"), "n/a")
        running_tasks = next((item.get("value") for item in metrics if item.get("id") == "tasks"), "n/a")
        print(f"  [Full Demo] Active Agents: {active_agents}")
        print(f"  [Full Demo] Running Tasks: {running_tasks}")
    print(f"  [Full Demo] Task cards returned: {len(tasks)}")
    return True


def check_backend(backend_url):
    """Check if backend is running"""
    host = backend_url.split("://", 1)[-1].split(":", 1)[0]
    port = int(backend_url.rsplit(":", 1)[-1])

    for path in ("/api/health", "/api/dashboard/overview"):
        try:
            resp = requests.get(f"{backend_url}{path}", timeout=3)
            if resp.status_code == 200:
                print(f"✓ Backend is running at {backend_url}")
                if path == "/api/health":
                    data = resp.json()
                    print(f"  Status: {data.get('status')}")
                    print(f"  WebSocket clients: {data.get('websocket_clients')}")
                else:
                    print("  Dashboard snapshot endpoint responded successfully")
                return True
        except Exception:
            pass

    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"✓ Backend port is reachable at {backend_url}")
            print("  HTTP health endpoint did not respond in this environment, but the port is open")
            return True
    except OSError:
        pass
    
    print(f"✗ Backend is NOT running at {backend_url}")
    print("  Please start the backend first:")
    print("    cd /root/lpx/webui && ./start.sh")
    return False


def main():
    parser = argparse.ArgumentParser(description="Test frontend display with sample messages")
    parser.add_argument("--pipeline", action="store_true", help="Only send pipeline logs")
    parser.add_argument("--element", action="store_true", help="Only send element logs")
    parser.add_argument("--topology-demo", action="store_true", help="Send a focused topology-map message sequence")
    parser.add_argument("--full-demo", action="store_true", help="Send a local registration and interaction demo")
    parser.add_argument("--all", action="store_true", help="Send all message types (default)")
    parser.add_argument("--count", type=int, default=1, help="Number of rounds to send (default: 1)")
    parser.add_argument("--delay", type=int, default=2, help="Delay between rounds in seconds (default: 2)")
    parser.add_argument("--step-delay", type=float, default=0.12, help="Delay between topology-demo messages in seconds (default: 0.12)")
    parser.add_argument("--host", default=DEFAULT_BACKEND_HOST, help=f"Backend host (default: {DEFAULT_BACKEND_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_BACKEND_PORT, help=f"Backend port (default: {DEFAULT_BACKEND_PORT})")
    
    args = parser.parse_args()
    
    # If no specific type selected, default to all
    if not (args.pipeline or args.element or args.topology_demo or args.full_demo):
        args.all = True
    
    print("=" * 60)
    print("  Frontend Display Test Script")
    print("=" * 60)

    backend_url = f"http://{args.host}:{args.port}"
    print(f"  Target backend: {backend_url}")
    
    # Check backend
    if not check_backend(backend_url):
        sys.exit(1)
    
    # Run tests
    for round_num in range(1, args.count + 1):
        if args.count > 1:
            print(f"\n{'='*60}")
            print(f"  Round {round_num}/{args.count}")
            print(f"{'='*60}")
        
        if args.all or args.pipeline:
            test_pipeline_messages(backend_url)

        if args.topology_demo:
            test_topology_demo(backend_url, step_delay=args.step_delay)

        if args.full_demo:
            test_full_system_demo(backend_url, step_delay=args.step_delay)

        if args.all or args.element:
            test_element_messages(backend_url)
        
        if args.all:
            test_mixed_scenario(backend_url)
        
        # Delay between rounds (except last)
        if round_num < args.count:
            print(f"\n  Waiting {args.delay} seconds before next round...")
            time.sleep(args.delay)
    
    print("\n" + "=" * 60)
    print("  Test completed!")
    print("=" * 60)
    print("\nCheck the frontend to see:")
    print("  1. Active Agents - demo agents appear in Overview and Agents")
    print("  2. Running Tasks - task cards appear in Overview and Control")
    print("  3. Message Flow - pipeline messages drive the Topology Map")
    print("  4. System Events - backend log feed shows the local demo steps")


if __name__ == "__main__":
    main()
