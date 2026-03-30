#!/usr/bin/env python3
"""
ACN Agent Monitor Backend
FastAPI + WebSocket server for agent monitoring
Port: 9050
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

# Database path
DB_PATH = "/root/lpx/acn_gw/agent_gw.db"

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
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
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

# Database helper
def get_agents_from_db() -> List[Dict[str, Any]]:
    """Get all agents from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents")
        rows = cursor.fetchall()
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
            agents.append(agent)
        return agents
    except Exception as e:
        print(f"[Database Error] {e}")
        return []

# Lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("ACN Agent Monitor Backend Starting...")
    print("=" * 60)
    print(f"API: http://0.0.0.0:9050")
    print(f"WebSocket: ws://0.0.0.0:9050/ws")
    print("=" * 60)
    
    # Start background task for agent updates
    task = asyncio.create_task(broadcast_agent_updates())
    
    yield
    
    # Cancel background task on shutdown
    task.cancel()
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
    app.mount("/static", StaticFiles(directory="/root/lpx/webui/frontend/build/static"), name="static")
    
    @app.get("/")
    async def serve_react():
        """Serve React frontend"""
        return FileResponse("/root/lpx/webui/frontend/build/index.html")
    
    @app.get("/{path:path}")
    async def serve_react_routes(path: str):
        """Serve React frontend for all routes"""
        return FileResponse("/root/lpx/webui/frontend/build/index.html")
        
except:
    print("[Warning] React build not found. API only mode.")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=9050,
        reload=False,
        log_level="info"
    )
