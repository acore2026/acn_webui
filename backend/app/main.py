#!/usr/bin/env python3
"""
ACN Agent Monitor Backend
FastAPI + WebSocket server for agent monitoring
Port: 9005
"""

import asyncio
import base64
import json
import os
import secrets
import socket
import sqlite3
import re
import tempfile
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
from contextlib import asynccontextmanager
import uvicorn
from typing import List, Dict, Any, Optional
import httpx
from cryptography import x509
from cryptography.x509.oid import NameOID

# Import video stream manager
from .video_stream import video_stream_manager, StreamStatus

# Import MOQ video subscriber
try:
    from .moq_video import moq_video_subscriber, VideoFrame

    MOQ_AVAILABLE = True
except ImportError as e:
    print(f"[Warning] MOQ video subscriber not available: {e}")
    MOQ_AVAILABLE = False

# Database paths and source settings
ROOT_DIR = Path(__file__).resolve().parents[2]
EXTERNAL_DB_DEFAULT_PATH = "/home/acn/zqm/acn_gw/agent_gw/agent_gw.db"
LOCAL_CACHE_DB_PATH = ROOT_DIR / "logs" / "webui_local_state.db"
DATA_SOURCE_SETTINGS_PATH = ROOT_DIR / "logs" / "data_source_settings.json"
CERT_DB_PATH = ROOT_DIR / "logs" / "certificates.db"
CERT_STORAGE_DIR = ROOT_DIR / "logs" / "cert_store"
IDM_CERT_UPLOAD_URL = "http://127.0.0.1:9020/idm/v1/cert-upload"
IDM_CERT_DELETE_URL = "http://127.0.0.1:9020/idm/v1/cert-delete"
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

NETWORK_ELEMENT_CONTROL_SCRIPTS = {
    "acn-agent": {
        "id": "acn-agent",
        "name": "ACN Agent",
        "script": Path("/home/acn/cxr/acn_agent/start_acn_agent.sh"),
        "description": "Controls the ACN Agent execution runtime.",
    },
    "agent-gw": {
        "id": "agent-gw",
        "name": "AgentGW",
        "script": Path("/home/acn/zqm/acn_gw/start_agent_gw.sh"),
        "description": "Controls ARF, ACF, and Relay services in AgentGW.",
    },
    "idm": {
        "id": "idm",
        "name": "IDM",
        "script": Path("/home/acn/cx/idm/start_idm.sh"),
        "description": "Controls the IDM identity verification service.",
    },
}
NETWORK_ELEMENT_CONTROL_ACTIONS = {"start", "stop", "restart"}

FLOW_NODE_LAYOUTS = {
    "ACN Agent": {"x": -260, "y": 300},
    "IDM": {"x": 250, "y": 70},
    "ARF": {"x": 760, "y": 130},
    "ACF": {"x": 760, "y": 300},
    "Relay": {"x": 760, "y": 470},
    "ACN SDK": {"x": 250, "y": 800},
}

MESSAGE_FLOW_TTL_SECONDS = 1
MESSAGE_FLOW_ACTIVE_SECONDS = 1
message_flow_display_runtime = {
    "ttl_seconds": float(MESSAGE_FLOW_TTL_SECONDS),
    "active_seconds": float(MESSAGE_FLOW_ACTIVE_SECONDS),
}

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

DATA_SOURCE_SETTINGS_LOCK = threading.Lock()
DEFAULT_DATA_SOURCE_SETTINGS = {
    "useExternalDb": True,
    "externalDbPath": EXTERNAL_DB_DEFAULT_PATH,
}


def _ensure_runtime_dirs() -> None:
    LOCAL_CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_SOURCE_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CERT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    CERT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _load_data_source_settings() -> Dict[str, Any]:
    _ensure_runtime_dirs()
    if not DATA_SOURCE_SETTINGS_PATH.exists():
        return dict(DEFAULT_DATA_SOURCE_SETTINGS)

    try:
        raw = json.loads(DATA_SOURCE_SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_DATA_SOURCE_SETTINGS)

    settings = dict(DEFAULT_DATA_SOURCE_SETTINGS)
    if isinstance(raw, dict):
        settings["useExternalDb"] = bool(raw.get("useExternalDb", settings["useExternalDb"]))
        external_path = str(raw.get("externalDbPath") or settings["externalDbPath"]).strip()
        settings["externalDbPath"] = external_path or EXTERNAL_DB_DEFAULT_PATH
    return settings


