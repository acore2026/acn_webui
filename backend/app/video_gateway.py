#!/usr/bin/env python3
"""
Video Gateway - Multi-format Video Transmission
Supports: H.264, MJPEG, WebRTC
Automatically transcodes between formats
"""

import asyncio
import base64
import io
import json
import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Callable, Any
from datetime import datetime

import numpy as np
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoFormat(Enum):
    """Supported video formats"""

    H264 = "h264"
    MJPEG = "mjpeg"
    WEBRTC = "webrtc"
    RAW_JPEG = "jpeg"
    UNKNOWN = "unknown"


@dataclass
class VideoFrame:
    """Unified video frame"""

    format: VideoFormat
    data: bytes
    width: int = 640
    height: int = 360
    timestamp: float = 0
    is_keyframe: bool = False
    track_id: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp == 0:
            self.timestamp = time.time()


class FormatDetector:
    """Detect video format from raw data"""

    @staticmethod
    def detect(data: bytes) -> VideoFormat:
        """Detect format from data"""
        if len(data) < 10:
            return VideoFormat.UNKNOWN

        # Check for JPEG
        if data[:2] == b"\xff\xd8":
            return VideoFormat.RAW_JPEG

        # Check for H.264 NAL units
        if data[:4] == b"\x00\x00\x00\x01" or data[:3] == b"\x00\x00\x01":
            return VideoFormat.H264

        # Check for MJPEG stream (multipart)
        if b"Content-Type: image/jpeg" in data[:200]:
            return VideoFormat.MJPEG

        # Check for WebRTC (SDP or binary)
        if data[:4] == b"\x16\x00\x00\x00":  # SRTP packet
            return VideoFormat.WEBRTC

        return VideoFormat.UNKNOWN


class VideoTranscoder:
    """Transcode between video formats"""

    def __init__(self):
        self.ffmpeg_lock = asyncio.Lock()
        self.frame_cache: Dict[str, VideoFrame] = {}

    async def transcode(
        self, frame: VideoFrame, target_format: VideoFormat
    ) -> Optional[VideoFrame]:
        """Transcode frame to target format"""
        if frame.format == target_format:
            return frame

        cache_key = f"{frame.track_id}_{frame.timestamp}_{target_format.value}"
        if cache_key in self.frame_cache:
            return self.frame_cache[cache_key]

        try:
            if (
                frame.format == VideoFormat.H264
                and target_format == VideoFormat.RAW_JPEG
            ):
                result = await self._h264_to_jpeg(frame)
            elif (
                frame.format == VideoFormat.RAW_JPEG
                and target_format == VideoFormat.MJPEG
            ):
                result = await self._jpeg_to_mjpeg(frame)
            elif (
                frame.format == VideoFormat.H264 and target_format == VideoFormat.MJPEG
            ):
                result = await self._h264_to_jpeg(frame)
            else:
                logger.warning(
                    f"Unsupported transcoding: {frame.format} -> {target_format}"
                )
                return None

            if result:
                self.frame_cache[cache_key] = result
                # Clean old cache
                if len(self.frame_cache) > 100:
                    old_keys = list(self.frame_cache.keys())[:50]
                    for k in old_keys:
                        del self.frame_cache[k]

            return result

        except Exception as e:
            logger.error(f"Transcoding error: {e}")
            return None

    async def _h264_to_jpeg(self, frame: VideoFrame) -> Optional[VideoFrame]:
        """Convert H.264 to JPEG using FFmpeg"""
        async with self.ffmpeg_lock:
            # Write H.264 data to temp file
            with tempfile.NamedTemporaryFile(suffix=".h264", delete=False) as f_in:
                f_in.write(frame.data)
                input_path = f_in.name

            output_path = input_path + ".jpg"

            try:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "h264",
                    "-i",
                    input_path,
                    "-vf",
                    f"scale={frame.width}:{frame.height}",
                    "-q:v",
                    "5",
                    "-f",
                    "image2",
                    "-vframes",
                    "1",
                    output_path,
                ]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)

                if proc.returncode == 0 and os.path.exists(output_path):
                    with open(output_path, "rb") as f:
                        jpeg_data = f.read()

                    return VideoFrame(
                        format=VideoFormat.RAW_JPEG,
                        data=jpeg_data,
                        width=frame.width,
                        height=frame.height,
                        timestamp=frame.timestamp,
                        is_keyframe=True,
                        track_id=frame.track_id,
                        metadata=frame.metadata,
                    )
                else:
                    logger.warning(f"FFmpeg failed: {stderr.decode()[:200]}")
                    return None

            finally:
                # Cleanup
                for path in [input_path, output_path]:
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except:
                        pass

    async def _jpeg_to_mjpeg(self, frame: VideoFrame) -> VideoFrame:
        """Wrap JPEG as MJPEG"""
        return VideoFrame(
            format=VideoFormat.MJPEG,
            data=frame.data,
            width=frame.width,
            height=frame.height,
            timestamp=frame.timestamp,
            is_keyframe=frame.is_keyframe,
            track_id=frame.track_id,
            metadata=frame.metadata,
        )


