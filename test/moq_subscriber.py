#!/usr/bin/env python3
"""
MOQ Video Subscriber for Testing
Subscribes to video stream and displays received data
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add webui root to path
WEBUI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.sub.subscriber import MOQSubscriber, ReceivedObject
from moq.encoding import FullTrackName

# Test configuration
RELAY_HOST = "localhost"
RELAY_PORT = 9004  # Use test relay port
TASK_ID = "test-video"
AGENT_ID = "test-publisher"


async def main():
    """Main test function"""
    print("=" * 70)
    print("MOQ Video Subscriber (Test)")
    print("=" * 70)

    subscriber = MOQSubscriber(RELAY_HOST, RELAY_PORT)

    # Statistics
    stats = {
        "objects_received": 0,
        "bytes_received": 0,
        "first_object_time": None,
        "last_object_time": None,
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
        stats["last_object_time"] = datetime.now()

        if stats["first_object_time"] is None:
            stats["first_object_time"] = datetime.now()
            print(f"\n[✓] FIRST OBJECT RECEIVED!")
            print(f"    Track alias: {obj.track_alias}")
            print(f"    Group ID: {obj.group_id}")
            print(f"    Object ID: {obj.object_id}")
            print(f"    Payload size: {len(obj.payload)} bytes")

        # Print progress every 30 objects
        if stats["objects_received"] % 30 == 0:
            print(
                f"[✓] Received {stats['objects_received']} objects "
                f"({stats['bytes_received']} bytes)"
            )

    subscriber.set_handlers(
        on_connected=on_connected,
        on_disconnected=on_disconnected,
        on_object_received=on_object_received,
        on_subscription_accepted=on_subscription_accepted,
        on_subscription_rejected=on_subscription_rejected,
    )

    # Connect
    print(f"\n[1] Connecting to relay at {RELAY_HOST}:{RELAY_PORT}...")
    connected = await subscriber.connect()
    if not connected:
        print("[✗] Failed to connect")
        return 1

    await asyncio.sleep(1)

    # Subscribe to track
    namespace = [TASK_ID, AGENT_ID]
    track_name = "Video"

    full_track_name = FullTrackName(
        namespace=[ns.encode() for ns in namespace],
        track_name=track_name.encode(),
    )

    print(f"\n[2] Subscribing to track:")
    print(f"    Namespace: {namespace}")
    print(f"    Track: {track_name}")

    await subscriber.subscribe(full_track_name)
    await asyncio.sleep(1)

    # Wait for objects
    print(f"\n[3] Waiting for objects (30 seconds)...")
    print(f"    Press Ctrl+C to stop early\n")

    try:
        await asyncio.sleep(30)
    except asyncio.CancelledError:
        pass

    # Summary
    print("\n" + "=" * 70)
    print("SUBSCRIPTION SUMMARY")
    print("=" * 70)
    print(f"Total objects received: {stats['objects_received']}")
    print(f"Total bytes received: {stats['bytes_received']}")

    if stats["first_object_time"] and stats["last_object_time"]:
        duration = (
            stats["last_object_time"] - stats["first_object_time"]
        ).total_seconds()
        if duration > 0:
            rate = stats["objects_received"] / duration
            print(f"Duration: {duration:.1f}s")
            print(f"Average rate: {rate:.1f} objects/s")

    if stats["objects_received"] > 0:
        print("\n[✓] SUCCESS! Objects are being received.")
    else:
        print("\n[✗] No objects received.")

    subscriber.disconnect()
    print("\n[4] Disconnected")

    return 0 if stats["objects_received"] > 0 else 1


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
