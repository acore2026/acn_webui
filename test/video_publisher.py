#!/usr/bin/env python3
"""
FFmpeg Video Publisher for MOQ

Supports two publishing modes:
1. Generate a real-time test stream with FFmpeg testsrc.
2. Publish frames transcoded from a local MP4 file such as ./test_video.mp4.
"""

import asyncio
import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add webui to path
WEBUI_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WEBUI_ROOT))

from moq.pub.publisher import MOQPublisher, PublishedObject
from moq.encoding import FullTrackName

# Configuration
RELAY_HOST = "localhost"
RELAY_PORT = 9003
TASK_ID = "test-ffmpeg-video"
AGENT_ID = "ffmpeg-publisher"

# Video settings
VIDEO_FPS = 30
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 360
VIDEO_DURATION = 60  # seconds
DEFAULT_INPUT_FILE = "test_video.mp4"


class FFmpegVideoPublisher:
    """FFmpeg video publisher"""

    def __init__(self, source_mode="generated", input_file=None):
        self.running = False
        self.publisher = None
        self.source_mode = source_mode
        self.input_file = input_file

    async def generate_and_publish(self):
        """Generate video with FFmpeg and publish via MOQ"""
        print("=" * 70)
        print("FFmpeg Video Publisher for MOQ")
        print("=" * 70)

        with tempfile.TemporaryDirectory(prefix="moq_video_") as temp_dir:
            video_path = os.path.join(temp_dir, "test.h264")

            # Step 1: Prepare video with FFmpeg
            print("\n[1] Preparing video with FFmpeg...")
            print(f"    Resolution: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
            print(f"    FPS: {VIDEO_FPS}")

            success = await self._prepare_video(video_path)
            if not success:
                print("[✗] FFmpeg failed")
                return False

            # Step 2: Split into NAL units
            print("\n[2] Splitting video into NAL units...")
            frames = await self._split_h264_frames(video_path)
            print(f"    Total frames: {len(frames)}")

            # Step 3: Connect to MOQ
            print(f"\n[3] Connecting to MOQ at {RELAY_HOST}:{RELAY_PORT}...")
            self.publisher = MOQPublisher(RELAY_HOST, RELAY_PORT)

            try:
                connected = await self.publisher.connect(agent_id=AGENT_ID)
                if not connected:
                    print("[✗] Failed to connect")
                    return False
                print("[✓] Connected")

                # Step 4: Publish track
                print("\n[4] Publishing track...")
                namespace = [TASK_ID, AGENT_ID]
                track_name = "Video"

                full_track_name = FullTrackName(
                    namespace=[ns.encode() for ns in namespace],
                    track_name=track_name.encode(),
                )

                success = await self.publisher.publish(full_track_name)
                if not success:
                    print("[✗] Failed to publish")
                    return False
                print("[✓] Track published")

                await asyncio.sleep(1)

                # Step 5: Publish frames
                print(f"\n[5] Publishing {len(frames)} frames...")
                self.running = True

                for i, frame_data in enumerate(frames):
                    if not self.running:
                        break

                    obj = PublishedObject(
                        group_id=0,
                        object_id=i,
                        payload=frame_data,
                        publisher_priority=128,
                        subgroup_id=0,
                        use_datagram=False,
                    )

                    await self.publisher.send_object(full_track_name, obj)

                    if (i + 1) % 30 == 0:
                        print(f"    Published {i + 1}/{len(frames)} frames")

                    await asyncio.sleep(1.0 / VIDEO_FPS)

                print("[✓] Published all frames")

                # Keep alive
                print("\n[6] Keeping stream alive...")
                while self.running:
                    await asyncio.sleep(1)

                return True

            finally:
                if self.publisher:
                    self.publisher.disconnect()

    async def _prepare_video(self, output_path):
        """Prepare the source video as raw H.264 elementary stream."""
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            print("    [✗] ffmpeg not found in PATH")
            print("    On Windows, add ffmpeg\\bin to PATH or use a full ffmpeg.exe path.")
            return False

        if self.source_mode == "file":
            input_path = self._resolve_input_file()
            if not input_path.exists():
                print(f"    [✗] Input video not found: {input_path}")
                return False
            print(f"    Source: file ({input_path})")
            return await self._transcode_video_file(ffmpeg_path, input_path, output_path)

        print("    Source: generated testsrc")
        print(f"    Duration: {VIDEO_DURATION}s")
        return await self._generate_video(ffmpeg_path, output_path)

    def _resolve_input_file(self):
        """Resolve the input MP4 path from the current working directory."""
        if self.input_file:
            input_path = Path(self.input_file)
        else:
            input_path = Path.cwd() / DEFAULT_INPUT_FILE

        if not input_path.is_absolute():
            input_path = Path.cwd() / input_path
        return input_path.resolve()

    async def _run_ffmpeg(self, cmd, timeout):
        """Run FFmpeg and report compact diagnostics."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except FileNotFoundError:
            print("    [✗] ffmpeg executable was not found")
            return False
        except Exception as e:
            print(f"    [✗] Error: {e}")
            return False

        if proc.returncode == 0:
            return True

        error_text = stderr.decode(errors="ignore")[-500:]
        print(f"    [✗] FFmpeg error: {error_text}")
        return False

    async def _generate_video(self, ffmpeg_path, output_path):
        """Generate H.264 video with FFmpeg"""
        cmd = [
            ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={VIDEO_DURATION}:size={VIDEO_WIDTH}x{VIDEO_HEIGHT}:rate={VIDEO_FPS}",
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
            "500k",
            "-g",
            str(VIDEO_FPS),
            "-keyint_min",
            str(VIDEO_FPS),
            "-sc_threshold",
            "0",
            "-f",
            "h264",
            output_path,
        ]

        success = await self._run_ffmpeg(cmd, timeout=120)
        if success:
            size = os.path.getsize(output_path)
            print(f"    [✓] Video generated: {size} bytes")
        return success

    async def _transcode_video_file(self, ffmpeg_path, input_path, output_path):
        """Transcode a local MP4 file into H.264 elementary stream."""
        cmd = [
            ffmpeg_path,
            "-y",
            "-i",
            str(input_path),
            "-an",
            "-vf",
            f"fps={VIDEO_FPS},scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}",
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
            "500k",
            "-g",
            str(VIDEO_FPS),
            "-keyint_min",
            str(VIDEO_FPS),
            "-sc_threshold",
            "0",
            "-f",
            "h264",
            output_path,
        ]

        success = await self._run_ffmpeg(cmd, timeout=300)
        if success:
            size = os.path.getsize(output_path)
            print(f"    [✓] Video transcoded: {size} bytes")
        return success

    async def _split_h264_frames(self, video_path):
        """Split H.264 file into NAL units."""
        with open(video_path, "rb") as f:
            data = f.read()

        frames = []
        start_code_4 = b"\x00\x00\x00\x01"
        start_code_3 = b"\x00\x00\x01"

        i = 0
        frame_start = 0

        while i < len(data) - 4:
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

        if frame_start < len(data):
            frames.append(data[frame_start:])

        return [frame for frame in frames if len(frame) > 10]

    def stop(self):
        self.running = False
        if self.publisher:
            self.publisher.disconnect()


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Publish H.264 video frames over MOQ.")
    parser.add_argument(
        "--source",
        choices=("generated", "file"),
        default="generated",
        help="generated: use FFmpeg testsrc, file: publish frames from a local MP4 file",
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT_FILE,
        help=f"MP4 file path used with --source file. Default: ./{DEFAULT_INPUT_FILE}",
    )
    return parser.parse_args(argv)


async def main(argv=None):
    args = parse_args(argv)
    input_file = args.input if args.source == "file" else None
    publisher = FFmpegVideoPublisher(source_mode=args.source, input_file=input_file)

    try:
        await publisher.generate_and_publish()
    except KeyboardInterrupt:
        print("\n\nStopping...")
        publisher.stop()


if __name__ == "__main__":
    asyncio.run(main())
