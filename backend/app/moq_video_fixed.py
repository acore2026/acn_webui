#!/usr/bin/env python3
"""
MOQ Video Stream Subscriber for Monitor Backend
Subscribes to video streams from MOQ Relay and forwards to WebSocket clients

FIXED VERSION: Correctly handles chunked transmission protocol from MoQClientChunked
- Small frames (<=16KB): group_id=0, object_id increments -> each object is independent frame
- Large frames (>16KB): group_id=frame_counter, object_id=chunk_index -> needs reassembly
"""

import asyncio
import logging
import time
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass
from datetime import datetime

import sys
import os

WEBUI_ROOT = "/root/lpx/webui"
MOQ_PATH = os.path.join(WEBUI_ROOT, "moq")

original_path = sys.path.copy()
sys.path = []

sys.path.insert(0, WEBUI_ROOT)

for p in original_path:
    if "moq" in p.lower() and not p.startswith(WEBUI_ROOT):
        continue
    if p not in sys.path:
        sys.path.append(p)

os.environ["PYTHONPATH"] = WEBUI_ROOT + ":" + os.environ.get("PYTHONPATH", "")

import moq

if "/root/lpx/webui/moq" not in moq.__file__:
    raise ImportError(
        f"错误的moq模块被加载: {moq.__file__}. 请确保使用 /root/lpx/webui/moq"
    )

from moq.sub.subscriber import MOQSubscriber, ReceivedObject
from moq.encoding import FullTrackName

from .video_frame_parser import VideoFrame, try_parse_video_frame

logger = logging.getLogger(__name__)


@dataclass
class VideoFrameData:
    """Video frame received from MOQ"""

    track_name: str
    group_id: int
    object_id: int
    timestamp: datetime
    payload: bytes
    frame_type: str


