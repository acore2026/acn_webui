#!/usr/bin/env python3
"""
Simple WebRTC Video Stream
Uses aiortc for WebRTC streaming
"""

import asyncio
import sys
from pathlib import Path

# Install aiortc if needed
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription
    from aiortc.contrib.media import MediaPlayer
except ImportError:
    print("Installing aiortc...")
    import subprocess

    subprocess.run([sys.executable, "-m", "pip", "install", "aiortc"], check=True)
    from aiortc import RTCPeerConnection, RTCSessionDescription
    from aiortc.contrib.media import MediaPlayer

from aiohttp import web
import json

# Configuration
HTTP_PORT = 8081


class WebRTCServer:
    """Simple WebRTC server"""

    def __init__(self):
        self.pcs = set()

    async def offer(self, request):
        """Handle WebRTC offer"""
        params = await request.json()

        # Create peer connection
        pc = RTCPeerConnection()
        self.pcs.add(pc)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print(f"[WebRTC] Connection state: {pc.connectionState}")
            if pc.connectionState == "closed":
                self.pcs.discard(pc)

        # Create media source (test pattern)
        player = MediaPlayer(
            "testsrc=size=640x360:rate=30",
            format="lavfi",
            options={
                "pix_fmt": "yuv420p",
                "c:v": "libx264",
            },
        )

        # Add track
        if player.video:
            pc.addTrack(player.video)

        # Handle offer
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
        await pc.setRemoteDescription(offer)

        # Create answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return web.json_response(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        )

    async def index(self, request):
        """Serve HTML page"""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>WebRTC Video Test</title>
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
        video {
            border: 2px solid #00d4ff;
            border-radius: 8px;
            max-width: 100%;
        }
        button {
            padding: 10px 20px;
            font-size: 16px;
            background: #00d4ff;
            color: #1a1a2e;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin: 10px;
        }
        button:hover { background: #00a0cc; }
        #status { margin: 10px; color: #aaa; }
    </style>
</head>
<body>
    <h1>WebRTC Video Test</h1>
    <div id="status">Click Connect to start</div>
    <video id="video" width="640" height="360" autoplay playsinline></video>
    <div>
        <button id="connect">Connect</button>
        <button id="disconnect">Disconnect</button>
    </div>
    
    <script>
        let pc = null;
        const video = document.getElementById('video');
        const status = document.getElementById('status');
        const connectBtn = document.getElementById('connect');
        const disconnectBtn = document.getElementById('disconnect');
        
        connectBtn.onclick = async () => {
            try {
                status.textContent = 'Connecting...';
                
                // Create peer connection
                pc = new RTCPeerConnection({
                    iceServers: [{urls: 'stun:stun.l.google.com:19302'}]
                });
                
                pc.ontrack = (event) => {
                    status.textContent = 'Connected - Receiving video';
                    if (event.streams[0]) {
                        video.srcObject = event.streams[0];
                    }
                };
                
                pc.onconnectionstatechange = () => {
                    status.textContent = `Connection state: ${pc.connectionState}`;
                };
                
                // Create offer
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                
                // Send to server
                const response = await fetch('/offer', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({sdp: offer.sdp, type: offer.type})
                });
                
                const answer = await response.json();
                await pc.setRemoteDescription(answer);
                
            } catch (err) {
                status.textContent = 'Error: ' + err.message;
                console.error(err);
            }
        };
        
        disconnectBtn.onclick = () => {
            if (pc) {
                pc.close();
                pc = null;
                video.srcObject = null;
                status.textContent = 'Disconnected';
            }
        };
    </script>
</body>
</html>"""

        return web.Response(text=html, content_type="text/html")

    async def start(self):
        """Start server"""
        print("=" * 70)
        print("WebRTC Server")
        print("=" * 70)
        print(f"\nStarting server on port {HTTP_PORT}...")

        app = web.Application()
        app.router.add_get("/", self.index)
        app.router.add_post("/offer", self.offer)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
        await site.start()

        print(f"[✓] Server started!")
        print(f"\nOpen browser: http://localhost:{HTTP_PORT}/")
        print(f"\nPress Ctrl+C to stop")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            # Close all peer connections
            coros = [pc.close() for pc in self.pcs]
            await asyncio.gather(*coros, return_exceptions=True)
            await runner.cleanup()


async def main():
    server = WebRTCServer()
    await server.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nStopped.")
