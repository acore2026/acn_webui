#!/usr/bin/env python3
"""
MOQ Video Publisher for Testing
Generates test video and publishes via MOQ
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
RELAY_PORT = 9004  # Use test relay port
TASK_ID = "test-video"
AGENT_ID = "test-publisher"

# Video settings
VIDEO_FPS = 30
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 360
FRAME_COUNT = 300  # 10 seconds at 30fps


def generate_test_frame(frame_num: int) -> bytes:
    """Generate a simple test image using ImageMagick or create manually"""
    # Create a simple BMP image with a pattern
    # BMP header + pixel data
    width = VIDEO_WIDTH
    height = VIDEO_HEIGHT

    # BMP file header (14 bytes)
    file_header = bytearray(
        [
            0x42,
            0x4D,  # "BM"
            0x00,
            0x00,
            0x00,
            0x00,  # File size (placeholder)
            0x00,
            0x00,  # Reserved
            0x00,
            0x00,  # Reserved
            0x36,
            0x00,
            0x00,
            0x00,  # Offset to pixel data (54 bytes)
        ]
    )

    # DIB header (BITMAPINFOHEADER - 40 bytes)
    dib_header = bytearray(
        [
            0x28,
            0x00,
            0x00,
            0x00,  # Header size (40)
            width & 0xFF,
            (width >> 8) & 0xFF,
            0x00,
            0x00,  # Width
            height & 0xFF,
            (height >> 8) & 0xFF,
            0x00,
            0x00,  # Height
            0x01,
            0x00,  # Planes
            0x18,
            0x00,  # Bits per pixel (24)
            0x00,
            0x00,
            0x00,
            0x00,  # Compression (none)
            0x00,
            0x00,
            0x00,
            0x00,  # Image size
            0x00,
            0x00,
            0x00,
            0x00,  # X pixels per meter
            0x00,
            0x00,
            0x00,
            0x00,  # Y pixels per meter
            0x00,
            0x00,
            0x00,
            0x00,  # Colors used
            0x00,
            0x00,
            0x00,
            0x00,  # Important colors
        ]
    )

    # Pixel data (BGR format, bottom-up)
    # Create a simple gradient pattern
    row_size = (width * 3 + 3) & ~3  # Align to 4 bytes
    pixel_data = bytearray()

    for y in range(height):
        row = bytearray()
        for x in range(width):
            # Create a moving gradient based on frame number
            r = (x + frame_num * 2) % 256
            g = (y + frame_num) % 256
            b = ((x + y) // 2) % 256
            row.extend([b, g, r])  # BGR order
        # Pad row to 4-byte alignment
        while len(row) < row_size:
            row.append(0)
        pixel_data.extend(row)

    # Calculate file size
    file_size = 54 + len(pixel_data)
    file_header[2:6] = file_size.to_bytes(4, "little")

    # Update DIB header with image size
    dib_header[20:24] = len(pixel_data).to_bytes(4, "little")

    return bytes(file_header) + bytes(dib_header) + bytes(pixel_data)


async def main():
    """Main test function"""
    print("=" * 70)
    print("MOQ Video Publisher (Test)")
    print("=" * 70)

    print(f"\n[1] Connecting to relay at {RELAY_HOST}:{RELAY_PORT}...")

    publisher = MOQPublisher(RELAY_HOST, RELAY_PORT)

    connected = await publisher.connect(agent_id=AGENT_ID)
    if not connected:
        print("[✗] Failed to connect to relay")
        return 1

    print("[✓] Connected to relay")

    # Create track
    namespace = [TASK_ID, AGENT_ID]
    track_name = "Video"

    full_track_name = FullTrackName(
        namespace=[ns.encode() for ns in namespace],
        track_name=track_name.encode(),
    )

    print(f"\n[2] Publishing track:")
    print(f"    Namespace: {namespace}")
    print(f"    Track: {track_name}")

    success = await publisher.publish(full_track_name)
    if not success:
        print("[✗] Failed to publish track")
        return 1

    print("[✓] Track published")
    await asyncio.sleep(1)

    # Send video frames
    print(
        f"\n[3] Sending {FRAME_COUNT} video frames ({FRAME_COUNT // VIDEO_FPS}s at {VIDEO_FPS}fps)..."
    )
    print(f"    Resolution: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")

    start_time = time.time()

    for i in range(FRAME_COUNT):
        # Generate test frame
        frame_data = generate_test_frame(i)

        obj = PublishedObject(
            group_id=0,
            object_id=i,
            payload=frame_data,
            publisher_priority=128,
            subgroup_id=0,
            use_datagram=False,
        )

        await publisher.send_object(full_track_name, obj)

        if (i + 1) % 30 == 0:
            elapsed = time.time() - start_time
            fps = (i + 1) / elapsed
            print(f"    Sent {i + 1}/{FRAME_COUNT} frames ({fps:.1f} fps)")

        # Maintain frame rate
        await asyncio.sleep(1.0 / VIDEO_FPS)

    elapsed = time.time() - start_time
    print(f"[✓] Sent {FRAME_COUNT} frames in {elapsed:.1f}s")

    # Keep stream alive
    print(f"\n[4] Keeping stream alive for 5 seconds...")
    await asyncio.sleep(5)

    publisher.disconnect()
    print("[✓] Disconnected")

    print("\n" + "=" * 70)
    print("PUBLISH COMPLETE")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
