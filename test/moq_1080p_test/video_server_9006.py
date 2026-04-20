#!/usr/bin/env python3
"""
MOQ Video Server for 9006
- 订阅MOQ track接收H.264视频
- 转码为MJPEG并通过HTTP 9006端口提供前端显示
"""

import asyncio
import io
import subprocess
import sys
import threading
import time
from pathlib import Path
from aiohttp import web
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add webui to path
WEBUI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.sub.subscriber import MOQSubscriber, ReceivedObject
from moq.encoding import FullTrackName

# Configuration
RELAY_HOST = "localhost"
RELAY_PORT = 9008
TASK_ID = "test-ffmpeg-video"
AGENT_ID = "ffmpeg-publisher"
TRACK_NAME = "Video"
HTTP_PORT = 9006

# Global frame buffer for MJPEG streaming
latest_frame = None
frame_event = asyncio.Event()


class VideoTranscoder:
    """H.264 to MJPEG transcoder using FFmpeg"""

    def __init__(self):
        self.process = None
        self.running = False
        self.frame_buffer = bytearray()
        self.lock = threading.Lock()

    def start(self):
        """Start FFmpeg transcoding process"""
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "h264",
            "-i",
            "-",  # Read from stdin
            "-f",
            "mjpeg",
            "-q:v",
            "5",
            "-vf",
            "scale=960:540",  # Scale down for web display
            "-r",
            "30",
            "-",
        ]

        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self.running = True

        # Start reader thread
        self.reader_thread = threading.Thread(target=self._read_frames)
        self.reader_thread.daemon = True
        self.reader_thread.start()

        logger.info("FFmpeg transcoder started")

    def _read_frames(self):
        """Read MJPEG frames from FFmpeg output"""
        global latest_frame

        buffer = bytearray()

        while self.running and self.process:
            try:
                chunk = self.process.stdout.read(4096)
                if not chunk:
                    break

                buffer.extend(chunk)

                # Look for JPEG markers (SOI: 0xFFD8, EOI: 0xFFD9)
                while True:
                    soi = buffer.find(b"\xff\xd8")
                    if soi == -1:
                        break

                    eoi = buffer.find(b"\xff\xd9", soi)
                    if eoi == -1:
                        break

                    # Extract complete JPEG frame
                    jpeg_frame = buffer[soi : eoi + 2]
                    buffer = buffer[eoi + 2 :]

                    with self.lock:
                        latest_frame = bytes(jpeg_frame)

            except Exception as e:
                logger.error(f"Error reading frames: {e}")
                break

    def write_h264(self, data):
        """Write H.264 data to FFmpeg stdin"""
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except BrokenPipeError:
                logger.warning("FFmpeg stdin pipe broken")
            except Exception as e:
                logger.error(f"Error writing to FFmpeg: {e}")

    def stop(self):
        """Stop transcoder"""
        self.running = False
        if self.process:
            self.process.stdin.close()
            self.process.terminate()
            self.process.wait()


class MOQVideoSubscriber:
    """MOQ subscriber that receives H.264 and transcodes to MJPEG"""

    def __init__(self):
        self.subscriber = None
        self.transcoder = VideoTranscoder()
        self.running = False
        self.received_frames = 0

    def _on_object_received(self, obj: ReceivedObject):
        """Handle received object"""
        self.received_frames += 1
        self.transcoder.write_h264(obj.payload)

        if self.received_frames % 30 == 0:
            logger.info(f"    Received {self.received_frames} frames")

    def _on_subscription_accepted(self, track_name: FullTrackName):
        """Handle subscription accepted"""
        logger.info(f"[✓] Subscription accepted: {track_name}")

    def _on_subscription_rejected(self, track_name: FullTrackName, reason: str):
        """Handle subscription rejected"""
        logger.error(f"[✗] Subscription rejected: {track_name} - {reason}")

    async def subscribe_and_receive(self):
        """Subscribe to MOQ track and receive video"""
        logger.info("=" * 70)
        logger.info("MOQ Video Subscriber")
        logger.info("=" * 70)

        # Start transcoder
        self.transcoder.start()

        # Connect to MOQ relay
        logger.info(f"\n[1] Connecting to MOQ at {RELAY_HOST}:{RELAY_PORT}...")
        self.subscriber = MOQSubscriber(RELAY_HOST, RELAY_PORT)

        # Set handlers before connecting
        self.subscriber.set_handlers(
            on_object_received=self._on_object_received,
            on_subscription_accepted=self._on_subscription_accepted,
            on_subscription_rejected=self._on_subscription_rejected,
        )

        connected = await self.subscriber.connect(agent_id="video-subscriber-9006")
        if not connected:
            logger.error("[✗] Failed to connect to relay")
            return False
        logger.info("[✓] Connected to relay")

        # Subscribe to track
        logger.info(f"\n[2] Subscribing to track...")
        namespace = [TASK_ID, AGENT_ID]

        full_track_name = FullTrackName(
            namespace=[ns.encode() for ns in namespace],
            track_name=TRACK_NAME.encode(),
        )

        subscribed = await self.subscriber.subscribe(full_track_name)
        if not subscribed:
            logger.error("[✗] Failed to subscribe")
            return False
        logger.info("[✓] Subscribed successfully")

        # Keep running to receive objects via handlers
        logger.info(f"\n[3] Receiving video frames (via handlers)...")
        self.running = True

        try:
            while self.running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error: {e}")

        return True

    def stop(self):
        """Stop subscriber"""
        self.running = False
        self.transcoder.stop()
        if self.subscriber:
            self.subscriber.disconnect()