class MultiFormatVideoGateway:
    """
    Video Gateway - Main entry point
    Handles multiple input formats and serves multiple output formats
    """

    def __init__(self):
        self.transcoder = VideoTranscoder()
        self.detector = FormatDetector()

        # Frame buffers for each track
        self.buffers: Dict[str, asyncio.Queue] = {}
        self.latest_frames: Dict[str, VideoFrame] = {}

        # Subscribers
        self.subscribers: Dict[str, list] = {}

        # Running flag
        self.running = False

    async def start(self):
        """Start the gateway"""
        self.running = True
        logger.info("Video Gateway started")

    async def stop(self):
        """Stop the gateway"""
        self.running = False
        logger.info("Video Gateway stopped")

    async def ingest_frame(
        self, track_id: str, data: bytes, metadata: Dict = None
    ) -> bool:
        """
        Ingest a video frame from any source

        Args:
            track_id: Unique track identifier
            data: Raw video data
            metadata: Optional metadata

        Returns:
            True if successful
        """
        try:
            # Detect format
            format_type = self.detector.detect(data)

            if format_type == VideoFormat.UNKNOWN:
                logger.warning(f"Unknown format for track {track_id}")
                return False

            # Create frame
            frame = VideoFrame(
                format=format_type,
                data=data,
                track_id=track_id,
                metadata=metadata or {},
            )

            # Store frame
            self.latest_frames[track_id] = frame

            # Add to buffer
            if track_id not in self.buffers:
                self.buffers[track_id] = asyncio.Queue(maxsize=30)

            buffer = self.buffers[track_id]
            if buffer.full():
                try:
                    buffer.get_nowait()  # Remove old frame
                except:
                    pass

            await buffer.put(frame)

            # Notify subscribers
            if track_id in self.subscribers:
                for callback in self.subscribers[track_id]:
                    try:
                        asyncio.create_task(callback(frame))
                    except:
                        pass

            return True

        except Exception as e:
            logger.error(f"Error ingesting frame: {e}")
            return False

    def subscribe(self, track_id: str, callback: Callable[[VideoFrame], None]):
        """Subscribe to a track"""
        if track_id not in self.subscribers:
            self.subscribers[track_id] = []
        self.subscribers[track_id].append(callback)
        logger.info(f"Subscriber added for track {track_id}")

    def unsubscribe(self, track_id: str, callback: Callable[[VideoFrame], None]):
        """Unsubscribe from a track"""
        if track_id in self.subscribers:
            self.subscribers[track_id].remove(callback)

    def get_latest_frame(
        self, track_id: str, target_format: VideoFormat = None
    ) -> Optional[VideoFrame]:
        """Get latest frame, optionally transcoded"""
        if track_id not in self.latest_frames:
            return None

        frame = self.latest_frames[track_id]

        if target_format and frame.format != target_format:
            # Note: This is synchronous, for async use transcode method
            return None

        return frame

    async def get_frame_async(
        self, track_id: str, target_format: VideoFormat = None
    ) -> Optional[VideoFrame]:
        """Get frame with async transcoding"""
        if track_id not in self.latest_frames:
            return None

        frame = self.latest_frames[track_id]

        if target_format and frame.format != target_format:
            return await self.transcoder.transcode(frame, target_format)

        return frame


# Singleton instance
gateway = MultiFormatVideoGateway()


# Convenience functions
async def ingest_h264_frame(
    track_id: str, h264_data: bytes, metadata: Dict = None
) -> bool:
    """Ingest H.264 frame"""
    return await gateway.ingest_frame(
        track_id, h264_data, {**(metadata or {}), "source_format": "h264"}
    )


async def ingest_jpeg_frame(
    track_id: str, jpeg_data: bytes, metadata: Dict = None
) -> bool:
    """Ingest JPEG frame"""
    return await gateway.ingest_frame(
        track_id, jpeg_data, {**(metadata or {}), "source_format": "jpeg"}
    )


def get_video_gateway() -> MultiFormatVideoGateway:
    """Get video gateway instance"""
    return gateway


# Import for type hints
import os
