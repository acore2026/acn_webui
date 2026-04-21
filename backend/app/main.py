#!/usr/bin/env python3
"""
ACN Agent Monitor Backend
FastAPI + WebSocket server for agent monitoring
Port: 9005
"""

import asyncio
import base64
import json
import socket
import sqlite3
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import uvicorn
from typing import List, Dict, Any, Optional
import httpx

# Import video stream manager
from .video_stream import video_stream_manager, StreamStatus

# Import MOQ video subscriber
try:
    from .moq_video import moq_video_subscriber, VideoFrame

    MOQ_AVAILABLE = True
except ImportError as e:
    print(f"[Warning] MOQ video subscriber not available: {e}")
    MOQ_AVAILABLE = False

# Database path
DB_PATH = "/home/acn/zqm/acn_gw/agent_gw/agent_gw.db"
# DB_PATH = "/root/lpx/webui/test/test_agent_gw.db"

# ARF Service Configuration
ARF_HOST = "localhost"  # ARF service host
ARF_CLEAR_URL = f"http://{ARF_HOST}:9001/clear"
LOCAL_STATUS_HOST = "127.0.0.1"
AGENT_GW_LOG_DIR = Path("/home/acn/zqm/acn_gw/agent_gw/logs")
IDM_LOG_DIR = Path("/home/acn/cx/idm/logs")
ACN_AGENT_LOG_FILE = Path("/home/acn/cxr/acn_agent/.acn_agent.log")

ELEMENT_PORTS = [
    {
        "id": "acn-agent",
        "label": "ACN Agent",
        "port": 9010,
        "protocol": "http",
        "group": "acn-agent",
        "group_label": "ACN Agent",
        "description": "Task execution runtime exposed by the ACN Agent service.",
    },
    {
        "id": "arf",
        "label": "ARF",
        "port": 9001,
        "protocol": "http",
        "group": "agent-gw",
        "group_label": "AgentGW",
        "description": "Agent Repository Function for registration and discovery.",
    },
    {
        "id": "acf",
        "label": "ACF",
        "port": 9002,
        "protocol": "ws",
        "group": "agent-gw",
        "group_label": "AgentGW",
        "description": "Agent Communication Function for WebSocket coordination.",
    },
    {
        "id": "relay",
        "label": "Relay",
        "port": 9003,
        "protocol": "udp",
        "group": "agent-gw",
        "group_label": "AgentGW",
        "description": "MOQ relay over QUIC for track distribution.",
    },
    {
        "id": "idm",
        "label": "IDM",
        "port": 9020,
        "protocol": "http",
        "group": "idm",
        "group_label": "IDM",
        "description": "Identity verification service used for VC checks.",
    },
]

FLOW_NODE_LAYOUTS = {
    "ACN Agent": {"x": 100, "y": 210},
    "IDM": {"x": 510, "y": 60},
    "AgentGW": {"x": 920, "y": 210},
    "ACN SDK": {"x": 510, "y": 360},
}

MESSAGE_FLOW_TTL_SECONDS = 1
MESSAGE_FLOW_ACTIVE_SECONDS = 1

NETWORK_ELEMENT_LOG_SOURCES = [
    {
        "id": "acn-agent",
        "name": "ACN Agent",
        "mode": "file",
        "path": ACN_AGENT_LOG_FILE,
    },
    {
        "id": "agent-gw",
        "name": "AgentGW",
        "mode": "all-logs",
        "path": AGENT_GW_LOG_DIR,
    },
    {
        "id": "idm",
        "name": "IDM",
        "mode": "latest-log",
        "path": IDM_LOG_DIR,
    },
]


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WebSocket] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(
                f"[WebSocket] Client disconnected. Total: {len(self.active_connections)}"
            )

    async def broadcast(self, message: dict):
        disconnected = []
        msg_type = message.get("type", "unknown")
        print(
            f"[Broadcast] Sending {msg_type} to {len(self.active_connections)} clients"
        )

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
                print(f"[Broadcast] Message sent successfully")
            except Exception as e:
                print(f"[Broadcast] Failed to send: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def send_to(self, websocket: WebSocket, message: dict):
        try:
            await websocket.send_json(message)
        except:
            pass


manager = ConnectionManager()

# Set connection manager for video stream manager
video_stream_manager.set_connection_manager(manager)


# Database helper
def get_agents_from_db() -> List[Dict[str, Any]]:
    """Get all agents from database and check for active tasks"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get all agents
        cursor.execute("SELECT * FROM agents")
        rows = cursor.fetchall()

        # Get all agents with active tasks (agents that have entries in tasks table)
        cursor.execute("SELECT DISTINCT agent_id FROM tasks")
        agents_with_tasks = {row[0] for row in cursor.fetchall()}

        conn.close()

        agents = []
        for row in rows:
            agent = dict(row)
            # Parse JSON capabilities
            if agent.get("agent_capability"):
                try:
                    agent["agent_capability"] = json.loads(agent["agent_capability"])
                except:
                    agent["agent_capability"] = []
            else:
                agent["agent_capability"] = []

            # Determine agent status: if agent has task_id (exists in tasks table), mark as working
            original_status = agent.get("agent_status", "offline")
            if agent.get("agent_id") in agents_with_tasks:
                agent["agent_status"] = "working"
            else:
                agent["agent_status"] = (
                    original_status if original_status else "offline"
                )

            agents.append(agent)
        return agents
    except Exception as e:
        print(f"[Database Error] {e}")
        return []


def get_task_count_from_db() -> int:
    """Get total task count from database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks")
        value = int(cursor.fetchone()[0] or 0)
        conn.close()
        return value
    except Exception as e:
        print(f"[Task Count Error] {e}")
        return 0


def get_tasks_from_db() -> List[Dict[str, Any]]:
    """Get active tasks grouped by task_id from database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, agent_id, task_id, task_description
            FROM tasks
            ORDER BY id DESC
            """
        )
        rows = cursor.fetchall()
        conn.close()

        grouped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            entry = dict(row)
            task_id = str(entry.get("task_id") or f"task-{entry.get('id')}")
            task = grouped.setdefault(
                task_id,
                {
                    "id": task_id,
                    "description": entry.get("task_description") or "",
                    "agent_ids": [],
                },
            )
            agent_id = entry.get("agent_id")
            if agent_id and agent_id not in task["agent_ids"]:
                task["agent_ids"].append(agent_id)
            if not task["description"] and entry.get("task_description"):
                task["description"] = entry["task_description"]

        return list(grouped.values())
    except Exception as e:
        print(f"[Task Query Error] {e}")
        return []


def _extract_task_type(description: str) -> Optional[str]:
    if not description:
        return None

    prefix, separator, _ = description.partition(":")
    if separator and len(prefix) <= 40:
        return prefix.strip()

    return None


def _task_agent_name_lookup() -> Dict[str, str]:
    lookup = {
        str(agent.get("agent_id")): str(agent.get("agent_name") or agent.get("agent_id"))
        for agent in get_agents_from_db()
    }

    for agent_id, cached in agent_status_cache.items():
        value = str(cached.get("agent_name") or agent_id)
        if cached.get("is_demo"):
            lookup.setdefault(str(agent_id), value)

    return lookup


