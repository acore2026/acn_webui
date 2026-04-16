#!/usr/bin/env python3
"""
MOQ Video Stream Diagnostic Script
Check if MOQ subscriber is receiving objects from relay
"""

import asyncio
import sys
import os

# Add webui root to path
WEBUI_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WEBUI_ROOT)

from moq.sub.subscriber import MOQSubscriber, ReceivedObject
from moq.encoding import FullTrackName

# Test track configuration
TEST_TRACK_NAMESPACE = ["task-test", "agent-test"]
TEST_TRACK_NAME = "Video"


async def test_moq_subscription():
    """Test if MOQ subscriber can receive objects"""
    print("=" * 60)
    print("MOQ Video Stream Diagnostic")
    print("=" * 60)

    # Create subscriber
    subscriber = MOQSubscriber("localhost", 9003)

    # Set up handlers with detailed logging
    received_objects = []

    def on_connected():
        print("[✓] Connected to MOQ Relay")

    def on_disconnected():
        print("[✗] Disconnected from MOQ Relay")

    def on_subscription_accepted(track_name):
        print(f"[✓] Subscription accepted: {track_name}")

    def on_subscription_rejected(track_name, reason):
        print(f"[✗] Subscription rejected: {track_name} - {reason}")

    def on_object_received(obj: ReceivedObject):
        print(
            f"[✓] Object received: track_alias={obj.track_alias}, "
            f"group_id={obj.group_id}, object_id={obj.object_id}, "
            f"payload_size={len(obj.payload)}"
        )
        received_objects.append(obj)

    subscriber.set_handlers(
        on_connected=on_connected,
        on_disconnected=on_disconnected,
        on_object_received=on_object_received,
        on_subscription_accepted=on_subscription_accepted,
        on_subscription_rejected=on_subscription_rejected,
    )

    # Connect to relay
    print("\n[1] Connecting to MOQ Relay at localhost:9003...")
    connected = await subscriber.connect()

    if not connected:
        print("[✗] Failed to connect to relay")
        return False

    # Wait for connection to be established
    await asyncio.sleep(1)

    # Check current subscriptions from backend
    print("\n[2] Checking current subscriptions...")
    # Note: This would require importing the backend module
    # For now, we'll just test the connection

    # Subscribe to a test track (if it exists)
    print(f"\n[3] Subscribing to test track...")
    print(f"    Namespace: {TEST_TRACK_NAMESPACE}")
    print(f"    Track name: {TEST_TRACK_NAME}")

    full_track_name = FullTrackName(
        namespace=[ns.encode() for ns in TEST_TRACK_NAMESPACE],
        track_name=TEST_TRACK_NAME.encode(),
    )

    success = await subscriber.subscribe(full_track_name)
    print(f"    Subscribe request sent: {success}")

    # Wait for subscription response
    await asyncio.sleep(2)

    print("\n[4] Waiting for objects (10 seconds)...")
    await asyncio.sleep(10)

    print(f"\n[5] Results:")
    print(f"    Total objects received: {len(received_objects)}")

    if received_objects:
        print(f"\n    First object details:")
        obj = received_objects[0]
        print(f"      - Track alias: {obj.track_alias}")
        print(f"      - Group ID: {obj.group_id}")
        print(f"      - Object ID: {obj.object_id}")
        print(f"      - Payload size: {len(obj.payload)} bytes")
        print(f"      - Payload preview: {obj.payload[:20].hex()}")
    else:
        print(f"\n    [!] No objects received")
        print(f"\n    Possible reasons:")
        print(f"      1. Publisher is not sending objects to this track")
        print(f"      2. Relay is not forwarding objects")
        print(f"      3. Namespace/track name mismatch")
        print(f"      4. Subscription filter is not matching published objects")

    # Disconnect
    subscriber.disconnect()
    print("\n[6] Disconnected")

    return len(received_objects) > 0


if __name__ == "__main__":
    result = asyncio.run(test_moq_subscription())
    sys.exit(0 if result else 1)