# HTTP Server handlers
async def index_handler(request):
    """Serve main page"""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>MOQ Video Test - Port 9006</title>
    <meta charset="utf-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #1a1a2e;
            color: white;
            text-align: center;
            padding: 20px;
            margin: 0;
        }
        h1 { color: #00d4ff; margin-bottom: 10px; }
        .subtitle { color: #888; margin-bottom: 20px; }
        .video-container {
            border: 3px solid #00d4ff;
            border-radius: 8px;
            display: inline-block;
            background: #000;
            padding: 10px;
        }
        img {
            max-width: 100%;
            height: auto;
            display: block;
        }
        .status {
            margin-top: 20px;
            padding: 10px;
            background: #2a2a4e;
            border-radius: 5px;
            font-size: 14px;
        }
        .info {
            margin-top: 15px;
            font-size: 12px;
            color: #aaa;
        }
        .error {
            color: #ff6b6b;
            font-weight: bold;
        }
        .success { color: #51cf66; }
    </style>
</head>
<body>
    <h1>🎥 MOQ Video Stream Test</h1>
    <div class="subtitle">1080p H.264 → MOQ → MJPEG Transcode → Browser</div>

    <div class="video-container">
        <img id="videoStream" src="/mjpeg" width="960" height="540" alt="Video Stream">
    </div>

    <div class="status">
        <div>Status: <span id="statusText" class="success">Connected</span></div>
        <div>Received Frames: <span id="frameCount">0</span></div>
    </div>

    <div class="info">
        <p>🔹 Source: test_1080p.h264 (1920x1080 @ 30fps)</p>
        <p>🔹 Protocol: MOQ over QUIC</p>
        <p>🔹 Transcode: H.264 → MJPEG (960x540)</p>
        <p>🔹 Port: 9006</p>
    </div>

    <script>
        const img = document.getElementById('videoStream');
        const statusText = document.getElementById('statusText');
        let frameCount = 0;

        img.onload = function() {
            frameCount++;
            document.getElementById('frameCount').textContent = frameCount;
            statusText.textContent = 'Receiving';
            statusText.className = 'success';
        };

        img.onerror = function() {
            statusText.textContent = 'Error';
            statusText.className = 'error';
        };

        // Check connection status every 2 seconds
        setInterval(() => {
            fetch('/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('frameCount').textContent = data.received_frames;
                })
                .catch(() => {
                    statusText.textContent = 'Disconnected';
                    statusText.className = 'error';
                });
        }, 2000);
    </script>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


async def mjpeg_handler(request):
    """Stream MJPEG"""
    global latest_frame

    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "multipart/x-mixed-replace; boundary=frame",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
    await response.prepare(request)

    last_frame = None

    while True:
        try:
            current_frame = latest_frame

            if current_frame and current_frame != last_frame:
                header = (
                    "Content-Length: " + str(len(current_frame)) + "\r\n\r\n"
                ).encode()
                part1 = b"--frame\r\nContent-Type: image/jpeg\r\n"
                part2 = current_frame + b"\r\n"
                await response.write(part1 + header + part2)
                last_frame = current_frame
            else:
                await asyncio.sleep(0.033)  # ~30fps

        except ConnectionResetError:
            break
        except Exception as e:
            logger.error(f"MJPEG stream error: {e}")
            break

    return response


async def status_handler(request):
    """Return current status"""
    return web.json_response(
        {
            "received_frames": moq_subscriber.received_frames if moq_subscriber else 0,
            "has_frame": latest_frame is not None,
        }
    )


# Global subscriber instance
moq_subscriber = None


async def start_moq_subscriber(app):
    """Start MOQ subscriber as background task"""
    global moq_subscriber
    moq_subscriber = MOQVideoSubscriber()

    # Run subscriber in background
    asyncio.create_task(moq_subscriber.subscribe_and_receive())
    logger.info("MOQ subscriber task started")


async def cleanup(app):
    """Cleanup on shutdown"""
    if moq_subscriber:
        moq_subscriber.stop()
        logger.info("MOQ subscriber stopped")


def main():
    """Main entry point"""
    app = web.Application()

    # Routes
    app.router.add_get("/", index_handler)
    app.router.add_get("/mjpeg", mjpeg_handler)
    app.router.add_get("/status", status_handler)

    # Startup and cleanup
    app.on_startup.append(start_moq_subscriber)
    app.on_cleanup.append(cleanup)

    logger.info(f"\n{'=' * 70}")
    logger.info(f"Starting HTTP server on port {HTTP_PORT}")
    logger.info(f"Access: http://localhost:{HTTP_PORT}")
    logger.info(f"{'=' * 70}\n")

    web.run_app(app, host="0.0.0.0", port=HTTP_PORT)


if __name__ == "__main__":
    main()
