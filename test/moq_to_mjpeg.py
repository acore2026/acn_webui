#!/usr/bin/env python3
"""
MOQ to MJPEG Bridge
Converts MOQ H.264 stream to MJPEG for browser display
"""

import asyncio
import sys
import os
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

# Add webui root to path
WEBUI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.sub.subscriber import MOQSubscriber, ReceivedObject
from moq.encoding import FullTrackName

# Configuration
RELAY_HOST = "localhost"
RELAY_PORT = 9003
TASK_ID = "task-c2a09"
AGENT_ID = "did:udid:type2.rid678.achid0.uerid1380013800032729@6gc.mnc015.mcc234.3gppnetwork.org"
WEBUI_API = "http://localhost:9005/api/video/mjpeg"

# Frame conversion
FRAME_WIDTH = 640
FRAME_HEIGHT = 360
FPS = 30


class MOQtoMJPEGBridge:
    """Bridge MOQ stream to MJPEG"""

    def __init__(self):
        self.subscriber = MOQSubscriber(RELAY_HOST, RELAY_PORT)
        self.frame_buffer = b""
        self.jpeg_sequence = 0
        self.running = False

    async def start(self):
        """Start the bridge"""
        print("=" * 70)
        print("MOQ to MJPEG Bridge")
        print("=" * 70)

        # Setup handlers
        self.subscriber.set_handlers(
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected,
            on_object_received=self._on_object_received,
            on_subscription_accepted=self._on_subscription_accepted,
        )

        # Connect to relay
        print(f"\n[1] Connecting to relay at {RELAY_HOST}:{RELAY_PORT}...")
        connected = await self.subscriber.connect()
        if not connected:
            print("[✗] Failed to connect")
            return False

        await asyncio.sleep(1)

        # Subscribe to track
        namespace = [TASK_ID, AGENT_ID]
        track_name = "Video"

        full_track_name = FullTrackName(
            namespace=[ns.encode() for ns in namespace],
            track_name=track_name.encode(),
        )

        print(f"\n[2] Subscribing to track...")
        await self.subscriber.subscribe(full_track_name)

        # Keep running
        self.running = True
        print(f"\n[3] Bridge running. Press Ctrl+C to stop.")
        print(f"    MJPEG stream available at:")
        print(f"    {WEBUI_API}/{self._get_track_id()}")

        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

        return True

    def _get_track_id(self):
        """Generate track ID"""
        return f"{AGENT_ID}_{TASK_ID}_video"

    def _on_connected(self):
        print("[✓] Connected to relay")

    def _on_disconnected(self):
        print("[✗] Disconnected from relay")
        self.running = False

    def _on_subscription_accepted(self, track_name):
        print(f"[✓] Subscription accepted: {track_name}")

    async def _on_object_received(self, obj: ReceivedObject):
        """Handle received object"""
        # Accumulate H.264 data
        self.frame_buffer += obj.payload

        # Convert to JPEG every N frames
        if len(self.frame_buffer) > 50000:  # ~50KB of data
            await self._convert_and_send()
            self.frame_buffer = b""

    async def _convert_and_send(self):
        """Convert H.264 to JPEG and send to MJPEG server"""
        try:
            # Use FFmpeg to convert H.264 to JPEG
            jpeg_data = await self._h264_to_jpeg(self.frame_buffer)

            if jpeg_data:
                # Send to MJPEG endpoint
                await self._send_jpeg(jpeg_data)
                self.jpeg_sequence += 1

                if self.jpeg_sequence % 10 == 0:
                    print(f"    Converted {self.jpeg_sequence} frames to JPEG")

        except Exception as e:
            print(f"    Conversion error: {e}")

    async def _h264_to_jpeg(self, h264_data: bytes) -> bytes:
        """Convert H.264 to JPEG using FFmpeg"""
        # Create temp files
        with tempfile.NamedTemporaryFile(suffix=".h264", delete=False) as f_in:
            f_in.write(h264_data)
            input_path = f_in.name

        output_path = input_path + ".jpg"

        try:
            # Run FFmpeg
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "h264",
                "-i",
                input_path,
                "-vf",
                f"scale={FRAME_WIDTH}:{FRAME_HEIGHT}",
                "-q:v",
                "5",  # Quality (1-31, lower is better)
                "-f",
                "image2",
                "-vframes",
                "1",
                output_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            await asyncio.wait_for(proc.wait(), timeout=5.0)

            # Read output
            if os.path.exists(output_path):
                with open(output_path, "rb") as f:
                    return f.read()

        except Exception as e:
            print(f"FFmpeg error: {e}")
        finally:
            # Cleanup
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(output_path):
                os.remove(output_path)

        return None

    async def _send_jpeg(self, jpeg_data: bytes):
        """Send JPEG to MJPEG server via API"""
        import aiohttp

        track_id = self._get_track_id()
        url = f"{WEBUI_API}/{track_id}/frame"

        try:
            async with aiohttp.ClientSession() as session:
                # For now, we'll save to a shared buffer
                # In production, this would be a proper API call
                pass
        except Exception as e:
            print(f"Send error: {e}")

    def stop(self):
        """Stop the bridge"""
        self.running = False
        self.subscriber.disconnect()


async def main():
    """Main function"""
    bridge = MOQtoMJPEGBridge()

    try:
        await bridge.start()
    except KeyboardInterrupt:
        print("\n\nStopping bridge...")
        bridge.stop()

    return 0


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