def _build_task_involved_agents(
    agent_ids: List[str],
    name_lookup: Dict[str, str],
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    agent_names = metadata.get("agent_names", {}) if metadata else {}
    involved_agents = []

    for agent_id in agent_ids:
        name = (
            agent_names.get(agent_id)
            or agent_status_cache.get(agent_id, {}).get("agent_name")
            or name_lookup.get(agent_id, agent_id)
        )
        involved_agents.append({"id": agent_id, "name": str(name)})

    return involved_agents


def build_control_tasks_snapshot(limit_finished: int = 20) -> List[Dict[str, Any]]:
    """Return active DB tasks plus recently finished control tasks."""
    name_lookup = _task_agent_name_lookup()
    active_tasks = []
    seen_task_ids = set()

    for task in get_tasks_from_db():
        task_id = str(task["id"])
        metadata = task_control_registry.get(task_id, {})
        description = str(
            task.get("description")
            or metadata.get("task_description")
            or "No description provided."
        )
        task_type = str(
            metadata.get("task_type")
            or _extract_task_type(description)
            or "General"
        )
        created_at = str(
            metadata.get("created_at")
            or metadata.get("updated_at")
            or datetime.utcnow().isoformat()
        )
        updated_at = str(metadata.get("updated_at") or created_at)

        active_tasks.append(
            {
                "id": task_id,
                "taskName": str(
                    metadata.get("task_name") or task_type or f"Task {task_id[-6:]}"
                ),
                "taskType": task_type,
                "description": description,
                "status": "processing",
                "involvedAgents": _build_task_involved_agents(
                    task.get("agent_ids", []), name_lookup, metadata
                ),
                "createdAt": created_at,
                "updatedAt": updated_at,
            }
        )
        seen_task_ids.add(task_id)

    for task_id, metadata in task_control_registry.items():
        if task_id in seen_task_ids or metadata.get("status") != "processing":
            continue

        description = str(
            metadata.get("task_description") or "No description provided."
        )
        task_type = str(
            metadata.get("task_type")
            or _extract_task_type(description)
            or "General"
        )
        created_at = str(
            metadata.get("created_at")
            or metadata.get("updated_at")
            or datetime.utcnow().isoformat()
        )
        updated_at = str(metadata.get("updated_at") or created_at)
        agent_ids = [str(agent_id) for agent_id in metadata.get("agent_ids", []) if agent_id]

        active_tasks.append(
            {
                "id": str(task_id),
                "taskName": str(
                    metadata.get("task_name") or task_type or f"Task {str(task_id)[-6:]}"
                ),
                "taskType": task_type,
                "description": description,
                "status": "processing",
                "involvedAgents": _build_task_involved_agents(
                    agent_ids, name_lookup, metadata
                ),
                "createdAt": created_at,
                "updatedAt": updated_at,
            }
        )

    active_tasks.sort(key=lambda item: item["updatedAt"], reverse=True)
    finished_tasks = list(reversed(control_task_history[-limit_finished:]))
    return active_tasks + finished_tasks


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _format_relative_time(value: Any) -> str:
    parsed = _parse_timestamp(value)
    if not parsed:
        return "Unknown"

    delta_seconds = max(int((datetime.utcnow() - parsed).total_seconds()), 0)
    if delta_seconds < 60:
        return f"{delta_seconds}s ago"
    if delta_seconds < 3600:
        return f"{delta_seconds // 60}m ago"
    if delta_seconds < 86400:
        return f"{delta_seconds // 3600}h ago"
    return f"{delta_seconds // 86400}d ago"


def _normalize_capabilities(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dashboard_status_from_agent(agent: Dict[str, Any]) -> str:
    agent_status = str(agent.get("agent_status", "")).lower()
    work_status = str(agent.get("work_status", "")).lower()

    if agent_status == "offline":
        return "offline"
    if agent_status in {"working", "busy"} or work_status in {
        "working",
        "tracking",
        "expelling",
    }:
        return "busy"
    return "online"


def _dashboard_role_from_agent(agent: Dict[str, Any]) -> str:
    capabilities = _normalize_capabilities(agent.get("agent_capability"))
    if capabilities:
        return str(capabilities[0]).replace("-", " ").replace("_", " ").title()
    if agent.get("current_task"):
        return str(agent["current_task"])
    if agent.get("network_capability"):
        return str(agent["network_capability"])
    return "General Agent"


def _dashboard_region_from_agent(agent: Dict[str, Any]) -> str:
    if agent.get("owner"):
        return str(agent["owner"])
    if agent.get("network_capability"):
        return str(agent["network_capability"])
    return "ACN Mesh"


def _dashboard_throughput_from_agent(agent: Dict[str, Any]) -> str:
    status = _dashboard_status_from_agent(agent)
    if status == "offline":
        return "0.0 Gbps"

    seed = sum(ord(char) for char in str(agent.get("agent_id", "agent")))
    base = 28 if status == "online" else 52
    throughput = (base + (seed % 43)) / 10
    return f"{throughput:.1f} Gbps"


def _dashboard_summary_from_agent(agent: Dict[str, Any]) -> str:
    capabilities = _normalize_capabilities(agent.get("agent_capability"))
    current_task = str(agent.get("current_task", "")).strip()
    role = _dashboard_role_from_agent(agent)
    agent_name = str(agent.get("agent_name") or agent.get("agent_id") or "This agent")

    if current_task and capabilities:
        return (
            f"{agent_name} is currently focused on {current_task.lower()} and supports "
            f"{', '.join(capabilities[:2])}."
        )
    if current_task:
        return f"{agent_name} is currently focused on {current_task.lower()}."
    if capabilities:
        return (
            f"{agent_name} is configured for {role.lower()} workflows and currently exposes "
            f"{len(capabilities)} registered capabilities."
        )
    return f"{agent_name} is connected to the ACN mesh and awaiting the next assigned workflow."


def _dashboard_alerts_from_agent(agent: Dict[str, Any]) -> List[str]:
    status = _dashboard_status_from_agent(agent)
    current_task = str(agent.get("current_task", "")).strip()
    last_update = _format_relative_time(agent.get("last_update"))
    capabilities = _normalize_capabilities(agent.get("agent_capability"))

    if status == "offline":
        return [
            f"Agent appears offline. Last update received {last_update}.",
            "Operator review recommended before assigning new work.",
        ]

    notes = []
    if current_task:
        notes.append(f"Current task: {current_task}")
    if capabilities:
        notes.append(f"{len(capabilities)} capability profiles registered")
    notes.append(f"Last heartbeat observed {last_update}")
    return notes[:3]


def _is_port_open(port: int, protocol: str = "tcp") -> bool:
    if protocol == "udp":
        hex_port = f"{port:04X}"
        for proc_path in ("/proc/net/udp", "/proc/net/udp6"):
            try:
                with open(proc_path, "r", encoding="utf-8") as handle:
                    lines = handle.readlines()[1:]
            except OSError:
                continue

            for line in lines:
                parts = line.split()
                if len(parts) < 2:
                    continue
                local_address = parts[1]
                if ":" not in local_address:
                    continue
                _, local_port = local_address.rsplit(":", 1)
                if local_port.upper() == hex_port:
                    return True
        return False

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.35)

    try:
        return sock.connect_ex((LOCAL_STATUS_HOST, port)) == 0
    except Exception:
        return False
    finally:
        sock.close()


def build_element_status_snapshot() -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}

    for element in ELEMENT_PORTS:
        status = "online" if _is_port_open(element["port"], element["protocol"]) else "offline"
        group = grouped.setdefault(
            element["group"],
            {
                "id": element["group"],
                "name": element["group_label"],
                "status": "online",
                "summary": "",
                "components": [],
            },
        )

        group["components"].append(
            {
                "id": element["id"],
                "name": element["label"],
                "port": element["port"],
                "protocol": element["protocol"],
                "status": status,
                "description": element["description"],
            }
        )

    snapshots: List[Dict[str, Any]] = []
    for group in grouped.values():
        components = group["components"]
        online_count = sum(1 for component in components if component["status"] == "online")
        total_count = len(components)

        if online_count == total_count:
            group_status = "online"
            summary = f"All {total_count} endpoints are reachable."
        elif online_count == 0:
            group_status = "offline"
            summary = "No endpoints are reachable."
        else:
            group_status = "degraded"
            summary = f"{online_count} of {total_count} endpoints are reachable."

        group["status"] = group_status
        group["summary"] = summary
        snapshots.append(group)

    return sorted(snapshots, key=lambda item: item["name"])


def _canonical_flow_node(name: str) -> Optional[str]:
    normalized = (name or "").strip().lower()
    if not normalized:
        return None

    if "acn sdk" in normalized or normalized == "sdk":
        return "ACN SDK"

    if "idm" in normalized:
        return "IDM"

    if (
        "agent gw" in normalized
        or "agentgw" in normalized
        or normalized == "arf"
        or normalized == "acf"
        or "/arf/" in normalized
        or "/acf/" in normalized
    ):
        return "AgentGW"

    if (
        "acn agent" in normalized
        or normalized.startswith("did:acn:agent:")
        or normalized.startswith("did:udid:")
        or "agent card" in normalized
        or "identity application" in normalized
    ):
        return "ACN Agent"

    return None


def build_message_flow_snapshot(
    elements: Optional[List[Dict[str, Any]]] = None, limit: int = 20
) -> Dict[str, Any]:
    element_status_map = {}
    for element in elements or []:
        name = str(element.get("name", "")).strip()
        status = str(element.get("status", "offline")).lower()
        if name:
            element_status_map[name] = "offline" if status == "offline" else "online"

    recent_events = list(reversed(pipeline_log_buffer[-limit:])) if pipeline_log_buffer else []
    edge_map: Dict[tuple, Dict[str, Any]] = {}
    now = datetime.utcnow()

    for event in recent_events:
        timestamp = _parse_timestamp(event.get("timestamp"))
        if not timestamp:
            continue

        age_seconds = (now - timestamp).total_seconds()
        if age_seconds < 0 or age_seconds > MESSAGE_FLOW_TTL_SECONDS:
            continue

        source = _canonical_flow_node(str(event.get("source", "")))
        target = _canonical_flow_node(str(event.get("destination", "")))
        if not source or not target or source == target:
            continue

        key = (source, target)
        abstract = str(event.get("abstract", "")).strip() or str(event.get("content", "")).strip() or "Message flow"
        if "响应返回" in abstract:
            continue
        entry = edge_map.get(key)
        if entry is None:
            edge_map[key] = {
                "id": f"{source}-{target}",
                "source": source,
                "target": target,
                "count": 1,
                "lastMessage": abstract[:96],
                "lastTimestamp": event.get("timestamp"),
                "active": age_seconds <= MESSAGE_FLOW_ACTIVE_SECONDS,
            }
        else:
            entry["count"] += 1
            if not entry.get("lastMessage"):
                entry["lastMessage"] = abstract[:96]
            if not entry.get("lastTimestamp"):
                entry["lastTimestamp"] = event.get("timestamp")
            entry["active"] = entry["active"] or age_seconds <= MESSAGE_FLOW_ACTIVE_SECONDS

    nodes = []
    for name, position in FLOW_NODE_LAYOUTS.items():
        nodes.append(
            {
                "id": name,
                "name": name,
                "position": position,
                "status": element_status_map.get(
                    name, "online" if name == "ACN SDK" else "offline"
                ),
            }
        )

    edges = sorted(edge_map.values(), key=lambda item: (-item["count"], item["id"]))

    return {
        "nodes": nodes,
        "edges": edges,
    }


def _merge_cached_agent_fields(
    base_agent: Dict[str, Any], cached_agent: Dict[str, Any]
) -> Dict[str, Any]:
    """Overlay transient runtime state without overriding DB-backed identity fields."""
    combined = dict(base_agent)

    # Runtime-only fields from live logs.
    for field in ("work_status", "current_task", "logs", "last_update"):
        if field in cached_agent and cached_agent.get(field) not in (None, ""):
            combined[field] = cached_agent[field]

    # Helpful metadata that may only exist in live log payloads.
    for field in ("owner", "network_capability"):
        if not combined.get(field) and cached_agent.get(field):
            combined[field] = cached_agent[field]

    # Fill identity fields from cache only when DB does not have them.
    if not combined.get("agent_name") and cached_agent.get("agent_name"):
        combined["agent_name"] = cached_agent["agent_name"]
    if not combined.get("agent_capability") and cached_agent.get("agent_capability"):
        combined["agent_capability"] = cached_agent["agent_capability"]
    if not combined.get("agent_status") and cached_agent.get("agent_status"):
        combined["agent_status"] = cached_agent["agent_status"]

    return combined


def _merge_agent_sources() -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen_agent_ids = set()

    # The ARF/AgentGW database is the source of truth for which agents exist.
    # Runtime cache only enriches those agents with transient state.
    for agent in get_agents_from_db():
        agent_id = str(agent.get("agent_id", "")).strip()
        if not agent_id:
            continue

        cached = agent_status_cache.get(agent_id)
        combined = (
            _merge_cached_agent_fields(agent, cached)
            if cached
            else dict(agent)
        )
        combined["agent_id"] = agent_id
        if "agent_capability" not in combined:
            combined["agent_capability"] = []
        if "agent_status" not in combined:
            combined["agent_status"] = "offline"
        merged.append(combined)
        seen_agent_ids.add(agent_id)

    for agent_id, cached in agent_status_cache.items():
        normalized_agent_id = str(agent_id).strip()
        if (
            not normalized_agent_id
            or normalized_agent_id in seen_agent_ids
            or not cached.get("is_demo")
        ):
            continue

        combined = dict(cached)
        combined["agent_id"] = normalized_agent_id
        if "agent_capability" not in combined:
            combined["agent_capability"] = []
        if "agent_status" not in combined:
            combined["agent_status"] = "online"
        merged.append(combined)

    return sorted(
        merged,
        key=lambda item: str(item.get("agent_name") or item.get("agent_id") or ""),
    )


def _dashboard_position(index: int) -> Dict[str, int]:
    columns = 3
    column = index % columns
    row = index // columns
    return {
        "x": 140 + column * 320,
        "y": 90 + row * 190,
    }


def build_dashboard_agents() -> List[Dict[str, Any]]:
    dashboard_agents: List[Dict[str, Any]] = []

    for index, agent in enumerate(_merge_agent_sources()):
        agent_id = str(agent.get("agent_id") or f"agent-{index}")
        status = _dashboard_status_from_agent(agent)
        capabilities = _normalize_capabilities(agent.get("agent_capability"))
        logs = agent.get("logs", [])

        dashboard_agents.append(
            {
                "id": agent_id,
                "name": str(agent.get("agent_name") or agent_id),
                "role": _dashboard_role_from_agent(agent),
                "status": status,
                "region": _dashboard_region_from_agent(agent),
                "throughput": _dashboard_throughput_from_agent(agent),
                "summary": _dashboard_summary_from_agent(agent),
                "uptime": "Unknown" if status == "offline" else "Online",
                "lastHeartbeat": _format_relative_time(
                    agent.get("last_update") or datetime.utcnow().isoformat()
                ),
                "taskCount": max(len(logs), 1 if status == "busy" else 0),
                "capabilities": capabilities or ["General connectivity"],
                "alerts": _dashboard_alerts_from_agent(agent),
                "position": _dashboard_position(index),
            }
        )

    return dashboard_agents


