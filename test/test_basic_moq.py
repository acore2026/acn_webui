#!/usr/bin/env python3
"""
Basic MOQ Test - Publisher and Subscriber
"""

import asyncio
import sys
from pathlib import Path

WEBUI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.relay.relay import MOQRelay
from moq.pub.publisher import MOQPublisher, PublishedObject
from moq.sub.subscriber import MOQSubscriber, ReceivedObject
from moq.encoding import FullTrackName


async def test_basic():
    """Basic test"""
    print("=" * 70)
    print("Basic MOQ Test")
    print("=" * 70)

    # Start relay
    print("\n[1] Starting relay...")
    relay = MOQRelay("localhost", 9005)
    await relay.start()
    print("[✓] Relay started on port 9005")

    await asyncio.sleep(1)

    # Start subscriber
    print("\n[2] Starting subscriber...")
    subscriber = MOQSubscriber("localhost", 9005)

    objects_received = []

    def on_object_received(obj: ReceivedObject):
        objects_received.append(obj)
        print(f"    [Sub] Received object {obj.object_id}, {len(obj.payload)} bytes")

    subscriber.set_handlers(
        on_connected=lambda: print("    [Sub] Connected"),
        on_object_received=on_object_received,
    )

    await subscriber.connect()
    await asyncio.sleep(0.5)

    # Subscribe to track
    track_name = FullTrackName(
        namespace=[b"test", b"agent"],
        track_name=b"video",
    )
    await subscriber.subscribe(track_name)
    print("    [Sub] Subscribed")

    await asyncio.sleep(0.5)

    # Start publisher
    print("\n[3] Starting publisher...")
    publisher = MOQPublisher("localhost", 9005)

    connected = await publisher.connect(agent_id="test-pub")
    if not connected:
        print("    [Pub] Failed to connect")
        await relay.stop()
        return 1

    print("    [Pub] Connected")

    # Publish track
    success = await publisher.publish(track_name)
    if not success:
        print("    [Pub] Failed to publish")
        await relay.stop()
        return 1

    print("    [Pub] Track published")
    await asyncio.sleep(0.5)

    # Send objects
    print("\n[4] Sending 10 objects...")
    for i in range(10):
        obj = PublishedObject(
            group_id=0,
            object_id=i,
            payload=b"Hello " * 100,  # 600 bytes
            publisher_priority=128,
            subgroup_id=0,
            use_datagram=False,
        )
        await publisher.send_object(track_name, obj)
        await asyncio.sleep(0.1)

    print("    [Pub] All objects sent")

    # Wait for subscriber to receive
    await asyncio.sleep(2)

    # Cleanup
    print("\n[5] Cleaning up...")
    publisher.disconnect()
    subscriber.disconnect()
    await relay.stop()
    print("[✓] All stopped")

    # Results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Objects sent: 10")
    print(f"Objects received: {len(objects_received)}")

    if len(objects_received) > 0:
        print("\n[✓] SUCCESS!")
        return 0
    else:
        print("\n[✗] FAILED!")
        return 1


if __name__ == "__main__":
    result = asyncio.run(test_basic())
    sys.exit(result)
