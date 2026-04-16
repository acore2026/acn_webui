#!/usr/bin/env python3
"""
MJPEG Publisher for WebUI
Generates JPEG frames and sends via HTTP multipart stream
Simple and compatible with all browsers
"""

import asyncio
import io
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import sys
from pathlib import Path
import aiohttp
from aiohttp import web

# Configuration
HTTP_PORT = 8080
FRAME_WIDTH = 640
FRAME_HEIGHT = 360
FPS = 30


class MJPEGPublisher:
    """MJPEG Publisher using HTTP multipart stream"""

    def __init__(self):
        self.frame_number = 0
        self.subscribers = []
        self.running = False

    def generate_frame(self, frame_num: int) -> bytes:
        """Generate a test frame with moving pattern"""
        # Create image
        img = Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), "black")
        draw = ImageDraw.Draw(img)

        # Background gradient
        for y in range(FRAME_HEIGHT):
            color = int(20 + (y / FRAME_HEIGHT) * 40)
            draw.line([(0, y), (FRAME_WIDTH, y)], fill=(color, color, color + 10))

        # Moving circle
        t = frame_num * 0.05
        center_x = int(FRAME_WIDTH / 2 + np.sin(t) * 150)
        center_y = int(FRAME_HEIGHT / 2 + np.cos(t * 0.7) * 100)
        radius = 40 + int(np.sin(t * 2) * 10)

        # Draw circle with glow
        for r in range(radius + 20, radius, -1):
            alpha = int(50 * (1 - (r - radius) / 20))
            color = (0, 200, 255, alpha)
            draw.ellipse(
                [center_x - r, center_y - r, center_x + r, center_y + r],
                fill=None,
                outline=(0, 200 - r, 255),
                width=2,
            )

        draw.ellipse(
            [
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
            ],
            fill=(0, 150, 255),
            outline=(100, 200, 255),
            width=3,
        )

        # Grid lines
        for x in range(0, FRAME_WIDTH, 80):
            draw.line([(x, 0), (x, FRAME_HEIGHT)], fill=(40, 40, 50), width=1)
        for y in range(0, FRAME_HEIGHT, 60):
            draw.line([(0, y), (FRAME_WIDTH, y)], fill=(40, 40, 50), width=1)

        # Info text
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16
            )
        except:
            font = ImageFont.load_default()

        text = f"MJPEG Test | Frame: {frame_num} | {datetime.now().strftime('%H:%M:%S.%f')[:-3]}"
        draw.text((10, 10), text, fill=(255, 255, 255), font=font)

        # FPS info
        fps_text = f"{FPS} FPS | {FRAME_WIDTH}x{FRAME_HEIGHT}"
        draw.text((10, FRAME_HEIGHT - 30), fps_text, fill=(200, 200, 200), font=font)

        # Convert to JPEG
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()

    async def frame_generator(self):
        """Generate frames continuously"""
        while self.running:
            frame = self.generate_frame(self.frame_number)
            self.frame_number += 1

            # Yield MJPEG format
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
                b"\r\n" + frame + b"\r\n"
            )

            # Maintain FPS
            await asyncio.sleep(1.0 / FPS)

    async def handle_mjpeg_stream(self, request):
        """Handle MJPEG stream request"""
        print(f"[MJPEG] Client connected from {request.remote}")

        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "multipart/x-mixed-replace; boundary=frame",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

        await response.prepare(request)

        try:
            async for data in self.frame_generator():
                await response.write(data)
        except:
            pass

        print(f"[MJPEG] Client disconnected")
        return response

    async def handle_latest_frame(self, request):
        """Handle single frame request"""
        frame = self.generate_frame(self.frame_number)

        return web.Response(
            body=frame,
            content_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )

    async def handle_index(self, request):
        """Serve simple HTML viewer"""
        html = (
            """<!DOCTYPE html>
<html>
<head>
    <title>MJPEG Stream Test</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            background: #1a1a2e; 
            color: white;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }
        h1 { color: #00d4ff; }
        .video-container {
            border: 2px solid #00d4ff;
            border-radius: 8px;
            padding: 10px;
            margin: 20px;
            background: #16213e;
        }
        img { display: block; max-width: 100%; }
        .info {
            margin-top: 10px;
            padding: 10px;
            background: rgba(0,0,0,0.3);
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <h1>MJPEG Stream Test</h1>
    <div class="video-container">
        <img src="/mjpeg" width="640" height="360" />
        <div class="info">
            <p>Stream: <code>"""
            + f"http://localhost:{HTTP_PORT}/mjpeg"
            + """</code></p>
            <p>Latest frame: <code>/latest</code></p>
        </div>
    </div>
    <p>Compatible with all browsers via &lt;img&gt; tag</p>
</body>
</html>"""
        )

        return web.Response(text=html, content_type="text/html")

    async def start(self):
        """Start HTTP server"""
        print("=" * 70)
        print("MJPEG Publisher Server")
        print("=" * 70)
        print(f"\nStarting HTTP server on port {HTTP_PORT}...")

        app = web.Application()
        app.router.add_get("/", self.handle_index)
        app.router.add_get("/mjpeg", self.handle_mjpeg_stream)
        app.router.add_get("/latest", self.handle_latest_frame)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
        await site.start()

        self.running = True

        print(f"[✓] Server started!")
        print(f"\nEndpoints:")
        print(f"  - Viewer:    http://localhost:{HTTP_PORT}/")
        print(f"  - MJPEG:     http://localhost:{HTTP_PORT}/mjpeg")
        print(f"  - Latest:    http://localhost:{HTTP_PORT}/latest")
        print(f"\nSettings:")
        print(f"  - Resolution: {FRAME_WIDTH}x{FRAME_HEIGHT}")
        print(f"  - FPS:        {FPS}")
        print(f"\nPress Ctrl+C to stop")
        print("")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await runner.cleanup()


async def main():
    """Main function"""
    publisher = MJPEGPublisher()
    await publisher.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nStopped.")
        sys.exit(0)