def _save_data_source_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {
        "useExternalDb": bool(settings.get("useExternalDb", True)),
        "externalDbPath": str(settings.get("externalDbPath") or EXTERNAL_DB_DEFAULT_PATH).strip()
        or EXTERNAL_DB_DEFAULT_PATH,
    }
    _ensure_runtime_dirs()
    with DATA_SOURCE_SETTINGS_LOCK:
        DATA_SOURCE_SETTINGS_PATH.write_text(
            json.dumps(normalized, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    return normalized


data_source_settings: Dict[str, Any] = _load_data_source_settings()


def get_data_source_settings() -> Dict[str, Any]:
    return dict(data_source_settings)


def get_external_db_path() -> str:
    return str(data_source_settings.get("externalDbPath") or EXTERNAL_DB_DEFAULT_PATH)


def should_use_external_db() -> bool:
    return bool(data_source_settings.get("useExternalDb", True))


def get_local_cache_db_path() -> str:
    return str(LOCAL_CACHE_DB_PATH)


def ensure_local_cache_db() -> None:
    _ensure_runtime_dirs()
    conn = sqlite3.connect(LOCAL_CACHE_DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                agent_name TEXT,
                agent_capability TEXT DEFAULT '[]',
                agent_status TEXT DEFAULT 'offline',
                work_status TEXT DEFAULT 'idle',
                current_task TEXT DEFAULT '',
                last_update TEXT,
                launch_time TEXT,
                offline_time TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        for column_name in ("launch_time", "offline_time"):
            try:
                cursor.execute(f"ALTER TABLE agents ADD COLUMN {column_name} TEXT")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                task_description TEXT DEFAULT '',
                task_name TEXT DEFAULT '',
                task_type TEXT DEFAULT '',
                status TEXT DEFAULT 'processing',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(agent_id, task_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ingested_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_kind TEXT NOT NULL,
                source_name TEXT,
                agent_id TEXT,
                task_id TEXT,
                summary TEXT,
                payload_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_task_id ON tasks(task_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)"
        )
        conn.commit()
    finally:
        conn.close()


def _connect_external_db_readonly(path: str) -> sqlite3.Connection:
    normalized = str(path or "").strip()
    if not normalized:
        raise FileNotFoundError("External database path is empty")
    if not Path(normalized).exists():
        raise FileNotFoundError(f"External database does not exist: {normalized}")
    conn = sqlite3.connect(f"file:{normalized}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_external_db_writable(path: str) -> sqlite3.Connection:
    normalized = str(path or "").strip()
    if not normalized:
        raise FileNotFoundError("External database path is empty")
    parent = Path(normalized).expanduser().resolve().parent
    if not parent.exists():
        raise FileNotFoundError(f"External database directory does not exist: {parent}")
    conn = sqlite3.connect(normalized)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_local_cache_db() -> sqlite3.Connection:
    ensure_local_cache_db()
    conn = sqlite3.connect(LOCAL_CACHE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_cert_db() -> None:
    _ensure_runtime_dirs()
    conn = sqlite3.connect(CERT_DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS certificates (
                cert_id TEXT PRIMARY KEY,
                cert_name TEXT NOT NULL,
                authority TEXT NOT NULL,
                validity TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _connect_cert_db() -> sqlite3.Connection:
    ensure_cert_db()
    conn = sqlite3.connect(CERT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _list_certificates() -> List[Dict[str, Any]]:
    conn = _connect_cert_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT cert_id, cert_name, authority, validity, uploaded_at
            FROM certificates
            ORDER BY uploaded_at DESC, cert_name ASC
            """
        )
        rows = cursor.fetchall()
        return [
            {
                "certID": row["cert_id"],
                "certName": row["cert_name"],
                "authority": row["authority"],
                "validity": row["validity"],
                "uploadedAt": row["uploaded_at"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def _generate_cert_id() -> str:
    ensure_cert_db()
    conn = _connect_cert_db()
    try:
        cursor = conn.cursor()
        while True:
            cert_id = f"cert-{secrets.randbelow(100000000):08d}"
            cursor.execute(
                "SELECT 1 FROM certificates WHERE cert_id = ? LIMIT 1",
                (cert_id,),
            )
            if cursor.fetchone() is None:
                return cert_id
    finally:
        conn.close()


def _decode_x509_certificate(cert_bytes: bytes) -> Dict[str, str]:
    try:
        certificate = x509.load_pem_x509_certificate(cert_bytes)
    except ValueError:
        certificate = x509.load_der_x509_certificate(cert_bytes)

    common_names = certificate.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
    authority = (
        str(common_names[0].value).strip()
        if common_names and str(common_names[0].value).strip()
        else certificate.issuer.rfc4514_string()
    )

    not_valid_before = getattr(certificate, "not_valid_before_utc", None) or certificate.not_valid_before
    not_valid_after = getattr(certificate, "not_valid_after_utc", None) or certificate.not_valid_after
    validity = f"{not_valid_before.strftime('%Y-%m-%d')} to {not_valid_after.strftime('%Y-%m-%d')}"
    return {"authority": authority, "validity": validity}


async def _read_certificate_upload(
    file: Optional[UploadFile], file_path: Optional[str]
) -> Dict[str, Any]:
    normalized_path = str(file_path or "").strip()
    if file is not None and file.filename:
        cert_name = Path(file.filename).name
        cert_bytes = await file.read()
        if not cert_bytes:
            raise HTTPException(status_code=400, detail="Uploaded certificate file is empty.")
        return {"cert_name": cert_name, "cert_bytes": cert_bytes}

    if normalized_path:
        source_path = Path(normalized_path).expanduser()
        if not source_path.exists() or not source_path.is_file():
            raise HTTPException(
                status_code=400,
                detail=f"Certificate file path does not exist: {normalized_path}",
            )
        cert_bytes = source_path.read_bytes()
        if not cert_bytes:
            raise HTTPException(status_code=400, detail="Certificate file is empty.")
        return {"cert_name": source_path.name, "cert_bytes": cert_bytes}

    raise HTTPException(
        status_code=400,
        detail="Provide a certificate file or a certificate file path.",
    )


async def _forward_certificate_to_idm(
    cert_id: str, cert_name: str, cert_bytes: bytes
) -> Dict[str, Any]:
    add_log_entry(
        f"[Cert Upload] Sending certificate to IDM: POST /idm/v1/cert-upload certID={cert_id} certName={cert_name}",
        "info",
    )
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.post(
                IDM_CERT_UPLOAD_URL,
                data={"certID": cert_id, "certName": cert_name},
                files={"file": (cert_name, cert_bytes, "application/octet-stream")},
                timeout=20.0,
            )
    except httpx.ConnectError as exc:
        add_log_entry(
            f"[Cert Upload] IDM connection failed for certID={cert_id}: {exc}",
            "error",
        )
        raise HTTPException(
            status_code=502,
            detail=f"Cannot connect to IDM certificate upload endpoint: {exc}",
        ) from exc
    except Exception as exc:
        add_log_entry(
            f"[Cert Upload] IDM request error for certID={cert_id}: {exc}",
            "error",
        )
        raise HTTPException(
            status_code=502,
            detail=f"Certificate upload to IDM failed: {exc}",
        ) from exc

    add_log_entry(
        f"[Cert Upload] IDM response for certID={cert_id}: HTTP {response.status_code}",
        "info" if response.status_code == 200 else "error",
    )
    if response.status_code != 200:
        body = response.text.strip()
        if body:
            add_log_entry(
                f"[Cert Upload] IDM rejected certID={cert_id}: {body}",
                "error",
            )
        raise HTTPException(
            status_code=502,
            detail=body or f"IDM certificate upload failed with HTTP {response.status_code}. Expected 200 OK.",
        )

    try:
        parsed_body: Any = response.json()
    except ValueError:
        parsed_body = response.text

    return {
        "statusCode": response.status_code,
        "ok": response.status_code == 200,
        "body": parsed_body,
    }


async def _forward_certificate_delete_to_idm(
    cert_id: str, cert_name: str
) -> Dict[str, Any]:
    payload = {"certID": cert_id, "certName": cert_name}
    add_log_entry(
        f"[Cert Delete] Sending delete request to IDM: POST /idm/v1/cert-delete certID={cert_id} certName={cert_name}",
        "info",
    )
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.post(
                IDM_CERT_DELETE_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=20.0,
            )
    except httpx.ConnectError as exc:
        add_log_entry(
            f"[Cert Delete] IDM connection failed for certID={cert_id}: {exc}",
            "error",
        )
        raise HTTPException(
            status_code=502,
            detail=f"Cannot connect to IDM certificate delete endpoint: {exc}",
        ) from exc
    except Exception as exc:
        add_log_entry(
            f"[Cert Delete] IDM request error for certID={cert_id}: {exc}",
            "error",
        )
        raise HTTPException(
            status_code=502,
            detail=f"Certificate delete request to IDM failed: {exc}",
        ) from exc

    add_log_entry(
        f"[Cert Delete] IDM response for certID={cert_id}: HTTP {response.status_code}",
        "info" if response.status_code == 200 else "error",
    )
    if response.status_code != 200:
        body = response.text.strip()
        if body:
            add_log_entry(
                f"[Cert Delete] IDM rejected certID={cert_id}: {body}",
                "error",
            )
        raise HTTPException(
            status_code=502,
            detail=body or f"IDM certificate delete failed with HTTP {response.status_code}. Expected 200 OK.",
        )

    try:
        parsed_body: Any = response.json()
    except ValueError:
        parsed_body = response.text

    return {
        "statusCode": response.status_code,
        "ok": response.status_code == 200,
        "body": parsed_body,
    }


def _store_certificate_record(
    cert_id: str,
    cert_name: str,
    authority: str,
    validity: str,
    cert_bytes: bytes,
) -> Dict[str, Any]:
    suffix = Path(cert_name).suffix or ".crt"
    stored_path = CERT_STORAGE_DIR / f"{cert_id}{suffix}"
    stored_path.write_bytes(cert_bytes)

    uploaded_at = datetime.utcnow().isoformat()
    conn = _connect_cert_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO certificates (cert_id, cert_name, authority, validity, stored_path, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (cert_id, cert_name, authority, validity, str(stored_path), uploaded_at),
        )
        conn.commit()
    except Exception:
        if stored_path.exists():
            stored_path.unlink()
        raise
    finally:
        conn.close()

    return {
        "certID": cert_id,
        "certName": cert_name,
        "authority": authority,
        "validity": validity,
        "uploadedAt": uploaded_at,
    }


def _delete_certificate_record(cert_id: str) -> None:
    normalized_cert_id = str(cert_id or "").strip()
    if not normalized_cert_id:
        return

    conn = _connect_cert_db()
    stored_path: Optional[Path] = None
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT stored_path
            FROM certificates
            WHERE cert_id = ?
            """,
            (normalized_cert_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return

        stored_path = Path(str(row["stored_path"]))
        cursor.execute("DELETE FROM certificates WHERE cert_id = ?", (normalized_cert_id,))
        conn.commit()
    finally:
        conn.close()

    if stored_path and stored_path.exists():
        stored_path.unlink()


def _upsert_local_agent(
    agent_id: str,
    *,
    agent_name: Optional[str] = None,
    agent_status: Optional[str] = None,
    work_status: Optional[str] = None,
    current_task: Optional[str] = None,
    agent_capability: Optional[List[str]] = None,
    last_update: Optional[str] = None,
    launch_time: Optional[str] = None,
    offline_time: Optional[str] = None,
) -> None:
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        return

    now_iso = datetime.utcnow().isoformat()
    conn = _connect_local_cache_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT agent_name, agent_capability, agent_status, work_status, current_task, last_update, launch_time, offline_time
            FROM agents
            WHERE agent_id = ?
            """,
            (normalized_agent_id,),
        )
        row = cursor.fetchone()
        capability_json = (
            json.dumps(agent_capability)
            if agent_capability is not None
            else (row["agent_capability"] if row else "[]")
        )
        resolved_name = (
            str(agent_name).strip()
            if agent_name is not None and str(agent_name).strip()
            else (row["agent_name"] if row else normalized_agent_id)
        )
        resolved_status = (
            str(agent_status).strip()
            if agent_status is not None and str(agent_status).strip()
            else (row["agent_status"] if row else "offline")
        )
        resolved_work_status = (
            str(work_status).strip()
            if work_status is not None and str(work_status).strip()
            else (row["work_status"] if row else "idle")
        )
        resolved_task = (
            str(current_task)
            if current_task is not None
            else (row["current_task"] if row else "")
        )
        resolved_last_update = (
            str(last_update).strip()
            if last_update is not None and str(last_update).strip()
            else (row["last_update"] if row else now_iso)
        )
        resolved_launch_time = (
            str(launch_time).strip()
            if launch_time is not None and str(launch_time).strip()
            else (row["launch_time"] if row else None)
        )
        resolved_offline_time = (
            str(offline_time).strip()
            if offline_time is not None and str(offline_time).strip()
            else (row["offline_time"] if row else None)
        )

        if resolved_work_status != "idle" and resolved_status == "offline":
            resolved_status = "online"
        if resolved_status == "offline":
            resolved_offline_time = resolved_offline_time or resolved_last_update or now_iso
        else:
            resolved_launch_time = resolved_launch_time or resolved_last_update or now_iso
            resolved_offline_time = None

        cursor.execute(
            """
            INSERT INTO agents (
                agent_id, agent_name, agent_capability, agent_status, work_status, current_task, last_update, launch_time, offline_time, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                agent_name = excluded.agent_name,
                agent_capability = excluded.agent_capability,
                agent_status = excluded.agent_status,
                work_status = excluded.work_status,
                current_task = excluded.current_task,
                last_update = excluded.last_update,
                launch_time = excluded.launch_time,
                offline_time = excluded.offline_time,
                updated_at = excluded.updated_at
            """,
            (
                normalized_agent_id,
                resolved_name,
                capability_json,
                resolved_status,
                resolved_work_status,
                resolved_task,
                resolved_last_update,
                resolved_launch_time,
                resolved_offline_time,
                now_iso,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _upsert_local_task(
    task_id: str,
    agent_id: str,
    *,
    task_description: str = "",
    task_name: str = "",
    task_type: str = "",
    status: str = "processing",
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> None:
    normalized_task_id = str(task_id or "").strip()
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_task_id or not normalized_agent_id:
        return

    now_iso = datetime.utcnow().isoformat()
    created_value = str(created_at or now_iso)
    updated_value = str(updated_at or now_iso)

    conn = _connect_local_cache_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (
                agent_id, task_id, task_description, task_name, task_type, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, task_id) DO UPDATE SET
                task_description = excluded.task_description,
                task_name = excluded.task_name,
                task_type = excluded.task_type,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                normalized_agent_id,
                normalized_task_id,
                str(task_description or ""),
                str(task_name or ""),
                str(task_type or ""),
                str(status or "processing"),
                created_value,
                updated_value,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _remove_local_task(task_id: str) -> None:
    normalized_task_id = str(task_id or "").strip()
    if not normalized_task_id:
        return
    conn = _connect_local_cache_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE task_id = ?", (normalized_task_id,))
        conn.commit()
    finally:
        conn.close()


def _record_local_log(
    source_kind: str,
    summary: str,
    payload: Dict[str, Any],
    *,
    source_name: Optional[str] = None,
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> None:
    conn = _connect_local_cache_db()
    try:
        conn.execute(
            """
            INSERT INTO ingested_logs (
                source_kind, source_name, agent_id, task_id, summary, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(source_kind),
                str(source_name or ""),
                str(agent_id or ""),
                str(task_id or ""),
                str(summary or ""),
                json.dumps(payload, ensure_ascii=True),
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _reset_local_cache_state() -> None:
    conn = _connect_local_cache_db()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks")
        cursor.execute("DELETE FROM agents")
        cursor.execute("DELETE FROM ingested_logs")
        conn.commit()
    finally:
        conn.close()


def _prime_local_cache_from_runtime_state() -> None:
    ensure_local_cache_db()
    for agent_id, cached in agent_status_cache.items():
        _upsert_local_agent(
            agent_id,
            agent_name=cached.get("agent_name"),
            agent_status=cached.get("agent_status"),
            work_status=cached.get("work_status"),
            current_task=cached.get("current_task"),
            agent_capability=cached.get("agent_capability")
            if isinstance(cached.get("agent_capability"), list)
            else None,
            last_update=cached.get("last_update"),
            launch_time=cached.get("launch_time"),
            offline_time=cached.get("offline_time"),
        )

    for task_id, metadata in task_control_registry.items():
        if metadata.get("status") != "processing":
            continue
        for agent_id in metadata.get("agent_ids", []):
            _upsert_local_task(
                str(task_id),
                str(agent_id),
                task_description=str(metadata.get("task_description") or ""),
                task_name=str(metadata.get("task_name") or ""),
                task_type=str(metadata.get("task_type") or ""),
                status="processing",
                created_at=str(metadata.get("created_at") or datetime.utcnow().isoformat()),
                updated_at=str(metadata.get("updated_at") or datetime.utcnow().isoformat()),
            )


def _insert_task_record(
    agent_id: str,
    task_id: str,
    task_description: str,
    *,
    task_name: str = "",
    task_type: str = "",
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> None:
    if should_use_external_db():
        conn = _connect_external_db_writable(get_external_db_path())
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tasks (agent_id, task_id, task_description) VALUES (?, ?, ?)",
                (agent_id, task_id, task_description),
            )
            conn.commit()
        finally:
            conn.close()

    _upsert_local_task(
        task_id,
        agent_id,
        task_description=task_description,
        task_name=task_name,
        task_type=task_type,
        status="processing",
        created_at=created_at,
        updated_at=updated_at,
    )


def _delete_task_records(task_id: str) -> None:
    if should_use_external_db():
        conn = _connect_external_db_writable(get_external_db_path())
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.commit()
        finally:
            conn.close()

    _remove_local_task(task_id)


def _parse_json_if_needed(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _claim_agent_names_from_content(value: Any, target_agent_id: str = "") -> List[str]:
    value = _parse_json_if_needed(value)
    names: List[str] = []

    if isinstance(value, list):
        for item in value:
            names.extend(_claim_agent_names_from_content(item, target_agent_id))
        return names

    if not isinstance(value, dict):
        return names

    claims = value.get("claims") if isinstance(value.get("claims"), dict) else None
    if claims:
        claim_agent_id = str(claims.get("agent_id") or "").strip()
        claim_agent_name = str(claims.get("agent_name") or "").strip()
        if claim_agent_name and (not target_agent_id or claim_agent_id == target_agent_id):
            names.append(claim_agent_name)

    for key in ("vc_list", "credentials", "vcs"):
        if isinstance(value.get(key), list):
            names.extend(_claim_agent_names_from_content(value[key], target_agent_id))

    for key, nested in value.items():
        if str(key).startswith("vc") and isinstance(nested, dict):
            names.extend(_claim_agent_names_from_content(nested, target_agent_id))

    return names


def _agent_claim_name_lookup(limit: int = 5000) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    try:
        conn = _connect_local_cache_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT agent_id, payload_json
                FROM ingested_logs
                WHERE payload_json IS NOT NULL
                  AND payload_json != ''
                  AND payload_json LIKE '%agent_name%'
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()
    except Exception:
        return lookup

    for row in rows:
        agent_id = str(row["agent_id"] or "").strip()
        payload = _parse_json_if_needed(row["payload_json"])
        content = payload.get("content") if isinstance(payload, dict) else payload
        if not agent_id and isinstance(content, dict):
            agent_id = str(content.get("agent_id") or "").strip()
        if not agent_id:
            continue

        names = _claim_agent_names_from_content(content, agent_id)
        if names:
            lookup.setdefault(agent_id, names[0])
    return lookup


def _is_identifier_like_name(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return (
        not normalized
        or normalized.startswith("did:")
        or normalized.startswith("type")
        or "self_id" in normalized
        or "@6gc." in normalized
    )


def _resolve_agent_display_name(
    agent: Dict[str, Any], claim_name_lookup: Optional[Dict[str, str]] = None
) -> str:
    agent_id = str(agent.get("agent_id") or "").strip()
    claim_name = (claim_name_lookup or {}).get(agent_id, "")
    current_name = str(agent.get("agent_name") or "").strip()

    if claim_name and (_is_identifier_like_name(current_name) or current_name == agent_id):
        return claim_name
    return current_name or claim_name or agent_id


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


def _list_all_video_tracks() -> List[Dict[str, Any]]:
    tracks: List[Dict[str, Any]] = []
    if MOQ_AVAILABLE:
        tracks.extend(moq_video_subscriber.list_discovered_tracks())
    return sorted(tracks, key=lambda item: item.get("lastSeen") or "", reverse=True)


async def _broadcast_video_tracks() -> None:
    await manager.broadcast(
        {
            "type": "VIDEO_TRACKS_AVAILABLE",
            "payload": {
                "tracks": _list_all_video_tracks(),
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
    )


def _normalize_virtual_agent_capabilities(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [
        part.strip()
        for part in str(value or "").split(",")
        if part.strip()
    ]


def _build_virtual_agent_id(agent_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", agent_name.lower()).strip("-")
    slug = slug or "virtual-agent"
    return f"did:acn:agent:virtual-{slug}-{secrets.token_hex(3)}"


async def add_virtual_agent(request: Dict[str, Any]) -> Dict[str, Any]:
    agent_name = str(request.get("agentName") or request.get("agent_name") or "").strip()
    if not agent_name:
        raise HTTPException(status_code=400, detail="Agent name is required.")

    agent_id = str(request.get("agentId") or request.get("agent_id") or "").strip()
    if not agent_id:
        agent_id = _build_virtual_agent_id(agent_name)

    capabilities = _normalize_virtual_agent_capabilities(
        request.get("capabilities") or request.get("agentCapability") or request.get("agent_capability")
    )
    agent_status = str(request.get("status") or "online").strip().lower()
    if agent_status not in {"online", "busy", "offline"}:
        agent_status = "online"

    current_task = str(request.get("currentTask") or request.get("current_task") or "").strip()
    work_status = "working" if agent_status == "busy" or current_task else "idle"
    if current_task and agent_status == "online":
        agent_status = "busy"

    now_iso = datetime.utcnow().isoformat()
    cache_entry = _ensure_agent_cache_entry(agent_id, agent_name=agent_name)
    cache_entry["agent_name"] = agent_name
    cache_entry["agent_capability"] = capabilities
    cache_entry["agent_status"] = "offline" if agent_status == "offline" else "online"
    cache_entry["work_status"] = work_status
    cache_entry["current_task"] = current_task
    cache_entry["is_demo"] = True
    cache_entry["is_virtual"] = True
    _sync_agent_timeline(cache_entry, status=cache_entry["agent_status"], timestamp=now_iso)

    _upsert_local_agent(
        agent_id,
        agent_name=agent_name,
        agent_status=cache_entry["agent_status"],
        work_status=work_status,
        current_task=current_task,
        agent_capability=capabilities,
        last_update=now_iso,
        launch_time=cache_entry.get("launch_time"),
        offline_time=cache_entry.get("offline_time"),
    )

    if current_task:
        task_id = f"virtual-task-{secrets.token_hex(3)}"
        _upsert_local_task(
            task_id,
            agent_id,
            task_description=current_task,
            task_name=current_task,
            task_type="Virtual",
            status="processing",
            created_at=now_iso,
            updated_at=now_iso,
        )
        task_control_registry[task_id] = {
            "task_name": current_task,
            "task_type": "Virtual",
            "task_description": current_task,
            "agent_ids": [agent_id],
            "agent_names": {agent_id: agent_name},
            "status": "processing",
            "created_at": now_iso,
            "updated_at": now_iso,
            "is_demo": True,
        }

    add_log_entry(f"[Virtual Agent] Added virtual agent: {agent_name} ({agent_id})", "info")

    dashboard = build_dashboard_snapshot()
    tasks = build_control_tasks_snapshot()
    await manager.broadcast({"type": "DASHBOARD_SNAPSHOT", "payload": dashboard})
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

    return {
        "agent": {
            "agentID": agent_id,
            "agentName": agent_name,
            "capabilities": capabilities,
            "status": agent_status,
            "currentTask": current_task,
        },
        "dashboard": dashboard,
        "tasks": tasks,
    }


# Database helper
def _parse_agent_rows(
    rows: List[sqlite3.Row], agents_with_tasks: set[str]
) -> List[Dict[str, Any]]:
    agents = []
    for row in rows:
        agent = dict(row)
        if agent.get("agent_capability"):
            try:
                agent["agent_capability"] = json.loads(agent["agent_capability"])
            except Exception:
                agent["agent_capability"] = []
        else:
            agent["agent_capability"] = []

        original_status = agent.get("agent_status", "offline")
        if agent.get("agent_id") in agents_with_tasks:
            agent["agent_status"] = "working"
        else:
            agent["agent_status"] = original_status if original_status else "offline"

        agents.append(agent)
    return agents


def _group_task_rows(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
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


def _get_agents_from_external_db(path: str) -> List[Dict[str, Any]]:
    conn = _connect_external_db_readonly(path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents")
        rows = cursor.fetchall()
        cursor.execute("SELECT DISTINCT agent_id FROM tasks")
        agents_with_tasks = {row[0] for row in cursor.fetchall()}
        return _parse_agent_rows(rows, agents_with_tasks)
    finally:
        conn.close()


def _get_agents_from_local_db() -> List[Dict[str, Any]]:
    conn = _connect_local_cache_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT agent_id, agent_name, agent_capability, agent_status, work_status, current_task, last_update, launch_time, offline_time
            FROM agents
            ORDER BY updated_at DESC
            """
        )
        rows = cursor.fetchall()
        cursor.execute("SELECT DISTINCT agent_id FROM tasks WHERE status = 'processing'")
        agents_with_tasks = {row[0] for row in cursor.fetchall()}
        return _parse_agent_rows(rows, agents_with_tasks)
    finally:
        conn.close()


def get_agents_from_db() -> List[Dict[str, Any]]:
    """Get agents from the configured source, with local-cache fallback."""
    if should_use_external_db():
        try:
            return _get_agents_from_external_db(get_external_db_path())
        except Exception as e:
            print(f"[Database Error] {e}")
            return _get_agents_from_local_db()
    try:
        return _get_agents_from_local_db()
    except Exception as e:
        print(f"[Local Database Error] {e}")
        return []


def _get_task_count_from_external_db(path: str) -> int:
    conn = _connect_external_db_readonly(path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks")
        return int(cursor.fetchone()[0] or 0)
    finally:
        conn.close()


def _get_task_count_from_local_db() -> int:
    conn = _connect_local_cache_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'processing'")
        return int(cursor.fetchone()[0] or 0)
    finally:
        conn.close()


def get_task_count_from_db() -> int:
    """Get total task count from the configured source."""
    try:
        if should_use_external_db():
            return _get_task_count_from_external_db(get_external_db_path())
        return _get_task_count_from_local_db()
    except Exception as e:
        print(f"[Task Count Error] {e}")
        try:
            return _get_task_count_from_local_db()
        except Exception:
            return 0


def _get_tasks_from_external_db(path: str) -> List[Dict[str, Any]]:
    conn = _connect_external_db_readonly(path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, agent_id, task_id, task_description
            FROM tasks
            ORDER BY id DESC
            """
        )
        rows = cursor.fetchall()
        return _group_task_rows(rows)
    finally:
        conn.close()


def _get_tasks_from_local_db() -> List[Dict[str, Any]]:
    conn = _connect_local_cache_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, agent_id, task_id, task_description
            FROM tasks
            WHERE status = 'processing'
            ORDER BY id DESC
            """
        )
        rows = cursor.fetchall()
        return _group_task_rows(rows)
    finally:
        conn.close()


def get_tasks_from_db() -> List[Dict[str, Any]]:
    """Get active tasks from the configured source, with local-cache fallback."""
    try:
        if should_use_external_db():
            return _get_tasks_from_external_db(get_external_db_path())
        return _get_tasks_from_local_db()
    except Exception as e:
        print(f"[Task Query Error] {e}")
        try:
            return _get_tasks_from_local_db()
        except Exception:
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


def _format_timestamp_display(value: Any) -> str:
    parsed = _parse_timestamp(value)
    if not parsed:
        return "Unknown"
    return parsed.strftime("%Y-%m-%d %H:%M:%S UTC")


def _format_elapsed_since(value: Any) -> str:
    parsed = _parse_timestamp(value)
    if not parsed:
        return "Unknown"

    delta_seconds = max(int((datetime.utcnow() - parsed).total_seconds()), 0)
    days, remainder = divmod(delta_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    if days:
        return f"{days}d {hours:02d}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _normalize_capabilities(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _default_agent_cache_entry(agent_id: str, agent_name: Optional[str] = None) -> Dict[str, Any]:
    fallback_name = str(agent_name or agent_id).strip() or agent_id
    return {
        "agent_id": agent_id,
        "agent_name": fallback_name,
        "work_status": "idle",
        "current_task": "",
        "logs": [],
        "agent_status": "online",
        "agent_capability": [],
        "last_update": None,
        "launch_time": None,
        "offline_time": None,
        "is_demo": False,
    }


def _ensure_agent_cache_entry(agent_id: str, agent_name: Optional[str] = None) -> Dict[str, Any]:
    entry = agent_status_cache.setdefault(
        agent_id,
        _default_agent_cache_entry(agent_id, agent_name=agent_name),
    )
    entry.setdefault("logs", [])
    entry.setdefault("agent_capability", [])
    entry.setdefault("launch_time", None)
    entry.setdefault("offline_time", None)
    if agent_name:
        entry["agent_name"] = agent_name
    elif not entry.get("agent_name"):
        entry["agent_name"] = agent_id
    return entry


def _sync_agent_timeline(
    cache_entry: Dict[str, Any],
    *,
    status: Optional[str],
    timestamp: Optional[str],
) -> str:
    normalized_timestamp = (
        str(timestamp).strip() if timestamp and str(timestamp).strip() else datetime.utcnow().isoformat()
    )
    normalized_status = str(status or "").lower()
    next_state = "offline" if normalized_status == "offline" else "online"
    previous_state = (
        "offline" if str(cache_entry.get("agent_status", "")).lower() == "offline" else "online"
    )

    if next_state == "offline":
        if previous_state != "offline" or not cache_entry.get("offline_time"):
            cache_entry["offline_time"] = normalized_timestamp
        cache_entry["agent_status"] = "offline"
    else:
        if previous_state == "offline" or not cache_entry.get("launch_time"):
            cache_entry["launch_time"] = normalized_timestamp
        cache_entry["offline_time"] = None
        cache_entry["agent_status"] = "online"

    cache_entry["last_update"] = normalized_timestamp
    return normalized_timestamp


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


def _build_agent_track_inventory() -> Dict[str, List[Dict[str, Any]]]:
    if not MOQ_AVAILABLE:
        return {}

    inventory: Dict[str, List[Dict[str, Any]]] = {}
    for track in moq_video_subscriber.list_discovered_tracks():
        if str(track.get("source") or "moq") != "moq":
            continue
        agent_id = str(track.get("agentId") or "").strip()
        if not agent_id:
            continue
        inventory.setdefault(agent_id, []).append(track)

    for tracks in inventory.values():
        tracks.sort(
            key=lambda item: str(item.get("lastSeen") or item.get("discoveredAt") or ""),
            reverse=True,
        )
    return inventory


def _dashboard_track_summary(track_names: List[str]) -> str:
    if not track_names:
        return "No track"
    if len(track_names) == 1:
        return track_names[0]
    if len(track_names) == 2:
        return f"{track_names[0]}, {track_names[1]}"
    return f"{track_names[0]}, {track_names[1]} +{len(track_names) - 2}"


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


def build_network_element_control_snapshot() -> List[Dict[str, Any]]:
    status_by_id = {str(group.get("id")): group for group in build_element_status_snapshot()}
    controls = []
    for element_id, config in NETWORK_ELEMENT_CONTROL_SCRIPTS.items():
        script_path = config["script"]
        group_status = status_by_id.get(element_id, {})
        controls.append(
            {
                "id": element_id,
                "name": config["name"],
                "description": config["description"],
                "scriptPath": str(script_path),
                "scriptExists": script_path.exists(),
                "status": group_status.get("status", "offline"),
                "summary": group_status.get("summary", "Status unavailable."),
                "components": group_status.get("components", []),
            }
        )
    return controls


async def run_network_element_action(element_id: str, action: str) -> Dict[str, Any]:
    normalized_element_id = str(element_id or "").strip()
    normalized_action = str(action or "").strip().lower()
    config = NETWORK_ELEMENT_CONTROL_SCRIPTS.get(normalized_element_id)

    if config is None:
        raise HTTPException(status_code=404, detail=f"Unknown network element: {element_id}")
    if normalized_action not in NETWORK_ELEMENT_CONTROL_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Action must be one of: {', '.join(sorted(NETWORK_ELEMENT_CONTROL_ACTIONS))}",
        )

    script_path: Path = config["script"]
    if not script_path.exists() or not script_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Control script not found: {script_path}",
        )

    add_log_entry(
        f"[Element Control] Running {config['name']} {normalized_action}: {script_path} {normalized_action}",
        "warning" if normalized_action in {"stop", "restart"} else "info",
    )

    with tempfile.NamedTemporaryFile() as stdout_file, tempfile.NamedTemporaryFile() as stderr_file:
        process = await asyncio.create_subprocess_exec(
            str(script_path),
            normalized_action,
            cwd=str(script_path.parent),
            stdout=stdout_file,
            stderr=stderr_file,
            start_new_session=True,
        )

        try:
            await asyncio.wait_for(process.wait(), timeout=120.0)
        except asyncio.TimeoutError as exc:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass

            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout = stdout_file.read().decode("utf-8", errors="replace").strip()
            stderr = stderr_file.read().decode("utf-8", errors="replace").strip()
            detail = stderr or stdout or f"{config['name']} {normalized_action} timed out after 120 seconds."
            add_log_entry(
                f"[Element Control] {config['name']} {normalized_action} timed out after 120s: {detail[:300]}",
                "error",
            )
            raise HTTPException(
                status_code=504,
                detail={
                    "error": f"{config['name']} {normalized_action} timed out.",
                    "detail": detail[:1000],
                    "exitCode": -1,
                },
            ) from exc

        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read().decode("utf-8", errors="replace").strip()
        stderr = stderr_file.read().decode("utf-8", errors="replace").strip()

    exit_code = int(process.returncode or 0)

    if exit_code != 0:
        detail = stderr or stdout or f"Script exited with code {exit_code}."
        add_log_entry(
            f"[Element Control] {config['name']} {normalized_action} failed with exit code {exit_code}: {detail[:300]}",
            "error",
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": f"{config['name']} {normalized_action} failed.",
                "detail": detail[:1000],
                "exitCode": exit_code,
            },
        )

    add_log_entry(
        f"[Element Control] {config['name']} {normalized_action} completed successfully",
        "info",
    )

    return {
        "elementId": normalized_element_id,
        "elementName": config["name"],
        "action": normalized_action,
        "exitCode": exit_code,
        "stdout": stdout[-2000:],
        "stderr": stderr[-2000:],
    }


def _network_element_error_result(
    element_id: str, action: str, error: Any
) -> Dict[str, Any]:
    config = NETWORK_ELEMENT_CONTROL_SCRIPTS.get(element_id, {})
    detail = getattr(error, "detail", error)
    if isinstance(detail, dict):
        message = str(detail.get("detail") or detail.get("error") or detail)
        exit_code = int(detail.get("exitCode", -1) or -1)
    else:
        message = str(detail)
        exit_code = -1

    return {
        "elementId": element_id,
        "elementName": config.get("name", element_id),
        "action": action,
        "exitCode": exit_code,
        "stdout": "",
        "stderr": message[:2000],
    }


async def run_network_element_batch_action(action: str) -> Dict[str, Any]:
    normalized_action = str(action or "").strip().lower()
    if normalized_action not in {"start", "restart"}:
        raise HTTPException(
            status_code=400,
            detail="Batch action must be start or restart.",
        )

    if normalized_action == "start":
        snapshot = build_network_element_control_snapshot()
        target_ids = [
            str(element.get("id"))
            for element in snapshot
            if element.get("id") and element.get("status") == "offline"
        ]
    else:
        target_ids = list(NETWORK_ELEMENT_CONTROL_SCRIPTS.keys())

    if not target_ids:
        message = "No offline network elements to start."
        add_log_entry(f"[Element Control] {message}", "info")
        return {
            "elementId": "all",
            "elementName": "All Network Elements",
            "action": normalized_action,
            "exitCode": 0,
            "stdout": message,
            "stderr": "",
            "results": [],
        }

    results = []
    for target_id in target_ids:
        try:
            results.append(await run_network_element_action(target_id, normalized_action))
        except HTTPException as exc:
            results.append(_network_element_error_result(target_id, normalized_action, exc))
        except Exception as exc:
            results.append(_network_element_error_result(target_id, normalized_action, exc))

    failed = [result for result in results if int(result.get("exitCode", -1)) != 0]
    stdout = "\n\n".join(
        f"[{result['elementName']}]\n{result.get('stdout') or 'No output'}"
        for result in results
    )
    stderr = "\n\n".join(
        f"[{result['elementName']}]\n{result.get('stderr')}"
        for result in results
        if result.get("stderr")
    )
    exit_code = 0 if not failed else 1

    return {
        "elementId": "all",
        "elementName": "All Network Elements",
        "action": normalized_action,
        "exitCode": exit_code,
        "stdout": stdout[-2000:],
        "stderr": stderr[-2000:],
        "results": results,
    }


def _canonical_flow_node(name: str, abstract: str = "") -> Optional[str]:
    normalized = (name or "").strip().lower()
    normalized = normalized.replace("（", "(").replace("）", ")")
    normalized_abstract = (abstract or "").strip().lower()
    normalized_abstract = normalized_abstract.replace("（", "(").replace("）", ")")
    if not normalized:
        return None

    if "acn sdk" in normalized or normalized == "sdk":
        return "ACN SDK"

    if "idm" in normalized:
        return "IDM"

    if "relay" in normalized or "moq relay" in normalized:
        return "Relay"

    if "arf" in normalized:
        return "ARF"

    if "acf" in normalized:
        return "ACF"

    if (
        "agent gw" in normalized
        or "agentgw" in normalized
        or "/arf/" in normalized
        or "/acf/" in normalized
    ):
        if "relay" in normalized_abstract or "moq" in normalized_abstract:
            return "Relay"
        if "acf" in normalized_abstract or "setup connection" in normalized_abstract:
            return "ACF"
        if (
            "arf" in normalized_abstract
            or "agent-card" in normalized_abstract
            or "agent-cards" in normalized_abstract
            or "vc-verification" in normalized_abstract
            or "vc-verifications" in normalized_abstract
        ):
            return "ARF"
        return "ACF"

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
        for component in element.get("components", []) or []:
            component_name = str(component.get("name", "")).strip()
            component_status = str(component.get("status", "offline")).lower()
            if component_name:
                element_status_map[component_name] = (
                    "offline" if component_status == "offline" else "online"
                )

    recent_events = list(reversed(pipeline_log_buffer[-limit:])) if pipeline_log_buffer else []
    edge_map: Dict[tuple, Dict[str, Any]] = {}
    now = datetime.utcnow()
    ttl_seconds = float(message_flow_display_runtime.get("ttl_seconds", MESSAGE_FLOW_TTL_SECONDS))
    active_seconds = float(
        message_flow_display_runtime.get("active_seconds", MESSAGE_FLOW_ACTIVE_SECONDS)
    )

    for event in recent_events:
        timestamp = _parse_timestamp(event.get("timestamp"))
        if not timestamp:
            continue

        age_seconds = (now - timestamp).total_seconds()
        if age_seconds < 0 or age_seconds > ttl_seconds:
            continue

        abstract = str(event.get("abstract", "")).strip() or str(event.get("content", "")).strip() or "Message flow"
        source = _canonical_flow_node(str(event.get("source", "")), abstract)
        target = _canonical_flow_node(str(event.get("destination", "")), abstract)
        if not source or not target or source == target:
            continue

        key = (source, target)
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
                "active": age_seconds <= active_seconds,
            }
        else:
            entry["count"] += 1
            if not entry.get("lastMessage"):
                entry["lastMessage"] = abstract[:96]
            if not entry.get("lastTimestamp"):
                entry["lastTimestamp"] = event.get("timestamp")
            entry["active"] = entry["active"] or age_seconds <= active_seconds

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
    for field in ("work_status", "current_task", "logs", "last_update", "launch_time", "offline_time"):
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

        cache_entry = _ensure_agent_cache_entry(
            agent_id,
            agent_name=str(agent.get("agent_name") or agent_id),
        )
        if agent.get("agent_capability") and not cache_entry.get("agent_capability"):
            cache_entry["agent_capability"] = agent.get("agent_capability")
        _sync_agent_timeline(
            cache_entry,
            status=agent.get("agent_status"),
            timestamp=agent.get("last_update"),
        )
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
    agent_tracks = _build_agent_track_inventory()
    claim_name_lookup = _agent_claim_name_lookup()

    for index, agent in enumerate(_merge_agent_sources()):
        agent_id = str(agent.get("agent_id") or f"agent-{index}")
        display_name = _resolve_agent_display_name(agent, claim_name_lookup)
        agent = {**agent, "agent_name": display_name}
        status = _dashboard_status_from_agent(agent)
        capabilities = _normalize_capabilities(agent.get("agent_capability"))
        logs = agent.get("logs", [])
        tracks = agent_tracks.get(agent_id, [])
        track_names = [
            str(track.get("trackName") or track.get("normalizedTrackName") or "Track")
            for track in tracks
        ]
        launch_time = agent.get("launch_time") or agent.get("last_update")
        offline_time = agent.get("offline_time") if status == "offline" else None

        dashboard_agents.append(
            {
                "id": agent_id,
                "name": display_name,
                "role": _dashboard_role_from_agent(agent),
                "status": status,
                "region": _dashboard_region_from_agent(agent),
                "trackSummary": _dashboard_track_summary(track_names),
                "tracks": [
                    {
                        "id": str(track.get("trackId") or ""),
                        "name": str(
                            track.get("trackName")
                            or track.get("normalizedTrackName")
                            or "Track"
                        ),
                        "taskId": str(track.get("taskId") or ""),
                        "namespace": str(track.get("namespace") or ""),
                        "watchState": str(track.get("watchState") or "available"),
                        "lastSeen": str(track.get("lastSeen") or ""),
                    }
                    for track in tracks
                ],
                "summary": _dashboard_summary_from_agent(agent),
                "uptime": "Unavailable"
                if status == "offline"
                else _format_elapsed_since(launch_time),
                "launchTime": _format_timestamp_display(launch_time),
                "offlineTime": _format_timestamp_display(offline_time),
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
            "abstract": "identity-applications",
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
            "source": "ACN SDK",
            "destination": "ACN Agent",
            "timestamp": (now + timedelta(milliseconds=240)).isoformat(),
            "task_id": "topology-card",
            "protocol": "HTTP/2",
            "headers": "",
            "abstract": "Agent-cards",
            "content": "ACN SDK starts agent-card publication",
        },
        {
            "source": "ACN Agent",
            "destination": "ARF",
            "timestamp": (now + timedelta(milliseconds=360)).isoformat(),
            "task_id": "topology-card",
            "protocol": "HTTP/2",
            "headers": "",
            "abstract": "Agent-cards",
            "content": "ACN Agent forwards the agent card to ARF",
        },
        {
            "source": "ARF",
            "destination": "IDM",
            "timestamp": (now + timedelta(milliseconds=480)).isoformat(),
            "task_id": "topology-card",
            "protocol": "HTTP/2",
            "headers": "",
            "abstract": "vc-verifications",
            "content": "ARF verifies the agent card with IDM",
        },
        {
            "source": "ACN SDK",
            "destination": "ACF",
            "timestamp": (now + timedelta(milliseconds=600)).isoformat(),
            "task_id": "topology-setup",
            "protocol": "WebSocket",
            "headers": "",
            "abstract": "SETUP connection",
            "content": "ACN SDK establishes ACF signaling connection",
        },
        {
            "source": "ACN SDK",
            "destination": "Relay",
            "timestamp": (now + timedelta(milliseconds=720)).isoformat(),
            "task_id": "topology-moq",
            "protocol": "MoQ",
            "headers": "",
            "abstract": "MoQ Connection",
            "content": "ACN SDK opens MoQ connection to Relay",
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


DEMO_STAGES = ("register", "task", "cooperate", "deregister")


def _normalize_demo_stages(stages: Any) -> List[str]:
    if not isinstance(stages, list):
        return ["register", "task", "cooperate"]

    normalized: List[str] = []
    for stage in stages:
        value = str(stage).strip().lower()
        if value in DEMO_STAGES and value not in normalized:
            normalized.append(value)

    return normalized or ["register", "task", "cooperate"]


def build_full_system_test_events(stages: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Build a realistic end-to-end demo scenario from known backend log patterns."""
    alpha_id = "did:acn:agent:demo-alpha"
    beta_id = "did:acn:agent:demo-beta"
    selected = set(_normalize_demo_stages(stages))
    events: List[Dict[str, Any]] = []

    include_alpha_registration = bool(selected.intersection({"register", "task", "cooperate"}))
    include_beta_registration = "cooperate" in selected

    if include_alpha_registration:
        events.extend(
            [
                # Step 1: ACN SDK -> ACN Agent -> IDM : identity-applications
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
                        "abstract": "identity-applications",
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
                        "abstract": "identity-applications",
                        "content": {
                            "agent_id": alpha_id,
                            "agent_name": "Demo Agent Alpha",
                            "owner": "demo-user",
                            "name": "Demo Agent Alpha",
                            "is_demo": True,
                        },
                    },
                    "delay_after_seconds": "stage",
                },
                # Step 2: ACN SDK -> ACN Agent -> ARF : Agent-cards
                #         ARF -> IDM : vc-verifications
                {
                    "kind": "element",
                    "payload": {
                        "element_id": "ARF",
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
                        "source": "ACN SDK",
                        "destination": "ACN Agent",
                        "task_id": "demo-alpha-card",
                        "protocol": "HTTP/2",
                        "headers": "",
                        "abstract": "Agent-cards",
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
                        "destination": "ARF",
                        "task_id": "demo-alpha-card",
                        "protocol": "HTTP/2",
                        "headers": "",
                        "abstract": "Agent-cards",
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
                        "source": "ARF",
                        "destination": "IDM",
                        "task_id": "demo-alpha-card",
                        "protocol": "HTTP/2",
                        "headers": "",
                        "abstract": "vc-verifications",
                        "content": {
                            "agent_id": alpha_id,
                            "agent_name": "Demo Agent Alpha",
                            "name": "Demo Agent Alpha",
                            "is_demo": True,
                        },
                    },
                    "delay_after_seconds": "stage",
                },
                # Step 3: ACN SDK -> ACF : SETUP connection
                #         ACN SDK -> Relay : MoQ Connection
                {
                    "kind": "element",
                    "payload": {
                        "element_id": "ACF",
                        "log_type": "SetupConnection",
                        "content": {
                            "agent_id": alpha_id,
                            "agent_name": "Demo Agent Alpha",
                            "is_demo": True,
                        },
                    },
                },
                {
                    "kind": "pipeline",
                    "payload": {
                        "source": "ACN SDK",
                        "destination": "ACF",
                        "task_id": "demo-alpha-setup",
                        "protocol": "WebSocket",
                        "headers": "",
                        "abstract": "SETUP connection",
                        "content": {
                            "agent_id": alpha_id,
                            "agent_name": "Demo Agent Alpha",
                            "name": "Demo Agent Alpha",
                            "is_demo": True,
                        },
                    },
                    "delay_after_seconds": "stage",
                },
                {
                    "kind": "element",
                    "payload": {
                        "element_id": "Relay",
                        "log_type": "VideoStream",
                        "content": {
                            "agent_id": alpha_id,
                            "agent_name": "Demo Agent Alpha",
                            "is_demo": True,
                        },
                    },
                },
                {
                    "kind": "pipeline",
                    "payload": {
                        "source": "ACN SDK",
                        "destination": "Relay",
                        "task_id": "demo-alpha-moq",
                        "protocol": "MoQ",
                        "headers": "",
                        "abstract": "MoQ Connection",
                        "content": {
                            "agent_id": alpha_id,
                            "agent_name": "Demo Agent Alpha",
                            "name": "Demo Agent Alpha",
                            "is_demo": True,
                        },
                    },
                    "delay_after_seconds": "stage",
                },
            ]
        )

    if "task" in selected:
        events.extend(
            [
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
                        "element_id": "ACN Agent",
                        "log_type": "TaskExecution",
                        "content": {
                            "agent_id": alpha_id,
                            "agent_name": "Demo Agent Alpha",
                            "is_demo": True,
                        },
                    },
                },
            ]
        )

    if include_beta_registration:
        events.extend(
            [
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
            ]
        )

    if "cooperate" in selected:
        events.extend(
            [
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
        )

    return events


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
    rounds: int = 1, step_delay_seconds: float = 0.22, stages: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Inject registration, interaction, and collaboration events for a full UI demo."""
    total_messages = 0
    normalized_rounds = max(1, rounds)
    selected_stages = _normalize_demo_stages(stages)

    add_log_entry(
        f"[Demo] Starting local demo scenario for stages: {', '.join(selected_stages)} (no external IDM, ACN Agent, or AgentGW calls)",
        "info",
    )

    if "deregister" in selected_stages and len(selected_stages) == 1:
        _clear_local_demo_state()
        add_log_entry("[Demo] Local demo agents deregistered.", "info")
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
            "messages_sent": 0,
            "tasks": tasks,
            "dashboard": dashboard,
            "stages": selected_stages,
        }

    _clear_local_demo_state()

    full_demo_events = build_full_system_test_events(selected_stages)
    demo_task_definitions = []
    if "task" in selected_stages:
        demo_task_definitions.append(
            {
                "id": "demo-task-alpha",
                "name": "Perimeter Sweep",
                "type": "Inspection",
                "description": "Inspect corridor A and validate telemetry uplink stability.",
                "agent_ids": ["did:acn:agent:demo-alpha"],
                "agent_names": {"did:acn:agent:demo-alpha": "Demo Agent Alpha"},
            }
        )
    if "cooperate" in selected_stages:
        demo_task_definitions.append(
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
            }
        )

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
                delay_value = event.get("delay_after_seconds", step_delay_seconds)
                delay_seconds = (
                    max(0.05, step_delay_seconds * 7.25)
                    if delay_value == "stage"
                    else max(0.05, float(delay_value))
                )
                await asyncio.sleep(delay_seconds)

    if "register" in selected_stages:
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

    if "deregister" in selected_stages:
        _clear_local_demo_state()
        add_log_entry("[Demo] Local demo agents deregistered.", "info")

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
        "stages": selected_stages,
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
            if response.status_code != 200:
                response_body = response.text.strip()
                detail = response_body[:500] if response_body else ""
                add_log_entry(
                    f"[ARF] Clear failed with HTTP {response.status_code}"
                    + (f": {detail}" if detail else ""),
                    "error",
                )
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"ARF clear failed with HTTP {response.status_code}",
                    "detail": detail,
                }
            return {
                "success": True,
                "status_code": response.status_code,
                "response": response.json(),
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
    """Broadcast MOQ bridge segments to WebUI clients."""
    payload: Dict[str, Any] = {
        "track_id": frame.track_name,
        "group_id": frame.group_id,
        "object_id": frame.object_id,
        "timestamp": frame.timestamp.isoformat(),
        "frame_type": frame.frame_type,
        "payload_size": len(frame.payload),
    }

    if frame.frame_type == "metadata":
        try:
            payload["metadata"] = json.loads(frame.payload.decode("utf-8"))
        except Exception:
            payload["metadata"] = None
            payload["payload_base64"] = base64.b64encode(frame.payload).decode("ascii")
    elif frame.payload:
        payload["payload_base64"] = base64.b64encode(frame.payload).decode("ascii")

    await manager.broadcast(
        {
            "type": "VIDEO_SEGMENT",
            "payload": payload,
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
    webui_scheme = os.environ.get("WEBUI_SCHEME", "https").lower()
    websocket_scheme = "wss" if webui_scheme == "https" else "ws"
    print("=" * 60)
    print("ACN Agent Monitor Backend Starting...")
    print("=" * 60)
    print(f"API: {webui_scheme}://0.0.0.0:9005")
    print(f"WebSocket: {websocket_scheme}://0.0.0.0:9005/ws")
    print("=" * 60)
    ensure_local_cache_db()
    _prime_local_cache_from_runtime_state()

    # Start background task for agent updates
    task = asyncio.create_task(broadcast_agent_updates())
    # Start MOQ video subscriber
    moq_task = None
    if MOQ_AVAILABLE:
        print("[MOQ] Starting video subscriber...")
        try:
            moq_video_subscriber.set_callbacks(
                on_frame_received=handle_moq_video_frame,
                on_track_subscribed=on_moq_track_subscribed,
            )
            await moq_video_subscriber.start()
            moq_task = moq_video_subscriber._connection_task
        except OSError as exc:
            add_log_entry(
                f"[MOQ] Video subscriber disabled during startup: {exc}",
                "warning",
            )
            print(f"[MOQ] Video subscriber disabled during startup: {exc}")
        except Exception as exc:
            add_log_entry(
                f"[MOQ] Video subscriber startup failed: {exc}",
                "warning",
            )
            print(f"[MOQ] Video subscriber startup failed: {exc}")

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


def _get_data_source_status() -> Dict[str, Any]:
    settings = get_data_source_settings()
    external_path = get_external_db_path()
    external_exists = Path(external_path).exists()
    local_exists = LOCAL_CACHE_DB_PATH.exists()
    active_source = "external" if should_use_external_db() else "local"
    if should_use_external_db() and not external_exists:
        active_source = "local-fallback"

    return {
        "useExternalDb": bool(settings["useExternalDb"]),
        "externalDbPath": external_path,
        "externalDbExists": external_exists,
        "localDbPath": get_local_cache_db_path(),
        "localDbExists": local_exists,
        "activeSource": active_source,
    }


@app.get("/api/settings/data-source")
async def get_data_source_config():
    """Return the current database source configuration."""
    return {
        "status": "success",
        "config": _get_data_source_status(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/settings/data-source")
async def update_data_source_config(request: Dict[str, Any]):
    """Update the database source configuration."""
    use_external = bool(request.get("useExternalDb", True))
    external_path = str(request.get("externalDbPath") or EXTERNAL_DB_DEFAULT_PATH).strip()
    data_source_settings.update(
        _save_data_source_settings(
            {"useExternalDb": use_external, "externalDbPath": external_path}
        )
    )
    ensure_local_cache_db()
    _prime_local_cache_from_runtime_state()
    dashboard = build_dashboard_snapshot()
    tasks = build_control_tasks_snapshot()
    payload = {
        "config": _get_data_source_status(),
        "dashboard": dashboard,
        "tasks": tasks,
        "timestamp": datetime.utcnow().isoformat(),
    }
    await manager.broadcast({"type": "DASHBOARD_SNAPSHOT", "payload": dashboard})
    await manager.broadcast({"type": "TASKS_UPDATED", "payload": payload})
    return {"status": "success", **payload}


@app.post("/api/settings/virtual-agents")
async def create_virtual_agent(request: Dict[str, Any]):
    """Create a local virtual agent and publish it into the dashboard roster."""
    payload = await add_virtual_agent(request)
    return {
        "status": "success",
        "message": "Virtual agent added.",
        **payload,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/settings/certificates")
async def get_certificates():
    """Return the managed certificate list."""
    return {
        "status": "success",
        "certificates": _list_certificates(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/settings/certificates/upload")
async def upload_certificate(
    file: Optional[UploadFile] = File(default=None),
    filePath: Optional[str] = Form(default=None),
):
    """Upload a certificate from form-data file bytes or a server-local file path."""
    upload_payload = await _read_certificate_upload(file, filePath)
    cert_name = str(upload_payload["cert_name"]).strip()
    cert_bytes = upload_payload["cert_bytes"]
    upload_source = "browser-file" if file is not None and file.filename else "server-file-path"
    add_log_entry(
        f"[Cert Upload] Received upload request: certName={cert_name} source={upload_source}",
        "info",
    )

    try:
        decoded = _decode_x509_certificate(cert_bytes)
        add_log_entry(
            f"[Cert Upload] Decoded X.509 certificate: certName={cert_name} authority={decoded['authority']} validity={decoded['validity']}",
            "info",
        )
    except ValueError as exc:
        add_log_entry(
            f"[Cert Upload] Failed to decode X.509 certificate certName={cert_name}: {exc}",
            "error",
        )
        raise HTTPException(
            status_code=400,
            detail=f"Certificate is not a valid X.509 PEM or DER file: {exc}",
        ) from exc

    cert_id = _generate_cert_id()
    add_log_entry(
        f"[Cert Upload] Generated CertID for {cert_name}: {cert_id}",
        "info",
    )
    try:
        idm_response = await _forward_certificate_to_idm(cert_id, cert_name, cert_bytes)
        certificate = _store_certificate_record(
            cert_id,
            cert_name,
            decoded["authority"],
            decoded["validity"],
            cert_bytes,
        )
        add_log_entry(
            f"[Cert Upload] Upload OK: certID={cert_id} certName={cert_name} saved to local cert database",
            "info",
        )
    except Exception:
        _delete_certificate_record(cert_id)
        add_log_entry(
            f"[Cert Upload] Upload failed and local cache cleared: certID={cert_id} certName={cert_name}",
            "error",
        )
        raise

    return {
        "status": "success",
        "message": "Upload OK",
        "certificate": certificate,
        "certificates": _list_certificates(),
        "idmResponse": idm_response,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.delete("/api/settings/certificates/{cert_id}")
async def delete_certificate(cert_id: str):
    """Delete a managed certificate record and its stored file."""
    normalized_cert_id = str(cert_id or "").strip()
    if not normalized_cert_id:
        raise HTTPException(status_code=400, detail="Certificate ID is required.")

    conn = _connect_cert_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT cert_name
            FROM certificates
            WHERE cert_id = ?
            """,
            (normalized_cert_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Certificate not found.")
    finally:
        conn.close()

    cert_name = str(row["cert_name"]).strip()
    add_log_entry(
        f"[Cert Delete] Received delete request: certID={normalized_cert_id} certName={cert_name}",
        "info",
    )
    idm_response = await _forward_certificate_delete_to_idm(normalized_cert_id, cert_name)
    _delete_certificate_record(normalized_cert_id)
    add_log_entry(
        f"[Cert Delete] Delete success: certID={normalized_cert_id} certName={cert_name} removed from local cert database",
        "info",
    )

    return {
        "status": "success",
        "message": "Delete success",
        "certificates": _list_certificates(),
        "idmResponse": idm_response,
        "timestamp": datetime.utcnow().isoformat(),
    }


# Log buffer for frontend display
log_buffer = []
max_log_entries = 1000
pipeline_log_buffer = []
max_pipeline_log_entries = 200
network_element_log_cutoffs: Dict[str, int] = {}
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


def _set_message_flow_display_window(
    ttl_seconds: Optional[Any] = None, active_seconds: Optional[Any] = None
) -> None:
    try:
        ttl = float(ttl_seconds) if ttl_seconds is not None else float(MESSAGE_FLOW_TTL_SECONDS)
    except (TypeError, ValueError):
        ttl = float(MESSAGE_FLOW_TTL_SECONDS)

    try:
        active = float(active_seconds) if active_seconds is not None else ttl
    except (TypeError, ValueError):
        active = ttl

    ttl = min(max(ttl, 0.8), 30.0)
    active = min(max(active, 0.5), ttl)
    message_flow_display_runtime["ttl_seconds"] = ttl
    message_flow_display_runtime["active_seconds"] = active


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


def _current_log_offset(file_path: Path) -> int:
    try:
        return file_path.stat().st_size if file_path.exists() and file_path.is_file() else 0
    except OSError:
        return 0


def _snapshot_network_element_log_cutoffs() -> Dict[str, int]:
    cutoffs: Dict[str, int] = {}

    for source in NETWORK_ELEMENT_LOG_SOURCES:
        path = source["path"]
        try:
            if source["mode"] == "file":
                if path.exists() and path.is_file():
                    cutoffs[str(path)] = _current_log_offset(path)
            else:
                for file_path in _list_log_files(path):
                    cutoffs[str(file_path)] = _current_log_offset(file_path)
        except Exception as exc:
            add_log_entry(
                f"[Clear] Failed to snapshot log cutoff for {source['name']}: {exc}",
                "warning",
            )

    return cutoffs


def _tail_log_entries(file_path: Path, limit: int) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []

    start_offset = network_element_log_cutoffs.get(str(file_path), 0)
    with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
        if start_offset > 0:
            current_size = _current_log_offset(file_path)
            handle.seek(start_offset if current_size >= start_offset else 0)
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
    network_element_log_cutoffs.clear()
    network_element_log_cutoffs.update(_snapshot_network_element_log_cutoffs())
    task_control_registry.clear()
    control_task_history.clear()
    _reset_local_cache_state()
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


@app.get("/api/control/network-elements")
async def get_network_element_controls():
    """Return script-backed network element control status."""
    return {
        "elements": build_network_element_control_snapshot(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/control/network-elements/{element_id}/{action}")
async def control_network_element(element_id: str, action: str):
    """Run start/stop/restart for a managed network element."""
    if str(element_id).strip().lower() == "all":
        result = await run_network_element_batch_action(action)
    else:
        result = await run_network_element_action(element_id, action)
    await asyncio.sleep(0.8)

    dashboard = build_dashboard_snapshot()
    elements = build_network_element_control_snapshot()
    success = int(result.get("exitCode", -1)) == 0
    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "result": result,
        "results": result.get("results", [result]),
        "elements": elements,
        "dashboard": dashboard,
    }

    await manager.broadcast({"type": "DASHBOARD_SNAPSHOT", "payload": dashboard})

    return {
        "success": success,
        "message": (
            f"{result['elementName']} {result['action']} completed."
            if success
            else f"{result['elementName']} {result['action']} completed with failures."
        ),
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
    _set_message_flow_display_window(
        body.get("display_ttl_seconds"),
        body.get("display_active_seconds"),
    )

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
    stages = body.get("stages")
    _set_message_flow_display_window(
        body.get("display_ttl_seconds"),
        body.get("display_active_seconds"),
    )

    try:
        result = await run_full_system_test_demo(
            rounds=int(rounds),
            step_delay_seconds=max(0.05, float(step_delay_seconds)),
            stages=stages,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run full system demo: {e}")

    return {
        "success": True,
        "message": f"Local demo injected for stages: {', '.join(result.get('stages', []))}.",
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
        for agent_id in normalized_agent_ids:
            _insert_task_record(
                agent_id,
                task_id,
                task_description,
                task_name=task_name,
                task_type=task_type,
                created_at=now,
                updated_at=now,
            )
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
        cache_entry = _ensure_agent_cache_entry(
            agent_id,
            agent_name=agent_names.get(agent_id, agent_id),
        )
        _sync_agent_timeline(
            cache_entry,
            status="online",
            timestamp=now,
        )
        cache_entry["work_status"] = "working"
        cache_entry["current_task"] = task_description
        cache_entry.setdefault("logs", []).append(
            {
                "time": now,
                "level": "info",
                "message": f"Dispatched task {task_name}",
            }
        )
        if len(cache_entry["logs"]) > 10:
            cache_entry["logs"] = cache_entry["logs"][-10:]
        _upsert_local_agent(
            agent_id,
            agent_name=cache_entry.get("agent_name"),
            agent_status=cache_entry.get("agent_status", "online"),
            work_status=cache_entry.get("work_status"),
            current_task=cache_entry.get("current_task"),
            agent_capability=cache_entry.get("agent_capability")
            if isinstance(cache_entry.get("agent_capability"), list)
            else None,
            last_update=now,
            launch_time=cache_entry.get("launch_time"),
            offline_time=cache_entry.get("offline_time"),
        )

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
        _delete_task_records(task_id)
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

        _sync_agent_timeline(
            cache_entry,
            status=cache_entry.get("agent_status", "online"),
            timestamp=now,
        )
        if agent_id in remaining_by_agent:
            cache_entry["work_status"] = "working"
            cache_entry["current_task"] = remaining_by_agent[agent_id]
        else:
            cache_entry["work_status"] = "idle"
            cache_entry["current_task"] = ""
        _upsert_local_agent(
            agent_id,
            agent_name=cache_entry.get("agent_name"),
            agent_status=cache_entry.get("agent_status", "online"),
            work_status=cache_entry.get("work_status"),
            current_task=cache_entry.get("current_task"),
            agent_capability=cache_entry.get("agent_capability")
            if isinstance(cache_entry.get("agent_capability"), list)
            else None,
            last_update=now,
            launch_time=cache_entry.get("launch_time"),
            offline_time=cache_entry.get("offline_time"),
        )

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
        "discovered_tracks": moq_video_subscriber.list_discovered_tracks(),
        "subscription_debug": moq_video_subscriber.get_track_debug_info(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/moq/tracks")
async def get_moq_discovered_tracks():
    """List discovered video tracks that can be watched on demand."""
    return {
        "status": "success",
        "tracks": _list_all_video_tracks(),
        "subscribed_tracks": (
            moq_video_subscriber.get_subscribed_tracks() if MOQ_AVAILABLE else []
        ),
        "timestamp": datetime.utcnow().isoformat(),
    }


def _parse_webui_subscription_payload(request: Dict[str, Any]) -> tuple[List[str], str]:
    """Parse WebUI namespace + trackName without implicit demo defaults."""
    raw_namespace = str(request.get("namespace") or "").strip()
    raw_track_name = str(request.get("trackName") or "").strip()

    namespace_parts = [part.strip() for part in raw_namespace.split("/") if part.strip()]
    if not namespace_parts:
        raise HTTPException(status_code=400, detail="namespace is required")

    if not raw_track_name:
        raise HTTPException(status_code=400, detail="trackName is required")

    return namespace_parts, raw_track_name


def _manual_video_track_id(namespace_parts: List[str], track_name: str) -> str:
    normalized_track_name = track_name.lower()
    namespace_str = "/".join(namespace_parts)
    return (
        "manual_"
        + re.sub(
            r"[^a-zA-Z0-9_.-]+",
            "_",
            f"{namespace_str}_{normalized_track_name}",
        ).strip("_")
    )


async def _start_or_switch_moq_subscription(
    payload: Dict[str, Any],
    request: Request,
) -> Dict[str, Any]:
    if not MOQ_AVAILABLE:
        raise HTTPException(status_code=503, detail="MOQ not available")

    namespace_parts, track_name = _parse_webui_subscription_payload(payload)
    namespace_str = "/" + "/".join(namespace_parts)
    track_id = str(payload.get("trackId") or "").strip() or _manual_video_track_id(
        namespace_parts,
        track_name,
    )

    moq_video_subscriber.register_discovered_track(
        track_id=track_id,
        namespace=namespace_str,
        track_name=track_name,
        agent_id=namespace_parts[-1] if namespace_parts else "manual-subscriber",
        task_id=namespace_parts[0] if namespace_parts else "manual-track",
        source="manual",
    )

    success = await moq_video_subscriber.subscribe_to_track(
        track_id=track_id,
        namespace=namespace_parts,
        track_name=track_name,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to subscribe to MOQ track")

    await moq_video_subscriber.switch_preview_track(track_id)

    host = request.url.hostname or "127.0.0.1"
    player = moq_video_subscriber.get_player_config(track_id, host=host)
    player["mjpegUrl"] = f"/api/video/stream/{quote(track_id, safe='')}/mjpeg"
    updated_track = moq_video_subscriber.get_discovered_track(track_id)

    await _broadcast_video_tracks()

    return {
        "ok": True,
        "status": "success",
        "track": updated_track,
        "tracks": _list_all_video_tracks(),
        "subscribed_tracks": moq_video_subscriber.get_subscribed_tracks(),
        "player": player,
        "bootstrap": moq_video_subscriber.get_preview_bridge_snapshot(),
        "subscription_debug": moq_video_subscriber.get_track_debug_info(),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/subscriber/start")
async def start_or_switch_webui_subscription(
    request: Request,
    payload: Dict[str, Any] | None = None,
):
    """Start/switch a browser preview subscription, matching examples/webui/server.py."""
    return await _start_or_switch_moq_subscription(payload or {}, request)


@app.delete("/api/moq/tracks/{track_id}")
async def delete_moq_track(track_id: str):
    """Remove a track from the WebUI track list."""
    if not MOQ_AVAILABLE:
        raise HTTPException(status_code=503, detail="MOQ not available")

    removed = await moq_video_subscriber.remove_discovered_track(track_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Track not found")

    await _broadcast_video_tracks()

    return {
        "status": "success",
        "trackId": track_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/video/stream/{track_id}/mjpeg")
async def stream_moq_video_as_mjpeg(track_id: str, request: Request):
    """Serve a watched track as MJPEG over HTTP."""
    if not MOQ_AVAILABLE:
        raise HTTPException(status_code=503, detail="MOQ not available")

    async def generate():
        last_fragment_count = -1
        last_jpeg_sequence = -1
        last_keepalive = asyncio.get_running_loop().time()

        while True:
            if await request.is_disconnected():
                break

            status = moq_video_subscriber.get_mjpeg_track_status(track_id)
            fragment_count = int(status.get("fragment_count") or 0)
            jpeg_sequence = int(status.get("jpeg_sequence") or 0)
            jpeg_bytes = None
            if jpeg_sequence > 0 and jpeg_sequence != last_jpeg_sequence:
                jpeg_bytes = await moq_video_subscriber.get_latest_jpeg_frame(track_id)

            if jpeg_bytes:
                last_fragment_count = fragment_count
                last_jpeg_sequence = jpeg_sequence
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: "
                    + str(len(jpeg_bytes)).encode("ascii")
                    + b"\r\n\r\n"
                    + jpeg_bytes
                    + b"\r\n"
                )
                continue

            now = asyncio.get_running_loop().time()
            if now - last_keepalive >= 10:
                last_keepalive = now
                yield b": keepalive\n\n"

            await asyncio.sleep(0.05)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/api/video/stream/{track_id}/latest")
async def get_latest_moq_video_frame(track_id: str):
    """Return the latest MJPEG frame snapshot for a watched track."""
    if not MOQ_AVAILABLE:
        raise HTTPException(status_code=503, detail="MOQ not available")

    jpeg_bytes = await moq_video_subscriber.get_latest_jpeg_frame(track_id)
    if not jpeg_bytes:
        raise HTTPException(status_code=404, detail="No frame available")

    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/video/stream/{track_id}/info")
async def get_moq_video_stream_info(track_id: str):
    """Get the current MJPEG playback state for a watched track."""
    if not MOQ_AVAILABLE:
        return {
            "track_id": track_id,
            "status": "unavailable",
            "has_frame": False,
            "metadata": None,
        }

    info = moq_video_subscriber.get_mjpeg_track_status(track_id)
    return {
        **info,
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

        # Filter video tracks and register them for later on-demand watch
        video_tracks = []

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
                    f"[Subscribe Track] Registering video track: {track_id}, namespace: {namespace_parts}, track: {track_name}"
                )
                add_log_entry(
                    f"MOQ track discovered: track_id={track_id} namespace={namespace_str} track={track_name}",
                    "info",
                )

                track_record = moq_video_subscriber.register_discovered_track(
                    track_id=track_id,
                    namespace=namespace_parts,
                    track_name=track_name,
                    agent_id=dst_agent_id,
                    task_id=task_id,
                )

                video_tracks.append(track_record)

        # Broadcast to frontend about new video tracks
        if video_tracks:
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
            f"ACF -> Monitor: Discovered {len(video_tracks)} video tracks for {dst_agent_id}",
            "info",
        )

        return {
            "status": "success",
            "agent_id": dst_agent_id,
            "task_id": task_id,
            "total_tracks": len(track_list),
            "video_tracks": video_tracks,
            "discovered_count": len(video_tracks),
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
        _record_local_log(
            "pipeline",
            log_message["payload"]["abstract"] or log_message["payload"]["content"],
            body,
            source_name=body.get("source"),
            task_id=body.get("task_id"),
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
                claim_names = _claim_agent_names_from_content(content, agent_id)
                if claim_names and (_is_identifier_like_name(agent_name) or not agent_name):
                    agent_name = claim_names[0]

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

                    cache_entry = _ensure_agent_cache_entry(
                        agent_id,
                        agent_name=agent_name or agent_id.split(":")[-1][:20],
                    )
                    _sync_agent_timeline(
                        cache_entry,
                        status="online",
                        timestamp=timestamp,
                    )
                    cache_entry["work_status"] = work_status
                    cache_entry["current_task"] = task_desc
                    if is_demo:
                        cache_entry["is_demo"] = True

                    # Broadcast status update
                    status_message = {
                        "type": "AGENT_STATUS_UPDATE",
                        "payload": {
                            "agent_id": agent_id,
                            "agent_name": cache_entry["agent_name"],
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
                    _upsert_local_agent(
                        agent_id,
                        agent_name=cache_entry["agent_name"],
                        agent_status=cache_entry.get("agent_status", "online"),
                        work_status=work_status,
                        current_task=task_desc,
                        agent_capability=cache_entry.get("agent_capability")
                        if isinstance(cache_entry.get("agent_capability"), list)
                        else None,
                        last_update=timestamp,
                        launch_time=cache_entry.get("launch_time"),
                        offline_time=cache_entry.get("offline_time"),
                    )
                    if task_id:
                        _upsert_local_task(
                            task_id,
                            agent_id,
                            task_description=task_desc or abstract,
                            task_name=task_desc or abstract,
                            task_type=_extract_task_type(task_desc or abstract) or "General",
                            status="processing",
                            created_at=timestamp,
                            updated_at=timestamp,
                        )
                    _record_local_log(
                        "pipeline",
                        abstract or task_desc,
                        body,
                        source_name=body.get("source"),
                        agent_id=agent_id,
                        task_id=task_id,
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
        "identity-applications": ("working", "Applying for identity"),
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
        "Agent-cards": ("working", "Publishing agent card"),
        "vc-verifications": ("working", "VC verification in progress"),
        "SETUP connection": ("online", "Setting up connection"),
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
        "MoQ Connection": ("tracking", "Setting up MoQ relay connection"),
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
        claim_names = _claim_agent_names_from_content(content, agent_id)
        if claim_names and (_is_identifier_like_name(agent_name) or not agent_name):
            agent_name = claim_names[0]
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
        _record_local_log(
            "element",
            f"{log_type}: {task_desc}",
            body,
            source_name=element_id,
            agent_id=agent_id,
            task_id=body.get("task_id") or content.get("task_id"),
        )

        # Update agent status cache
        if agent_id:
            cache_entry = _ensure_agent_cache_entry(
                agent_id,
                agent_name=agent_name or agent_id.split(":")[-1][:20],
            )
            if content.get("agent_capability") and not cache_entry.get("agent_capability"):
                cache_entry["agent_capability"] = (
                    content.get("agent_capability", [])
                    if isinstance(content.get("agent_capability"), list)
                    else [content.get("agent_capability", "")]
                )
            _sync_agent_timeline(
                cache_entry,
                status="online",
                timestamp=timestamp,
            )
            cache_entry["work_status"] = work_status
            cache_entry["current_task"] = task_desc
            if is_demo:
                cache_entry["is_demo"] = True

            _upsert_local_agent(
                agent_id,
                agent_name=cache_entry["agent_name"],
                agent_status=cache_entry.get("agent_status", "online"),
                work_status=work_status,
                current_task=task_desc,
                agent_capability=cache_entry.get("agent_capability")
                if isinstance(cache_entry.get("agent_capability"), list)
                else None,
                last_update=timestamp,
                launch_time=cache_entry.get("launch_time"),
                offline_time=cache_entry.get("offline_time"),
            )
            element_task_id = str(body.get("task_id") or content.get("task_id") or "").strip()
            if element_task_id:
                _upsert_local_task(
                    element_task_id,
                    agent_id,
                    task_description=task_desc,
                    task_name=task_desc,
                    task_type=log_type,
                    status="processing",
                    created_at=timestamp,
                    updated_at=timestamp,
                )

            # Add log entry
            cache_entry["logs"].append(log_entry)
            # Keep only last 10 logs
            if len(cache_entry["logs"]) > 10:
                cache_entry["logs"] = cache_entry["logs"][-10:]

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
                        _reset_local_cache_state()
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

    FRONTEND_BUILD_DIR = ROOT_DIR / "frontend" / "build"
    FRONTEND_STATIC_DIR = FRONTEND_BUILD_DIR / "static"
    FRONTEND_INDEX_FILE = FRONTEND_BUILD_DIR / "index.html"

    app.mount(
        "/static",
        NoCacheStaticFiles(directory=str(FRONTEND_STATIC_DIR)),
        name="static",
    )

    @app.get("/")
    async def serve_react():
        """Serve React frontend with no-cache headers"""
        response = FileResponse(
            str(FRONTEND_INDEX_FILE),
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
            str(FRONTEND_INDEX_FILE),
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
