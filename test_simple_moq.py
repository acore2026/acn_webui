#!/usr/bin/env python3
"""
Simple MOQ Test - Send test images to existing track
"""

import asyncio
import sys
import os
from pathlib import Path

WEBUI_ROOT = Path(__file__).parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.pub.publisher import MOQPublisher, PublishedObject
from moq.encoding import FullTrackName

# Test configuration - use existing track from WebUI
RELAY_HOST = "localhost"
RELAY_PORT = 9003
TASK_ID = "task-c2a09"
AGENT_ID = "did:udid:type2.rid678.achid0.uerid1380013800032729@6gc.mnc015.mcc234.3gppnetwork.org"

# Create simple test image (1x1 pixel PNG)
TEST_IMAGE = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c49444154789c63000000010001cd05720d0000000049454e44"
    "ae426082"
)


async def main():
    """Main test function"""
    print("=" * 70)
    print("Simple MOQ Publisher Test")
    print("=" * 70)
    print(f"\nTarget: {TASK_ID}")
    print(f"Agent: {AGENT_ID}")

    print(f"\n[1] Connecting to MOQ Relay at {RELAY_HOST}:{RELAY_PORT}...")

    publisher = MOQPublisher(RELAY_HOST, RELAY_PORT)

    connected = await publisher.connect(agent_id=AGENT_ID)
    if not connected:
        print("[✗] Failed to connect to relay")
        return 1

    print("[✓] Connected to relay")

    # Create track name matching WebUI's subscription
    namespace = [TASK_ID, AGENT_ID]
    track_name = "Video"

    full_track_name = FullTrackName(
        namespace=[ns.encode() for ns in namespace],
        track_name=track_name.encode(),
    )

    print(f"\n[2] Publishing to track:")
    print(f"    Namespace: {namespace}")
    print(f"    Track name: {track_name}")
    print(f"    Full name: {full_track_name}")

    # Publish track
    success = await publisher.publish(full_track_name)
    if not success:
        print("[✗] Failed to publish track")
        return 1

    print("[✓] Track published")

    # Wait for PUBLISH_OK
    await asyncio.sleep(1)

    # Send objects
    print(f"\n[3] Sending objects...")

    for i in range(100):
        # Create object with test image
        obj = PublishedObject(
            group_id=0,
            object_id=i,
            payload=TEST_IMAGE,
            publisher_priority=128,
            subgroup_id=0,
            use_datagram=False,
        )

        await publisher.send_object(full_track_name, obj)

        if (i + 1) % 10 == 0:
            print(f"    Sent {i + 1} objects")

        await asyncio.sleep(0.1)

    print(f"[✓] Sent 100 objects")

    # Keep alive
    print(f"\n[4] Keeping stream alive for 5 seconds...")
    await asyncio.sleep(5)

    publisher.disconnect()
    print("[✓] Disconnected")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print(f"\nCheck WebUI at http://localhost:9005")
    print(f"You should see data for: {TASK_ID}")

    return 0


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
