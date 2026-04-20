#!/usr/bin/env python3
"""
HTTP Video Server
Provides multiple video format endpoints
"""

import asyncio
import base64
import json
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import logging

from .video_gateway import VideoGateway, VideoFormat, VideoFrame, get_video_gateway

logger = logging.getLogger(__name__)
router = APIRouter()

# Get gateway instance
gateway = get_video_gateway()


@router.get("/video/stream/{track_id}/mjpeg")
async def mjpeg_stream_endpoint(track_id: str, request: Request):
    """
    MJPEG stream endpoint
    Compatible with <img src="..."> in all browsers
    """
    logger.info(f"MJPEG subscriber connected: {track_id}")

    async def generate():
        queue = asyncio.Queue(maxsize=5)

        # Subscribe to track
        def on_frame(frame: VideoFrame):
            try:
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(frame)
            except:
                pass

        gateway.subscribe(track_id, on_frame)

        try:
            # Send initial frame if available
            frame = gateway.get_latest_frame(track_id, VideoFormat.RAW_JPEG)
            if frame and frame.data:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame.data)).encode() + b"\r\n"
                    b"\r\n" + frame.data + b"\r\n"
                )

            # Stream new frames
            while True:
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=30.0)

                    # Transcode to JPEG if needed
                    if frame.format != VideoFormat.RAW_JPEG:
                        frame = await gateway.transcoder.transcode(
                            frame, VideoFormat.RAW_JPEG
                        )

                    if frame and frame.data:
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"Content-Length: "
                            + str(len(frame.data)).encode()
                            + b"\r\n"
                            b"\r\n" + frame.data + b"\r\n"
                        )

                except asyncio.TimeoutError:
                    yield b": keepalive\n\n"

        except asyncio.CancelledError:
            logger.info(f"MJPEG subscriber disconnected: {track_id}")
        finally:
            gateway.unsubscribe(track_id, on_frame)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/video/stream/{track_id}/latest")
async def latest_frame_endpoint(track_id: str):
    """Get latest frame as JPEG"""
    frame = gateway.get_latest_frame(track_id)

    if not frame:
        raise HTTPException(status_code=404, detail="No frame available")

    # Transcode to JPEG if needed
    if frame.format != VideoFormat.RAW_JPEG:
        frame = await gateway.transcoder.transcode(frame, VideoFormat.RAW_JPEG)

    if not frame or not frame.data:
        raise HTTPException(status_code=500, detail="Transcoding failed")

    return Response(
        content=frame.data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache",
            "X-Frame-Format": frame.format.value,
            "X-Frame-Timestamp": str(frame.timestamp),
        },
    )


@router.get("/video/stream/{track_id}/info")
async def stream_info_endpoint(track_id: str):
    """Get stream information"""
    frame = gateway.get_latest_frame(track_id)

    if not frame:
        return JSONResponse(
            {"track_id": track_id, "status": "inactive", "has_frame": False}
        )

    return JSONResponse(
        {
            "track_id": track_id,
            "status": "active",
            "has_frame": True,
            "format": frame.format.value,
            "width": frame.width,
            "height": frame.height,
            "timestamp": datetime.fromtimestamp(frame.timestamp).isoformat(),
            "is_keyframe": frame.is_keyframe,
            "data_size": len(frame.data),
            "metadata": frame.metadata,
        }
    )


@router.get("/video/streams")
async def list_streams_endpoint():
    """List all active streams"""
    streams = []
    for track_id in gateway.latest_frames.keys():
        frame = gateway.latest_frames[track_id]
        streams.append(
            {
                "track_id": track_id,
                "format": frame.format.value,
                "width": frame.width,
                "height": frame.height,
                "last_update": datetime.fromtimestamp(frame.timestamp).isoformat(),
            }
        )

    return JSONResponse({"streams": streams, "count": len(streams)})


@router.post("/video/ingest/{track_id}", status_code=201)
async def ingest_frame_endpoint(track_id: str, request: Request):
    """
    Ingest video frame via HTTP
    Supports: H.264, JPEG (auto-detected)
    """
    try:
        data = await request.body()

        # Get metadata from headers
        metadata = {
            "source": "http",
            "content_type": request.headers.get("content-type", "unknown"),
            "timestamp": datetime.now().isoformat(),
        }

        # Ingest frame
        success = await gateway.ingest_frame(track_id, data, metadata)

        if success:
            return JSONResponse(
                {"status": "success", "track_id": track_id, "size": len(data)}
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to ingest frame")

    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/video/player/{track_id}")
async def video_player_page(track_id: str, request: Request):
    """Serve HTML player page for testing"""
    base_url = str(request.base_url).rstrip("/")

    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Video Player - {track_id}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #1a1a2e;
            color: white;
            padding: 20px;
            margin: 0;
        }}
        h1 {{ color: #00d4ff; }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        .video-box {{
            border: 2px solid #00d4ff;
            border-radius: 8px;
            overflow: hidden;
            margin: 20px 0;
            background: #000;
        }}
        img {{
            display: block;
            width: 100%;
            max-width: 640px;
        }}
        .info {{
            background: #16213e;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .endpoint {{
            background: rgba(0,0,0,0.3);
            padding: 10px;
            border-radius: 4px;
            font-family: monospace;
            margin: 10px 0;
        }}
        code {{
            color: #00ff88;
        }}
        .status {{
            padding: 10px 20px;
            border-radius: 20px;
            display: inline-block;
            margin: 10px 0;
        }}
        .status.active {{
            background: rgba(0, 255, 136, 0.2);
            color: #00ff88;
        }}
        .status.inactive {{
            background: rgba(255, 51, 102, 0.2);
            color: #ff3366;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔴 Video Player</h1>
        <p>Track: <code>{track_id}</code></p>
        
        <div class="video-box">
            <img src="{base_url}/api/video/stream/{track_id}/mjpeg" 
                 width="640" height="360" 
                 alt="Video Stream" />
        </div>
        
        <div class="info">
            <h3>Available Endpoints:</h3>
            <div class="endpoint">
                <strong>MJPEG Stream:</strong><br>
                <code>{base_url}/api/video/stream/{track_id}/mjpeg</code>
            </div>
            <div class="endpoint">
                <strong>Latest Frame:</strong><br>
                <code>{base_url}/api/video/stream/{track_id}/latest</code>
            </div>
            <div class="endpoint">
                <strong>Stream Info:</strong><br>
                <code>{base_url}/api/video/stream/{track_id}/info</code>
            </div>
        </div>
        
        <p>💡 <strong>Features:</strong></p>
        <ul>
            <li>✅ Auto-detects input format (H.264, JPEG, etc.)</li>
            <li>✅ Real-time transcoding to MJPEG</li>
            <li>✅ Works in all browsers</li>
            <li>✅ Low latency (~100ms)</li>
        </ul>
    </div>
    <script>
        // Auto-refresh stream info
        async function updateInfo() {{
            try {{
                const res = await fetch('{base_url}/api/video/stream/{track_id}/info');
                const data = await res.json();
                console.log('Stream info:', data);
            }} catch (e) {{
                console.error('Error:', e);
            }}
        }}
        setInterval(updateInfo, 5000);
    </script>
</body>
</html>'''

    return Response(content=html, media_type="text/html")
