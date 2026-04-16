#!/usr/bin/env python3
"""
MJPEG Streaming Server
Provides simple MJPEG over HTTP for video display
Compatible with all browsers via <img> tag
"""

import asyncio
import base64
import io
from typing import Dict, Set, Optional
from datetime import datetime
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Global storage for MJPEG streams
# track_id -> {frames: [], subscribers: set(), latest_frame: bytes}
mjpeg_streams: Dict[str, dict] = {}


class MJPEGStream:
    """MJPEG stream for a track"""

    def __init__(self, track_id: str):
        self.track_id = track_id
        self.frames = []  # List of JPEG frames
        self.max_frames = 30  # Keep last 30 frames
        self.subscribers: Set[asyncio.Queue] = set()
        self.latest_frame: Optional[bytes] = None
        self.frame_count = 0
        self.created_at = datetime.now()

    def add_frame(self, jpeg_data: bytes):
        """Add a JPEG frame to the stream"""
        self.latest_frame = jpeg_data
        self.frames.append(jpeg_data)
        self.frame_count += 1

        # Keep only recent frames
        if len(self.frames) > self.max_frames:
            self.frames.pop(0)

        # Notify all subscribers
        for queue in list(self.subscribers):
            try:
                # Non-blocking put
                if queue.full():
                    try:
                        queue.get_nowait()  # Remove old frame
                    except:
                        pass
                queue.put_nowait(jpeg_data)
            except:
                pass

    def get_latest_frame(self) -> Optional[bytes]:
        """Get the latest frame"""
        return self.latest_frame

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to the stream"""
        queue = asyncio.Queue(maxsize=5)
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from the stream"""
        self.subscribers.discard(queue)


def get_or_create_stream(track_id: str) -> MJPEGStream:
    """Get or create MJPEG stream for track"""
    if track_id not in mjpeg_streams:
        mjpeg_streams[track_id] = MJPEGStream(track_id)
        logger.info(f"Created MJPEG stream for {track_id}")
    return mjpeg_streams[track_id]


async def add_frame_to_stream(track_id: str, jpeg_data: bytes):
    """Add a frame to MJPEG stream"""
    stream = get_or_create_stream(track_id)
    stream.add_frame(jpeg_data)


@router.get("/mjpeg/{track_id}")
async def mjpeg_stream_endpoint(track_id: str, request: Request):
    """
    MJPEG stream endpoint
    Returns multipart/x-mixed-replace stream
    Compatible with <img src="/api/video/mjpeg/{track_id}">
    """
    stream = get_or_create_stream(track_id)
    queue = stream.subscribe()

    logger.info(f"MJPEG subscriber connected: {track_id}")

    async def generate():
        try:
            # Send initial frame if available
            if stream.latest_frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: "
                    + str(len(stream.latest_frame)).encode()
                    + b"\r\n"
                    b"\r\n" + stream.latest_frame + b"\r\n"
                )

            # Stream new frames
            while True:
                try:
                    # Wait for new frame with timeout
                    frame = await asyncio.wait_for(queue.get(), timeout=30.0)

                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
                        b"\r\n" + frame + b"\r\n"
                    )
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield b": keepalive\n\n"

        except asyncio.CancelledError:
            logger.info(f"MJPEG subscriber disconnected: {track_id}")
        finally:
            stream.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/mjpeg/{track_id}/latest")
async def mjpeg_latest_frame(track_id: str):
    """
    Get latest frame as single JPEG image
    Useful for snapshot or polling
    """
    stream = get_or_create_stream(track_id)
    frame = stream.get_latest_frame()

    if frame:
        return Response(
            content=frame,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
            },
        )
    else:
        return Response(
            status_code=404, content=b"No frame available", media_type="text/plain"
        )


@router.get("/mjpeg/{track_id}/status")
async def mjpeg_stream_status(track_id: str):
    """Get stream status"""
    if track_id in mjpeg_streams:
        stream = mjpeg_streams[track_id]
        return {
            "track_id": track_id,
            "frame_count": stream.frame_count,
            "buffered_frames": len(stream.frames),
            "subscribers": len(stream.subscribers),
            "has_frame": stream.latest_frame is not None,
            "created_at": stream.created_at.isoformat(),
        }
    else:
        return {
            "track_id": track_id,
            "frame_count": 0,
            "buffered_frames": 0,
            "subscribers": 0,
            "has_frame": False,
        }


@router.get("/mjpeg")
async def list_mjpeg_streams():
    """List all active MJPEG streams"""
    return {
        "streams": [
            {
                "track_id": track_id,
                "frame_count": stream.frame_count,
                "subscribers": len(stream.subscribers),
                "has_frame": stream.latest_frame is not None,
            }
            for track_id, stream in mjpeg_streams.items()
        ]
    }
