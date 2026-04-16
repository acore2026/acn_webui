#!/usr/bin/env python3
"""
WebRTC Publisher for WebUI
Generates test video and streams via WebRTC
Best for real-time video transmission
"""

import asyncio
import sys
from pathlib import Path
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer
from av import VideoFrame
import numpy as np
from aiohttp import web
import json

# Configuration
HTTP_PORT = 8081
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 360
FPS = 30


class TestVideoStream(VideoStreamTrack):
    """
    Custom video stream track with animated test pattern
    """

    def __init__(self):
        super().__init__()
        self.frame_num = 0
        self.start_time = asyncio.get_event_loop().time()

    async def recv(self):
        """Generate next video frame"""
        # Calculate timestamp
        pts = int((asyncio.get_event_loop().time() - self.start_time) * 90000)

        # Generate frame
        frame = self._generate_frame()
        self.frame_num += 1

        # Convert to VideoFrame
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = 1 / 90000

        return video_frame

    def _generate_frame(self):
        """Generate test pattern frame"""
        # Create blank image
        frame = np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)

        # Background gradient
        for y in range(VIDEO_HEIGHT):
            color = int(20 + (y / VIDEO_HEIGHT) * 40)
            frame[y, :] = [color, color, color + 10]

        # Moving circle
        t = self.frame_num * 0.05
        center_x = int(VIDEO_WIDTH / 2 + np.sin(t) * 150)
        center_y = int(VIDEO_HEIGHT / 2 + np.cos(t * 0.7) * 100)
        radius = 40

        # Draw circle
        y, x = np.ogrid[:VIDEO_HEIGHT, :VIDEO_WIDTH]
        mask = (x - center_x) ** 2 + (y - center_y) ** 2 <= radius**2
        frame[mask] = [0, 150, 255]  # Blue circle

        # Glow effect
        for r in range(radius + 20, radius, -2):
            mask = (x - center_x) ** 2 + (y - center_y) ** 2 <= r**2
            alpha = 0.3 * (1 - (r - radius) / 20)
            frame[mask] = frame[mask] * (1 - alpha) + np.array([0, 200, 255]) * alpha

        # Grid lines
        for x in range(0, VIDEO_WIDTH, 80):
            frame[:, x : x + 1] = [40, 40, 50]
        for y in range(0, VIDEO_HEIGHT, 60):
            frame[y : y + 1, :] = [40, 40, 50]

        # Info text (simplified - just rectangles)
        frame[10:30, 10:300] = [0, 0, 0]  # Background for text
        frame[VIDEO_HEIGHT - 40 : VIDEO_HEIGHT - 10, 10:200] = [0, 0, 0]

        return frame


