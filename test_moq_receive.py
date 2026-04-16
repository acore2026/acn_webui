#!/usr/bin/env python3
"""
Test MOQ Object Reception with Incremental Parsing
"""

import asyncio
import sys
import os

WEBUI_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WEBUI_ROOT)

from moq.sub.subscriber import MOQSubscriber, ReceivedObject
from moq.encoding import FullTrackName


async def test_moq_reception():
    """Test if MOQ subscriber receives objects"""
    print("=" * 70)
    print("MOQ Object Reception Test")
    print("=" * 70)

    subscriber = MOQSubscriber("localhost", 9003)

    stats = {
        "objects_received": 0,
        "bytes_received": 0,
        "first_object_time": None,
    }

    def on_connected():
        print("[✓] Connected to MOQ Relay")

    def on_disconnected():
        print("[✗] Disconnected from MOQ Relay")

    def on_subscription_accepted(track_name):
        print(f"[✓] Subscription accepted: {track_name}")

    def on_subscription_rejected(track_name, reason):
        print(f"[✗] Subscription rejected: {track_name} - {reason}")

    def on_object_received(obj: ReceivedObject):
        stats["objects_received"] += 1
        stats["bytes_received"] += len(obj.payload)
        if stats["first_object_time"] is None:
            stats["first_object_time"] = asyncio.get_event_loop().time()
            print(f"\n[✓] FIRST OBJECT RECEIVED!")
            print(f"    Track alias: {obj.track_alias}")
            print(f"    Group ID: {obj.group_id}")
            print(f"    Object ID: {obj.object_id}")
            print(f"    Payload size: {len(obj.payload)} bytes")
            print(f"    Payload preview: {obj.payload[:20].hex()}")

        # Print progress every 10 objects
        if stats["objects_received"] % 10 == 0:
            elapsed = asyncio.get_event_loop().time() - stats["first_object_time"]
            print(
                f"[✓] Received {stats['objects_received']} objects "
                f"({stats['bytes_received']} bytes) in {elapsed:.1f}s"
            )

    subscriber.set_handlers(
        on_connected=on_connected,
        on_disconnected=on_disconnected,
        on_object_received=on_object_received,
        on_subscription_accepted=on_subscription_accepted,
        on_subscription_rejected=on_subscription_rejected,
    )

    # Connect
    print("\n[1] Connecting to MOQ Relay...")
    connected = await subscriber.connect()
    if not connected:
        print("[✗] Failed to connect")
        return False

    await asyncio.sleep(1)

    # Get current subscriptions and subscribe to them
    print("\n[2] Subscribing to active tracks...")
    import subprocess
    import json

    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:9005/api/moq/status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        status = json.loads(result.stdout)

        for track_info in status.get("subscription_debug", []):
            track_id = track_info["track_id"]
            namespace = track_info["namespace"]
            track_name = track_info["track_name"]

            print(f"\n    Subscribing to: {track_id}")

            full_track_name = FullTrackName(
                namespace=[ns.encode() for ns in namespace],
                track_name=track_name.encode(),
            )

            await subscriber.subscribe(full_track_name)

    except Exception as e:
        print(f"    [✗] Failed: {e}")

    # Wait for objects
    print("\n[3] Waiting for objects (20 seconds)...")
    print("    (Press Ctrl+C to stop early)\n")

    try:
        await asyncio.sleep(20)
    except asyncio.CancelledError:
        pass

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total objects received: {stats['objects_received']}")
    print(f"Total bytes received: {stats['bytes_received']}")

    if stats["objects_received"] > 0:
        print("\n[✓] SUCCESS! Objects are being received.")
    else:
        print("\n[✗] FAILED! No objects received.")
        print("\nPossible issues:")
        print("  1. Publisher is not sending objects")
        print("  2. Namespace/track name mismatch")
        print("  3. Stream parsing error")

    subscriber.disconnect()
    print("\n[4] Disconnected")

    return stats["objects_received"] > 0


if __name__ == "__main__":
    result = asyncio.run(test_moq_reception())
    sys.exit(0 if result else 1)
