#!/usr/bin/env python3
"""
H.264 Video Test for WebUI
Generate H.264 test video with FFmpeg and publish via MOQ
"""

import asyncio
import subprocess
import os
import sys
import tempfile
import time
from pathlib import Path

# Add webui root to path
WEBUI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.pub.publisher import MOQPublisher, PublishedObject
from moq.encoding import FullTrackName

# Test configuration
RELAY_HOST = "localhost"
RELAY_PORT = 9003  # Use existing agent_gw relay
TASK_ID = "task-c2a09"  # Use existing task that WebUI is subscribed to
AGENT_ID = "did:udid:type2.rid678.achid0.uerid1380013800032729@6gc.mnc015.mcc234.3gppnetwork.org"

# Video settings
VIDEO_DURATION = 10  # seconds
VIDEO_FPS = 30
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 360
VIDEO_BITRATE = "500k"


def generate_h264_video(output_path: str, duration: int = 10):
    """Generate H.264 test video using FFmpeg"""
    print(
        f"[1] Generating {duration}s H.264 test video ({VIDEO_WIDTH}x{VIDEO_HEIGHT}@{VIDEO_FPS}fps)..."
    )

    cmd = [
        "ffmpeg",
        "-y",
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
        "-b:v",
        VIDEO_BITRATE,
        "-g",
        str(VIDEO_FPS),  # GOP size = 1 second
        "-keyint_min",
        str(VIDEO_FPS),
        "-sc_threshold",
        "0",
        "-f",
        "h264",
        output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            file_size = os.path.getsize(output_path)
            duration_str = f"{duration}s"
            print(f"[✓] H.264 video generated: {output_path}")
            print(f"    Size: {file_size} bytes ({file_size / 1024:.1f} KB)")
            print(f"    Duration: {duration_str}")
            print(f"    Expected frames: {duration * VIDEO_FPS}")
            return True
        else:
            print(f"[✗] FFmpeg failed (exit code: {result.returncode})")
            if result.stderr:
                print(f"    Error: {result.stderr[-500:]}")
            return False

    except subprocess.TimeoutExpired:
        print("[✗] FFmpeg timed out")
        return False
    except FileNotFoundError:
        print("[✗] FFmpeg not found")
        print("    Install: apt-get install ffmpeg")
        return False


def split_h264_frames(data: bytes) -> list:
    """
    Split H.264 data into NAL units (frames)
    H.264 NAL unit start codes: 0x00 0x00 0x00 0x01 or 0x00 0x00 0x01
    """
    frames = []
    start_code_4 = b"\x00\x00\x00\x01"
    start_code_3 = b"\x00\x00\x01"

    i = 0
    frame_start = 0

    while i < len(data) - 4:
        # Check for start code
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

    # Add last frame
    if frame_start < len(data):
        frames.append(data[frame_start:])

    # Filter: keep only substantial frames (NAL units)
    # H.264 NAL type is in first byte after start code
    frames = [f for f in frames if len(f) >= 5]

    return frames


def analyze_frame_types(frames: list) -> dict:
    """Analyze H.264 frame types"""
    stats = {
        "IDR": 0,  # Instantaneous Decoder Refresh (keyframe)
        "non-IDR": 0,  # Non-IDR slice
        "SEI": 0,  # Supplemental Enhancement Information
        "SPS": 0,  # Sequence Parameter Set
        "PPS": 0,  # Picture Parameter Set
        "AUD": 0,  # Access Unit Delimiter
        "other": 0,
    }

    for frame in frames:
        if len(frame) < 5:
            continue

        # Find NAL unit type (skip start code)
        if frame[0:4] == b"\x00\x00\x00\x01":
            nal_type = frame[4] & 0x1F
        elif frame[0:3] == b"\x00\x00\x01":
            nal_type = frame[3] & 0x1F
        else:
            continue

        # Classify NAL type
        if nal_type == 5:
            stats["IDR"] += 1
        elif nal_type == 1:
            stats["non-IDR"] += 1
        elif nal_type == 6:
            stats["SEI"] += 1
        elif nal_type == 7:
            stats["SPS"] += 1
        elif nal_type == 8:
            stats["PPS"] += 1
        elif nal_type == 9:
            stats["AUD"] += 1
        else:
            stats["other"] += 1

    return stats


async def publish_video_frames(video_path: str):
    """Publish H.264 video frames via MOQ"""
    print(f"\n[2] Connecting to MOQ Relay at {RELAY_HOST}:{RELAY_PORT}...")

    publisher = MOQPublisher(RELAY_HOST, RELAY_PORT)

    connected = await publisher.connect(agent_id=AGENT_ID)
    if not connected:
        print("[✗] Failed to connect to relay")
        return False

    print("[✓] Connected to relay")

    # Create track name matching WebUI subscription
    namespace = [TASK_ID, AGENT_ID]
    track_name = "Video"

    full_track_name = FullTrackName(
        namespace=[ns.encode() for ns in namespace],
        track_name=track_name.encode(),
    )

    print(f"\n[3] Publishing to track:")
    print(f"    Namespace: {namespace}")
    print(f"    Track: {track_name}")

    # Publish track
    success = await publisher.publish(full_track_name)
    if not success:
        print("[✗] Failed to publish track")
        return False

    print("[✓] Track published")
    await asyncio.sleep(0.5)

    # Read video file
    print(f"\n[4] Reading H.264 file: {video_path}")
    with open(video_path, "rb") as f:
        video_data = f.read()

    print(f"    File size: {len(video_data)} bytes")

    # Split into NAL units
    frames = split_h264_frames(video_data)
    print(f"    NAL units found: {len(frames)}")

    # Analyze frame types
    frame_stats = analyze_frame_types(frames)
    print(f"\n    Frame analysis:")
    for ftype, count in frame_stats.items():
        if count > 0:
            print(f"      {ftype}: {count}")

    # Send frames
    print(f"\n[5] Publishing {len(frames)} NAL units...")

    group_id = 0
    object_id = 0
    idr_count = 0
    start_time = time.time()

    for i, frame_data in enumerate(frames):
        # Determine if this is a keyframe (IDR)
        is_idr = False
        if len(frame_data) >= 5:
            if frame_data[0:4] == b"\x00\x00\x00\x01":
                nal_type = frame_data[4] & 0x1F
            elif frame_data[0:3] == b"\x00\x00\x01":
                nal_type = frame_data[3] & 0x1F
            else:
                nal_type = 0
            is_idr = nal_type == 5
            if is_idr:
                idr_count += 1

        # Create object
        obj = PublishedObject(
            group_id=group_id,
            object_id=object_id,
            payload=frame_data,
            publisher_priority=128,
            subgroup_id=0,
            use_datagram=False,
        )

        # Publish
        await publisher.send_object(full_track_name, obj)
        object_id += 1

        # Progress every second of video
        if (i + 1) % VIDEO_FPS == 0:
            elapsed = time.time() - start_time
            fps = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"    Published {i + 1}/{len(frames)} NAL units ({fps:.1f} fps)")

        # Maintain timing (simulate real-time streaming)
        await asyncio.sleep(1.0 / VIDEO_FPS)

    elapsed = time.time() - start_time
    print(f"[✓] Published {len(frames)} NAL units in {elapsed:.1f}s")
    print(f"    Keyframes (IDR): {idr_count}")

    # Keep stream alive
    print(f"\n[6] Keeping stream alive for 5 seconds...")
    await asyncio.sleep(5)

    publisher.disconnect()
    print("[✓] Disconnected")

    return True


async def main():
    """Main test function"""
    print("=" * 70)
    print("H.264 Video Test for WebUI")
    print("=" * 70)
    print(f"\nTarget: {TASK_ID}")
    print(f"Agent: {AGENT_ID}")

    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="h264_test_")
    video_path = os.path.join(temp_dir, "test.h264")

    try:
        # Generate H.264 video
        if not generate_h264_video(video_path, VIDEO_DURATION):
            print("\n[✗] Failed to generate video")
            return 1

        # Publish video
        success = await publish_video_frames(video_path)

        if success:
            print("\n" + "=" * 70)
            print("TEST COMPLETE")
            print("=" * 70)
            print(f"\nCheck WebUI at http://localhost:9005")
            print(f"You should see H.264 video for: {TASK_ID}")
            print("\nNote: Frontend needs WebCodecs API support for H.264 decoding")
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
