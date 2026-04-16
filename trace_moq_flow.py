#!/usr/bin/env python3
"""
MOQ Data Flow Tracer
Trace where objects are being lost in the MOQ pipeline
"""

import asyncio
import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Add webui root to path
WEBUI_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WEBUI_ROOT)

from moq.sub.subscriber import MOQSubscriber, ReceivedObject
from moq.encoding import FullTrackName


async def trace_moq_flow():
    """Trace MOQ data flow"""
    print("=" * 70)
    print("MOQ Data Flow Tracer")
    print("=" * 70)

    # Create subscriber with full debugging
    subscriber = MOQSubscriber("localhost", 9003)

    events_log = []

    def log_event(event_type, details):
        msg = f"[{event_type}] {details}"
        events_log.append(msg)
        print(msg)

    def on_connected():
        log_event("CONNECTION", "Connected to MOQ Relay")

    def on_disconnected():
        log_event("CONNECTION", "Disconnected from MOQ Relay")

    def on_subscription_accepted(track_name):
        log_event("SUBSCRIPTION", f"Accepted: {track_name}")

    def on_subscription_rejected(track_name, reason):
        log_event("SUBSCRIPTION", f"Rejected: {track_name} - {reason}")

    def on_object_received(obj: ReceivedObject):
        log_event(
            "OBJECT",
            f"Received: track_alias={obj.track_alias}, "
            f"group_id={obj.group_id}, object_id={obj.object_id}, "
            f"payload_size={len(obj.payload)}",
        )

    # Patch the subscriber to trace all internal events
    original_handle_stream_data = subscriber._handle_stream_data
    original_handle_datagram = subscriber._handle_datagram
    original_handle_subgroup_stream = subscriber._handle_subgroup_stream

    async def patched_handle_stream_data(protocol, data):
        log_event(
            "STREAM",
            f"stream_id={data.stream_id}, "
            f"data_len={len(data.data)}, end_stream={data.end_stream}",
        )
        await original_handle_stream_data(protocol, data)

    async def patched_handle_datagram(protocol, data):
        log_event("DATAGRAM", f"data_len={len(data.data)}")
        await original_handle_datagram(protocol, data)

    async def patched_handle_subgroup_stream(stream_id, data, offset):
        log_event(
            "SUBGROUP", f"stream_id={stream_id}, data_len={len(data)}, offset={offset}"
        )
        await original_handle_subgroup_stream(stream_id, data, offset)

    subscriber._handle_stream_data = patched_handle_stream_data
    subscriber._handle_datagram = patched_handle_datagram
    subscriber._handle_subgroup_stream = patched_handle_subgroup_stream

    subscriber.set_handlers(
        on_connected=on_connected,
        on_disconnected=on_disconnected,
        on_object_received=on_object_received,
        on_subscription_accepted=on_subscription_accepted,
        on_subscription_rejected=on_subscription_rejected,
    )

    # Connect to relay
    print("\n[1] Connecting to MOQ Relay...")
    connected = await subscriber.connect()

    if not connected:
        print("[✗] Failed to connect to relay")
        return False

    await asyncio.sleep(1)

    # Get currently active subscriptions from backend API
    print("\n[2] Checking active subscriptions from backend...")
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

        print(f"    Connected: {status.get('connected')}")
        print(f"    Subscribed tracks: {status.get('subscribed_tracks', [])}")

        # Subscribe to existing tracks
        for track_info in status.get("subscription_debug", []):
            track_id = track_info["track_id"]
            namespace = track_info["namespace"]
            track_name = track_info["track_name"]

            print(f"\n    [3] Subscribing to: {track_id}")
            print(f"        Namespace: {namespace}")
            print(f"        Track name: {track_name}")

            full_track_name = FullTrackName(
                namespace=[ns.encode() for ns in namespace],
                track_name=track_name.encode(),
            )

            success = await subscriber.subscribe(full_track_name)
            print(f"        Subscribe result: {success}")

    except Exception as e:
        print(f"    [✗] Failed to get status: {e}")

    # Wait for objects
    print("\n[4] Waiting for objects (15 seconds)...")
    await asyncio.sleep(15)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    object_events = [e for e in events_log if "[OBJECT]" in e]
    stream_events = [e for e in events_log if "[STREAM]" in e]
    datagram_events = [e for e in events_log if "[DATAGRAM]" in e]
    subgroup_events = [e for e in events_log if "[SUBGROUP]" in e]

    print(f"Total events logged: {len(events_log)}")
    print(f"  - Stream events: {len(stream_events)}")
    print(f"  - Datagram events: {len(datagram_events)}")
    print(f"  - Subgroup events: {len(subgroup_events)}")
    print(f"  - Object events: {len(object_events)}")

    if not object_events:
        print("\n[!] No objects received!")
        print("\nPossible issues:")
        print("  1. Publisher is not publishing to the subscribed tracks")
        print("  2. Relay is not forwarding to this subscriber")
        print("  3. Data is being sent on streams but not parsed correctly")
        print("  4. Subscription filter is not matching")

    subscriber.disconnect()
    print("\n[5] Disconnected")


if __name__ == "__main__":
    asyncio.run(trace_moq_flow())
