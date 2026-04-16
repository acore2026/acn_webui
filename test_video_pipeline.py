#!/usr/bin/env python3
"""
MOQ Video Pipeline Test
Generate test video with FFmpeg and publish via MOQ
"""

import asyncio
import subprocess
import os
import sys
import tempfile
import time
from pathlib import Path

WEBUI_ROOT = Path(__file__).parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.pub.publisher import MOQPublisher, PublishedObject
from moq.encoding import FullTrackName

# Test configuration
RELAY_HOST = "localhost"
RELAY_PORT = 9003
TASK_ID = "test-video-001"
AGENT_ID = "test-agent-001"
VIDEO_DURATION = 30  # seconds
VIDEO_FPS = 30
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 360


def generate_test_video(output_path: str, duration: int = 30):
    """Generate test video using FFmpeg"""
    print(f"[1] Generating {duration}s test video...")

    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration}:size={VIDEO_WIDTH}x{VIDEO_HEIGHT}:rate={VIDEO_FPS}",
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
        "-g",
        "30",  # GOP size
        "-keyint_min",
        "30",
        "-sc_threshold",
        "0",
        "-f",
        "h264",  # Output raw H264
        output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            file_size = os.path.getsize(output_path)
            print(f"[✓] Video generated: {output_path}")
            print(f"    Size: {file_size} bytes")
            return True
        else:
            print(f"[✗] FFmpeg failed:")
            print(f"    stderr: {result.stderr[-500:]}")  # Last 500 chars
            return False

    except subprocess.TimeoutExpired:
        print("[✗] FFmpeg timed out")
        return False
    except FileNotFoundError:
        print("[✗] FFmpeg not found. Please install: apt-get install ffmpeg")
        return False


async def publish_video_frames(video_path: str):
    """Publish video frames via MOQ"""
    print(f"\n[2] Connecting to MOQ Relay at {RELAY_HOST}:{RELAY_PORT}...")

    publisher = MOQPublisher(RELAY_HOST, RELAY_PORT)

    connected = await publisher.connect(agent_id=AGENT_ID)
    if not connected:
        print("[✗] Failed to connect to relay")
        return False

    print("[✓] Connected to relay")

    # Create track name
    namespace = [TASK_ID, AGENT_ID]
    track_name = "Video"

    full_track_name = FullTrackName(
        namespace=[ns.encode() for ns in namespace],
        track_name=track_name.encode(),
    )

    print(f"\n[3] Publishing to track:")
    print(f"    Namespace: {namespace}")
    print(f"    Track name: {track_name}")

    # Publish track
    success = await publisher.publish(full_track_name)
    if not success:
        print("[✗] Failed to publish track")
        return False

    print("[✓] Track published")

    # Wait for PUBLISH_OK
    await asyncio.sleep(1)

    # Read video file and publish frames
    print(f"\n[4] Publishing video frames from {video_path}...")

    # Read the H264 file
    with open(video_path, "rb") as f:
        video_data = f.read()

    # Split into frames (simplified: split by NAL unit start codes)
    frames = split_h264_frames(video_data)

    print(f"    Total frames to publish: {len(frames)}")

    group_id = 0
    object_id = 0
    frames_published = 0

    for i, frame_data in enumerate(frames):
        # Create object
        obj = PublishedObject(
            group_id=group_id,
            object_id=object_id,
            payload=frame_data,
            publisher_priority=128,
            subgroup_id=0,
            use_datagram=False,  # Use stream
        )

        # Publish object
        await publisher.send_object(full_track_name, obj)

        frames_published += 1
        object_id += 1

        # Progress
        if frames_published % 10 == 0:
            print(f"    Published {frames_published}/{len(frames)} frames")

        # Simulate 30fps timing
        await asyncio.sleep(1.0 / VIDEO_FPS)

    print(f"[✓] Published {frames_published} frames")

    # Keep publishing for a while
    print(f"\n[5] Keeping stream alive for 10 seconds...")
    await asyncio.sleep(10)

    publisher.disconnect()
    print("[✓] Disconnected")

    return True


def split_h264_frames(data: bytes) -> list:
    """Split H264 data into frames (simplified)"""
    frames = []

    # Look for NAL unit start codes: 0x00 0x00 0x00 0x01 or 0x00 0x00 0x01
    start_code_4 = b"\x00\x00\x00\x01"
    start_code_3 = b"\x00\x00\x01"

    i = 0
    current_frame_start = 0

    while i < len(data) - 4:
        if data[i : i + 4] == start_code_4 or data[i : i + 3] == start_code_3:
            if current_frame_start < i:
                frames.append(data[current_frame_start:i])
            current_frame_start = i
            i += 4 if data[i : i + 4] == start_code_4 else 3
        else:
            i += 1

    # Add last frame
    if current_frame_start < len(data):
        frames.append(data[current_frame_start:])

    # Filter out empty frames and very small frames
    frames = [f for f in frames if len(f) > 10]

    return frames


async def main():
    """Main test function"""
    print("=" * 70)
    print("MOQ Video Pipeline Test")
    print("=" * 70)

    # Create temp directory for test video
    temp_dir = tempfile.mkdtemp(prefix="moq_test_")
    video_path = os.path.join(temp_dir, "test.h264")

    try:
        # Generate test video
        if not generate_test_video(video_path, VIDEO_DURATION):
            print("\n[✗] Failed to generate test video")
            return 1

        # Publish video
        success = await publish_video_frames(video_path)

        if success:
            print("\n" + "=" * 70)
            print("TEST COMPLETE")
            print("=" * 70)
            print(f"\nNow check the WebUI at http://localhost:9005")
            print(f"You should see video for task: {TASK_ID}")
            return 0
        else:
            print("\n[✗] Test failed")
            return 1

    finally:
        # Cleanup
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
