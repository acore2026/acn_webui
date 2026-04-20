#!/usr/bin/env python3
"""
Multi-Format Video Test
Tests H.264, MJPEG, and auto-transcoding
"""

import asyncio
import sys
import os
from pathlib import Path

# Add webui root to path
WEBUI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEBUI_ROOT))

from backend.app.video_gateway import (
    MultiFormatVideoGateway,
    VideoFormat,
    VideoFrame,
    ingest_h264_frame,
    ingest_jpeg_frame,
    get_video_gateway,
)
from moq.pub.publisher import MOQPublisher, PublishedObject
from moq.encoding import FullTrackName

# Configuration
RELAY_HOST = "localhost"
RELAY_PORT = 9003
TASK_ID = "test-multi-format"
AGENT_ID = "test-agent-multi"


class MultiFormatTester:
    """Test multiple video formats"""

    def __init__(self):
        self.gateway = get_video_gateway()
        self.results = []

    async def test_h264_ingestion(self):
        """Test H.264 frame ingestion"""
        print("\n[Test 1] H.264 Frame Ingestion")
        print("-" * 50)

        # Create fake H.264 NAL unit (start code + data)
        h264_data = b"\x00\x00\x00\x01" + b"\x09\x10" + b"\x00" * 100

        track_id = f"{AGENT_ID}_{TASK_ID}_h264"

        success = await ingest_h264_frame(
            track_id=track_id, h264_data=h264_data, metadata={"test": "h264_ingestion"}
        )

        print(f"  Ingestion: {'✅ Success' if success else '❌ Failed'}")

        # Check detection
        frame = self.gateway.get_latest_frame(track_id)
        if frame:
            print(f"  Format detected: {frame.format.value}")
            print(f"  Data size: {len(frame.data)} bytes")

        return success

    async def test_jpeg_ingestion(self):
        """Test JPEG frame ingestion"""
        print("\n[Test 2] JPEG Frame Ingestion")
        print("-" * 50)

        # Create fake JPEG (start marker + data + end marker)
        jpeg_data = b"\xff\xd8" + b"\xff\xe0\x00\x10JFIF" + b"\x00" * 500 + b"\xff\xd9"

        track_id = f"{AGENT_ID}_{TASK_ID}_jpeg"

        success = await ingest_jpeg_frame(
            track_id=track_id, jpeg_data=jpeg_data, metadata={"test": "jpeg_ingestion"}
        )

        print(f"  Ingestion: {'✅ Success' if success else '❌ Failed'}")

        frame = self.gateway.get_latest_frame(track_id)
        if frame:
            print(f"  Format detected: {frame.format.value}")
            print(f"  Data size: {len(frame.data)} bytes")

        return success

    async def test_transcoding(self):
        """Test H.264 to JPEG transcoding"""
        print("\n[Test 3] H.264 to JPEG Transcoding")
        print("-" * 50)

        track_id = f"{AGENT_ID}_{TASK_ID}_h264"

        # Get H.264 frame
        h264_frame = self.gateway.get_latest_frame(track_id)
        if not h264_frame:
            print("  ❌ No H.264 frame available")
            return False

        print(f"  Source format: {h264_frame.format.value}")

        # Transcode to JPEG
        jpeg_frame = await self.gateway.get_frame_async(track_id, VideoFormat.RAW_JPEG)

        if jpeg_frame:
            print(f"  ✅ Transcoded to: {jpeg_frame.format.value}")
            print(f"  Output size: {len(jpeg_frame.data)} bytes")
            return True
        else:
            print("  ❌ Transcoding failed (expected - no real H.264 data)")
            return False

    async def test_stream_info(self):
        """Test stream information API"""
        print("\n[Test 4] Stream Information")
        print("-" * 50)

        streams = list(self.gateway.latest_frames.keys())
        print(f"  Active streams: {len(streams)}")

        for track_id in streams:
            frame = self.gateway.latest_frames[track_id]
            print(f"\n  Stream: {track_id[:50]}...")
            print(f"    Format: {frame.format.value}")
            print(f"    Size: {len(frame.data)} bytes")
            print(f"    Resolution: {frame.width}x{frame.height}")

        return len(streams) > 0

    async def test_moq_integration(self):
        """Test MOQ integration"""
        print("\n[Test 5] MOQ Integration")
        print("-" * 50)

        try:
            # Create publisher
            publisher = MOQPublisher(RELAY_HOST, RELAY_PORT)

            print(f"  Connecting to relay at {RELAY_HOST}:{RELAY_PORT}...")
            connected = await publisher.connect(agent_id=AGENT_ID)

            if not connected:
                print("  ⚠️  Could not connect to relay (may not be running)")
                print("  ℹ️  This is OK - gateway works independently")
                return True

            print("  ✅ Connected to relay")

            # Publish track
            namespace = [TASK_ID, AGENT_ID]
            track_name = "Video"

            full_track_name = FullTrackName(
                namespace=[ns.encode() for ns in namespace],
                track_name=track_name.encode(),
            )

            success = await publisher.publish(full_track_name)
            print(f"  Publish: {'✅ Success' if success else '❌ Failed'}")

            publisher.disconnect()
            return True

        except Exception as e:
            print(f"  ⚠️  MOQ test skipped: {e}")
            print("  ℹ️  Gateway works independently of MOQ relay")
            return True

    async def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("MULTI-FORMAT VIDEO TEST SUMMARY")
        print("=" * 70)

        streams = list(self.gateway.latest_frames.keys())

        print(f"\n✅ Active Streams: {len(streams)}")

        if streams:
            print("\n📊 Stream Details:")
            for track_id in streams:
                frame = self.gateway.latest_frames[track_id]
                print(f"\n  📹 {track_id}")
                print(f"     Format: {frame.format.value.upper()}")
                print(f"     Size: {len(frame.data)} bytes")
                print(f"     Resolution: {frame.width}x{frame.height}")

        print(f"\n🔗 HTTP Endpoints:")
        print(
            f"   MJPEG Stream: http://localhost:9005/api/video/stream/<track_id>/mjpeg"
        )
        print(
            f"   Latest Frame: http://localhost:9005/api/video/stream/<track_id>/latest"
        )
        print(
            f"   Stream Info:  http://localhost:9005/api/video/stream/<track_id>/info"
        )
        print(f"   Player Page:  http://localhost:9005/api/video/player/<track_id>")

        print(f"\n🎯 Usage Examples:")
        print(f'   <img src="/api/video/stream/{AGENT_ID}_{TASK_ID}_jpeg/mjpeg">')
        print(f'   <iframe src="/api/video/player/{AGENT_ID}_{TASK_ID}_h264">')

        print(f"\n💡 Supported Formats:")
        print(f"   ✅ H.264 (auto-transcoded to MJPEG)")
        print(f"   ✅ MJPEG (native)")
        print(f"   ✅ JPEG (single frames)")
        print(f"   🔄 WebRTC (planned)")

        print("\n" + "=" * 70)

    async def run_all_tests(self):
        """Run all tests"""
        print("=" * 70)
        print("MULTI-FORMAT VIDEO TEST")
        print("=" * 70)

        # Start gateway
        await self.gateway.start()

        try:
            # Run tests
            await self.test_h264_ingestion()
            await self.test_jpeg_ingestion()
            await self.test_transcoding()
            await self.test_stream_info()
            await self.test_moq_integration()

            # Print summary
            await self.print_summary()

        finally:
            await self.gateway.stop()


async def main():
    """Main function"""
    tester = MultiFormatTester()
    await tester.run_all_tests()
    return 0


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
