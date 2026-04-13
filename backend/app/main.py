#!/usr/bin/env python3
"""
ACN Agent Monitor Backend
FastAPI + WebSocket server for agent monitoring
Port: 9005
"""

import asyncio
import json
import sqlite3
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import uvicorn
from typing import List, Dict, Any
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
DB_PATH = "/home/acn/cxr/acn_gw/agent_gw/agent_gw.db"
# DB_PATH = "/root/lpx/webui/test/test_agent_gw.db"

# ARF Service Configuration
ARF_HOST = "localhost"  # ARF service host
ARF_CLEAR_URL = f"http://{ARF_HOST}:9001/clear"

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
            print(f"[WebSocket] Client disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        disconnected = []
        msg_type = message.get("type", "unknown")
        print(f"[Broadcast] Sending {msg_type} to {len(self.active_connections)} clients")
        
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
            if agent.get('agent_capability'):
                try:
                    agent['agent_capability'] = json.loads(agent['agent_capability'])
                except:
                    agent['agent_capability'] = []
            else:
                agent['agent_capability'] = []
            
            # Determine agent status: if agent has task_id (exists in tasks table), mark as working
            original_status = agent.get('agent_status', 'offline')
            if agent.get('agent_id') in agents_with_tasks:
                agent['agent_status'] = 'working'
            else:
                agent['agent_status'] = original_status if original_status else 'offline'
            
            agents.append(agent)
        return agents
    except Exception as e:
        print(f"[Database Error] {e}")
        return []

# ARF Service helper
async def call_arf_clear() -> Dict[str, Any]:
    """Call ARF /clear endpoint to reset environment"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "method": "POST",
                "url": "/clear",
                "body": {}
            }
            print(f"[ARF] Sending clear request to {ARF_CLEAR_URL}")
            response = await client.post(
                ARF_CLEAR_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            print(f"[ARF] Clear response: {response.status_code}")
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else None
            }
    except httpx.ConnectError as e:
        print(f"[ARF Error] Cannot connect to ARF service: {e}")
        return {"success": False, "error": "Cannot connect to ARF service", "detail": str(e)}
    except Exception as e:
        print(f"[ARF Error] {e}")
        return {"success": False, "error": str(e)}

# Video frame handler for MOQ
async def handle_moq_video_frame(frame: 'VideoFrame'):
    """Handle received video frame from MOQ"""
    # Broadcast to all WebSocket clients
    await manager.broadcast({
        "type": "VIDEO_FRAME",
        "payload": {
            "track_id": frame.track_name,
            "group_id": frame.group_id,
            "object_id": frame.object_id,
            "timestamp": frame.timestamp.isoformat(),
            "frame_type": frame.frame_type,
            "payload_size": len(frame.payload)
            # Note: Actual video data is not sent via WebSocket
            # Instead, we send metadata and use a separate mechanism
        }
    })

def on_moq_track_subscribed(track_id: str):
    """Handler for MOQ track subscribed"""
    print(f"[MOQ] Track subscribed: {track_id}")

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
            on_track_subscribed=on_moq_track_subscribed
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
    lifespan=lifespan
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
    agents = get_agents_from_db()
    return {
        "agents": agents,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "websocket_clients": len(manager.active_connections)
    }

# Log buffer for frontend display
log_buffer = []
max_log_entries = 1000

def add_log_entry(message: str, level: str = "info"):
    """Add a log entry to the buffer"""
    log_entry = {
        "time": datetime.utcnow().isoformat(),
        "level": level,
        "message": message
    }
    log_buffer.append(log_entry)
    if len(log_buffer) > max_log_entries:
        log_buffer.pop(0)

@app.get("/api/logs")
async def get_logs(limit: int = 100):
    """Get recent backend logs"""
    return {
        "logs": log_buffer[-limit:] if log_buffer else [],
        "total": len(log_buffer),
        "timestamp": datetime.utcnow().isoformat()
    }

# MOQ Video Stream API Endpoints (outside static file block)
@app.get("/api/moq/status")
async def get_moq_status():
    """Get MOQ subscriber status"""
    if not MOQ_AVAILABLE:
        return {
            "status": "unavailable",
            "message": "MOQ video subscriber not available"
        }

    return {
        "status": "available",
        "connected": moq_video_subscriber._subscriber is not None,
        "relay_host": moq_video_subscriber.relay_host,
        "relay_port": moq_video_subscriber.relay_port,
        "subscribed_tracks": moq_video_subscriber.get_subscribed_tracks(),
        "timestamp": datetime.utcnow().isoformat()
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
        track_id=track_id,
        namespace=namespace,
        track_name=track_name
    )

    if success:
        return {
            "status": "success",
            "track_id": track_id,
            "namespace": namespace,
            "track_name": track_name,
            "timestamp": datetime.utcnow().isoformat()
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
        "timestamp": datetime.utcnow().isoformat()
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
                "payload_size": len(f.payload)
            }
            for f in recent_frames
        ],
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/moq/auto-subscribe/{agent_id}")
async def auto_subscribe_agent(agent_id: str):
    """Auto-subscribe to common video tracks for an agent"""
    if not MOQ_AVAILABLE:
        return {"status": "error", "message": "MOQ not available"}

    # Common video tracks for an agent
    tracks = [
        ("camera", ["acn", "agent", agent_id], "camera"),
        ("thermal", ["acn", "agent", agent_id], "thermal"),
    ]

    results = []
    for track_id_suffix, namespace, track_name in tracks:
        track_id = f"{agent_id}_{track_id_suffix}"
        success = await moq_video_subscriber.subscribe_to_track(
            track_id=track_id,
            namespace=namespace,
            track_name=track_name
        )
        results.append({
            "track_id": track_id,
            "success": success
        })

    return {
        "status": "success",
        "agent_id": agent_id,
        "results": results,
        "timestamp": datetime.utcnow().isoformat()
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
                "content": body.get("content", "")
            }
        }
        
        log_msg = f"{log_message['payload']['source']} -> {log_message['payload']['destination']}: {log_message['payload']['abstract'] or log_message['payload']['content'][:50]}"
        print(f"[Pipeline Log] {log_msg}")
        add_log_entry(log_msg, "info")
        
        # Broadcast to all connected WebSocket clients
        await manager.broadcast(log_message)
        
        return {
            "status": "success",
            "message": "Log received and broadcasted",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"[Pipeline Log Error] {e}")
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Agent status tracking
agent_status_cache: Dict[str, Dict[str, Any]] = {}


def get_work_status_from_log_type(log_type: str) -> tuple:
    """Map log_type to work_status and task description"""
    status_map = {
        "ApplyProfile": ("working", "Applying for digital identity"),
        "PublishAgent": ("working", "Registering agent capabilities"),
        "SetupConnection": ("online", "Setting up connection"),
        "LLMMessage": ("working", "Processing LLM message")
    }
    return status_map.get(log_type, ("idle", "Unknown task"))


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
        
        # Determine work status based on log_type
        work_status, task_desc = get_work_status_from_log_type(log_type)
        
        # Create log entry
        log_entry = {
            "time": datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%H:%M:%S') if 'T' in timestamp else datetime.now().strftime('%H:%M:%S'),
            "level": "info",
            "message": f"{log_type}: {task_desc}"
        }
        
        # Add to log buffer
        add_log_entry(f"[{element_id}] {agent_id}: {log_type} - {task_desc}", "info")
        
        # Update agent status cache
        if agent_id:
            if agent_id not in agent_status_cache:
                agent_status_cache[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": agent_name or agent_id.split(':')[-1][:20],
                    "work_status": work_status,
                    "current_task": task_desc,
                    "logs": [],
                    "agent_status": "online",
                    "agent_capability": content.get("agent_capability", []) if isinstance(content.get("agent_capability"), list) else [content.get("agent_capability", "")] if content.get("agent_capability") else [],
                    "last_update": timestamp
                }
            else:
                # Update existing agent status
                agent_status_cache[agent_id]["work_status"] = work_status
                agent_status_cache[agent_id]["current_task"] = task_desc
                if agent_name:
                    agent_status_cache[agent_id]["agent_name"] = agent_name
                agent_status_cache[agent_id]["last_update"] = timestamp
            
            # Add log entry
            agent_status_cache[agent_id]["logs"].append(log_entry)
            # Keep only last 10 logs
            if len(agent_status_cache[agent_id]["logs"]) > 10:
                agent_status_cache[agent_id]["logs"] = agent_status_cache[agent_id]["logs"][-10:]
        
        # Create update message
        update_message = {
            "type": "AGENT_STATUS_UPDATE",
            "payload": {
                "agent_id": agent_id,
                "agent_name": agent_name or (agent_status_cache.get(agent_id, {}).get("agent_name", "")),
                "work_status": work_status,
                "current_task": task_desc,
                "log_type": log_type,
                "element_id": element_id,
                "timestamp": timestamp,
                "log": log_entry,
                "agent": agent_status_cache.get(agent_id, {}) if agent_id else None
            }
        }
        
        print(f"[Element Log] {element_id} | {log_type} | Agent: {agent_id[:30] if agent_id else 'N/A'}... | Status: {work_status}")
        
        # Broadcast to all connected WebSocket clients
        await manager.broadcast(update_message)
        
        return {
            "status": "success",
            "message": "Element log received and agent status updated",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"[Element Log Error] {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    
    try:
        # Send initial data
        agents = get_agents_from_db()
        await manager.send_to(websocket, {
            "type": "AGENT_LIST",
            "payload": {"agents": agents}
        })
        
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
                    await manager.broadcast({
                        "type": "TASK_DISPATCHED",
                        "payload": payload
                    })
                    
                elif msg_type == "EMERGENCY_LAND":
                    print("[Emergency] Landing command received")
                    await manager.broadcast({
                        "type": "EMERGENCY_LAND",
                        "payload": {"timestamp": datetime.utcnow().isoformat()}
                    })
                    
                elif msg_type == "ABORT_ALL":
                    print("[Abort] All tasks command received")
                    await manager.broadcast({
                        "type": "ABORT_ALL",
                        "payload": {"timestamp": datetime.utcnow().isoformat()}
                    })
                    
                elif msg_type == "PING":
                    await manager.send_to(websocket, {
                        "type": "PONG",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                elif msg_type == "REFRESH":
                    print("[Refresh] Clear environment request received")
                    
                    # Call ARF /clear endpoint
                    result = await call_arf_clear()
                    
                    if result.get("success"):
                        # Get fresh agent list after clear
                        agents = get_agents_from_db()
                        
                        # Broadcast refresh completion to all clients
                        await manager.broadcast({
                            "type": "REFRESH_COMPLETE",
                            "payload": {
                                "timestamp": datetime.utcnow().isoformat(),
                                "agents": agents,
                                "arf_response": result.get("response")
                            }
                        })
                        print("[Refresh] Environment cleared and agent list refreshed")
                    else:
                        # Send error to requesting client
                        await manager.send_to(websocket, {
                            "type": "REFRESH_ERROR",
                            "payload": {
                                "timestamp": datetime.utcnow().isoformat(),
                                "error": result.get("error", "Unknown error"),
                                "detail": result.get("detail", "")
                            }
                        })
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
        await asyncio.sleep(5)  # Update every 5 seconds
        
        if manager.active_connections:
            try:
                agents = get_agents_from_db()
                await manager.broadcast({
                    "type": "AGENT_LIST",
                    "payload": {"agents": agents}
                })
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
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response
    
    app.mount("/static", NoCacheStaticFiles(directory="/root/lpx/webui/frontend/build/static"), name="static")
    
    @app.get("/")
    async def serve_react():
        """Serve React frontend with no-cache headers"""
        response = FileResponse(
            "/root/lpx/webui/frontend/build/index.html",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
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
                "Expires": "0"
            }
        )
        return response

    # Video Stream API Endpoints
    @app.get("/api/video/streams")
    async def get_video_streams():
        """Get all active video streams"""
        return {
            "streams": video_stream_manager.get_all_streams(),
            "timestamp": datetime.utcnow().isoformat()
        }

    @app.get("/api/video/streams/{agent_id}")
    async def get_agent_video_streams(agent_id: str):
        """Get video streams for a specific agent"""
        streams = video_stream_manager.get_agent_streams(agent_id)
        return {
            "agent_id": agent_id,
            "streams": [s.to_dict() for s in streams],
            "timestamp": datetime.utcnow().isoformat()
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
            fps=fps
        )

        # Broadcast to all clients
        await video_stream_manager.broadcast_stream_list()

        return {
            "status": "success",
            "stream": stream.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
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
                "timestamp": datetime.utcnow().isoformat()
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
            "timestamp": datetime.utcnow().isoformat()
        }

    @app.post("/api/video/webrtc/ice")
    async def handle_ice_candidate(request: Dict[str, Any]):
        """Handle ICE candidate exchange"""
        stream_id = request.get("stream_id")
        candidate = request.get("candidate")
        is_agent = request.get("is_agent", True)  # True if from agent, False if from viewer

        if stream_id and candidate:
            video_stream_manager.add_ice_candidate(stream_id, {
                "candidate": candidate,
                "is_agent": is_agent
            })

            # Broadcast ICE candidate to the other party
            await manager.broadcast({
                "type": "WEBRTC_ICE_CANDIDATE",
                "payload": {
                    "stream_id": stream_id,
                    "candidate": candidate,
                    "from_agent": is_agent
                }
            })

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
            "timestamp": datetime.utcnow().isoformat()
        }

except Exception as e:
    print(f"[Warning] React build not found or error: {e}. API only mode.")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=9005,
        reload=False,
        log_level="info"
    )
