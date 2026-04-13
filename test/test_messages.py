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
from datetime import datetime

# Backend API endpoints
BACKEND_URL = "http://localhost:9050"
PIPELINE_LOGS_URL = f"{BACKEND_URL}/acn/v3/pipeline-logs"
ELEMENT_LOGS_URL = f"{BACKEND_URL}/acn/v3/element-logs"

# Test agent IDs
TEST_AGENTS = [
    "did:acn:agent:001",
    "did:acn:agent:002",
    "did:acn:agent:987654321"
]


def send_pipeline_log(source, destination, protocol, abstract, content, task_id=None):
    """Send pipeline log message (for Message Flow)"""
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
        resp = requests.post(PIPELINE_LOGS_URL, json=payload, timeout=5)
        if resp.status_code == 200:
            print(f"  [Pipeline] {source} -> {destination}: {abstract[:40]}... ✓")
            return True
        else:
            print(f"  [Pipeline] Error: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  [Pipeline] Error: {e}")
        return False


def send_element_log(element_id, log_type, agent_id, agent_name=None, **kwargs):
    """Send element log message (for Agent Status)"""
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
        resp = requests.post(ELEMENT_LOGS_URL, json=payload, timeout=5)
        if resp.status_code == 200:
            print(f"  [Element] {element_id} | {log_type} | {agent_id[:25]}... ✓")
            return True
        else:
            print(f"  [Element] Error: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  [Element] Error: {e}")
        return False


def test_pipeline_messages():
    """Test pipeline logs (Message Flow)"""
    print("\n=== Testing Pipeline Logs (Message Flow) ===")
    
    messages = [
        ("Agent GW", "IDM", "GTP-U+", "Agent registration request", "Requesting digital identity for new agent", "task-001"),
        ("IDM", "Agent GW", "HTTP/2", "Identity verification completed", "VC issued successfully", "task-001"),
        ("Agent GW", "ARF", "HTTP/2", "Agent discovery request", "Requesting available agents for patrol task", "task-002"),
        ("ARF", "Agent GW", "HTTP/2", "Discovery results", "Found 3 matching agents", "task-002"),
        ("Drone Alpha", "MOQT Relay", "MOQT", "Subscribe to track", "Subscribing to surveillance-feed-01", None),
        ("MOQT Relay", "Drone Alpha", "MOQT", "Subscription confirmed", "Track surveillance-feed-01 active", None),
        ("Drone Beta", "ACF", "WebSocket", "Status update", "Target T-001 detected at coordinates [34.0522, -118.2437]", "task-003"),
        ("ACF", "Ground Unit 1", "GTP-U+", "Dispatch command", "Proceed to location for backup", "task-004"),
        ("Marine Unit A", "ACF", "WebSocket", "Sonar data", "Underwater scan completed, no anomalies", None),
        ("System", "ALL", "Internal", "Network check", "Latency check: 12ms, Packet loss: 0%", None),
    ]
    
    for src, dst, proto, abstract, content, task_id in messages:
        send_pipeline_log(src, dst, proto, abstract, content, task_id)
        time.sleep(0.3)


