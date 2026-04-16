#!/usr/bin/env python3
"""
MOQ Integration Test for WebUI
Tests the complete pipeline: Relay -> Publisher -> Backend Subscriber
"""

import asyncio
import sys
import os
import subprocess
import time
from pathlib import Path

# Add webui root to path
WEBUI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.relay.relay import MOQRelay
from moq.pub.publisher import MOQPublisher, PublishedObject
from moq.sub.subscriber import MOQSubscriber, ReceivedObject
from moq.encoding import FullTrackName

# Test configuration
RELAY_HOST = "localhost"
RELAY_PORT = 9004
TASK_ID = "test-integration"
AGENT_ID = "test-agent"

# Test data
TEST_FRAMES = []


def generate_test_frames():
    """Generate test frames"""
    frames = []
    for i in range(30):  # 1 second at 30fps
        # Simple frame data with pattern
        frame_data = bytes([i % 256] * 1000)  # 1KB per frame
        frames.append(frame_data)
    return frames


async def run_relay():
    """Run MOQ Relay"""
    relay = MOQRelay(RELAY_HOST, RELAY_PORT)
    await relay.start()
    print(f"[Relay] Started on {RELAY_HOST}:{RELAY_PORT}")
    return relay


async def run_publisher():
    """Run MOQ Publisher"""
    print("[Publisher] Connecting...")
    publisher = MOQPublisher(RELAY_HOST, RELAY_PORT)

    connected = await publisher.connect(agent_id=AGENT_ID)
    if not connected:
        print("[Publisher] Failed to connect")
        return None

    print("[Publisher] Connected")

    # Create track
    namespace = [TASK_ID, AGENT_ID]
    track_name = "Video"

    full_track_name = FullTrackName(
        namespace=[ns.encode() for ns in namespace],
        track_name=track_name.encode(),
    )

    # Publish track
    success = await publisher.publish(full_track_name)
    if not success:
        print("[Publisher] Failed to publish")
        return None

    print("[Publisher] Track published")
    await asyncio.sleep(0.5)

    # Send frames
    frames = generate_test_frames()
    print(f"[Publisher] Sending {len(frames)} frames...")

    for i, frame_data in enumerate(frames):
        obj = PublishedObject(
            group_id=0,
            object_id=i,
            payload=frame_data,
            publisher_priority=128,
            subgroup_id=0,
            use_datagram=False,
        )
        await publisher.send_object(full_track_name, obj)
        await asyncio.sleep(1.0 / 30)  # 30fps

    print("[Publisher] All frames sent")

    # Keep alive
    await asyncio.sleep(2)
    publisher.disconnect()
    print("[Publisher] Disconnected")
    return True


async def run_subscriber():
    """Run MOQ Subscriber"""
    print("[Subscriber] Connecting...")
    subscriber = MOQSubscriber(RELAY_HOST, RELAY_PORT)

    # Stats
    objects_received = 0
    bytes_received = 0
    first_object = None

    def on_connected():
        print("[Subscriber] Connected")

    def on_object_received(obj: ReceivedObject):
        nonlocal objects_received, bytes_received, first_object
        objects_received += 1
        bytes_received += len(obj.payload)
        if first_object is None:
            first_object = obj

    subscriber.set_handlers(
        on_connected=on_connected,
        on_object_received=on_object_received,
    )

    connected = await subscriber.connect()
    if not connected:
        print("[Subscriber] Failed to connect")
        return 0, 0

    await asyncio.sleep(0.5)

    # Subscribe
    namespace = [TASK_ID, AGENT_ID]
    track_name = "Video"

    full_track_name = FullTrackName(
        namespace=[ns.encode() for ns in namespace],
        track_name=track_name.encode(),
    )

    await subscriber.subscribe(full_track_name)
    print("[Subscriber] Subscribed")

    # Wait for objects
    await asyncio.sleep(5)

    subscriber.disconnect()
    print("[Subscriber] Disconnected")

    return objects_received, bytes_received


async def main():
    """Main test function"""
    print("=" * 70)
    print("MOQ Integration Test")
    print("=" * 70)
    print()

    # Step 1: Start relay
    print("[Step 1] Starting relay...")
    relay = await run_relay()
    await asyncio.sleep(1)

    # Step 2: Start subscriber
    print("\n[Step 2] Starting subscriber...")
    subscriber_task = asyncio.create_task(run_subscriber())
    await asyncio.sleep(1)

    # Step 3: Start publisher
    print("\n[Step 3] Starting publisher...")
    publisher_task = asyncio.create_task(run_publisher())

    # Wait for completion
    await publisher_task
    objects_received, bytes_received = await subscriber_task

    # Stop relay
    print("\n[Step 4] Stopping relay...")
    await relay.stop()

    # Results
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    print(f"Objects sent: 30")
    print(f"Objects received: {objects_received}")
    print(f"Bytes received: {bytes_received}")

    if objects_received > 0:
        print("\n[✓] SUCCESS! Pipeline is working.")
        return 0
    else:
        print("\n[✗] FAILED! No objects received.")
        return 1


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
