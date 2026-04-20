#!/usr/bin/env python3
"""
FFmpeg Video Publisher for MOQ
Generates real video with FFmpeg and publishes via MOQ
"""

import asyncio
import subprocess
import os
import sys
import tempfile
import time
from pathlib import Path

# Add webui to path
WEBUI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.pub.publisher import MOQPublisher, PublishedObject
from moq.encoding import FullTrackName

# Configuration
RELAY_HOST = "localhost"
RELAY_PORT = 9003
TASK_ID = "test-ffmpeg-video"
AGENT_ID = "ffmpeg-publisher"

# Video settings
VIDEO_FPS = 30
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 360
VIDEO_DURATION = 60  # seconds


class FFmpegVideoPublisher:
    """FFmpeg video publisher"""

    def __init__(self):
        self.running = False
        self.publisher = None

    async def generate_and_publish(self):
        """Generate video with FFmpeg and publish via MOQ"""
        print("=" * 70)
        print("FFmpeg Video Publisher for MOQ")
        print("=" * 70)

        # Create temp directory for video
        temp_dir = tempfile.mkdtemp(prefix="moq_video_")
        video_path = os.path.join(temp_dir, "test.h264")

        try:
            # Step 1: Generate video with FFmpeg
            print("\n[1] Generating video with FFmpeg...")
            print(f"    Resolution: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
            print(f"    FPS: {VIDEO_FPS}")
            print(f"    Duration: {VIDEO_DURATION}s")

            success = await self._generate_video(video_path)
            if not success:
                print("[✗] FFmpeg failed")
                return False

            # Step 2: Split into NAL units
            print("\n[2] Splitting video into NAL units...")
            frames = await self._split_h264_frames(video_path)
            print(f"    Total frames: {len(frames)}")

            # Step 3: Connect to MOQ
            print(f"\n[3] Connecting to MOQ at {RELAY_HOST}:{RELAY_PORT}...")
            self.publisher = MOQPublisher(RELAY_HOST, RELAY_PORT)

            connected = await self.publisher.connect(agent_id=AGENT_ID)
            if not connected:
                print("[✗] Failed to connect")
                return False
            print("[✓] Connected")

            # Step 4: Publish track
            print("\n[4] Publishing track...")
            namespace = [TASK_ID, AGENT_ID]
            track_name = "Video"

            full_track_name = FullTrackName(
                namespace=[ns.encode() for ns in namespace],
                track_name=track_name.encode(),
            )

            success = await self.publisher.publish(full_track_name)
            if not success:
                print("[✗] Failed to publish")
                return False
            print("[✓] Track published")

            await asyncio.sleep(1)

            # Step 5: Publish frames
            print(f"\n[5] Publishing {len(frames)} frames...")
            self.running = True

            for i, frame_data in enumerate(frames):
                if not self.running:
                    break

                obj = PublishedObject(
                    group_id=0,
                    object_id=i,
                    payload=frame_data,
                    publisher_priority=128,
                    subgroup_id=0,
                    use_datagram=False,
                )

                await self.publisher.send_object(full_track_name, obj)

                if (i + 1) % 30 == 0:
                    print(f"    Published {i + 1}/{len(frames)} frames")

                await asyncio.sleep(1.0 / VIDEO_FPS)

            print(f"[✓] Published all frames")

            # Keep alive
            print("\n[6] Keeping stream alive...")
            while self.running:
                await asyncio.sleep(1)

            return True

        finally:
            if self.publisher:
                self.publisher.disconnect()
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    async def _generate_video(self, output_path):
        """Generate H.264 video with FFmpeg"""
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={VIDEO_DURATION}:size={VIDEO_WIDTH}x{VIDEO_HEIGHT}:rate={VIDEO_FPS}",
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-profile:v",
            "baseline",
            "-level",
            "3.0",
            "-b:v",
            "500k",
            "-g",
            str(VIDEO_FPS),
            "-keyint_min",
            str(VIDEO_FPS),
            "-sc_threshold",
            "0",
            "-f",
            "h264",
            output_path,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

            if proc.returncode == 0:
                size = os.path.getsize(output_path)
                print(f"    [✓] Video generated: {size} bytes")
                return True
            else:
                print(f"    [✗] FFmpeg error: {stderr.decode()[-200:]}")
                return False

        except Exception as e:
            print(f"    [✗] Error: {e}")
            return False

    async def _split_h264_frames(self, video_path):
        """Split H.264 file into NAL units"""
        with open(video_path, "rb") as f:
            data = f.read()

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

        frames = [f for f in frames if len(f) > 10]
        return frames

    def stop(self):
        self.running = False
        if self.publisher:
            self.publisher.disconnect()


async def main():
    publisher = FFmpegVideoPublisher()

    try:
        await publisher.generate_and_publish()
    except KeyboardInterrupt:
        print("\n\nStopping...")
        publisher.stop()


if __name__ == "__main__":
    asyncio.run(main())
