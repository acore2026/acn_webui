#!/usr/bin/env python3
"""
MOQ video demo publisher for the WebUI.

Modes:
1. Manual demo mode:
   - publish a real ffmpeg-generated test stream
   - announce the track to the WebUI backend
   - wait for an operator to click `Watch`

2. Fuller automated test mode:
   - optionally trigger the watch request automatically
   - optionally verify that the backend starts producing MJPEG frames
   - optionally stop after a fixed duration
   - optionally unsubscribe/delete the discovered track on exit

Examples:
    # Original manual demo flow
    python3 test/moq_video_ui_demo.py

    # More complete backend-driven test
    python3 test/moq_video_ui_demo.py \
      --auto-watch \
      --wait-for-frames \
      --run-seconds 20 \
      --unsubscribe-on-exit \
      --delete-track-on-exit
"""

import argparse
import asyncio
import json
import logging
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
MOQ_ROOT = REPO_ROOT / "moq"
for candidate in (str(REPO_ROOT), str(MOQ_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from moq import MOQPublisher, FullTrackName, PublishedObject

logger = logging.getLogger(__name__)

GROUP_ID = 1
SUBGROUP_ID = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
FRAME_RATE = 30
KEYFRAME_INTERVAL = 6
INIT_REPEAT_FRAGMENT_INTERVAL = 25
CHUNK_SIZE = 512 * 1024
VIDEO_BITRATE = "2M"
PUBLISHER_STARTUP_DELAY_SECONDS = 0.5
FFMPEG_STARTUP_GRACE_PERIOD = 0.25
DEFAULT_MSE_CODEC = "avc1.64001F"
DEFAULT_MIME_TYPE = f'video/mp4; codecs="{DEFAULT_MSE_CODEC}"'
WATCH_POLL_INTERVAL_SECONDS = 1.0


def build_video_filter(include_timestamp: bool = True) -> str:
    source = f"testsrc2=size={FRAME_WIDTH}x{FRAME_HEIGHT}:rate={FRAME_RATE}"
    if not include_timestamp:
        return source

    return (
        f"{source},"
        "drawtext=expansion=strftime:text=%Y-%m-%d\\ %H\\:%M\\:%S:"
        "x=20:y=20:fontsize=36:fontcolor=white:box=1:boxcolor=0x00000099"
    )


def build_ffmpeg_command(include_timestamp: bool = True) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-re",
        "-f",
        "lavfi",
        "-i",
        build_video_filter(include_timestamp=include_timestamp),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-pix_fmt",
        "yuv420p",
        "-g",
        str(KEYFRAME_INTERVAL),
        "-keyint_min",
        str(KEYFRAME_INTERVAL),
        "-sc_threshold",
        "0",
        "-b:v",
        VIDEO_BITRATE,
        "-maxrate",
        VIDEO_BITRATE,
        "-bufsize",
        "4M",
        "-movflags",
        "+frag_keyframe+empty_moov+default_base_moof",
        "-f",
        "mp4",
        "pipe:1",
    ]


async def launch_ffmpeg_live_source() -> Optional[asyncio.subprocess.Process]:
    for include_timestamp in (True, False):
        command = build_ffmpeg_command(include_timestamp=include_timestamp)
        logger.info(
            "Launching ffmpeg test source%s",
            " with timestamp overlay" if include_timestamp else " without timestamp overlay",
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            logger.error("ffmpeg executable not found in PATH")
            return None

        await asyncio.sleep(FFMPEG_STARTUP_GRACE_PERIOD)
        if process.returncode is None:
            if not include_timestamp:
                logger.warning("Continuing without ffmpeg timestamp overlay")
            return process

        stderr = b""
        if process.stderr is not None:
            stderr = await process.stderr.read()
        stderr_text = stderr.decode("utf-8", errors="replace")

        if include_timestamp:
            logger.warning(
                "ffmpeg timestamp overlay failed with code %d; retrying without drawtext: %s",
                process.returncode,
                stderr_text,
            )
            continue

        logger.error(
            "ffmpeg exited during startup with code %d: %s",
            process.returncode,
            stderr_text,
        )
        return None

    return None


def decode_mp4_box_length(
    buffer: bytearray, offset: int = 0
) -> tuple[int, bytes, int] | None:
    if len(buffer) - offset < 8:
        return None

    size = struct.unpack_from(">I", buffer, offset)[0]
    box_type = bytes(buffer[offset + 4 : offset + 8])
    header_length = 8

    if size == 1:
        if len(buffer) - offset < 16:
            return None
        size = struct.unpack_from(">Q", buffer, offset + 8)[0]
        header_length = 16
    elif size == 0:
        return None

    if size < header_length:
        raise ValueError(f"Invalid MP4 box size {size} for box {box_type!r}")

    return size, box_type, header_length


class FragmentedMp4Muxer:
    def __init__(self):
        self._buffer = bytearray()
        self._init_parts: list[bytes] = []
        self._current_fragment_parts: list[bytes] = []
        self._saw_first_fragment = False

    def feed(self, data: bytes) -> list[tuple[str, bytes]]:
        self._buffer.extend(data)
        emitted: list[tuple[str, bytes]] = []

        while True:
            decoded = decode_mp4_box_length(self._buffer)
            if decoded is None:
                break

            box_length, box_type, _ = decoded
            if len(self._buffer) < box_length:
                break

            box = bytes(self._buffer[:box_length])
            del self._buffer[:box_length]

            if not self._saw_first_fragment:
                if box_type == b"moof":
                    self._saw_first_fragment = True
                    init_segment = b"".join(self._init_parts)
                    self._init_parts.clear()
                    if init_segment:
                        emitted.append(("init", init_segment))
                    self._current_fragment_parts = [box]
                else:
                    self._init_parts.append(box)
                continue

            if box_type == b"moof":
                if self._current_fragment_parts:
                    emitted.append(("fragment", b"".join(self._current_fragment_parts)))
                self._current_fragment_parts = [box]
                continue

            self._current_fragment_parts.append(box)

        return emitted

    def flush(self) -> list[tuple[str, bytes]]:
        emitted: list[tuple[str, bytes]] = []

        if not self._saw_first_fragment and self._init_parts:
            emitted.append(("init", b"".join(self._init_parts)))
            self._init_parts.clear()

        if self._current_fragment_parts:
            emitted.append(("fragment", b"".join(self._current_fragment_parts)))
            self._current_fragment_parts = []

        if self._buffer:
            raise ValueError(
                f"Trailing {len(self._buffer)} bytes remain after MP4 muxer flush"
            )

        return emitted


def send_subscribe_track_announcement(
    backend_url: str, agent_id: str, task_id: str, namespace: str, track_name: str
) -> None:
    payload = {
        "payload": {
            "dst_agent_id": agent_id,
            "task_id": task_id,
            "track_list": [
                {
                    "namespace": namespace,
                    "track": track_name,
                }
            ],
        }
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{backend_url}/api/acn/v3/subscribe_track",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            logger.info("WebUI subscribe_track response: %s", body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error("subscribe_track failed: HTTP %s %s", exc.code, body)
        raise
    except Exception as exc:
        logger.error("subscribe_track failed: %s", exc)
        raise


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body) if body else {}


async def wait_for_watch_request(
    backend_url: str, track_id: str, timeout_seconds: float = 300.0
) -> None:
    deadline = datetime.now(timezone.utc).timestamp() + timeout_seconds
    tracks_url = f"{backend_url}/api/moq/tracks"

    while datetime.now(timezone.utc).timestamp() < deadline:
        try:
            with urllib.request.urlopen(tracks_url, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            logger.warning("Failed to poll watch state: %s", exc)
            await asyncio.sleep(WATCH_POLL_INTERVAL_SECONDS)
            continue

        for track in payload.get("tracks", []):
            if track.get("trackId") != track_id:
                continue
            if track.get("watchState") == "subscribed":
                logger.info("Detected watch request for %s", track_id)
                return

        logger.info("Waiting for Watch on %s...", track_id)
        await asyncio.sleep(WATCH_POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"Timed out waiting for Watch on {track_id}")


def trigger_watch_request(backend_url: str, track_id: str) -> dict[str, Any]:
    encoded_track_id = urllib.parse.quote(track_id, safe="")
    response = http_json(
        f"{backend_url}/api/moq/watch/{encoded_track_id}",
        method="POST",
    )
    logger.info("Auto watch response: %s", response)
    return response


def unsubscribe_track(backend_url: str, track_id: str) -> dict[str, Any]:
    encoded_track_id = urllib.parse.quote(track_id, safe="")
    response = http_json(
        f"{backend_url}/api/moq/unsubscribe/{encoded_track_id}",
        method="POST",
    )
    logger.info("Unsubscribe response: %s", response)
    return response


def delete_track(backend_url: str, track_id: str) -> dict[str, Any]:
    encoded_track_id = urllib.parse.quote(track_id, safe="")
    response = http_json(
        f"{backend_url}/api/moq/tracks/{encoded_track_id}",
        method="DELETE",
    )
    logger.info("Delete track response: %s", response)
    return response


async def wait_for_frames(
    backend_url: str, track_id: str, timeout_seconds: float = 60.0
) -> dict[str, Any]:
    deadline = datetime.now(timezone.utc).timestamp() + timeout_seconds
    info_url = (
        f"{backend_url}/api/video/stream/"
        f"{urllib.parse.quote(track_id, safe='')}/info"
    )

    while datetime.now(timezone.utc).timestamp() < deadline:
        try:
            payload = http_json(info_url)
        except Exception as exc:
            logger.warning("Failed to poll frame state: %s", exc)
            await asyncio.sleep(WATCH_POLL_INTERVAL_SECONDS)
            continue

        if payload.get("has_frame") and int(payload.get("jpeg_sequence") or 0) > 0:
            logger.info("Detected backend video frames for %s: %s", track_id, payload)
            return payload

        logger.info(
            "Waiting for backend frames on %s... fragment_count=%s jpeg_sequence=%s",
            track_id,
            payload.get("fragment_count"),
            payload.get("jpeg_sequence"),
        )
        await asyncio.sleep(WATCH_POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"Timed out waiting for frames on {track_id}")


async def close_live_subgroup(
    publisher: MOQPublisher, track_name: FullTrackName, group_id: int, subgroup_id: int
) -> None:
    request_id = publisher._publications.get(track_name)
    if request_id is None or publisher._session is None:
        return

    publication = publisher._session.get_publication(request_id)
    if publication is None:
        return

    await publisher.close_subgroup_stream(
        publication.track_alias,
        group_id,
        subgroup_id,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish ffmpeg test video to MOQ relay 9003 and announce it to WebUI 9005."
    )
    parser.add_argument("--relay-host", default="127.0.0.1")
    parser.add_argument("--relay-port", type=int, default=9003)
    parser.add_argument("--backend-host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=9005)
    parser.add_argument("--agent-id", default="did:acn:agent:test-video")
    parser.add_argument("--task-id", default="task-video-demo")
    parser.add_argument("--track-name", default="Video")
    parser.add_argument(
        "--auto-watch",
        action="store_true",
        help="Trigger the /api/moq/watch request automatically instead of waiting for a manual click.",
    )
    parser.add_argument(
        "--watch-timeout",
        type=float,
        default=300.0,
        help="Seconds to wait for the track to enter subscribed/watch state.",
    )
    parser.add_argument(
        "--wait-for-frames",
        action="store_true",
        help="After watch begins, wait until the backend reports actual MJPEG frames.",
    )
    parser.add_argument(
        "--frame-timeout",
        type=float,
        default=60.0,
        help="Seconds to wait for backend video frames when --wait-for-frames is enabled.",
    )
    parser.add_argument(
        "--run-seconds",
        type=float,
        default=None,
        help="If set, stop streaming automatically after this many seconds.",
    )
    parser.add_argument(
        "--unsubscribe-on-exit",
        action="store_true",
        help="Call /api/moq/unsubscribe/{track_id} during cleanup.",
    )
    parser.add_argument(
        "--delete-track-on-exit",
        action="store_true",
        help="Delete the discovered track card from the WebUI during cleanup.",
    )
    args = parser.parse_args()

    backend_url = f"http://{args.backend_host}:{args.backend_port}"
    namespace = f"/{args.task_id}/{args.agent_id}"
    track_name = FullTrackName([namespace.encode()], args.track_name.encode())

    logger.info("Starting MOQ WebUI video demo publisher")
    logger.info("Relay: %s:%s", args.relay_host, args.relay_port)
    logger.info("WebUI: %s", backend_url)
    logger.info("Track namespace: %s", namespace)
    logger.info("Track name: %s", args.track_name)
    logger.info("Expected UI card id: %s_%s_%s", args.agent_id, args.task_id, args.track_name.lower())
    logger.info(
        "Stop commands: Ctrl+C in the foreground terminal, or `pkill -f \"python3 test/moq_video_ui_demo.py\"` if running in the background"
    )

    publisher = MOQPublisher(relay_host=args.relay_host, relay_port=args.relay_port)
    publisher.set_handlers(
        on_connected=lambda: logger.info("Publisher connected to relay"),
        on_disconnected=lambda: logger.info("Publisher disconnected from relay"),
        on_publication_accepted=lambda full_track_name: logger.info(
            "Publication accepted: %s", full_track_name
        ),
        on_publication_rejected=lambda full_track_name, reason: logger.warning(
            "Publication rejected: %s - %s", full_track_name, reason
        ),
    )

    if not await publisher.connect():
        logger.error("Failed to connect to relay")
        return

    ffmpeg_process: Optional[asyncio.subprocess.Process] = None
    object_id = 2
    sent_bytes = 0
    muxer = FragmentedMp4Muxer()
    cached_init_segment: Optional[bytes] = None
    fragments_since_init_repeat = 0
    track_id = f"{args.agent_id}_{args.task_id}_{args.track_name.lower()}"
    frame_wait_task: Optional[asyncio.Task] = None

    try:
        if not await publisher.publish(track_name):
            logger.error("Failed to publish track: %s", track_name)
            return

        await asyncio.sleep(PUBLISHER_STARTUP_DELAY_SECONDS)

        send_subscribe_track_announcement(
            backend_url=backend_url,
            agent_id=args.agent_id,
            task_id=args.task_id,
            namespace=namespace,
            track_name=args.track_name,
        )

        logger.info("Open http://localhost:9005 -> Agents -> Videos")
        if args.auto_watch:
            logger.info("Auto-watch enabled; triggering WebUI watch request now")
            trigger_watch_request(backend_url=backend_url, track_id=track_id)
        else:
            logger.info("You should see the track card first. Click `Watch` to subscribe and play.")

        logger.info("Waiting for the WebUI watch request before starting live publication")
        await wait_for_watch_request(
            backend_url=backend_url,
            track_id=track_id,
            timeout_seconds=args.watch_timeout,
        )

        metadata = {
            "type": "webui-live-test-stream",
            "codec": "H.264",
            "container": "fMP4",
            "mime_type": DEFAULT_MIME_TYPE,
            "mse_codec": DEFAULT_MSE_CODEC,
            "width": FRAME_WIDTH,
            "height": FRAME_HEIGHT,
            "fps": FRAME_RATE,
            "mode": "continuous",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        await publisher.send_object(
            track_name,
            PublishedObject(
                group_id=GROUP_ID,
                object_id=1,
                subgroup_id=SUBGROUP_ID,
                payload=json.dumps(metadata).encode("utf-8"),
            ),
        )
        logger.info("Sent metadata object")

        ffmpeg_process = await launch_ffmpeg_live_source()
        if ffmpeg_process is None:
            return

        async def publish_media_unit(unit_type: str, payload: bytes) -> None:
            nonlocal object_id, sent_bytes, cached_init_segment, fragments_since_init_repeat

            await publisher.send_object(
                track_name,
                PublishedObject(
                    group_id=GROUP_ID,
                    object_id=object_id,
                    subgroup_id=SUBGROUP_ID,
                    payload=payload,
                ),
            )
            sent_bytes += len(payload)
            logger.info(
                "Sent %s as object=%d (%d bytes total=%d)",
                unit_type,
                object_id,
                len(payload),
                sent_bytes,
            )
            if unit_type in {"init", "init-repeat"}:
                cached_init_segment = payload
                fragments_since_init_repeat = 0
            elif unit_type == "fragment":
                fragments_since_init_repeat += 1
            object_id += 1

        start_at = asyncio.get_running_loop().time()
        if args.wait_for_frames:
            logger.info("Will verify backend frame generation while the stream is running")
            frame_wait_task = asyncio.create_task(
                wait_for_frames(
                    backend_url=backend_url,
                    track_id=track_id,
                    timeout_seconds=args.frame_timeout,
                )
            )

        while True:
            if args.run_seconds is not None:
                elapsed = asyncio.get_running_loop().time() - start_at
                if elapsed >= args.run_seconds:
                    logger.info("Reached run-seconds=%.1f; stopping demo stream", args.run_seconds)
                    break

            try:
                chunk = await asyncio.wait_for(
                    ffmpeg_process.stdout.read(CHUNK_SIZE),
                    timeout=0.5,
                )
            except asyncio.TimeoutError:
                chunk = b""

            if not chunk:
                if ffmpeg_process.returncode is not None:
                    break
                if frame_wait_task is not None and frame_wait_task.done():
                    try:
                        frame_wait_task.result()
                    except Exception as exc:
                        logger.warning("Frame verification failed: %s", exc)
                    frame_wait_task = None
                continue

            for unit_type, payload in muxer.feed(chunk):
                if (
                    unit_type == "fragment"
                    and cached_init_segment is not None
                    and fragments_since_init_repeat >= INIT_REPEAT_FRAGMENT_INTERVAL
                ):
                    await publish_media_unit("init-repeat", cached_init_segment)
                await publish_media_unit(unit_type, payload)

            if frame_wait_task is not None and frame_wait_task.done():
                try:
                    frame_wait_task.result()
                except Exception as exc:
                    logger.warning("Frame verification failed: %s", exc)
                frame_wait_task = None

        stderr = b""
        if ffmpeg_process.stderr is not None:
            stderr = await ffmpeg_process.stderr.read()

        return_code = await ffmpeg_process.wait()
        if return_code != 0:
            logger.error(
                "ffmpeg exited with code %d: %s",
                return_code,
                stderr.decode("utf-8", errors="replace"),
            )
            return

        for unit_type, payload in muxer.flush():
            await publish_media_unit(unit_type, payload)

    except KeyboardInterrupt:
        logger.info("Stopping demo publisher")
    finally:
        if ffmpeg_process is not None and ffmpeg_process.returncode is None:
            ffmpeg_process.kill()
            await ffmpeg_process.wait()

        if frame_wait_task is not None and not frame_wait_task.done():
            frame_wait_task.cancel()
            try:
                await frame_wait_task
            except asyncio.CancelledError:
                pass

        try:
            await close_live_subgroup(publisher, track_name, GROUP_ID, SUBGROUP_ID)
        except Exception as exc:
            logger.error("Error closing subgroup stream: %s", exc)

        try:
            await publisher.unpublish(track_name, "webui video demo stopped")
        except Exception as exc:
            logger.error("Error during unpublish: %s", exc)

        if args.unsubscribe_on_exit:
            try:
                unsubscribe_track(backend_url=backend_url, track_id=track_id)
            except Exception as exc:
                logger.error("Error during track unsubscribe: %s", exc)

        if args.delete_track_on_exit:
            try:
                delete_track(backend_url=backend_url, track_id=track_id)
            except Exception as exc:
                logger.error("Error deleting discovered track: %s", exc)

        publisher.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
