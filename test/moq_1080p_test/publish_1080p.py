#!/usr/bin/env python3
"""
Publisher for 1080p test video
读取 test_1080p.h264 并推送到 MOQ Relay
"""

import asyncio
import sys
from pathlib import Path
import time

# Add webui to path
WEBUI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.pub.publisher import MOQPublisher, PublishedObject
from moq.encoding import FullTrackName

# Configuration
RELAY_HOST = "localhost"
RELAY_PORT = 9008
TASK_ID = "test-ffmpeg-video"
AGENT_ID = "ffmpeg-publisher"
VIDEO_FILE = "/root/lpx/webui/test/test_1080p.h264"
FPS = 30


class H264Publisher:
    """Publish H.264 video file via MOQ"""

    def __init__(self):
        self.publisher = None
        self.running = False

    def split_h264_frames(self, data):
        """Split H.264 file into NAL units"""
        frames = []
        start_code_4 = b"\x00\x00\x00\x01"
        start_code_3 = b"\x00\x00\x01"

        i = 0
        frame_start = 0

        while i < len(data) - 4:
            if data[i : i + 4] == start_code_4:
                if frame_start < i:
                    frames.append(data[frame_start:i])
                frame_start = i
                i += 4
            elif data[i : i + 3] == start_code_3:
                if frame_start < i:
                    frames.append(data[frame_start:i])
                frame_start = i
                i += 3
            else:
                i += 1

        if frame_start < len(data):
            frames.append(data[frame_start:])

        return [f for f in frames if len(f) > 10]

    async def publish_video(self):
        """Read video file and publish via MOQ"""
        print("=" * 70)
        print("1080p H.264 Video Publisher")
        print("=" * 70)

        # Read video file
        print(f"\n[1] Reading {VIDEO_FILE}...")
        try:
            with open(VIDEO_FILE, "rb") as f:
                video_data = f.read()
            print(f"    File size: {len(video_data)} bytes")
        except FileNotFoundError:
            print(f"    [✗] File not found: {VIDEO_FILE}")
            return False

        # Split into frames
        print(f"\n[2] Splitting into NAL units...")
        frames = self.split_h264_frames(video_data)
        print(f"    Total frames: {len(frames)}")

        # Connect to relay
        print(f"\n[3] Connecting to MOQ relay at {RELAY_HOST}:{RELAY_PORT}...")
        self.publisher = MOQPublisher(RELAY_HOST, RELAY_PORT)

        connected = await self.publisher.connect(agent_id=AGENT_ID)
        if not connected:
            print("    [✗] Failed to connect")
            return False
        print("    [✓] Connected")

        # Publish track
        print(f"\n[4] Publishing track...")
        namespace = [TASK_ID, AGENT_ID]
        track_name = "Video"

        full_track_name = FullTrackName(
            namespace=[ns.encode() for ns in namespace],
            track_name=track_name.encode(),
        )

        success = await self.publisher.publish(full_track_name)
        if not success:
            print("    [✗] Failed to publish")
            return False
        print("    [✓] Track published")

        await asyncio.sleep(0.5)

        # Publish frames
        print(f"\n[5] Publishing {len(frames)} frames (looping)...")
        print("    Press Ctrl+C to stop\n")

        self.running = True
        frame_count = 0

        try:
            while self.running:
                for i, frame_data in enumerate(frames):
                    if not self.running:
                        break

                    obj = PublishedObject(
                        group_id=0,
                        object_id=frame_count,
                        payload=frame_data,
                        publisher_priority=128,
                        subgroup_id=0,
                        use_datagram=False,
                    )

                    await self.publisher.send_object(full_track_name, obj)
                    frame_count += 1

                    if frame_count % 30 == 0:
                        print(
                            f"    Published {frame_count} frames (current: {i + 1}/{len(frames)})"
                        )

                    await asyncio.sleep(1.0 / FPS)

                print(f"    Loop completed, restarting...")

        except KeyboardInterrupt:
            print("\n\nStopping publisher...")

        return True

    def stop(self):
        """Stop publisher"""
        self.running = False
        if self.publisher:
            self.publisher.disconnect()


async def main():
    publisher = H264Publisher()
    try:
        await publisher.publish_video()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        publisher.stop()


if __name__ == "__main__":
    asyncio.run(main())
