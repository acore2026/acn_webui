# Video Stream Manager for LiveFeed
# Supports WebRTC signaling for agent video streams

from typing import Dict, List, Any, Optional
import json
import asyncio
from dataclasses import dataclass, asdict
from enum import Enum

class StreamStatus(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    ERROR = "error"
    DISCONNECTED = "disconnected"

@dataclass
class VideoStream:
    stream_id: str
    agent_id: str
    agent_name: str
    stream_type: str  # "camera", "thermal", "infrared"
    status: StreamStatus
    resolution: str
    fps: int
    bitrate: int
    webrtc_offer: Optional[str] = None
    webrtc_answer: Optional[str] = None
    ice_candidates: List[Dict] = None
    viewers: int = 0
    
    def __post_init__(self):
        if self.ice_candidates is None:
            self.ice_candidates = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "stream_type": self.stream_type,
            "status": self.status.value,
            "resolution": self.resolution,
            "fps": self.fps,
            "bitrate": self.bitrate,
            "viewers": self.viewers
        }


class VideoStreamManager:
    """Manages video streams from agents"""
    
    def __init__(self):
        self.streams: Dict[str, VideoStream] = {}
        self.agent_streams: Dict[str, List[str]] = {}  # agent_id -> list of stream_ids
        self.connection_manager = None  # Will be set to WebSocket ConnectionManager
    
    def set_connection_manager(self, manager):
        """Set the WebSocket connection manager for broadcasting"""
        self.connection_manager = manager
    
    def register_stream(self, agent_id: str, agent_name: str, stream_type: str = "camera",
                       resolution: str = "1920x1080", fps: int = 30) -> VideoStream:
        """Register a new video stream from an agent"""
        stream_id = f"{agent_id}_{stream_type}"
        
        stream = VideoStream(
            stream_id=stream_id,
            agent_id=agent_id,
            agent_name=agent_name,
            stream_type=stream_type,
            status=StreamStatus.IDLE,
            resolution=resolution,
            fps=fps,
            bitrate=4500
        )
        
        self.streams[stream_id] = stream
        
        if agent_id not in self.agent_streams:
            self.agent_streams[agent_id] = []
        if stream_id not in self.agent_streams[agent_id]:
            self.agent_streams[agent_id].append(stream_id)
        
        print(f"[VideoStream] Registered stream {stream_id} for agent {agent_name}")
        return stream
    
    def unregister_stream(self, stream_id: str):
        """Unregister a video stream"""
        if stream_id in self.streams:
            stream = self.streams[stream_id]
            agent_id = stream.agent_id
            
            del self.streams[stream_id]
            
            if agent_id in self.agent_streams:
                if stream_id in self.agent_streams[agent_id]:
                    self.agent_streams[agent_id].remove(stream_id)
            
            print(f"[VideoStream] Unregistered stream {stream_id}")
    
    def update_stream_status(self, stream_id: str, status: StreamStatus):
        """Update stream status"""
        if stream_id in self.streams:
            self.streams[stream_id].status = status
            print(f"[VideoStream] Stream {stream_id} status: {status.value}")
    
    def set_webrtc_offer(self, stream_id: str, offer: str):
        """Set WebRTC offer from agent"""
        if stream_id in self.streams:
            self.streams[stream_id].webrtc_offer = offer
            self.streams[stream_id].status = StreamStatus.CONNECTING
    
    def set_webrtc_answer(self, stream_id: str, answer: str):
        """Set WebRTC answer for agent"""
        if stream_id in self.streams:
            self.streams[stream_id].webrtc_answer = answer
    
    def add_ice_candidate(self, stream_id: str, candidate: Dict):
        """Add ICE candidate"""
        if stream_id in self.streams:
            self.streams[stream_id].ice_candidates.append(candidate)
    
    def get_stream(self, stream_id: str) -> Optional[VideoStream]:
        """Get stream by ID"""
        return self.streams.get(stream_id)
    
    def get_agent_streams(self, agent_id: str) -> List[VideoStream]:
        """Get all streams for an agent"""
        stream_ids = self.agent_streams.get(agent_id, [])
        return [self.streams[sid] for sid in stream_ids if sid in self.streams]
    
    def get_all_streams(self) -> List[Dict[str, Any]]:
        """Get all active streams as dict"""
        return [stream.to_dict() for stream in self.streams.values()]
    
    async def broadcast_stream_update(self, stream_id: str):
        """Broadcast stream update to all connected clients"""
        if stream_id in self.streams and self.connection_manager:
            stream = self.streams[stream_id]
            message = {
                "type": "VIDEO_STREAM_UPDATE",
                "payload": stream.to_dict()
            }
            await self.connection_manager.broadcast(message)
    
    async def broadcast_stream_list(self):
        """Broadcast full stream list"""
        if self.connection_manager:
            message = {
                "type": "VIDEO_STREAM_LIST",
                "payload": {
                    "streams": self.get_all_streams()
                }
            }
            await self.connection_manager.broadcast(message)


# Global instance
video_stream_manager = VideoStreamManager()
