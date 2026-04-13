#!/usr/bin/env python3
"""
MOQ Video Stream Subscriber for Monitor Backend
Subscribes to video streams from MOQ Relay and forwards to WebSocket clients
"""

import asyncio
import logging
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass
from datetime import datetime

# Import MOQ modules
import sys
sys.path.insert(0, '/home/acn/cxr/acn_gw')

from moq.sub.subscriber import MOQSubscriber, ReceivedObject
from moq.encoding import FullTrackName

logger = logging.getLogger(__name__)


@dataclass
class VideoFrame:
    """Video frame received from MOQ"""
    track_name: str
    group_id: int
    object_id: int
    timestamp: datetime
    payload: bytes
    frame_type: str  # 'keyframe' or 'deltaframe'


class MOQVideoSubscriber:
    """
    MOQ Video Stream Subscriber
    Connects to MOQ Relay, subscribes to video tracks, and forwards frames
    """
    
    def __init__(self, relay_host: str = "localhost", relay_port: int = 9003):
        self.relay_host = relay_host
        self.relay_port = relay_port
        
        # MOQ Subscriber
        self._subscriber: Optional[MOQSubscriber] = None
        
        # Active video subscriptions
        self._video_tracks: Dict[str, FullTrackName] = {}  # track_id -> FullTrackName
        
        # Frame buffer for each track (keeps last few seconds)
        self._frame_buffers: Dict[str, List[VideoFrame]] = {}
        
        # Callbacks
        self._on_frame_received: Optional[Callable[[VideoFrame], None]] = None
        self._on_track_subscribed: Optional[Callable[[str], None]] = None
        self._on_track_unsubscribed: Optional[Callable[[str], None]] = None
        
        # Running flag
        self._running = False
        self._connection_task: Optional[asyncio.Task] = None
        
        logger.info(f"MOQVideoSubscriber initialized for {relay_host}:{relay_port}")
    
    def set_callbacks(self,
                     on_frame_received: Optional[Callable[[VideoFrame], None]] = None,
                     on_track_subscribed: Optional[Callable[[str], None]] = None,
                     on_track_unsubscribed: Optional[Callable[[str], None]] = None):
        """Set event callbacks"""
        self._on_frame_received = on_frame_received
        self._on_track_subscribed = on_track_subscribed
        self._on_track_unsubscribed = on_track_unsubscribed
    
    async def start(self):
        """Start the MOQ subscriber"""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting MOQ Video Subscriber")
        
        # Start connection loop
        self._connection_task = asyncio.create_task(self._connection_loop())
    
    async def stop(self):
        """Stop the MOQ subscriber"""
        logger.info("Stopping MOQ Video Subscriber")
        self._running = False
        
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
        
        if self._subscriber:
            self._subscriber.disconnect()
            self._subscriber = None
    
    async def _connection_loop(self):
        """Maintain connection to MOQ Relay"""
        while self._running:
            try:
                if not self._subscriber:
                    logger.info(f"Connecting to MOQ Relay at {self.relay_host}:{self.relay_port}")
                    
                    # Create subscriber
                    self._subscriber = MOQSubscriber(self.relay_host, self.relay_port)
                    self._subscriber.set_handlers(
                        on_connected=self._on_connected,
                        on_disconnected=self._on_disconnected,
                        on_object_received=self._on_object_received,
                        on_subscription_accepted=self._on_subscription_accepted,
                        on_subscription_rejected=self._on_subscription_rejected
                    )
                    
                    # Connect
                    connected = await self._subscriber.connect()
                    if not connected:
                        logger.error("Failed to connect to MOQ Relay")
                        self._subscriber = None
                        await asyncio.sleep(5)
                        continue
                    
                    # Resubscribe to previously active tracks
                    for track_id, track_name in list(self._video_tracks.items()):
                        logger.info(f"Resubscribing to track: {track_id}")
                        await self._subscriber.subscribe(track_name)
                
                # Keep connection alive
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Connection loop error: {e}")
                if self._subscriber:
                    self._subscriber.disconnect()
                    self._subscriber = None
                await asyncio.sleep(5)
    
    async def subscribe_to_track(self, track_id: str, namespace: List[str], track_name: str) -> bool:
        """
        Subscribe to a video track
        
        Args:
            track_id: Unique identifier for this track (e.g., "agent001_camera")
            namespace: Track namespace (e.g., ["acn", "agent", "001"])
            track_name: Track name (e.g., b"camera")
        
        Returns:
            True if subscription initiated
        """
        if track_id in self._video_tracks:
            logger.warning(f"Already subscribed to track: {track_id}")
            return True
        
        # Create FullTrackName
        full_track_name = FullTrackName(
            namespace=[ns.encode() for ns in namespace],
            track_name=track_name.encode() if isinstance(track_name, str) else track_name
        )
        
        self._video_tracks[track_id] = full_track_name
        
        # Subscribe if connected
        if self._subscriber:
            try:
                logger.info(f"Subscribing to track: {track_id} ({full_track_name})")
                await self._subscriber.subscribe(full_track_name)
                return True
            except Exception as e:
                logger.error(f"Failed to subscribe to {track_id}: {e}")
                return False
        
        return True  # Will subscribe when connected
    
    async def unsubscribe_from_track(self, track_id: str):
        """Unsubscribe from a video track"""
        if track_id not in self._video_tracks:
            return
        
        track_name = self._video_tracks[track_id]
        del self._video_tracks[track_id]
        
        if track_id in self._frame_buffers:
            del self._frame_buffers[track_id]
        
        if self._subscriber:
            try:
                await self._subscriber.unsubscribe(track_name)
            except Exception as e:
                logger.error(f"Failed to unsubscribe from {track_id}: {e}")
        
        if self._on_track_unsubscribed:
            self._on_track_unsubscribed(track_id)
        
        logger.info(f"Unsubscribed from track: {track_id}")
    
    def get_subscribed_tracks(self) -> List[str]:
        """Get list of subscribed track IDs"""
        return list(self._video_tracks.keys())
    
    def get_frame_buffer(self, track_id: str) -> List[VideoFrame]:
        """Get frame buffer for a track"""
        return self._frame_buffers.get(track_id, [])
    
    def _on_connected(self):
        """Handler for MOQ connection established"""
        logger.info("Connected to MOQ Relay")
    
    def _on_disconnected(self):
        """Handler for MOQ connection lost"""
        logger.warning("Disconnected from MOQ Relay")
        self._subscriber = None
    
    def _on_subscription_accepted(self, track_name: FullTrackName):
        """Handler for subscription accepted"""
        # Find track_id from track_name
        for tid, tn in self._video_tracks.items():
            if tn == track_name:
                logger.info(f"Subscription accepted for track: {tid}")
                if self._on_track_subscribed:
                    self._on_track_subscribed(tid)
                break
    
    def _on_subscription_rejected(self, track_name: FullTrackName, reason: str):
        """Handler for subscription rejected"""
        logger.warning(f"Subscription rejected for {track_name}: {reason}")
    
    def _on_object_received(self, obj: ReceivedObject):
        """Handler for received MOQ object (video frame)"""
        try:
            # Find track_id from track_alias
            track_id = None
            for tid, tn in self._video_tracks.items():
                # Note: track_alias is assigned by session, we need to map it
                # For now, use the namespace/track_name from the object
                track_id = tid
                break
            
            if not track_id:
                return
            
            # Create VideoFrame
            frame = VideoFrame(
                track_name=track_id,
                group_id=obj.group_id,
                object_id=obj.object_id,
                timestamp=datetime.now(),
                payload=obj.payload,
                frame_type='keyframe' if obj.object_id == 0 else 'deltaframe'
            )
            
            # Add to buffer
            if track_id not in self._frame_buffers:
                self._frame_buffers[track_id] = []
            
            self._frame_buffers[track_id].append(frame)
            
            # Keep only last 30 frames (1 second at 30fps)
            if len(self._frame_buffers[track_id]) > 30:
                self._frame_buffers[track_id] = self._frame_buffers[track_id][-30:]
            
            # Notify callback
            if self._on_frame_received:
                self._on_frame_received(frame)
            
        except Exception as e:
            logger.error(f"Error processing received object: {e}")


# Global instance for the application
moq_video_subscriber = MOQVideoSubscriber()