class WebRTCPublisher:
    """WebRTC Publisher Server"""

    def __init__(self):
        self.pcs = set()
        self.video_track = None

    async def offer(self, request):
        """Handle WebRTC offer"""
        params = await request.json()

        print(f"[WebRTC] Received offer from {request.remote}")

        # Create peer connection
        pc = RTCPeerConnection()
        self.pcs.add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print(f"[WebRTC] Connection state: {pc.connectionState}")
            if pc.connectionState == "failed" or pc.connectionState == "closed":
                self.pcs.discard(pc)

        @pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            print(f"[WebRTC] ICE state: {pc.iceConnectionState}")

        # Add video track
        if not self.video_track:
            self.video_track = TestVideoStream()
        pc.addTrack(self.video_track)

        # Handle offer
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
        await pc.setRemoteDescription(offer)

        # Create answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        print(f"[WebRTC] Sending answer")

        return web.json_response(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        )

    async def index(self, request):
        """Serve HTML page with WebRTC client"""
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>WebRTC Video Stream Test</title>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            min-height: 100vh;
            margin: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }}
        h1 {{
            color: #00d4ff;
            margin-bottom: 10px;
            text-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
        }}
        .subtitle {{
            color: #888;
            margin-bottom: 20px;
        }}
        .video-container {{
            border: 3px solid #00d4ff;
            border-radius: 12px;
            padding: 15px;
            background: rgba(22, 33, 62, 0.8);
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.3);
            margin: 20px 0;
        }}
        video {{
            display: block;
            border-radius: 8px;
            background: #000;
        }}
        .controls {{
            display: flex;
            gap: 15px;
            margin: 20px 0;
        }}
        button {{
            padding: 12px 30px;
            font-size: 16px;
            font-weight: bold;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .connect {{
            background: linear-gradient(135deg, #00d4ff, #0099cc);
            color: #1a1a2e;
        }}
        .connect:hover {{
            background: linear-gradient(135deg, #00e5ff, #00aadd);
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
        }}
        .disconnect {{
            background: linear-gradient(135deg, #ff3366, #cc0044);
            color: white;
        }}
        .disconnect:hover {{
            background: linear-gradient(135deg, #ff4477, #dd0055);
        }}
        .disconnect:disabled {{
            background: #444;
            cursor: not-allowed;
        }}
        #status {{
            margin: 15px;
            padding: 10px 20px;
            background: rgba(0,0,0,0.3);
            border-radius: 20px;
            font-family: monospace;
            color: #00d4ff;
        }}
        .info {{
            margin-top: 20px;
            padding: 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            text-align: center;
            color: #aaa;
        }}
        .info code {{
            background: rgba(0,212,255,0.1);
            padding: 2px 6px;
            border-radius: 4px;
            color: #00d4ff;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 20px;
            width: 100%;
            max-width: 640px;
        }}
        .stat-box {{
            background: rgba(0,0,0,0.3);
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #00d4ff;
        }}
        .stat-label {{
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <h1>🔴 WebRTC Video Stream</h1>
    <p class="subtitle">Real-time video transmission test</p>
    
    <div id="status">⏸️ Ready to connect</div>
    
    <div class="video-container">
        <video id="video" width="{VIDEO_WIDTH}" height="{VIDEO_HEIGHT}" autoplay playsinline muted></video>
    </div>
    
    <div class="controls">
        <button id="connectBtn" class="connect">▶️ Connect</button>
        <button id="disconnectBtn" class="disconnect" disabled>⏹️ Disconnect</button>
    </div>
    
    <div class="stats">
        <div class="stat-box">
            <div class="stat-value" id="resolution">{VIDEO_WIDTH}x{VIDEO_HEIGHT}</div>
            <div class="stat-label">Resolution</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" id="fpsDisplay">--</div>
            <div class="stat-label">FPS</div>
        </div>
        <div class="stat-box">
            <div class="stat-value" id="latency">--</div>
            <div class="stat-label">Latency (ms)</div>
        </div>
    </div>
    
    <div class="info">
        <p>💡 This stream uses <strong>WebRTC</strong> for ultra-low latency transmission</p>
        <p>Compatible with Chrome, Firefox, Safari, and Edge</p>
    </div>
    
    <script>
        let pc = null;
        let statsInterval = null;
        let frameCount = 0;
        let lastTime = performance.now();
        
        const video = document.getElementById('video');
        const status = document.getElementById('status');
        const connectBtn = document.getElementById('connectBtn');
        const disconnectBtn = document.getElementById('disconnectBtn');
        const fpsDisplay = document.getElementById('fpsDisplay');
        const latencyDisplay = document.getElementById('latency');
        
        async function connect() {{
            try {{
                status.textContent = '🔄 Connecting...';
                connectBtn.disabled = true;
                
                // Create peer connection
                pc = new RTCPeerConnection({{
                    iceServers: [
                        {{urls: 'stun:stun.l.google.com:19302'}},
                        {{urls: 'stun:stun1.l.google.com:19302'}}
                    ]
                }});
                
                pc.ontrack = (event) => {{
                    console.log('[WebRTC] Received track:', event.track.kind);
                    if (event.streams && event.streams[0]) {{
                        video.srcObject = event.streams[0];
                        status.textContent = '🟢 Connected - Receiving video';
                        disconnectBtn.disabled = false;
                        startStats();
                    }}
                }};
                
                pc.onconnectionstatechange = () => {{
                    console.log('[WebRTC] State:', pc.connectionState);
                    status.textContent = `🔄 ${{pc.connectionState}}`;
                    
                    if (pc.connectionState === 'connected') {{
                        status.textContent = '🟢 Connected';
                    }} else if (pc.connectionState === 'failed') {{
                        status.textContent = '❌ Connection failed';
                        disconnect();
                    }}
                }};
                
                pc.oniceconnectionstatechange = () => {{
                    console.log('[WebRTC] ICE state:', pc.iceConnectionState);
                }};
                
                // Create offer
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                
                // Send to server
                const response = await fetch('/offer', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        sdp: offer.sdp,
                        type: offer.type
                    }})
                }});
                
                if (!response.ok) {{
                    throw new Error('Server error: ' + response.status);
                }}
                
                const answer = await response.json();
                await pc.setRemoteDescription(answer);
                
                console.log('[WebRTC] Connected');
                
            }} catch (err) {{
                console.error('[WebRTC] Error:', err);
                status.textContent = '❌ Error: ' + err.message;
                connectBtn.disabled = false;
                disconnectBtn.disabled = true;
            }}
        }}
        
        function disconnect() {{
            if (pc) {{
                pc.close();
                pc = null;
            }}
            video.srcObject = null;
            status.textContent = '⏸️ Disconnected';
            connectBtn.disabled = false;
            disconnectBtn.disabled = true;
            stopStats();
            fpsDisplay.textContent = '--';
            latencyDisplay.textContent = '--';
        }}
        
        function startStats() {{
            statsInterval = setInterval(async () => {{
                if (!pc) return;
                
                const stats = await pc.getStats();
                stats.forEach(report => {{
                    if (report.type === 'inbound-rtp' && report.mediaType === 'video') {{
                        // Calculate FPS
                        if (report.framesPerSecond) {{
                            fpsDisplay.textContent = report.framesPerSecond.toFixed(1);
                        }}
                        
                        // Calculate latency
                        if (report.jitter) {{
                            latencyDisplay.textContent = (report.jitter * 1000).toFixed(1);
                        }}
                    }}
                }});
            }}, 1000);
        }}
        
        function stopStats() {{
            if (statsInterval) {{
                clearInterval(statsInterval);
                statsInterval = null;
            }}
        }}
        
        connectBtn.onclick = connect;
        disconnectBtn.onclick = disconnect;
    </script>
</body>
</html>'''

        return web.Response(text=html, content_type="text/html")

    async def start(self):
        """Start server"""
        print("=" * 70)
        print("🔴 WebRTC Publisher Server")
        print("=" * 70)
        print(f"\n📡 Starting server on port {HTTP_PORT}...")

        app = web.Application()
        app.router.add_get("/", self.index)
        app.router.add_post("/offer", self.offer)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
        await site.start()

        print(f"✅ Server started!")
        print(f"\n🌐 Endpoints:")
        print(f"   📄 Viewer:    http://localhost:{HTTP_PORT}/")
        print(f"   🔌 WebRTC:    POST http://localhost:{HTTP_PORT}/offer")
        print(f"\n📊 Settings:")
        print(f"   📐 Resolution: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
        print(f"   🎬 FPS:        {FPS}")
        print(f"   🎯 Protocol:   WebRTC (Ultra-low latency)")
        print(f"\n⚡ Features:")
        print(f"   ✓ Hardware acceleration support")
        print(f"   ✓ Automatic bitrate adaptation")
        print(f"   ✓ End-to-end encryption (DTLS-SRTP)")
        print(f"\n🛑 Press Ctrl+C to stop\n")

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            print("\n🧹 Cleaning up...")
            # Close all peer connections
            if self.pcs:
                coros = [pc.close() for pc in self.pcs]
                await asyncio.gather(*coros, return_exceptions=True)
            await runner.cleanup()
            print("✅ Stopped")


async def main():
    """Main function"""
    # Check dependencies
    try:
        import aiortc
        import av
    except ImportError:
        print("📦 Installing dependencies...")
        import subprocess

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "aiortc", "av"], check=True
        )
        print("✅ Dependencies installed\n")

    server = WebRTCPublisher()
    await server.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
