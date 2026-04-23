#!/usr/bin/env python3
"""
Video Service - Multi-format video streaming
Runs on port 9006, integrates with existing WebUI
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from ..video_gateway import (
    VideoFormat,
    VideoFrame,
    get_video_gateway,
    ingest_h264_frame,
    ingest_jpeg_frame,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global gateway instance
gateway = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global gateway

    logger.info("=" * 70)
    logger.info("Video Service Starting")
    logger.info("=" * 70)

    gateway = get_video_gateway()
    await gateway.start()
    logger.info("✅ Video Gateway initialized")

    yield

    if gateway:
        await gateway.stop()
        logger.info("Video Gateway stopped")


app = FastAPI(
    title="Video Service",
    description="Multi-format video streaming service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Video Service",
        "version": "1.0.0",
        "port": 9006,
        "endpoints": [
            "/video/stream/{track_id}/mjpeg",
            "/video/stream/{track_id}/latest",
            "/video/stream/{track_id}/info",
            "/video/player/{track_id}",
            "/video/ingest/{track_id}",
            "/video/streams",
        ],
    }


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "gateway": True,
        "streams": len(gateway.latest_frames) if gateway else 0,
    }


@app.get("/video/stream/{track_id}/mjpeg")
async def mjpeg_stream(track_id: str, request: Request):
    """
    MJPEG stream endpoint
    Compatible with <img src="..."> in all browsers
    """
    if not gateway:
        raise HTTPException(status_code=503, detail="Video gateway not available")

    logger.info(f"[MJPEG] Subscriber connected: {track_id}")

    async def generate():
        queue = asyncio.Queue(maxsize=5)

        def on_frame(frame: VideoFrame):
            try:
                if queue.full():
                    try:
                        queue.get_nowait()
                    except Exception:
                        pass
                queue.put_nowait(frame)
            except Exception:
                pass

        gateway.subscribe(track_id, on_frame)

        try:
            frame = gateway.get_latest_frame(track_id)
            if frame and frame.format == VideoFormat.RAW_JPEG:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"\r\n" + frame.data + b"\r\n"
                )

            while True:
                try:
                    frame = await asyncio.wait_for(queue.get(), timeout=30.0)

                    if frame.format != VideoFormat.RAW_JPEG:
                        frame = await gateway.get_frame_async(
                            track_id, VideoFormat.RAW_JPEG
                        )

                    if frame and frame.data:
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"\r\n" + frame.data + b"\r\n"
                        )

                except asyncio.TimeoutError:
                    yield b": keepalive\n\n"

        except asyncio.CancelledError:
            logger.info(f"[MJPEG] Subscriber disconnected: {track_id}")
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


@app.get("/video/stream/{track_id}/latest")
async def latest_frame(track_id: str):
    """Get latest frame as JPEG"""
    if not gateway:
        raise HTTPException(status_code=503, detail="Video gateway not available")

    frame = gateway.get_latest_frame(track_id)
    if not frame:
        raise HTTPException(status_code=404, detail="No frame available")

    if frame.format != VideoFormat.RAW_JPEG:
        frame = await gateway.get_frame_async(track_id, VideoFormat.RAW_JPEG)

    if not frame or not frame.data:
        raise HTTPException(status_code=500, detail="Transcoding failed")

    return Response(
        content=frame.data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/video/stream/{track_id}/info")
async def stream_info(track_id: str):
    """Get stream information"""
    if not gateway:
        raise HTTPException(status_code=503, detail="Video gateway not available")

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
            "timestamp": frame.timestamp,
            "is_keyframe": frame.is_keyframe,
            "data_size": len(frame.data),
            "metadata": frame.metadata,
        }
    )


@app.get("/video/player/{track_id}", response_class=HTMLResponse)
async def video_player(track_id: str, request: Request):
    """HTML player page"""
    base_url = str(request.base_url).rstrip("/")

    html = f"""<!DOCTYPE html>
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
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        h1 {{ color: #00d4ff; }}
        .video-box {{
            border: 2px solid #00d4ff;
            border-radius: 8px;
            overflow: hidden;
            margin: 20px 0;
            background: #000;
        }}
        img {{ display: block; max-width: 100%; }}
        .info {{
            background: #16213e;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            max-width: 600px;
        }}
        .endpoint {{
            background: rgba(0,0,0,0.3);
            padding: 10px;
            border-radius: 4px;
            font-family: monospace;
            margin: 10px 0;
            font-size: 12px;
        }}
        code {{ color: #00ff88; }}
    </style>
</head>
<body>
    <h1>🔴 Video Player</h1>
    <p>Track: <code>{track_id}</code></p>

    <div class="video-box">
        <img src="{base_url}/video/stream/{track_id}/mjpeg"
             width="640" height="360"
             alt="Video Stream" />
    </div>

    <div class="info">
        <h3>Endpoints:</h3>
        <div class="endpoint">
            <strong>MJPEG Stream:</strong><br>
            <code>{base_url}/video/stream/{track_id}/mjpeg</code>
        </div>
        <div class="endpoint">
            <strong>Latest Frame:</strong><br>
            <code>{base_url}/video/stream/{track_id}/latest</code>
        </div>
        <div class="endpoint">
            <strong>Stream Info:</strong><br>
            <code>{base_url}/video/stream/{track_id}/info</code>
        </div>
    </div>

    <script>
        async function updateInfo() {{
            try {{
                const res = await fetch('{base_url}/video/stream/{track_id}/info');
                const data = await res.json();
                console.log('Stream info:', data);
            }} catch (e) {{
                console.error('Error:', e);
            }}
        }}
        setInterval(updateInfo, 5000);
    </script>
</body>
</html>"""

    return html


@app.post("/video/ingest/{track_id}", status_code=201)
async def ingest_frame(track_id: str, request: Request):
    """Ingest video frame"""
    if not gateway:
        raise HTTPException(status_code=503, detail="Video gateway not available")

    try:
        data = await request.body()

        success = await gateway.ingest_frame(
            track_id=track_id,
            data=data,
            metadata={
                "source": "http",
                "content_type": request.headers.get("content-type", "unknown"),
            },
        )

        if success:
            frame = gateway.get_latest_frame(track_id)
            return JSONResponse(
                {
                    "status": "success",
                    "track_id": track_id,
                    "format_detected": frame.format.value if frame else "unknown",
                    "size": len(data),
                }
            )
        raise HTTPException(status_code=400, detail="Failed to ingest frame")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Ingest error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/video/streams")
async def list_streams():
    """List all active streams"""
    if not gateway:
        return JSONResponse({"streams": [], "count": 0})

    streams = []
    for track_id, frame in gateway.latest_frames.items():
        streams.append(
            {
                "track_id": track_id,
                "format": frame.format.value,
                "width": frame.width,
                "height": frame.height,
                "timestamp": frame.timestamp,
                "has_data": len(frame.data) > 0,
            }
        )

    return JSONResponse({"streams": streams, "count": len(streams)})


@app.post("/video/test/ingest-jpeg/{track_id}")
async def test_ingest_jpeg(track_id: str):
    """Test endpoint - ingest fake JPEG"""
    if not gateway:
        raise HTTPException(status_code=503, detail="Video gateway not available")

    jpeg_data = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 1000 + b"\xff\xd9"

    success = await ingest_jpeg_frame(
        track_id=track_id, jpeg_data=jpeg_data, metadata={"test": "fake_jpeg"}
    )

    return {
        "status": "success" if success else "failed",
        "track_id": track_id,
        "data_size": len(jpeg_data),
    }


@app.post("/video/test/ingest-h264/{track_id}")
async def test_ingest_h264(track_id: str):
    """Test endpoint - ingest fake H.264"""
    if not gateway:
        raise HTTPException(status_code=503, detail="Video gateway not available")

    h264_data = b"\x00\x00\x00\x01\x09\x10" + b"\x00" * 100

    success = await ingest_h264_frame(
        track_id=track_id, h264_data=h264_data, metadata={"test": "fake_h264"}
    )

    return {
        "status": "success" if success else "failed",
        "track_id": track_id,
        "data_size": len(h264_data),
    }


def run_server():
    """Run the video service"""
    uvicorn.run(
        "app.video_9006.service:app",
        host="0.0.0.0",
        port=9006,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    run_server()
