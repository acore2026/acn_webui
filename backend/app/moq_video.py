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
import os

# 使用当前webui目录下的moq文件夹
WEBUI_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, WEBUI_ROOT)

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
        self._track_states: Dict[str, str] = {}
        self._track_object_counts: Dict[str, int] = {}

        # Callbacks
        self._on_frame_received: Optional[Callable[[VideoFrame], None]] = None
        self._on_track_subscribed: Optional[Callable[[str], None]] = None
        self._on_track_unsubscribed: Optional[Callable[[str], None]] = None

        # Running flag
        self._running = False
        self._connection_task: Optional[asyncio.Task] = None

        logger.info(f"MOQVideoSubscriber initialized for {relay_host}:{relay_port}")

    def set_callbacks(
        self,
        on_frame_received: Optional[Callable[[VideoFrame], None]] = None,
        on_track_subscribed: Optional[Callable[[str], None]] = None,
        on_track_unsubscribed: Optional[Callable[[str], None]] = None,
    ):
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
                    logger.info(
                        f"Connecting to MOQ Relay at {self.relay_host}:{self.relay_port}"
                    )

                    # Create subscriber
                    self._subscriber = MOQSubscriber(self.relay_host, self.relay_port)
                    self._subscriber.set_handlers(
                        on_connected=self._on_connected,
                        on_disconnected=self._on_disconnected,
                        on_object_received=self._on_object_received,
                        on_subscription_accepted=self._on_subscription_accepted,
                        on_subscription_rejected=self._on_subscription_rejected,
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

    async def subscribe_to_track(
        self, track_id: str, namespace: List[str], track_name: str
    ) -> bool:
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
            track_name=track_name.encode()
            if isinstance(track_name, str)
            else track_name,
        )

        self._video_tracks[track_id] = full_track_name
        self._track_states[track_id] = "requested"
        self._track_object_counts.setdefault(track_id, 0)
        logger.info(
            "Track request registered: track_id=%s namespace=%s track_name=%s connected=%s",
            track_id,
            "/".join(namespace) if namespace else "",
            track_name,
            bool(self._subscriber),
        )

        # Subscribe if connected
        if self._subscriber:
            try:
                logger.info(
                    f"Subscribing to track immediately: {track_id} ({full_track_name})"
                )
                await self._subscriber.subscribe(full_track_name)
                return True
            except Exception as e:
                self._track_states[track_id] = "rejected"
                logger.error(f"Failed to subscribe to {track_id}: {e}")
                return False

        self._track_states[track_id] = "pending"
        logger.info(f"Track queued until relay connection is ready: {track_id}")
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

    def get_track_debug_info(self) -> List[Dict[str, object]]:
        """Get subscription and object state for debugging."""
        debug_rows = []
        for track_id, full_track_name in self._video_tracks.items():
            debug_rows.append(
                {
                    "track_id": track_id,
                    "namespace": [part.decode() for part in full_track_name.namespace],
                    "track_name": full_track_name.track_name.decode()
                    if isinstance(full_track_name.track_name, bytes)
                    else str(full_track_name.track_name),
                    "state": self._track_states.get(track_id, "unknown"),
                    "object_count": self._track_object_counts.get(track_id, 0),
                    "buffered_frames": len(self._frame_buffers.get(track_id, [])),
                }
            )
        return debug_rows

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
                self._track_states[tid] = "accepted"
                logger.info(f"Subscription accepted for track: {tid}")
                if self._on_track_subscribed:
                    self._on_track_subscribed(tid)
                break

    def _on_subscription_rejected(self, track_name: FullTrackName, reason: str):
        """Handler for subscription rejected"""
        for tid, tn in self._video_tracks.items():
            if tn == track_name:
                self._track_states[tid] = "rejected"
                logger.warning(f"Subscription rejected for {tid}: {reason}")
                break
        else:
            logger.warning(f"Subscription rejected for {track_name}: {reason}")

    def _on_object_received(self, obj: ReceivedObject):
        """Handler for received MOQ object (video frame)"""
        try:
            logger.info(
                f"[MOQ] _on_object_received called: track_alias={obj.track_alias}, group_id={obj.group_id}, object_id={obj.object_id}, payload_len={len(obj.payload)}"
            )

            # Find track_id from track_alias via subscriber's internal mapping
            track_id = None
            if self._subscriber and hasattr(self._subscriber, "_track_aliases"):
                full_track_name = self._subscriber._track_aliases.get(obj.track_alias)
                logger.info(
                    f"[MOQ] Looking up track_alias {obj.track_alias}: found={full_track_name is not None}, registered_tracks={list(self._video_tracks.keys())[:3]}"
                )
                if full_track_name:
                    # Find matching track_id from our registered tracks
                    for tid, tn in self._video_tracks.items():
                        if tn == full_track_name:
                            track_id = tid
                            logger.info(f"[MOQ] Matched track_id={tid}")
                            break

            if not track_id:
                logger.warning(
                    f"[MOQ] Received object for unknown track_alias: {obj.track_alias}, available aliases={list(self._subscriber._track_aliases.keys()) if self._subscriber and hasattr(self._subscriber, '_track_aliases') else 'N/A'}"
                )
                return

            # Create VideoFrame
            frame = VideoFrame(
                track_name=track_id,
                group_id=obj.group_id,
                object_id=obj.object_id,
                timestamp=datetime.now(),
                payload=obj.payload,
                frame_type="keyframe" if obj.object_id == 0 else "deltaframe",
            )

            # Add to buffer
            if track_id not in self._frame_buffers:
                self._frame_buffers[track_id] = []

            self._frame_buffers[track_id].append(frame)

            # Keep only last 30 frames (1 second at 30fps)
            if len(self._frame_buffers[track_id]) > 30:
                self._frame_buffers[track_id] = self._frame_buffers[track_id][-30:]

            self._track_states[track_id] = "received"
            self._track_object_counts[track_id] = (
                self._track_object_counts.get(track_id, 0) + 1
            )
            object_count = self._track_object_counts[track_id]
            if object_count == 1 or object_count % 10 == 0:
                logger.info(
                    "MOQ object received: track_id=%s group_id=%s object_id=%s payload_bytes=%s total_objects=%s",
                    track_id,
                    obj.group_id,
                    obj.object_id,
                    len(obj.payload),
                    object_count,
                )

            # Notify callback
            if self._on_frame_received:
                try:
                    import asyncio

                    if asyncio.iscoroutinefunction(self._on_frame_received):
                        asyncio.create_task(self._on_frame_received(frame))
                    else:
                        self._on_frame_received(frame)
                except Exception as cb_err:
                    logger.error(f"Callback error: {cb_err}")

        except Exception as e:
            logger.error(f"Error processing received object: {e}")


# Global instance for the application
moq_video_subscriber = MOQVideoSubscriber()