def test_element_messages():
    """Test element logs (Agent Work Status)"""
    print("\n=== Testing Element Logs (Agent Work Status) ===")
    
    # ApplyProfile - 申请数字身份
    print("\n  > ApplyProfile (申请数字身份):")
    send_element_log("IDM", "ApplyProfile", "did:acn:agent:987654321", "Alice的个人助手", 
                    owner="user-001", capability="6G业务开通")
    time.sleep(0.5)
    
    # PublishAgent - 能力注册
    print("\n  > PublishAgent (能力注册):")
    send_element_log("AgentGW", "PublishAgent", "did:acn:agent:987654321", "Alice的个人助手",
                    capability="跌倒监测-手环")
    time.sleep(0.5)
    
    # SetupConnection - 入网
    print("\n  > SetupConnection (入网):")
    send_element_log("AgentGW", "SetupConnection", "did:acn:agent:987654321")
    time.sleep(0.5)
    
    # LLMMessage - 路由/处理
    print("\n  > LLMMessage (LLM处理):")
    send_element_log("ACN Agent", "LLMMessage", "did:acn:agent:987654321",
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
        send_element_log("AgentGW", log_type, agent_id, name)
        time.sleep(0.3)


def test_mixed_scenario():
    """Test a realistic mixed scenario"""
    print("\n=== Testing Mixed Scenario (Realistic Flow) ===")
    
    agent_id = "did:acn:agent:test001"
    agent_name = "Test Drone"
    
    # 1. Agent 申请数字身份
    print("\n  Step 1: Agent applying for identity...")
    send_element_log("IDM", "ApplyProfile", agent_id, agent_name, 
                    owner="test-user", capability="surveillance")
    send_pipeline_log("Agent GW", "IDM", "HTTP/2", "Apply for digital identity", 
                     f"Agent {agent_name} requesting identity", "task-init")
    time.sleep(1)
    
    # 2. IDM 返回验证结果
    print("\n  Step 2: IDM verification...")
    send_pipeline_log("IDM", "Agent GW", "HTTP/2", "Identity verification completed", 
                     "VC issued with surveillance capability", "task-init")
    time.sleep(1)
    
    # 3. Agent 注册能力
    print("\n  Step 3: Agent registering capabilities...")
    send_element_log("AgentGW", "PublishAgent", agent_id, agent_name,
                    capability="面部识别-追踪-驱逐")
    send_pipeline_log(agent_name, "ARF", "HTTP/2", "Register capabilities", 
                     "Publishing agent capabilities to repository", "task-reg")
    time.sleep(1)
    
    # 4. 建立连接
    print("\n  Step 4: Setting up connection...")
    send_element_log("AgentGW", "SetupConnection", agent_id, agent_name)
    send_pipeline_log("ACF", agent_name, "WebSocket", "Connection established", 
                     "WebSocket connection active", None)
    time.sleep(1)
    
    # 5. 开始任务
    print("\n  Step 5: Agent starting task...")
    send_element_log("ACN Agent", "LLMMessage", agent_id, agent_name,
                    message="Task received: Patrol sector A")
    send_pipeline_log(agent_name, "MOQT Relay", "MOQT", "Subscribe to video feed", 
                     "Subscribing to sector-a-feed", "task-001")
    time.sleep(1)
    
    # 6. 任务执行中
    print("\n  Step 6: Task in progress...")
    send_pipeline_log(agent_name, "System", "Internal", "Status update", 
                     "Patrol progress: 45% complete", "task-001")
    send_pipeline_log(agent_name, "System", "Internal", "Detection alert", 
                     "Suspicious activity detected at checkpoint 3", "task-001")
    time.sleep(1)
    
    print("\n  Scenario completed!")


def check_backend():
    """Check if backend is running"""
    try:
        resp = requests.get(f"{BACKEND_URL}/api/health", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✓ Backend is running at {BACKEND_URL}")
            print(f"  Status: {data.get('status')}")
            print(f"  WebSocket clients: {data.get('websocket_clients')}")
            return True
    except:
        pass
    
    print(f"✗ Backend is NOT running at {BACKEND_URL}")
    print("  Please start the backend first:")
    print("    cd /root/lpx/webui && ./start.sh")
    return False


def main():
    parser = argparse.ArgumentParser(description="Test frontend display with sample messages")
    parser.add_argument("--pipeline", action="store_true", help="Only send pipeline logs")
    parser.add_argument("--element", action="store_true", help="Only send element logs")
    parser.add_argument("--all", action="store_true", help="Send all message types (default)")
    parser.add_argument("--count", type=int, default=1, help="Number of rounds to send (default: 1)")
    parser.add_argument("--delay", type=int, default=2, help="Delay between rounds in seconds (default: 2)")
    
    args = parser.parse_args()
    
    # If no specific type selected, default to all
    if not (args.pipeline or args.element):
        args.all = True
    
    print("=" * 60)
    print("  Frontend Display Test Script")
    print("=" * 60)
    
    # Check backend
    if not check_backend():
        sys.exit(1)
    
    # Run tests
    for round_num in range(1, args.count + 1):
        if args.count > 1:
            print(f"\n{'='*60}")
            print(f"  Round {round_num}/{args.count}")
            print(f"{'='*60}")
        
        if args.all or args.pipeline:
            test_pipeline_messages()
        
        if args.all or args.element:
            test_element_messages()
        
        if args.all:
            test_mixed_scenario()
        
        # Delay between rounds (except last)
        if round_num < args.count:
            print(f"\n  Waiting {args.delay} seconds before next round...")
            time.sleep(args.delay)
    
    print("\n" + "=" * 60)
    print("  Test completed!")
    print("=" * 60)
    print("\nCheck the frontend to see:")
    print("  1. Message Flow - pipeline messages")
    print("  2. Agent Work Status - element log updates")
    print("  3. Registered Agents - sidebar updates")


if __name__ == "__main__":
    main()