def build_dashboard_links(agents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(agents) < 2:
        return []

    hub = next((agent for agent in agents if agent["status"] != "offline"), agents[0])
    links = []

    for agent in agents:
        if agent["id"] == hub["id"]:
            continue

        seed = sum(ord(char) for char in f'{hub["id"]}:{agent["id"]}')
        active = hub["status"] != "offline" and agent["status"] != "offline"
        latency = 12 + (seed % 24)
        if not active:
            latency += 28

        links.append(
            {
                "id": f'{hub["id"]}-{agent["id"]}',
                "source": hub["id"],
                "target": agent["id"],
                "latency": f"{latency}ms",
                "active": active,
            }
        )

    return links


def _message_level_from_log(entry: Dict[str, Any]) -> str:
    level = str(entry.get("level", "info")).lower()
    message = str(entry.get("message", "")).lower()

    if level == "error" or "failed" in message or "error" in message:
        return "error"
    if level == "warning" or "warn" in message or "latency" in message:
        return "warning"
    return "info"


def _should_include_dashboard_message(entry: Dict[str, Any]) -> bool:
    message = str(entry.get("message", "")).strip().lower()
    if not message:
        return False

    return "send moq object" not in message


def build_dashboard_messages(limit: int = 8) -> List[Dict[str, Any]]:
    recent_logs = (
        [entry for entry in reversed(log_buffer) if _should_include_dashboard_message(entry)][:limit]
        if log_buffer
        else []
    )
    messages = []

    for index, entry in enumerate(recent_logs):
        message = str(entry.get("message", "")).strip() or "System update"
        timestamp = _parse_timestamp(entry.get("time"))
        title = message.split(":", 1)[0][:72] if ":" in message else message[:72]
        source = "Backend"
        if "->" in message:
            source = message.split("->", 1)[0].strip("[] ")

        messages.append(
            {
                "id": f'msg-{index}-{entry.get("time", index)}',
                "level": _message_level_from_log(entry),
                "title": title or "System update",
                "message": message,
                "timestamp": timestamp.strftime("%H:%M:%S")
                if timestamp
                else datetime.utcnow().strftime("%H:%M:%S"),
                "source": source or "Backend",
            }
        )

    return messages


def build_dashboard_metrics(
    agents: List[Dict[str, Any]], links: List[Dict[str, Any]], messages: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    active_agents = sum(1 for agent in agents if agent["status"] != "offline")
    busy_agents = sum(1 for agent in agents if agent["status"] == "busy")
    total_agents = len(agents)
    active_latencies = [
        int(str(link["latency"]).replace("ms", "")) for link in links if link["active"]
    ]
    average_latency = (
        round(sum(active_latencies) / len(active_latencies)) if active_latencies else 0
    )
    warning_messages = sum(1 for message in messages if message["level"] == "warning")
    task_count = sum(
        1 for task in build_control_tasks_snapshot(limit_finished=0) if task["status"] == "processing"
    )
    if task_count == 0:
        task_count = get_task_count_from_db() or busy_agents

    latency_tone = "healthy"
    if average_latency >= 50:
        latency_tone = "critical"
    elif average_latency >= 30:
        latency_tone = "warning"

    return [
        {
            "id": "latency",
            "title": "System Latency",
            "value": f"{average_latency}ms",
            "detail": "Average active link latency from current backend mesh state.",
            "tone": latency_tone,
            "trend": (
                f"{len(active_latencies)} active links sampled"
                if active_latencies
                else "Waiting for active routes"
            ),
        },
        {
            "id": "agents",
            "title": "Active Agents",
            "value": f"{active_agents} / {total_agents}",
            "detail": "Live agent roster derived from the backend database and in-memory status cache.",
            "tone": "warning" if active_agents < total_agents else "healthy",
            "trend": f"{busy_agents} busy, {warning_messages} warning messages",
        },
        {
            "id": "tasks",
            "title": "Running Tasks",
            "value": str(task_count),
            "detail": "Current workload count backed by the tasks table and active agent state.",
            "tone": "warning" if busy_agents > max(active_agents // 2, 1) else "healthy",
            "trend": f"{busy_agents} agents currently busy",
        },
    ]


def build_dashboard_snapshot() -> Dict[str, Any]:
    agents = build_dashboard_agents()
    links = build_dashboard_links(agents)
    messages = build_dashboard_messages()
    metrics = build_dashboard_metrics(agents, links, messages)
    elements = build_element_status_snapshot()
    message_flow = build_message_flow_snapshot(elements)

    return {
        "metrics": metrics,
        "elements": elements,
        "messageFlow": message_flow,
        "topology": {
            "agents": agents,
            "links": links,
        },
        "messages": messages,
        "timestamp": datetime.utcnow().isoformat(),
    }


def build_topology_test_messages() -> List[Dict[str, Any]]:
    """Focused message-flow demo aligned with the Topology Map layout."""
    now = datetime.utcnow()
    return [
        {
            "source": "ACN SDK",
            "destination": "ACN Agent",
            "timestamp": now.isoformat(),
            "task_id": "topology-identity",
            "protocol": "HTTP/2",
            "headers": "",
            "abstract": "Register agent identity",
            "content": "ACN SDK starts identity registration",
        },
        {
            "source": "ACN Agent",
            "destination": "IDM",
            "timestamp": (now + timedelta(milliseconds=120)).isoformat(),
            "task_id": "topology-identity",
            "protocol": "HTTP/2",
            "headers": "",
            "abstract": "/idm/v1/identity-applications已转发到IDM",
            "content": "ACN Agent forwards the identity application to IDM",
        },
        {
            "source": "IDM",
            "destination": "ACN SDK",
            "timestamp": (now + timedelta(milliseconds=240)).isoformat(),
            "task_id": "topology-identity",
            "protocol": "HTTP/2",
            "headers": "",
            "abstract": "/idm/v1/identity-applications响应返回ACN SDK",
            "content": "IDM returns the identity response to ACN SDK",
        },
        {
            "source": "ACN Agent",
            "destination": "AgentGW",
            "timestamp": (now + timedelta(milliseconds=360)).isoformat(),
            "task_id": "topology-card",
            "protocol": "HTTP/2",
            "headers": "",
            "abstract": "/arf/v1/agent-cards已转发到AgentGW",
            "content": "ACN Agent forwards the agent card to AgentGW",
        },
        {
            "source": "AgentGW",
            "destination": "ACN SDK",
            "timestamp": (now + timedelta(milliseconds=480)).isoformat(),
            "task_id": "topology-card",
            "protocol": "HTTP/2",
            "headers": "",
            "abstract": "/arf/v1/agent-cards响应返回ACN SDK",
            "content": "AgentGW returns the agent-card response to ACN SDK",
        },
    ]


async def run_topology_test_demo(
    rounds: int = 1, step_delay_seconds: float = 0.12
) -> Dict[str, Any]:
    """Inject a focused set of pipeline logs for Topology Map testing."""
    total_messages = 0
    normalized_rounds = max(1, rounds)
    topology_test_runtime["running"] = True
    topology_test_runtime["paused"] = False

    try:
        for round_index in range(normalized_rounds):
            round_messages = build_topology_test_messages()
            for message_index, message in enumerate(round_messages):
                while topology_test_runtime["paused"]:
                    await asyncio.sleep(0.1)

                payload = dict(message)
                payload["task_id"] = f"{message['task_id']}-r{round_index + 1}"
                payload["timestamp"] = (
                    datetime.utcnow() + timedelta(milliseconds=message_index * 120)
                ).isoformat()
                await receive_pipeline_log({"body": payload})
                total_messages += 1
                if message_index < len(round_messages) - 1:
                    await asyncio.sleep(step_delay_seconds)
    finally:
        topology_test_runtime["running"] = False
        topology_test_runtime["paused"] = False

    dashboard = build_dashboard_snapshot()
    await manager.broadcast({"type": "DASHBOARD_SNAPSHOT", "payload": dashboard})

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "rounds": normalized_rounds,
        "messages_sent": total_messages,
        "dashboard": dashboard,
    }


def build_full_system_test_events() -> List[Dict[str, Any]]:
    """Build a realistic end-to-end demo scenario from known backend log patterns."""
    alpha_id = "did:acn:agent:demo-alpha"
    beta_id = "did:acn:agent:demo-beta"

    return [
        {
            "kind": "element",
            "payload": {
                "element_id": "IDM",
                "log_type": "ApplyProfile",
                "content": {
                    "agent_id": alpha_id,
                    "agent_name": "Demo Agent Alpha",
                    "owner": "demo-user",
                    "network_capability": "Perimeter inspection",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "pipeline",
            "payload": {
                "source": "ACN SDK",
                "destination": "ACN Agent",
                "task_id": "demo-alpha-identity",
                "protocol": "HTTP/2",
                "headers": "",
                "abstract": "Register agent identity",
                "content": {
                    "agent_id": alpha_id,
                    "agent_name": "Demo Agent Alpha",
                    "name": "Demo Agent Alpha",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "pipeline",
            "payload": {
                "source": "ACN Agent",
                "destination": "IDM",
                "task_id": "demo-alpha-identity",
                "protocol": "HTTP/2",
                "headers": "",
                "abstract": "/idm/v1/identity-applications已转发到IDM",
                "content": {
                    "agent_id": alpha_id,
                    "agent_name": "Demo Agent Alpha",
                    "owner": "demo-user",
                    "name": "Demo Agent Alpha",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "pipeline",
            "payload": {
                "source": "IDM",
                "destination": "ACN SDK",
                "task_id": "demo-alpha-identity",
                "protocol": "HTTP/2",
                "headers": "",
                "abstract": "/idm/v1/identity-applications响应返回ACN SDK",
                "content": {
                    "agent_id": alpha_id,
                    "agent_name": "Demo Agent Alpha",
                    "name": "Demo Agent Alpha",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "element",
            "payload": {
                "element_id": "AgentGW",
                "log_type": "PublishAgent",
                "content": {
                    "agent_id": alpha_id,
                    "agent_name": "Demo Agent Alpha",
                    "agent_capability": "Route patrol, telemetry uplink",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "pipeline",
            "payload": {
                "source": "ACN Agent",
                "destination": "AgentGW",
                "task_id": "demo-alpha-card",
                "protocol": "HTTP/2",
                "headers": "",
                "abstract": "/arf/v1/agent-cards已转发到AgentGW",
                "content": {
                    "agent_id": alpha_id,
                    "agent_name": "Demo Agent Alpha",
                    "name": "Demo Agent Alpha",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "pipeline",
            "payload": {
                "source": "AgentGW",
                "destination": "ACN SDK",
                "task_id": "demo-alpha-card",
                "protocol": "HTTP/2",
                "headers": "",
                "abstract": "/arf/v1/agent-cards响应返回ACN SDK",
                "content": {
                    "agent_id": alpha_id,
                    "agent_name": "Demo Agent Alpha",
                    "name": "Demo Agent Alpha",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "element",
            "payload": {
                "element_id": "AgentGW",
                "log_type": "SetupConnection",
                "content": {
                    "agent_id": alpha_id,
                    "agent_name": "Demo Agent Alpha",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "element",
            "payload": {
                "element_id": "ACN Agent",
                "log_type": "LLMMessage",
                "content": {
                    "agent_id": alpha_id,
                    "agent_name": "Demo Agent Alpha",
                    "message": "Inspecting corridor A and validating telemetry health.",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "pipeline",
            "payload": {
                "source": "ACN SDK",
                "destination": "ACN Agent",
                "task_id": "demo-task-alpha",
                "protocol": "HTTP/2",
                "headers": "",
                "abstract": "Request task execution",
                "content": {
                    "agent_id": alpha_id,
                    "agent_name": "Demo Agent Alpha",
                    "name": "Demo Agent Alpha",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "element",
            "payload": {
                "element_id": "IDM",
                "log_type": "ApplyProfile",
                "content": {
                    "agent_id": beta_id,
                    "agent_name": "Demo Agent Beta",
                    "owner": "demo-user",
                    "network_capability": "Anomaly correlation",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "element",
            "payload": {
                "element_id": "AgentGW",
                "log_type": "PublishAgent",
                "content": {
                    "agent_id": beta_id,
                    "agent_name": "Demo Agent Beta",
                    "agent_capability": "Anomaly validation, cross-agent collaboration",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "element",
            "payload": {
                "element_id": "AgentGW",
                "log_type": "SetupConnection",
                "content": {
                    "agent_id": beta_id,
                    "agent_name": "Demo Agent Beta",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "pipeline",
            "payload": {
                "source": "ACN SDK",
                "destination": "ACN Agent",
                "task_id": "demo-task-beta",
                "protocol": "HTTP/2",
                "headers": "",
                "abstract": "Request task collaboration",
                "content": {
                    "agent_id": beta_id,
                    "agent_name": "Demo Agent Beta",
                    "name": "Demo Agent Beta",
                    "is_demo": True,
                },
            },
        },
        {
            "kind": "element",
            "payload": {
                "element_id": "ACN Agent",
                "log_type": "TaskExecution",
                "content": {
                    "agent_id": beta_id,
                    "agent_name": "Demo Agent Beta",
                    "is_demo": True,
                },
            },
        },
    ]


def _clear_local_demo_state():
    demo_agent_ids = [
        agent_id for agent_id, cached in agent_status_cache.items() if cached.get("is_demo")
    ]
    for agent_id in demo_agent_ids:
        agent_status_cache.pop(agent_id, None)

    demo_task_ids = [
        task_id for task_id, metadata in task_control_registry.items() if metadata.get("is_demo")
    ]
    for task_id in demo_task_ids:
        task_control_registry.pop(task_id, None)

    control_task_history[:] = [
        task for task in control_task_history if not task.get("isDemo")
    ]

    demo_task_prefixes = ("demo-task-", "demo-alpha-", "demo-beta-", "demo-finished-")
    stale_task_keys = [
        task_id for task_id in task_agent_mapping.keys() if str(task_id).startswith(demo_task_prefixes)
    ]
    for task_id in stale_task_keys:
        task_agent_mapping.pop(task_id, None)


async def run_full_system_test_demo(
    rounds: int = 1, step_delay_seconds: float = 0.22
) -> Dict[str, Any]:
    """Inject registration, interaction, and collaboration events for a full UI demo."""
    total_messages = 0
    normalized_rounds = max(1, rounds)
    _clear_local_demo_state()

    add_log_entry(
        "[Demo] Starting local demo scenario (no external IDM, ACN Agent, or AgentGW calls)",
        "info",
    )

    full_demo_events = build_full_system_test_events()
    demo_task_definitions = [
        {
            "id": "demo-task-alpha",
            "name": "Perimeter Sweep",
            "type": "Inspection",
            "description": "Inspect corridor A and validate telemetry uplink stability.",
            "agent_ids": ["did:acn:agent:demo-alpha"],
            "agent_names": {"did:acn:agent:demo-alpha": "Demo Agent Alpha"},
        },
        {
            "id": "demo-task-beta",
            "name": "Correlation Assist",
            "type": "Collaboration",
            "description": "Correlate anomaly findings and support cross-agent verification.",
            "agent_ids": [
                "did:acn:agent:demo-alpha",
                "did:acn:agent:demo-beta",
            ],
            "agent_names": {
                "did:acn:agent:demo-alpha": "Demo Agent Alpha",
                "did:acn:agent:demo-beta": "Demo Agent Beta",
            },
        },
    ]

    for round_index in range(normalized_rounds):
        now = datetime.utcnow().isoformat()
        for definition in demo_task_definitions:
            task_id = f"{definition['id']}-r{round_index + 1}"
            task_control_registry[task_id] = {
                "task_name": definition["name"],
                "task_type": definition["type"],
                "task_description": definition["description"],
                "created_at": now,
                "updated_at": now,
                "status": "processing",
                "agent_ids": list(definition["agent_ids"]),
                "agent_names": dict(definition["agent_names"]),
                "is_demo": True,
            }

        for event_index, event in enumerate(full_demo_events):
            payload = dict(event["payload"])
            payload["timestamp"] = datetime.utcnow().isoformat()
            if "task_id" in payload:
                payload["task_id"] = f"{payload['task_id']}-r{round_index + 1}"

            if event["kind"] == "pipeline":
                await receive_pipeline_log({"body": payload})
            else:
                await receive_element_log({"body": payload})

            total_messages += 1
            if event_index < len(full_demo_events) - 1:
                await asyncio.sleep(step_delay_seconds)

    finished_time = datetime.utcnow().isoformat()
    control_task_history.append(
        {
            "id": f"demo-finished-{normalized_rounds}",
            "taskName": "Identity Bootstrap",
            "taskType": "Registration",
            "description": "Finished the local identity bootstrap demo for Demo Agent Alpha.",
            "status": "finished",
            "involvedAgents": [
                {
                    "id": "did:acn:agent:demo-alpha",
                    "name": "Demo Agent Alpha",
                }
            ],
            "createdAt": finished_time,
            "updatedAt": finished_time,
            "isDemo": True,
        }
    )
    if len(control_task_history) > max_control_task_history:
        control_task_history.pop(0)

    add_log_entry(
        "[Demo] Local demo events injected successfully; external services were not contacted",
        "info",
    )

    tasks = build_control_tasks_snapshot()
    dashboard = build_dashboard_snapshot()
    await manager.broadcast(
        {
            "type": "TASKS_UPDATED",
            "payload": {
                "timestamp": datetime.utcnow().isoformat(),
                "tasks": tasks,
                "dashboard": dashboard,
            },
        }
    )
    await manager.broadcast({"type": "DASHBOARD_SNAPSHOT", "payload": dashboard})

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "rounds": normalized_rounds,
        "messages_sent": total_messages,
        "tasks": tasks,
        "dashboard": dashboard,
    }


# ARF Service helper
async def call_arf_clear() -> Dict[str, Any]:
    """Call ARF /clear endpoint to reset environment"""
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            payload = {"method": "POST", "url": "/clear", "body": {}}
            print(f"[ARF] Sending clear request to {ARF_CLEAR_URL}")
            response = await client.post(
                ARF_CLEAR_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )
            print(f"[ARF] Clear response: {response.status_code}")
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else None,
            }
    except httpx.ConnectError as e:
        print(f"[ARF Error] Cannot connect to ARF service: {e}")
        return {
            "success": False,
            "error": "Cannot connect to ARF service",
            "detail": str(e),
        }
    except Exception as e:
        print(f"[ARF Error] {e}")
        return {"success": False, "error": str(e)}


# Video frame handler for MOQ
async def handle_moq_video_frame(frame: "VideoFrame"):
    """Handle received video frame from MOQ"""
    # Import VideoFrame parser
    try:
        from .video_frame_parser import try_parse_video_frame, extract_h264_data

        # Try to parse VideoFrame structure (from demo_task_initiator_video_production.py)
        video_frame = try_parse_video_frame(frame.payload)
        if video_frame:
            # Extract pure H264 data from VideoFrame
            h264_payload = video_frame.data
            frame_info = video_frame.get_info()
            print(
                f"[VIDEO_FRAME] Parsed VideoFrame: frame_id={frame_info['frame_id']}, "
                f"gop_id={frame_info['gop_id']}, {frame_info['width']}x{frame_info['height']}, "
                f"fps={frame_info['fps']}, keyframe={frame_info['is_keyframe']}"
            )
        else:
            # Not VideoFrame format, use raw payload
            h264_payload = frame.payload
    except ImportError:
        # Parser not available, use raw payload
        h264_payload = frame.payload

    payload_b64 = base64.b64encode(h264_payload).decode("ascii")
    mime_type = _infer_moq_mime_type(h264_payload)
    codec = _infer_moq_codec(h264_payload)

    payload_preview = (
        h264_payload[:20].hex() if len(h264_payload) >= 20 else h264_payload.hex()
    )
    print(
        f"[VIDEO_FRAME] track={frame.track_name[:50]} mime={mime_type} codec={codec} size={len(h264_payload)} payload_preview={payload_preview}"
    )

    # Force H264 if payload looks like video data
    if mime_type == "application/octet-stream" and len(h264_payload) > 100:
        mime_type = "video/h264"
        codec = "h264"

    # Broadcast to all WebSocket clients
    await manager.broadcast(
        {
            "type": "VIDEO_FRAME",
            "payload": {
                "track_id": frame.track_name,
                "group_id": frame.group_id,
                "object_id": frame.object_id,
                "timestamp": frame.timestamp.isoformat(),
                "frame_type": frame.frame_type,
                "payload_size": len(h264_payload),
                "mime_type": mime_type,
                "codec": codec,
                "payload_base64": payload_b64,
                "data_url": f"data:{mime_type};base64,{payload_b64}",
            },
        }
    )


def on_moq_track_subscribed(track_id: str):
    """Handler for MOQ track subscribed"""
    print(f"[MOQ] Track subscribed: {track_id}")


def _infer_moq_mime_type(payload: bytes) -> str:
    """Infer a browser-friendly MIME type from MOQ payload bytes."""
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"GIF87a") or payload.startswith(b"GIF89a"):
        return "image/gif"
    if payload.startswith(b"RIFF") and len(payload) >= 12 and payload[8:12] == b"WEBP":
        return "image/webp"
    if _looks_like_h264(payload):
        return "video/h264"

    # Default to octet-stream so the frontend can decide whether to render
    # the frame or fall back to a placeholder.
    return "application/octet-stream"


def _looks_like_h264(payload: bytes) -> bool:
    """Best-effort detection for Annex B H.264 payloads."""
    if len(payload) < 5:
        return False

    start_code_len = 0
    if payload.startswith(b"\x00\x00\x00\x01"):
        start_code_len = 4
    elif payload.startswith(b"\x00\x00\x01"):
        start_code_len = 3
    else:
        if len(payload) < 8:
            return False
        nal_length = int.from_bytes(payload[0:4], "big")
        if nal_length <= 0 or nal_length + 4 > len(payload):
            return False
        nal_type = payload[4] & 0x1F
        return nal_type in {1, 5, 6, 7, 8}

    nal_header_index = start_code_len
    if nal_header_index >= len(payload):
        return False

    nal_type = payload[nal_header_index] & 0x1F
    return nal_type in {1, 5, 6, 7, 8}


def _infer_moq_codec(payload: bytes) -> str | None:
    """Infer a codec hint for browser-side rendering."""
    if _looks_like_h264(payload):
        return "h264"
    return None


# Lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("ACN Agent Monitor Backend Starting...")
    print("=" * 60)
    print(f"API: http://0.0.0.0:9005")
    print(f"WebSocket: ws://0.0.0.0:9005/ws")
    print("=" * 60)

    # Start background task for agent updates
    task = asyncio.create_task(broadcast_agent_updates())

    # Start MOQ video subscriber
    moq_task = None
    if MOQ_AVAILABLE:
        print("[MOQ] Starting video subscriber...")
        moq_video_subscriber.set_callbacks(
            on_frame_received=handle_moq_video_frame,
            on_track_subscribed=on_moq_track_subscribed,
        )
        await moq_video_subscriber.start()
        moq_task = moq_video_subscriber._connection_task

    yield

    # Cancel background task on shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Stop MOQ subscriber
    if MOQ_AVAILABLE:
        print("[MOQ] Stopping video subscriber...")
        await moq_video_subscriber.stop()

    print("[Shutdown] Backend stopping...")


# Create FastAPI app
app = FastAPI(
    title="ACN Agent Monitor Backend",
    description="Backend API and WebSocket for ACN Agent Monitor",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Routes
@app.get("/api/agents", response_model=Dict[str, Any])
async def get_agents():
    """Get all registered agents"""
    agents = _merge_agent_sources()
    return {"agents": agents, "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "websocket_clients": len(manager.active_connections),
    }


# Log buffer for frontend display
log_buffer = []
max_log_entries = 1000
pipeline_log_buffer = []
max_pipeline_log_entries = 200
task_control_registry: Dict[str, Dict[str, Any]] = {}
control_task_history: List[Dict[str, Any]] = []
max_control_task_history = 50
topology_test_runtime = {"running": False, "paused": False}


def add_log_entry(message: str, level: str = "info"):
    """Add a log entry to the buffer"""
    log_entry = {
        "time": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
    }
    log_buffer.append(log_entry)
    if len(log_buffer) > max_log_entries:
        log_buffer.pop(0)


def add_pipeline_log_entry(source: str, destination: str, abstract: str, content: Any, timestamp: Any, task_id: Any):
    entry = {
        "source": source,
        "destination": destination,
        "abstract": abstract,
        "content": content if isinstance(content, str) else json.dumps(content, ensure_ascii=False) if content else "",
        "timestamp": timestamp or datetime.utcnow().isoformat(),
        "task_id": task_id,
    }
    pipeline_log_buffer.append(entry)
    if len(pipeline_log_buffer) > max_pipeline_log_entries:
        pipeline_log_buffer.pop(0)


LOG_TIMESTAMP_PATTERNS = [
    re.compile(r"(?P<value>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:[.,]\d+)?)"),
    re.compile(r"(?P<value>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)"),
]


def _find_latest_log_file(directory: Path) -> Optional[Path]:
    if not directory.exists() or not directory.is_dir():
        return None

    candidates = [
        file_path
        for file_path in directory.iterdir()
        if file_path.is_file()
        and file_path.suffix == ".log"
    ]
    if not candidates:
        return None

    return max(candidates, key=lambda path: path.stat().st_mtime)


def _list_log_files(directory: Path) -> List[Path]:
    if not directory.exists() or not directory.is_dir():
        return []

    candidates = [
        file_path
        for file_path in directory.iterdir()
        if file_path.is_file() and file_path.suffix == ".log"
    ]
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def _parse_log_time(line: str) -> Optional[str]:
    for pattern in LOG_TIMESTAMP_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group("value")
    return None


def _parse_log_level(line: str) -> str:
    normalized = line.upper()
    if " ERROR " in normalized or normalized.startswith("ERROR"):
        return "error"
    if " WARNING " in normalized or " WARN " in normalized or normalized.startswith("WARN"):
        return "warning"
    return "info"


def _tail_log_entries(file_path: Path, limit: int) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []

    with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
        lines = list(deque(handle, maxlen=limit))

    entries = []
    for line in lines:
        message = line.rstrip()
        if not message:
            continue
        entries.append(
            {
                "time": _parse_log_time(message),
                "level": _parse_log_level(message),
                "message": message,
            }
        )

    return entries


def build_network_element_logs_snapshot(limit: int = 40) -> List[Dict[str, Any]]:
    elements: List[Dict[str, Any]] = []

    for source in NETWORK_ELEMENT_LOG_SOURCES:
        path = source["path"]
        resolved_path: Optional[Path] = None
        error: Optional[str] = None

        try:
            if source["mode"] == "file":
                resolved_path = path if path.exists() else None
                sub_logs = []
            elif source["mode"] == "all-logs":
                log_files = _list_log_files(path)
                resolved_path = log_files[0] if log_files else None
                sub_logs = [
                    {
                        "id": file_path.stem,
                        "name": file_path.name,
                        "path": str(file_path),
                        "entries": _tail_log_entries(file_path, limit),
                        "error": None,
                    }
                    for file_path in log_files
                ]
            else:
                resolved_path = _find_latest_log_file(path)
                sub_logs = []

            if resolved_path is None:
                error = "Log file not found."
                entries = []
                if source["mode"] == "all-logs":
                    sub_logs = []
            else:
                entries = _tail_log_entries(resolved_path, limit)
        except Exception as exc:
            error = str(exc)
            entries = []
            sub_logs = []

        elements.append(
            {
                "id": source["id"],
                "name": source["name"],
                "path": str(resolved_path or path),
                "entries": entries,
                "subLogs": sub_logs,
                "error": error,
            }
        )

    return elements


@app.get("/api/logs")
async def get_logs(limit: int = 100):
    """Get recent backend logs"""
    return {
        "logs": log_buffer[-limit:] if log_buffer else [],
        "total": len(log_buffer),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/network-element-logs")
async def get_network_element_logs(limit: int = 40):
    """Get recent logs for ACN Agent, AgentGW, and IDM."""
    normalized_limit = max(10, min(limit, 120))
    return {
        "elements": build_network_element_logs_snapshot(normalized_limit),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/dashboard/overview")
async def get_dashboard_overview():
    """Get frontend-ready dashboard snapshot."""
    return build_dashboard_snapshot()


@app.post("/api/control/clear")
async def clear_environment():
    """Reset the environment through ARF and return the refreshed dashboard snapshot."""
    result = await call_arf_clear()

    if not result.get("success"):
        raise HTTPException(
            status_code=502,
            detail={
                "error": result.get("error", "Failed to clear environment"),
                "detail": result.get("detail", ""),
            },
        )

    agent_status_cache.clear()
    task_agent_mapping.clear()
    pipeline_log_buffer.clear()
    task_control_registry.clear()
    control_task_history.clear()
    agents = _merge_agent_sources()
    dashboard = build_dashboard_snapshot()
    tasks = build_control_tasks_snapshot()
    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "agents": agents,
        "arf_response": result.get("response"),
        "dashboard": dashboard,
        "tasks": tasks,
    }

    await manager.broadcast({"type": "REFRESH_COMPLETE", "payload": payload})

    return {
        "success": True,
        "message": "Environment cleared successfully.",
        **payload,
    }


@app.post("/api/control/test-messages/topology-demo")
async def trigger_topology_test_demo(request: Request):
    """Inject a focused pipeline-log demo for the Topology Map."""
    if topology_test_runtime["running"]:
        raise HTTPException(status_code=409, detail="Topology test is already running.")

    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    rounds = body.get("rounds", 1)
    step_delay_seconds = body.get("step_delay_seconds", 0.12)

    try:
        result = await run_topology_test_demo(
            rounds=int(rounds),
            step_delay_seconds=max(0.02, float(step_delay_seconds)),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run topology test demo: {e}")

    return {
        "success": True,
        "message": f"Topology demo injected with {result['messages_sent']} messages.",
        **result,
    }


@app.post("/api/control/test-messages/topology-demo/pause")
async def pause_topology_test_demo():
    """Pause an in-flight topology test demo."""
    if not topology_test_runtime["running"]:
        return {
            "success": False,
            "running": False,
            "paused": False,
            "message": "Topology test is not running.",
        }

    topology_test_runtime["paused"] = True
    return {
        "success": True,
        "running": True,
        "paused": True,
        "message": "Topology test paused.",
    }


@app.post("/api/control/test-messages/topology-demo/resume")
async def resume_topology_test_demo():
    """Resume a paused topology test demo."""
    if not topology_test_runtime["running"]:
        return {
            "success": False,
            "running": False,
            "paused": False,
            "message": "Topology test is not running.",
        }

    topology_test_runtime["paused"] = False
    return {
        "success": True,
        "running": True,
        "paused": False,
        "message": "Topology test resumed.",
    }


@app.post("/api/control/test-messages/full-demo")
async def trigger_full_system_test_demo(request: Request):
    """Inject a broader local registration + interaction demo for the full WebUI."""
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    rounds = body.get("rounds", 1)
    step_delay_seconds = body.get("step_delay_seconds", 0.22)

    try:
        result = await run_full_system_test_demo(
            rounds=int(rounds),
            step_delay_seconds=max(0.05, float(step_delay_seconds)),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run full system demo: {e}")

    return {
        "success": True,
        "message": f"Local demo injected with {result['messages_sent']} events.",
        **result,
    }


@app.get("/api/control/tasks")
async def get_control_tasks():
    """Get active and recently finished control tasks."""
    return {
        "tasks": build_control_tasks_snapshot(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/control/tasks")
async def dispatch_control_task(request: Request):
    """Dispatch a new task across one or more agents."""
    body = await request.json()
    agent_ids = body.get("agent_ids") or []
    task_type = str(body.get("task_type") or "").strip()
    task_description = str(body.get("task_description") or "").strip()
    task_name = str(body.get("task_name") or task_type or "Task").strip()

    if not isinstance(agent_ids, list) or not agent_ids:
        raise HTTPException(status_code=400, detail="At least one agent must be selected.")
    if not task_type:
        raise HTTPException(status_code=400, detail="Task type is required.")
    if not task_description:
        raise HTTPException(status_code=400, detail="Task description is required.")

    normalized_agent_ids = []
    for agent_id in agent_ids:
        value = str(agent_id).strip()
        if value and value not in normalized_agent_ids:
            normalized_agent_ids.append(value)

    if not normalized_agent_ids:
        raise HTTPException(status_code=400, detail="No valid agents were provided.")

    task_id = f"task-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    now = datetime.utcnow().isoformat()
    agent_names = _task_agent_name_lookup()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO tasks (agent_id, task_id, task_description) VALUES (?, ?, ?)",
            [
                (agent_id, task_id, task_description)
                for agent_id in normalized_agent_ids
            ],
        )
        conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to dispatch task: {e}")

    task_control_registry[task_id] = {
        "task_name": task_name,
        "task_type": task_type,
        "task_description": task_description,
        "created_at": now,
        "updated_at": now,
        "status": "processing",
        "agent_ids": list(normalized_agent_ids),
        "agent_names": {
            agent_id: agent_names.get(agent_id, agent_id)
            for agent_id in normalized_agent_ids
        },
    }

    for agent_id in normalized_agent_ids:
        cache_entry = agent_status_cache.setdefault(
            agent_id,
            {
                "agent_name": agent_names.get(agent_id, agent_id),
                "logs": [],
            },
        )
        cache_entry["work_status"] = "working"
        cache_entry["current_task"] = task_description
        cache_entry["last_update"] = now
        cache_entry.setdefault("logs", []).append(
            {
                "time": now,
                "level": "info",
                "message": f"Dispatched task {task_name}",
            }
        )
        if len(cache_entry["logs"]) > 10:
            cache_entry["logs"] = cache_entry["logs"][-10:]

    add_log_entry(
        f"[Control] Dispatched task {task_id} ({task_type}) to {len(normalized_agent_ids)} agents",
        "info",
    )

    tasks = build_control_tasks_snapshot()
    agents = _merge_agent_sources()
    dashboard = build_dashboard_snapshot()
    payload = {
        "timestamp": now,
        "taskId": task_id,
        "tasks": tasks,
        "agents": agents,
        "dashboard": dashboard,
    }

    await manager.broadcast({"type": "TASKS_UPDATED", "payload": payload})

    return {
        "success": True,
        "message": f"Task {task_name} dispatched.",
        **payload,
    }


@app.post("/api/control/tasks/{task_id}/stop")
async def stop_control_task(task_id: str):
    """Stop a running task and mark it finished in the control surface."""
    active_tasks = {
        item["id"]: item
        for item in build_control_tasks_snapshot()
        if item.get("status") == "processing"
    }
    task = active_tasks.get(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    now = datetime.utcnow().isoformat()
    involved_agents = task.get("involvedAgents", [])
    involved_agent_ids = [
        str(agent.get("id"))
        for agent in involved_agents
        if agent.get("id")
    ]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop task: {e}")

    task_control_registry[task_id] = {
        **task_control_registry.get(task_id, {}),
        "task_name": task.get("taskName"),
        "task_type": task.get("taskType"),
        "task_description": task.get("description"),
        "created_at": task.get("createdAt") or now,
        "updated_at": now,
        "status": "finished",
        "agent_ids": involved_agent_ids,
        "agent_names": {
            str(agent.get("id")): str(agent.get("name") or agent.get("id"))
            for agent in involved_agents
            if agent.get("id")
        },
    }

    finished_record = {
        **task,
        "status": "finished",
        "updatedAt": now,
    }
    control_task_history.append(finished_record)
    if len(control_task_history) > max_control_task_history:
        control_task_history.pop(0)

    remaining_tasks = get_tasks_from_db()
    remaining_by_agent: Dict[str, str] = {}
    for remaining_task in remaining_tasks:
        for agent_id in remaining_task.get("agent_ids", []):
            remaining_by_agent.setdefault(
                agent_id,
                str(remaining_task.get("description") or ""),
            )

    for agent_id in involved_agent_ids:
        cache_entry = agent_status_cache.get(agent_id)
        if not cache_entry:
            continue

        cache_entry["last_update"] = now
        if agent_id in remaining_by_agent:
            cache_entry["work_status"] = "working"
            cache_entry["current_task"] = remaining_by_agent[agent_id]
        else:
            cache_entry["work_status"] = "idle"
            cache_entry["current_task"] = ""

    add_log_entry(f"[Control] Stopped task {task_id}", "warning")

    tasks = build_control_tasks_snapshot()
    agents = _merge_agent_sources()
    dashboard = build_dashboard_snapshot()
    payload = {
        "timestamp": now,
        "taskId": task_id,
        "tasks": tasks,
        "agents": agents,
        "dashboard": dashboard,
    }

    await manager.broadcast({"type": "TASKS_UPDATED", "payload": payload})

    return {
        "success": True,
        "message": f"Task {task.get('taskName') or task_id} stopped.",
        **payload,
    }


# MOQ Video Stream API Endpoints (outside static file block)
@app.get("/api/moq/status")
async def get_moq_status():
    """Get MOQ subscriber status"""
    if not MOQ_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "MOQ video subscriber not available",
        }

    return {
        "status": "available",
        "connected": moq_video_subscriber._subscriber is not None,
        "relay_host": moq_video_subscriber.relay_host,
        "relay_port": moq_video_subscriber.relay_port,
        "subscribed_tracks": moq_video_subscriber.get_subscribed_tracks(),
        "subscription_debug": moq_video_subscriber.get_track_debug_info(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/moq/subscribe")
async def subscribe_moq_track(request: Dict[str, Any]):
    """Subscribe to a MOQ video track"""
    if not MOQ_AVAILABLE:
        return {"status": "error", "message": "MOQ not available"}

    track_id = request.get("track_id")
    namespace = request.get("namespace", [])  # e.g., ["acn", "agent", "001"]
    track_name = request.get("track_name")  # e.g., "camera" or "thermal"

    if not track_id or not track_name:
        return {"status": "error", "message": "Missing track_id or track_name"}

    success = await moq_video_subscriber.subscribe_to_track(
        track_id=track_id, namespace=namespace, track_name=track_name
    )

    if success:
        return {
            "status": "success",
            "track_id": track_id,
            "namespace": namespace,
            "track_name": track_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

    return {"status": "error", "message": "Failed to subscribe"}


@app.post("/api/moq/unsubscribe/{track_id}")
async def unsubscribe_moq_track(track_id: str):
    """Unsubscribe from a MOQ video track"""
    if not MOQ_AVAILABLE:
        return {"status": "error", "message": "MOQ not available"}

    await moq_video_subscriber.unsubscribe_from_track(track_id)

    return {
        "status": "success",
        "track_id": track_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/moq/tracks/{track_id}/frames")
async def get_moq_track_frames(track_id: str, limit: int = 10):
    """Get recent frames for a track (for testing/debugging)"""
    if not MOQ_AVAILABLE:
        return {"status": "error", "message": "MOQ not available"}

    frames = moq_video_subscriber.get_frame_buffer(track_id)
    recent_frames = frames[-limit:] if frames else []

    return {
        "track_id": track_id,
        "frame_count": len(frames),
        "frames": [
            {
                "group_id": f.group_id,
                "object_id": f.object_id,
                "timestamp": f.timestamp.isoformat(),
                "frame_type": f.frame_type,
                "payload_size": len(f.payload),
            }
            for f in recent_frames
        ],
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/moq/auto-subscribe/{agent_id}")
async def auto_subscribe_agent(agent_id: str):
    """
    Auto-subscribe to common video tracks for an agent.
    NOTE: This endpoint is deprecated. Please use /api/acn/v3/subscribe_track
    with proper namespace information from ACF.
    """
    if not MOQ_AVAILABLE:
        return {"status": "error", "message": "MOQ not available"}

    # DEPRECATED: Hardcoded namespace format no longer matches Publisher's namespace format
    # Publisher uses: /{task_id}/{agent_id} (e.g., /task-fa4af/did:udid:...)
    # This endpoint no longer performs automatic subscription to avoid namespace mismatch.
    #
    # To subscribe to video tracks, ACF should call:
    # POST /api/acn/v3/subscribe_track
    # with body containing:
    # {
    #     "payload": {
    #         "dst_agent_id": "...",
    #         "task_id": "task-xxx",
    #         "track_list": [
    #             {"namespace": "/task-xxx/did:...", "track": "Video"}
    #         ]
    #     }
    # }

    return {
        "status": "warning",
        "agent_id": agent_id,
        "message": "Auto-subscribe with hardcoded namespace is deprecated. Use /api/acn/v3/subscribe_track with proper namespace from ACF.",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/acn/v3/subscribe_track")
async def subscribe_tracks_from_acf(request: Request):
    """
    Receive track list from ACF and auto-subscribe to video tracks

    Request body format:
    {
        "method": "POST",
        "url": "/ACN_v3/subscribe_track",
        "headers": {"Content-Type": "application/json"},
        "body": {
            "type": "SUBSCRIBE_TRACK",
            "timestamp": "2026-04-13T10:20:30Z",
            "payload": {
                "src_agent_id": "ACF",
                "dst_agent_id": "did:acn:agent:222222222",
                "task_id": "task-12345",
                "track_list": [
                    {"namespace": "/task-12345/did:acn:agent:222222222", "track": "Video"},
                    {"namespace": "/task-12345/did:acn:agent:222222222", "track": "Location"}
                ]
            }
        }
    }
    """
    try:
        raw_body = await request.body()
        body_text = raw_body.decode("utf-8", errors="replace") if raw_body else ""

        # Extract body (support both direct and nested formats)
        body: Dict[str, Any] = {}
        if raw_body:
            try:
                parsed = await request.json()
                if isinstance(parsed, dict):
                    body = parsed
                elif isinstance(parsed, list):
                    body = {"track_list": parsed}
                else:
                    body = {"payload": parsed}
            except Exception:
                # Fall back to text for non-JSON payloads.
                body = {"raw_body": body_text}

        if "body" in body and isinstance(body["body"], dict):
            body = body["body"]

        payload = body.get("payload", body)
        if not isinstance(payload, dict):
            payload = {}

        track_list = (
            payload.get("track_list")
            or payload.get("tracklist")
            or payload.get("trackList")
            or payload.get("tracks")
            or body.get("track_list")
            or body.get("tracklist")
            or body.get("trackList")
            or body.get("tracks")
            or []
        )
        if not isinstance(track_list, list):
            track_list = []

        dst_agent_id = (
            payload.get("dst_agent_id") or body.get("dst_agent_id") or "unknown"
        )
        task_id = payload.get("task_id") or body.get("task_id") or "unknown"

        print(
            f"[Subscribe Track] Received {len(track_list)} tracks for agent {dst_agent_id}, task {task_id}"
        )
        if body_text:
            print(f"[Subscribe Track] Raw body: {body_text}")
        add_log_entry(
            f"ACF subscribe_track received: agent={dst_agent_id} task={task_id} tracks={len(track_list)}",
            "info",
        )

        if not MOQ_AVAILABLE:
            return {
                "status": "error",
                "message": "MOQ not available",
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Filter video tracks and subscribe
        video_tracks = []
        subscribed_tracks = []

        for track_info in track_list:
            if not isinstance(track_info, dict):
                continue

            namespace_str = track_info.get("namespace", "")
            track_name = track_info.get("track", "")
            if not isinstance(namespace_str, str):
                namespace_str = "/".join(str(part) for part in namespace_str if part)
            if not isinstance(track_name, str):
                track_name = str(track_name)

            # Check if it's a video track (case-insensitive)
            normalized_track_name = track_name.lower()
            if normalized_track_name in ["video", "camera", "thermal"]:
                # Parse namespace (e.g., "/task-12345/did:acn:agent:222222222")
                namespace_parts = [p for p in namespace_str.split("/") if p]

                # Create track_id
                track_id = f"{dst_agent_id}_{task_id}_{normalized_track_name}"

                print(
                    f"[Subscribe Track] Subscribing to video track: {track_id}, namespace: {namespace_parts}, track: {track_name}"
                )
                add_log_entry(
                    f"MOQ subscribe request: track_id={track_id} namespace={namespace_str} track={track_name}",
                    "info",
                )

                # Subscribe to MOQ track
                success = await moq_video_subscriber.subscribe_to_track(
                    track_id=track_id,
                    namespace=namespace_parts,
                    track_name=track_name,
                )

                video_tracks.append(
                    {
                        "track_id": track_id,
                        "namespace": namespace_str,
                        "track_name": track_name,
                        "success": success,
                    }
                )

                if success:
                    subscribed_tracks.append(track_id)
                else:
                    add_log_entry(
                        f"MOQ subscribe failed: track_id={track_id} namespace={namespace_str} track={track_name}",
                        "error",
                    )

        # Broadcast to frontend about new video tracks
        if subscribed_tracks:
            await manager.broadcast(
                {
                    "type": "VIDEO_TRACKS_AVAILABLE",
                    "payload": {
                        "agent_id": dst_agent_id,
                        "task_id": task_id,
                        "tracks": video_tracks,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                }
            )

        add_log_entry(
            f"ACF -> Monitor: Subscribed {len(subscribed_tracks)} video tracks for {dst_agent_id}",
            "info",
        )

        return {
            "status": "success",
            "agent_id": dst_agent_id,
            "task_id": task_id,
            "total_tracks": len(track_list),
            "video_tracks": video_tracks,
            "subscribed_count": len(subscribed_tracks),
            "subscription_debug": moq_video_subscriber.get_track_debug_info(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"[Subscribe Track Error] {e}")
        import traceback

        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.post("/acn/v3/pipeline-logs")
async def receive_pipeline_log(request: Dict[str, Any]):
    """Receive pipeline log messages and broadcast to all connected clients"""
    try:
        # Debug: print full request
        print(f"[Pipeline Log] Raw request: {request}")

        # Extract the message body - support both formats:
        # 1. {source, destination, ...} - direct format
        # 2. {body: {source, destination, ...}} - nested format
        if "body" in request and isinstance(request["body"], dict):
            body = request["body"]
        else:
            body = request

        print(f"[Pipeline Log] Body: {body}")

        # Create the log message structure
        log_message = {
            "type": "PIPELINE_LOG",
            "payload": {
                "source": body.get("source", "Unknown"),
                "destination": body.get("destination", "Unknown"),
                "timestamp": body.get("timestamp", datetime.utcnow().isoformat()),
                "task_id": body.get("task_id"),
                "protocol": body.get("protocol", ""),
                "headers": body.get("headers", ""),
                "abstract": body.get("abstract", ""),
                "content": body.get("content", ""),
            },
        }

        log_msg = f"{log_message['payload']['source']} -> {log_message['payload']['destination']}: {log_message['payload']['abstract'] or log_message['payload']['content'][:50]}"
        print(f"[Pipeline Log] {log_msg}")
        add_log_entry(log_msg, "info")
        add_pipeline_log_entry(
            source=log_message["payload"]["source"],
            destination=log_message["payload"]["destination"],
            abstract=log_message["payload"]["abstract"],
            content=log_message["payload"]["content"],
            timestamp=log_message["payload"]["timestamp"],
            task_id=log_message["payload"]["task_id"],
        )

        # Broadcast to all connected WebSocket clients
        await manager.broadcast(log_message)

        # Update agent status based on abstract
        abstract = body.get("abstract", "")
        if abstract:
            work_status, task_desc = get_work_status_from_abstract(abstract)
            if work_status != "idle":
                # Try to extract agent_id from content
                content = body.get("content", {})
                if isinstance(content, str):
                    try:
                        content = json.loads(content)
                    except:
                        content = {}

                agent_id = content.get("agent_id", "")
                agent_name = content.get("agent_name", content.get("name", ""))
                task_id = body.get("task_id", "")

                # Extract agent_id for internal forwarded messages
                if not agent_id and abstract in [
                    "收到/idm/v1/identity-applications请求",
                    "/idm/v1/identity-applications已转发到IDM",
                    "收到/arf/v1/agent-cards请求",
                    "/arf/v1/agent-cards已转发到AgentGW",
                    "/idm/v1/identity-applications响应返回ACN SDK",
                    "/idm/v1/identity-applications上游响应返回",
                    "/arf/v1/agent-cards响应返回ACN SDK",
                    "/arf/v1/agent-cards上游响应返回",
                ]:
                    # Use owner + name to find agent in cache
                    owner = content.get("owner", "")
                    name = content.get("name", "")
                    if name:
                        for cached_id, cached_data in agent_status_cache.items():
                            if cached_data.get("agent_name") == name:
                                agent_id = cached_id
                                break

                # Extract agent_id from MoQ-related messages
                if not agent_id:
                    if abstract == "Publish MoQ track":
                        namespace = content.get("namespace", "")
                        if namespace and "did:udid:" in namespace:
                            parts = namespace.split("/")
                            for part in parts:
                                if part.startswith("did:udid:"):
                                    agent_id = part
                                    break
                    elif abstract == "Announce MoQ published track":
                        payload = content.get("payload", {})
                        agent_id = payload.get("src_agent_id", "")
                    elif abstract == "Send MoQ object":
                        agent_id = task_agent_mapping.get(task_id, "")

                # Update task-agent mapping when we have both
                if agent_id and task_id:
                    task_agent_mapping[task_id] = agent_id

                # Fallback: find agent with this task_id in cache
                if not agent_id and task_id:
                    for cached_id, cached_data in agent_status_cache.items():
                        if task_id in str(cached_data):
                            agent_id = cached_id
                            agent_name = cached_data.get("agent_name", "")
                            break

                if agent_id:
                    timestamp = body.get("timestamp", datetime.utcnow().isoformat())
                    is_demo = bool(content.get("is_demo"))

                    # Update agent status cache
                    if agent_id not in agent_status_cache:
                        agent_status_cache[agent_id] = {
                            "agent_id": agent_id,
                            "agent_name": agent_name or agent_id.split(":")[-1][:20],
                            "work_status": work_status,
                            "current_task": task_desc,
                            "logs": [],
                            "agent_status": "online",
                            "agent_capability": [],
                            "last_update": timestamp,
                            "is_demo": is_demo,
                        }
                    else:
                        agent_status_cache[agent_id]["work_status"] = work_status
                        agent_status_cache[agent_id]["current_task"] = task_desc
                        if agent_name:
                            agent_status_cache[agent_id]["agent_name"] = agent_name
                        agent_status_cache[agent_id]["last_update"] = timestamp
                        if is_demo:
                            agent_status_cache[agent_id]["is_demo"] = True

                    # Broadcast status update
                    status_message = {
                        "type": "AGENT_STATUS_UPDATE",
                        "payload": {
                            "agent_id": agent_id,
                            "agent_name": agent_status_cache[agent_id]["agent_name"],
                            "work_status": work_status,
                            "current_task": task_desc,
                            "log_type": abstract,
                            "element_id": body.get("source", "Pipeline"),
                            "timestamp": timestamp,
                            "agent": agent_status_cache.get(agent_id, {}),
                        },
                    }
                    print(
                        f"[Pipeline Status] {abstract} -> Agent: {agent_id[:30]}... | Status: {work_status}"
                    )
                    await manager.broadcast(status_message)

        return {
            "status": "success",
            "message": "Log received and broadcasted",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"[Pipeline Log Error] {e}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


# Agent status tracking
agent_status_cache: Dict[str, Dict[str, Any]] = {}
# Task to agent mapping for MoQ messages
task_agent_mapping: Dict[str, str] = {}


def get_work_status_from_log_type(log_type: str) -> tuple:
    """Map log_type to work_status and task description"""
    status_map = {
        "ApplyProfile": ("working", "Applying for digital identity"),
        "PublishAgent": ("working", "Registering agent capabilities"),
        "SetupConnection": ("online", "Setting up connection"),
        "LLMMessage": ("working", "Processing LLM message"),
        "TargetTracking": ("tracking", "Tracking target"),
        "LocationTracking": ("tracking", "Tracking location"),
        "VideoTracking": ("tracking", "Tracking video"),
        "PersonExpelling": ("expelling", "Expelling suspicious person"),
        "SuspiciousPerson": ("expelling", "Identifying suspicious person"),
        "EmergencyAlert": ("expelling", "Emergency alert"),
        "TaskExecution": ("working", "Executing task"),
        "VideoStream": ("working", "Streaming video"),
        "LocationUpdate": ("working", "Updating location"),
    }
    return status_map.get(log_type, ("idle", "Unknown task"))


def get_work_status_from_abstract(abstract: str) -> tuple:
    """Map pipeline-logs abstract to work_status and task description"""
    status_map = {
        "Register agent identity": ("working", "Registering identity"),
        "收到/idm/v1/identity-applications请求": ("working", "Applying for identity"),
        "/idm/v1/identity-applications已转发到IDM": (
            "working",
            "Identity application forwarded",
        ),
        "/idm/v1/identity-applications上游响应返回": (
            "working",
            "Identity application response",
        ),
        "/idm/v1/identity-applications响应返回ACN SDK": (
            "working",
            "Identity registered",
        ),
        "Register agent capabilities": ("working", "Registering capabilities"),
        "收到/arf/v1/agent-cards请求": ("working", "Publishing agent card"),
        "/arf/v1/agent-cards已转发到AgentGW": ("working", "Agent card forwarded"),
        "/arf/v1/agent-cards上游响应返回": ("working", "Agent card response"),
        "/arf/v1/agent-cards响应返回ACN SDK": ("working", "Capabilities registered"),
        "Request task execution": ("working", "Executing task"),
        "Request task collaboration": ("working", "Collaborating"),
        "Publish MoQ track": ("tracking", "Publishing video track"),
        "Announce MoQ published track": ("tracking", "Video track published"),
        "Send MoQ object": ("tracking", "Streaming video data"),
        "WebSocket setup handshake": ("online", "Setting up connection"),
    }
    return status_map.get(abstract, ("idle", abstract))


@app.post("/acn/v3/element-logs")
async def receive_element_log(request: Dict[str, Any]):
    """Receive element log messages and update agent work status"""
    try:
        # Support both formats: direct or nested in body
        if "body" in request and isinstance(request["body"], dict):
            body = request["body"]
        else:
            body = request

        element_id = body.get("element_id", "Unknown")
        log_type = body.get("log_type", "Unknown")
        content = body.get("content", {})
        timestamp = body.get("timestamp", datetime.utcnow().isoformat())

        # Extract agent_id from content
        agent_id = content.get("agent_id", "")
        agent_name = content.get("agent_name", "")
        is_demo = bool(content.get("is_demo"))

        # Determine work status based on log_type
        work_status, task_desc = get_work_status_from_log_type(log_type)

        # Create log entry
        log_entry = {
            "time": datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime(
                "%H:%M:%S"
            )
            if "T" in timestamp
            else datetime.now().strftime("%H:%M:%S"),
            "level": "info",
            "message": f"{log_type}: {task_desc}",
        }

        # Add to log buffer
        add_log_entry(f"[{element_id}] {agent_id}: {log_type} - {task_desc}", "info")

        # Update agent status cache
        if agent_id:
            if agent_id not in agent_status_cache:
                agent_status_cache[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": agent_name or agent_id.split(":")[-1][:20],
                    "work_status": work_status,
                    "current_task": task_desc,
                    "logs": [],
                    "agent_status": "online",
                    "agent_capability": content.get("agent_capability", [])
                    if isinstance(content.get("agent_capability"), list)
                    else [content.get("agent_capability", "")]
                    if content.get("agent_capability")
                    else [],
                    "last_update": timestamp,
                    "is_demo": is_demo,
                }
            else:
                # Update existing agent status
                agent_status_cache[agent_id]["work_status"] = work_status
                agent_status_cache[agent_id]["current_task"] = task_desc
                if agent_name:
                    agent_status_cache[agent_id]["agent_name"] = agent_name
                agent_status_cache[agent_id]["last_update"] = timestamp
                if is_demo:
                    agent_status_cache[agent_id]["is_demo"] = True

            # Add log entry
            agent_status_cache[agent_id]["logs"].append(log_entry)
            # Keep only last 10 logs
            if len(agent_status_cache[agent_id]["logs"]) > 10:
                agent_status_cache[agent_id]["logs"] = agent_status_cache[agent_id][
                    "logs"
                ][-10:]

        # Create update message
        update_message = {
            "type": "AGENT_STATUS_UPDATE",
            "payload": {
                "agent_id": agent_id,
                "agent_name": agent_name
                or (agent_status_cache.get(agent_id, {}).get("agent_name", "")),
                "work_status": work_status,
                "current_task": task_desc,
                "log_type": log_type,
                "element_id": element_id,
                "timestamp": timestamp,
                "log": log_entry,
                "agent": agent_status_cache.get(agent_id, {}) if agent_id else None,
            },
        }

        print(
            f"[Element Log] {element_id} | {log_type} | Agent: {agent_id[:30] if agent_id else 'N/A'}... | Status: {work_status}"
        )

        # Broadcast to all connected WebSocket clients
        await manager.broadcast(update_message)

        return {
            "status": "success",
            "message": "Element log received and agent status updated",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"[Element Log Error] {e}")
        import traceback

        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)

    try:
        # Send initial data
        agents = _merge_agent_sources()
        await manager.send_to(
            websocket, {"type": "AGENT_LIST", "payload": {"agents": agents}}
        )
        await manager.send_to(
            websocket, {"type": "DASHBOARD_SNAPSHOT", "payload": build_dashboard_snapshot()}
        )

        while True:
            # Receive and handle messages from client
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "DISPATCH_TASK":
                    payload = message.get("payload", {})
                    print(f"[Task] Dispatched: {payload}")

                    # Broadcast to all clients
                    await manager.broadcast(
                        {"type": "TASK_DISPATCHED", "payload": payload}
                    )

                elif msg_type == "EMERGENCY_LAND":
                    print("[Emergency] Landing command received")
                    await manager.broadcast(
                        {
                            "type": "EMERGENCY_LAND",
                            "payload": {"timestamp": datetime.utcnow().isoformat()},
                        }
                    )

                elif msg_type == "ABORT_ALL":
                    print("[Abort] All tasks command received")
                    await manager.broadcast(
                        {
                            "type": "ABORT_ALL",
                            "payload": {"timestamp": datetime.utcnow().isoformat()},
                        }
                    )

                elif msg_type == "PING":
                    await manager.send_to(
                        websocket,
                        {"type": "PONG", "timestamp": datetime.utcnow().isoformat()},
                    )

                elif msg_type == "REFRESH":
                    print("[Refresh] Clear environment request received")

                    # Call ARF /clear endpoint
                    result = await call_arf_clear()

                    if result.get("success"):
                        agent_status_cache.clear()
                        task_agent_mapping.clear()
                        pipeline_log_buffer.clear()
                        task_control_registry.clear()
                        control_task_history.clear()
                        # Get fresh agent list after clear
                        agents = _merge_agent_sources()

                        # Broadcast refresh completion to all clients
                        await manager.broadcast(
                            {
                                "type": "REFRESH_COMPLETE",
                                "payload": {
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "agents": agents,
                                    "arf_response": result.get("response"),
                                    "dashboard": build_dashboard_snapshot(),
                                    "tasks": build_control_tasks_snapshot(),
                                },
                            }
                        )
                        print("[Refresh] Environment cleared and agent list refreshed")
                    else:
                        # Send error to requesting client
                        await manager.send_to(
                            websocket,
                            {
                                "type": "REFRESH_ERROR",
                                "payload": {
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "error": result.get("error", "Unknown error"),
                                    "detail": result.get("detail", ""),
                                },
                            },
                        )
                        print(f"[Refresh Error] {result.get('error')}")

            except json.JSONDecodeError:
                print("[WebSocket] Invalid JSON received")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WebSocket Error] {e}")
        manager.disconnect(websocket)


# Background task to broadcast updates
async def broadcast_agent_updates():
    """Periodically broadcast agent updates to all clients"""
    while True:
        await asyncio.sleep(1)  # Update every 1 second

        if manager.active_connections:
            try:
                agents = _merge_agent_sources()
                await manager.broadcast(
                    {"type": "AGENT_LIST", "payload": {"agents": agents}}
                )
                await manager.broadcast(
                    {"type": "DASHBOARD_SNAPSHOT", "payload": build_dashboard_snapshot()}
                )
            except Exception as e:
                print(f"[Broadcast Error] {e}")


# Serve static files (React build)
try:
    from starlette.staticfiles import StaticFiles as StarletteStaticFiles
    from starlette.responses import Response

    class NoCacheStaticFiles(StarletteStaticFiles):
        """Custom StaticFiles that adds no-cache headers"""

        async def get_response(self, path: str, scope):
            response = await super().get_response(path, scope)
            # Add cache control headers to prevent caching
            response.headers["Cache-Control"] = (
                "no-cache, no-store, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

    app.mount(
        "/static",
        NoCacheStaticFiles(directory="/root/lpx/webui/frontend/build/static"),
        name="static",
    )

    @app.get("/")
    async def serve_react():
        """Serve React frontend with no-cache headers"""
        response = FileResponse(
            "/root/lpx/webui/frontend/build/index.html",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
        return response

    @app.get("/{path:path}")
    async def serve_react_routes(path: str):
        """Serve React frontend for all routes with no-cache headers"""
        response = FileResponse(
            "/root/lpx/webui/frontend/build/index.html",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
        return response

    # Video Stream API Endpoints
    @app.get("/api/video/streams")
    async def get_video_streams():
        """Get all active video streams"""
        return {
            "streams": video_stream_manager.get_all_streams(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    @app.get("/api/video/streams/{agent_id}")
    async def get_agent_video_streams(agent_id: str):
        """Get video streams for a specific agent"""
        streams = video_stream_manager.get_agent_streams(agent_id)
        return {
            "agent_id": agent_id,
            "streams": [s.to_dict() for s in streams],
            "timestamp": datetime.utcnow().isoformat(),
        }

    @app.post("/api/video/streams/{agent_id}/register")
    async def register_video_stream(agent_id: str, request: Dict[str, Any]):
        """Register a new video stream from an agent"""
        agent_name = request.get("agent_name", agent_id)
        stream_type = request.get("stream_type", "camera")
        resolution = request.get("resolution", "1920x1080")
        fps = request.get("fps", 30)

        stream = video_stream_manager.register_stream(
            agent_id=agent_id,
            agent_name=agent_name,
            stream_type=stream_type,
            resolution=resolution,
            fps=fps,
        )

        # Broadcast to all clients
        await video_stream_manager.broadcast_stream_list()

        return {
            "status": "success",
            "stream": stream.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    @app.post("/api/video/webrtc/offer")
    async def handle_webrtc_offer(request: Dict[str, Any]):
        """Handle WebRTC offer from agent (agent wants to stream)"""
        stream_id = request.get("stream_id")
        offer = request.get("offer")

        if not stream_id or not offer:
            return {"status": "error", "message": "Missing stream_id or offer"}

        video_stream_manager.set_webrtc_offer(stream_id, offer)
        stream = video_stream_manager.get_stream(stream_id)

        if stream:
            # In a real implementation, you would:
            # 1. Create a WebRTC peer connection on the server
            # 2. Set the remote description (offer)
            # 3. Create an answer
            # 4. Return the answer to the agent

            # For now, we'll simulate this
            await video_stream_manager.broadcast_stream_update(stream_id)

            return {
                "status": "success",
                "stream_id": stream_id,
                "message": "Offer received, waiting for viewer to connect",
                "timestamp": datetime.utcnow().isoformat(),
            }

        return {"status": "error", "message": "Stream not found"}

    @app.post("/api/video/webrtc/answer")
    async def handle_webrtc_answer(request: Dict[str, Any]):
        """Handle WebRTC answer from viewer (browser wants to watch)"""
        stream_id = request.get("stream_id")
        answer = request.get("answer")

        if not stream_id or not answer:
            return {"status": "error", "message": "Missing stream_id or answer"}

        video_stream_manager.set_webrtc_answer(stream_id, answer)
        video_stream_manager.update_stream_status(stream_id, StreamStatus.STREAMING)

        await video_stream_manager.broadcast_stream_update(stream_id)

        return {
            "status": "success",
            "stream_id": stream_id,
            "message": "Viewer connected",
            "timestamp": datetime.utcnow().isoformat(),
        }

    @app.post("/api/video/webrtc/ice")
    async def handle_ice_candidate(request: Dict[str, Any]):
        """Handle ICE candidate exchange"""
        stream_id = request.get("stream_id")
        candidate = request.get("candidate")
        is_agent = request.get(
            "is_agent", True
        )  # True if from agent, False if from viewer

        if stream_id and candidate:
            video_stream_manager.add_ice_candidate(
                stream_id, {"candidate": candidate, "is_agent": is_agent}
            )

            # Broadcast ICE candidate to the other party
            await manager.broadcast(
                {
                    "type": "WEBRTC_ICE_CANDIDATE",
                    "payload": {
                        "stream_id": stream_id,
                        "candidate": candidate,
                        "from_agent": is_agent,
                    },
                }
            )

            return {"status": "success"}

        return {"status": "error", "message": "Missing stream_id or candidate"}

    @app.delete("/api/video/streams/{stream_id}")
    async def unregister_video_stream(stream_id: str):
        """Unregister a video stream"""
        video_stream_manager.unregister_stream(stream_id)
        await video_stream_manager.broadcast_stream_list()

        return {
            "status": "success",
            "stream_id": stream_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

except Exception as e:
    print(f"[Warning] React build not found or error: {e}. API only mode.")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=9005, reload=False, log_level="info"
    )