class MOQVideoSubscriber:
    """
    MOQ Video Stream Subscriber - FIXED VERSION

    Key fix: Correctly distinguish between small frame mode and chunked mode:
    - group_id=0: small frame mode, each object is a complete independent frame
    - group_id>0: chunked mode, need to reassemble multiple chunks
    """

    def __init__(self, relay_host: str = "localhost", relay_port: int = 9003):
        self.relay_host = relay_host
        self.relay_port = relay_port

        self._subscriber: Optional[MOQSubscriber] = None

        self._video_tracks: Dict[str, FullTrackName] = {}
        self._frame_buffers: Dict[str, List[VideoFrameData]] = {}
        self._track_states: Dict[str, str] = {}
        self._track_object_counts: Dict[str, int] = {}

        self._on_frame_received: Optional[Callable[[VideoFrameData], None]] = None
        self._on_track_subscribed: Optional[Callable[[str], None]] = None
        self._on_track_unsubscribed: Optional[Callable[[str], None]] = None

        self._running = False
        self._connection_task: Optional[asyncio.Task] = None

        self._chunk_buffers: Dict[str, Dict[int, Dict[int, bytes]]] = {}
        self._chunk_timestamps: Dict[str, Dict[int, float]] = {}

        self._small_frame_counters: Dict[str, int] = {}

        logger.info(
            f"[MOQ] MOQVideoSubscriber initialized for {relay_host}:{relay_port}"
        )

    def set_callbacks(
        self,
        on_frame_received: Optional[Callable[[VideoFrameData], None]] = None,
        on_track_subscribed: Optional[Callable[[str], None]] = None,
        on_track_unsubscribed: Optional[Callable[[str], None]] = None,
    ):
        self._on_frame_received = on_frame_received
        self._on_track_subscribed = on_track_subscribed
        self._on_track_unsubscribed = on_track_unsubscribed

    async def start(self):
        if self._running:
            return

        self._running = True
        logger.info("[MOQ] Starting MOQ Video Subscriber")

        self._connection_task = asyncio.create_task(self._connection_loop())

    async def stop(self):
        logger.info("[MOQ] Stopping MOQ Video Subscriber")
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
        while self._running:
            try:
                if not self._subscriber:
                    logger.info(
                        f"[MOQ] Connecting to MOQ Relay at {self.relay_host}:{self.relay_port}"
                    )

                    self._subscriber = MOQSubscriber(self.relay_host, self.relay_port)
                    self._subscriber.set_handlers(
                        on_connected=self._on_connected,
                        on_disconnected=self._on_disconnected,
                        on_object_received=self._on_object_received,
                        on_subscription_accepted=self._on_subscription_accepted,
                        on_subscription_rejected=self._on_subscription_rejected,
                    )

                    connected = await self._subscriber.connect()
                    if not connected:
                        logger.error("[MOQ] Failed to connect to MOQ Relay")
                        self._subscriber = None
                        await asyncio.sleep(5)
                        continue

                    for track_id, track_name in list(self._video_tracks.items()):
                        logger.info(f"[MOQ] Resubscribing to track: {track_id}")
                        await self._subscriber.subscribe(track_name)

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"[MOQ] Connection loop error: {e}")
                if self._subscriber:
                    self._subscriber.disconnect()
                    self._subscriber = None
                await asyncio.sleep(5)

    async def subscribe_to_track(
        self, track_id: str, namespace: List[str], track_name: str
    ) -> bool:
        if track_id in self._video_tracks:
            logger.warning(f"[MOQ] Already subscribed to track: {track_id}")
            return True

        full_track_name = FullTrackName(
            namespace=[ns.encode() for ns in namespace],
            track_name=track_name.encode()
            if isinstance(track_name, str)
            else track_name,
        )

        self._video_tracks[track_id] = full_track_name
        self._track_states[track_id] = "requested"
        self._track_object_counts.setdefault(track_id, 0)
        self._small_frame_counters[track_id] = 0

        logger.info(
            "[MOQ] Track request registered: track_id=%s namespace=%s track_name=%s",
            track_id,
            "/".join(namespace) if namespace else "",
            track_name,
        )

        if self._subscriber:
            try:
                logger.info(f"[MOQ] Subscribing to track: {track_id}")
                await self._subscriber.subscribe(full_track_name)
                return True
            except Exception as e:
                self._track_states[track_id] = "rejected"
                logger.error(f"[MOQ] Failed to subscribe to {track_id}: {e}")
                return False

        self._track_states[track_id] = "pending"
        return True

    async def unsubscribe_from_track(self, track_id: str):
        if track_id not in self._video_tracks:
            return

        track_name = self._video_tracks[track_id]
        del self._video_tracks[track_id]

        if track_id in self._frame_buffers:
            del self._frame_buffers[track_id]
        if track_id in self._chunk_buffers:
            del self._chunk_buffers[track_id]
        if track_id in self._chunk_timestamps:
            del self._chunk_timestamps[track_id]
        if track_id in self._small_frame_counters:
            del self._small_frame_counters[track_id]

        if self._subscriber:
            try:
                await self._subscriber.unsubscribe(track_name)
            except Exception as e:
                logger.error(f"[MOQ] Failed to unsubscribe from {track_id}: {e}")

        if self._on_track_unsubscribed:
            self._on_track_unsubscribed(track_id)

        logger.info(f"[MOQ] Unsubscribed from track: {track_id}")

    def get_subscribed_tracks(self) -> List[str]:
        return list(self._video_tracks.keys())

    def get_frame_buffer(self, track_id: str) -> List[VideoFrameData]:
        return self._frame_buffers.get(track_id, [])

    def get_track_debug_info(self) -> List[Dict[str, object]]:
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
                    "chunk_buffers": len(self._chunk_buffers.get(track_id, {})),
                }
            )
        return debug_rows

    def _on_connected(self):
        logger.info("[MOQ] Connected to MOQ Relay")

    def _on_disconnected(self):
        logger.warning("[MOQ] Disconnected from MOQ Relay")
        self._subscriber = None

    def _on_subscription_accepted(self, track_name: FullTrackName):
        for tid, tn in self._video_tracks.items():
            if tn == track_name:
                self._track_states[tid] = "accepted"
                logger.info(f"[MOQ] Subscription accepted for track: {tid}")
                if self._on_track_subscribed:
                    self._on_track_subscribed(tid)
                break

    def _on_subscription_rejected(self, track_name: FullTrackName, reason: str):
        for tid, tn in self._video_tracks.items():
            if tn == track_name:
                self._track_states[tid] = "rejected"
                logger.warning(f"[MOQ] Subscription rejected for {tid}: {reason}")
                break

    def _on_object_received(self, obj: ReceivedObject):
        """Handle received MOQ object - FIXED to correctly handle both small and chunked frames"""
        try:
            logger.info(
                f"[MOQ] Received: track_alias={obj.track_alias}, group_id={obj.group_id}, "
                f"object_id={obj.object_id}, payload_len={len(obj.payload)}"
            )

            track_id = None
            if self._subscriber and hasattr(self._subscriber, "_track_aliases"):
                full_track_name = self._subscriber._track_aliases.get(obj.track_alias)
                if full_track_name:
                    for tid, tn in self._video_tracks.items():
                        if tn == full_track_name:
                            track_id = tid
                            break

            if not track_id:
                logger.warning(
                    f"[MOQ] Received object for unknown track_alias: {obj.track_alias}"
                )
                return

            group_id = obj.group_id
            object_id = obj.object_id
            payload = obj.payload

            if group_id == 0:
                frame_data = self._handle_small_frame(track_id, object_id, payload)
            else:
                frame_data = self._handle_chunked_frame(
                    track_id, group_id, object_id, payload
                )

            if frame_data:
                self._process_complete_frame(track_id, frame_data)

        except Exception as e:
            logger.error(f"[MOQ] Error processing received object: {e}", exc_info=True)

    def _handle_small_frame(
        self, track_id: str, object_id: int, payload: bytes
    ) -> Optional[bytes]:
        """
        Handle small frame mode (group_id=0)
        Each object is a complete independent frame
        """
        logger.info(
            f"[MOQ] Small frame mode: track={track_id}, object_id={object_id}, size={len(payload)}"
        )

        self._small_frame_counters[track_id] = (
            self._small_frame_counters.get(track_id, 0) + 1
        )

        return payload

    def _handle_chunked_frame(
        self, track_id: str, frame_id: int, chunk_id: int, payload: bytes
    ) -> Optional[bytes]:
        """
        Handle chunked frame mode (group_id>0)
        Multiple chunks need to be reassembled
        """
        if track_id not in self._chunk_buffers:
            self._chunk_buffers[track_id] = {}
            self._chunk_timestamps[track_id] = {}

        if frame_id not in self._chunk_buffers[track_id]:
            self._chunk_buffers[track_id][frame_id] = {}
            self._chunk_timestamps[track_id][frame_id] = time.time()
            logger.info(f"[MOQ] Started receiving chunked frame {frame_id}")

        self._chunk_buffers[track_id][frame_id][chunk_id] = payload

        chunks = self._chunk_buffers[track_id][frame_id]
        total_size = sum(len(c) for c in chunks.values())
        num_chunks = len(chunks)

        logger.info(
            f"[MOQ] Chunked frame {frame_id}: chunk {chunk_id}, total_chunks={num_chunks}, "
            f"total_size={total_size}"
        )

        if num_chunks >= 2:
            sorted_chunks = [chunks[i] for i in sorted(chunks.keys())]
            reassembled = b"".join(sorted_chunks)

            video_frame = try_parse_video_frame(reassembled)
            if video_frame:
                logger.info(
                    f"[MOQ] Reassembled frame {frame_id}: {len(reassembled)} bytes, "
                    f"parsed VideoFrame: {video_frame.width}x{video_frame.height}, "
                    f"keyframe={video_frame.is_keyframe()}, data_size={len(video_frame.data)}"
                )
                del self._chunk_buffers[track_id][frame_id]
                del self._chunk_timestamps[track_id][frame_id]
                return reassembled

        if chunk_id == 0 and len(payload) >= 52:
            video_frame = try_parse_video_frame(payload)
            if video_frame:
                logger.info(
                    f"[MOQ] Single chunk frame {frame_id}: parsed VideoFrame, "
                    f"keyframe={video_frame.is_keyframe()}, data_size={len(video_frame.data)}"
                )
                del self._chunk_buffers[track_id][frame_id]
                del self._chunk_timestamps[track_id][frame_id]
                return payload

        self._cleanup_old_chunks(track_id)

        return None

    def _cleanup_old_chunks(self, track_id: str, max_age: float = 5.0):
        """Remove chunk buffers older than max_age seconds"""
        if track_id not in self._chunk_timestamps:
            return

        current_time = time.time()
        old_frames = [
            fid
            for fid, ts in self._chunk_timestamps[track_id].items()
            if current_time - ts > max_age
        ]

        for fid in old_frames:
            logger.warning(f"[MOQ] Removing stale chunk buffer for frame {fid}")
            del self._chunk_buffers[track_id][fid]
            del self._chunk_timestamps[track_id][fid]

    def _process_complete_frame(self, track_id: str, payload: bytes):
        """Process a complete frame payload"""
        video_frame = try_parse_video_frame(payload)

        if video_frame:
            frame_data = video_frame.data
            frame_type = "keyframe" if video_frame.is_keyframe() else "deltaframe"
            frame_id = video_frame.frame_id
            group_id = video_frame.gop_id

            logger.info(
                f"[MOQ] Processed VideoFrame: track={track_id}, frame_id={frame_id}, "
                f"gop_id={group_id}, {video_frame.width}x{video_frame.height}, "
                f"keyframe={video_frame.is_keyframe()}, data_size={len(frame_data)}"
            )
        else:
            frame_data = payload
            frame_type = "keyframe"
            frame_id = self._track_object_counts.get(track_id, 0)
            group_id = 0

            logger.info(
                f"[MOQ] Processed raw frame: track={track_id}, size={len(payload)}"
            )

        frame = VideoFrameData(
            track_name=track_id,
            group_id=group_id,
            object_id=frame_id,
            timestamp=datetime.now(),
            payload=frame_data,
            frame_type=frame_type,
        )

        if track_id not in self._frame_buffers:
            self._frame_buffers[track_id] = []

        self._frame_buffers[track_id].append(frame)

        if len(self._frame_buffers[track_id]) > 30:
            self._frame_buffers[track_id] = self._frame_buffers[track_id][-30:]

        self._track_states[track_id] = "received"
        self._track_object_counts[track_id] = (
            self._track_object_counts.get(track_id, 0) + 1
        )

        count = self._track_object_counts[track_id]
        if count == 1 or count % 30 == 0:
            logger.info(
                f"[MOQ] Frame #{count}: track={track_id}, payload={len(frame.payload)} bytes"
            )

        if self._on_frame_received:
            try:
                if asyncio.iscoroutinefunction(self._on_frame_received):
                    asyncio.create_task(self._on_frame_received(frame))
                else:
                    self._on_frame_received(frame)
            except Exception as e:
                logger.error(f"[MOQ] Callback error: {e}")


moq_video_subscriber = MOQVideoSubscriber()
