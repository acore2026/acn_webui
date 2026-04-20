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

# 强制使用当前webui目录下的moq文件夹（绝对路径）
WEBUI_ROOT = "/root/lpx/webui"
MOQ_PATH = os.path.join(WEBUI_ROOT, "moq")

# 在导入任何moq相关模块之前，先清理sys.path
# 移除所有可能包含其他moq实现的路径
original_path = sys.path.copy()
sys.path = []

# 首先添加webui根目录（最高优先级）
sys.path.insert(0, WEBUI_ROOT)

# 然后添加原始路径中不是moq相关的路径
for p in original_path:
    # 跳过包含"moq"但不以webui开头的路径
    if "moq" in p.lower() and not p.startswith(WEBUI_ROOT):
        continue
    if p not in sys.path:
        sys.path.append(p)

# 设置PYTHONPATH环境变量，确保子进程也使用正确的路径
os.environ["PYTHONPATH"] = WEBUI_ROOT + ":" + os.environ.get("PYTHONPATH", "")

# 验证使用的是正确的moq
import moq

if "/root/lpx/webui/moq" not in moq.__file__:
    raise ImportError(
        f"错误的moq模块被加载: {moq.__file__}. 请确保使用 /root/lpx/webui/moq"
    )

# 确认后导入其他模块
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

        # Chunk reassembly buffer for each track (for chunked transmission)
        self._chunk_buffers: Dict[str, Dict[int, Dict[int, bytes]]] = {}
        self._chunk_expected: Dict[str, int] = {}

        logger.info(f"MOQVideoSubscriber initialized for {relay_host}:{relay_port}")

    def _on_object_received(self, obj: ReceivedObject):
        """Handler for received MOQ object (video frame)"""
        try:
            logger.info(
                f"[MOQ] _on_object_received: track_alias={obj.track_alias}, group_id={obj.group_id}, object_id={obj.object_id}, payload_len={len(obj.payload)}"
            )

            # Find track_id from track_alias via subscriber's internal mapping
            track_id = None
            if self._subscriber and hasattr(self._subscriber, "_track_aliases"):
                full_track_name = self._subscriber._track_aliases.get(obj.track_alias)
                logger.info(
                    f"[MOQ] Looking up track_alias {obj.track_alias}: found={full_track_name is not None}"
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
                    f"[MOQ] Received object for unknown track_alias: {obj.track_alias}"
                )
                return

            # Handle chunked transmission
            # MoQClientChunked uses group_id as frame_id, object_id as chunk_id
            frame_id = obj.group_id
            chunk_id = obj.object_id

            # Initialize chunk buffer for this track
            if track_id not in self._chunk_buffers:
                self._chunk_buffers[track_id] = {}
                self._chunk_expected[track_id] = {}

            # Add chunk to buffer
            if frame_id not in self._chunk_buffers[track_id]:
                self._chunk_buffers[track_id][frame_id] = {}
                logger.info(f"[MOQ] Started receiving frame {frame_id}")

            self._chunk_buffers[track_id][frame_id][chunk_id] = obj.payload

            # Check if this is the last chunk (small payload indicates last chunk)
            # or if we have enough chunks to form a complete frame
            chunks = self._chunk_buffers[track_id][frame_id]
            total_size = sum(len(c) for c in chunks.values())

            logger.info(
                f"[MOQ] Frame {frame_id}: received chunk {chunk_id}, total_chunks={len(chunks)}, total_size={total_size}"
            )

            # Try to reassemble frame if payload is complete
            # A complete VideoFrame should have at least HEADER_SIZE (52) bytes
            if total_size >= 52:
                # Sort chunks by chunk_id and reassemble
                sorted_chunks = [chunks[i] for i in sorted(chunks.keys())]
                reassembled_data = b"".join(sorted_chunks)

                logger.info(
                    f"[MOQ] Reassembled frame {frame_id}: {len(reassembled_data)} bytes"
                )

                # Try to parse as VideoFrame
                try:
                    from .video_frame_parser import try_parse_video_frame

                    video_frame = try_parse_video_frame(reassembled_data)
                    if video_frame:
                        # Successfully parsed VideoFrame
                        logger.info(
                            f"[MOQ] Parsed VideoFrame: frame_id={video_frame.frame_id}, "
                            f"gop_id={video_frame.gop_id}, {video_frame.width}x{video_frame.height}, "
                            f"fps={video_frame.fps}, keyframe={video_frame.is_keyframe()}, "
                            f"data_size={len(video_frame.data)}"
                        )

                        # Create VideoFrame for callback
                        frame = VideoFrame(
                            track_name=track_id,
                            group_id=video_frame.gop_id,
                            object_id=video_frame.frame_id,
                            timestamp=datetime.now(),
                            payload=video_frame.data,  # Use pure H264 data
                            frame_type="keyframe"
                            if video_frame.is_keyframe()
                            else "deltaframe",
                        )

                        # Clear chunk buffer for this frame
                        del self._chunk_buffers[track_id][frame_id]

                    else:
                        # Not a VideoFrame, use raw data
                        frame = VideoFrame(
                            track_name=track_id,
                            group_id=obj.group_id,
                            object_id=obj.object_id,
                            timestamp=datetime.now(),
                            payload=reassembled_data,
                            frame_type="keyframe"
                            if obj.object_id == 0
                            else "deltaframe",
                        )

                        # Clear chunk buffer
                        del self._chunk_buffers[track_id][frame_id]

                except Exception as parse_err:
                    logger.error(f"[MOQ] Failed to parse VideoFrame: {parse_err}")
                    # Use raw data
                    frame = VideoFrame(
                        track_name=track_id,
                        group_id=obj.group_id,
                        object_id=obj.object_id,
                        timestamp=datetime.now(),
                        payload=reassembled_data,
                        frame_type="keyframe" if obj.object_id == 0 else "deltaframe",
                    )
                    del self._chunk_buffers[track_id][frame_id]

                # Add to buffer
                if track_id not in self._frame_buffers:
                    self._frame_buffers[track_id] = []

                self._frame_buffers[track_id].append(frame)

                # Keep only last 30 frames
                if len(self._frame_buffers[track_id]) > 30:
                    self._frame_buffers[track_id] = self._frame_buffers[track_id][-30:]

                self._track_states[track_id] = "received"
                self._track_object_counts[track_id] = (
                    self._track_object_counts.get(track_id, 0) + 1
                )

                object_count = self._track_object_counts[track_id]
                if object_count == 1 or object_count % 10 == 0:
                    logger.info(
                        "MOQ frame received: track_id=%s frame_id=%s payload_bytes=%s total_frames=%s",
                        track_id,
                        video_frame.frame_id if video_frame else obj.object_id,
                        len(frame.payload),
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
            logger.error(f"Error processing received object: {e}", exc_info=True)


# Global instance for the application
moq_video_subscriber = MOQVideoSubscriber()
