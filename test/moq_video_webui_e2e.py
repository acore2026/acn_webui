#!/usr/bin/env python3
"""
End-to-end MOQ video test for the WebUI.

This script:
1. Publishes an ffmpeg-generated H.264 fMP4 test stream to the MOQ relay on port 9003
2. Announces the track to the WebUI backend with /api/acn/v3/subscribe_track
3. Opens the WebUI in a browser with playwright-cli
4. Clicks `Agents` -> `Watch` for the discovered track
5. Verifies the WebUI starts rendering the stream and saves a screenshot

Prerequisites:
- MOQ relay is already running on 127.0.0.1:9003
- WebUI backend is available on http://127.0.0.1:9005
- `ffmpeg` and `playwright-cli` are available in PATH

Example:
    python3 test/moq_video_webui_e2e.py
"""

import argparse
import asyncio
import contextlib
import json
import logging
import os
import shutil
import struct
import subprocess
import sys
import time
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

from moq import MOQPublisher, FullTrackName, PublishedObject

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
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
FFMPEG_STARTUP_GRACE_PERIOD = 0.25
DEFAULT_MSE_CODEC = "avc1.64001F"
DEFAULT_MIME_TYPE = f'video/mp4; codecs="{DEFAULT_MSE_CODEC}"'
HTTP_POLL_INTERVAL_SECONDS = 1.0


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


def http_json(url: str, *, method: str = "GET", payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body) if body else {}


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
    response = http_json(
        f"{backend_url}/api/acn/v3/subscribe_track",
        method="POST",
        payload=payload,
    )
    logger.info("WebUI subscribe_track response: %s", response)


async def poll_until(
    description: str,
    predicate,
    *,
    timeout_seconds: float,
    interval_seconds: float = HTTP_POLL_INTERVAL_SECONDS,
):
    deadline = time.monotonic() + timeout_seconds
    last_error: Optional[Exception] = None

    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except Exception as exc:
            last_error = exc
        await asyncio.sleep(interval_seconds)

    if last_error is not None:
        raise TimeoutError(f"Timed out waiting for {description}: {last_error}") from last_error
    raise TimeoutError(f"Timed out waiting for {description}")


async def wait_for_track_discovered(
    backend_url: str, track_id: str, timeout_seconds: float
) -> dict[str, Any]:
    def _predicate():
        payload = http_json(f"{backend_url}/api/moq/tracks")
        for track in payload.get("tracks", []):
            if track.get("trackId") == track_id:
                return track
        return None

    return await poll_until(
        f"track discovery for {track_id}",
        _predicate,
        timeout_seconds=timeout_seconds,
    )


async def wait_for_watch_request(
    backend_url: str, track_id: str, timeout_seconds: float
) -> dict[str, Any]:
    def _predicate():
        payload = http_json(f"{backend_url}/api/moq/tracks")
        for track in payload.get("tracks", []):
            if track.get("trackId") != track_id:
                continue
            if track.get("watchState") == "subscribed":
                return track
        return None

    return await poll_until(
        f"watch request for {track_id}",
        _predicate,
        timeout_seconds=timeout_seconds,
    )


async def wait_for_stream_frames(
    backend_url: str, track_id: str, timeout_seconds: float
) -> dict[str, Any]:
    info_url = f"{backend_url}/api/video/stream/{urllib.parse.quote(track_id, safe='')}/info"

    def _predicate():
        payload = http_json(info_url)
        if payload.get("has_frame") and int(payload.get("jpeg_sequence") or 0) > 0:
            return payload
        return None

    return await poll_until(
        f"frames for {track_id}",
        _predicate,
        timeout_seconds=timeout_seconds,
    )


def ensure_tooling() -> None:
    missing = []
    for tool_name in ("ffmpeg", "playwright-cli"):
        if shutil.which(tool_name) is None:
            missing.append(tool_name)
    if missing:
        raise RuntimeError(f"Missing required tools in PATH: {', '.join(missing)}")


def playwright_env() -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = "/tmp"
    env["XDG_CACHE_HOME"] = "/tmp"
    return env


def run_playwright(
    session_name: str,
    *args: str,
    timeout_seconds: float = 60.0,
) -> subprocess.CompletedProcess[str]:
    command = ["playwright-cli", f"-s={session_name}", *args]
    logger.info("Running browser step: %s", " ".join(command[2:]))
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=playwright_env(),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or f"exit code {result.returncode}"
        raise RuntimeError(
            f"Playwright command failed: {' '.join(command)}\n{details}\n"
            "If Chromium is not installed for playwright-cli, run:\n"
            "HOME=/tmp XDG_CACHE_HOME=/tmp playwright-cli install-browser chromium"
        )
    return result


async def browser_open_and_watch(
    *,
    session_name: str,
    ui_url: str,
    browser_name: str,
    track_name: str,
    agent_id: str,
    task_id: str,
) -> None:
    await asyncio.to_thread(
        run_playwright,
        session_name,
        "open",
        ui_url,
        f"--browser={browser_name}",
        timeout_seconds=90.0,
    )

    click_agents = """
async page => {
  const agentsButton = page.getByRole('button', { name: /Agents/i });
  await agentsButton.waitFor({ state: 'visible', timeout: 30000 });
  await agentsButton.click();
}
""".strip()
    await asyncio.to_thread(
        run_playwright,
        session_name,
        "run-code",
        click_agents,
        timeout_seconds=60.0,
    )

    click_watch = f"""
async page => {{
  const article = page
    .locator('article')
    .filter({{ hasText: {json.dumps(track_name)} }})
    .filter({{ hasText: {json.dumps(agent_id)} }})
    .filter({{ hasText: {json.dumps(task_id)} }})
    .first();

  await article.waitFor({{ state: 'visible', timeout: 120000 }});

  const watchButton = article.getByRole('button', {{ name: /Watch/i }});
  await watchButton.waitFor({{ state: 'visible', timeout: 120000 }});
  await watchButton.click();
}}
""".strip()
    await asyncio.to_thread(
        run_playwright,
        session_name,
        "run-code",
        click_watch,
        timeout_seconds=150.0,
    )


async def browser_assert_video_rendering(
    *,
    session_name: str,
    screenshot_path: Path,
) -> str:
    assert_rendered = """
async page => {
  const dialog = page.getByRole('dialog');
  await dialog.waitFor({ state: 'visible', timeout: 30000 });

  await page.waitForFunction(() => {
    const images = Array.from(
      document.querySelectorAll('[role="dialog"] .video-monitor-screen img')
    );
    return images.some((img) => (
      img instanceof HTMLImageElement &&
      img.complete &&
      img.naturalWidth > 0 &&
      img.naturalHeight > 0
    ));
  }, { timeout: 120000 });

  return JSON.stringify({
    overlay: document.querySelector('[role="dialog"] .video-monitor-overlay')?.textContent?.trim() ?? '',
    imageCount: document.querySelectorAll('[role="dialog"] .video-monitor-screen img').length
  });
}
""".strip()

    result = await asyncio.to_thread(
        run_playwright,
        session_name,
        "run-code",
        assert_rendered,
        timeout_seconds=150.0,
    )

    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(
        run_playwright,
        session_name,
        "screenshot",
        f"--filename={screenshot_path}",
        timeout_seconds=60.0,
    )
    return result.stdout.strip()


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


async def publish_video_stream(
    publisher: MOQPublisher,
    track_name: FullTrackName,
    *,
    stop_event: asyncio.Event,
) -> None:
    ffmpeg_process: Optional[asyncio.subprocess.Process] = None
    object_id = 2
    sent_bytes = 0
    muxer = FragmentedMp4Muxer()
    cached_init_segment: Optional[bytes] = None
    fragments_since_init_repeat = 0

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

    async def publish_media_unit(unit_type: str, payload: bytes) -> int:
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
        return object_id

    try:
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
        if ffmpeg_process is None or ffmpeg_process.stdout is None:
            raise RuntimeError("Unable to start ffmpeg live source")

        while not stop_event.is_set():
            chunk = await ffmpeg_process.stdout.read(CHUNK_SIZE)
            if not chunk:
                break

            for unit_type, payload in muxer.feed(chunk):
                if (
                    unit_type == "fragment"
                    and cached_init_segment is not None
                    and fragments_since_init_repeat >= INIT_REPEAT_FRAGMENT_INTERVAL
                ):
                    await publish_media_unit("init-repeat", cached_init_segment)
                await publish_media_unit(unit_type, payload)

        if ffmpeg_process.stderr is not None:
            stderr = await ffmpeg_process.stderr.read()
            if stderr:
                logger.debug("ffmpeg stderr: %s", stderr.decode("utf-8", errors="replace"))

        for unit_type, payload in muxer.flush():
            await publish_media_unit(unit_type, payload)
    finally:
        if ffmpeg_process is not None and ffmpeg_process.returncode is None:
            ffmpeg_process.kill()
            await ffmpeg_process.wait()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish ffmpeg video to MOQ relay 9003 and verify WebUI playback."
    )
    parser.add_argument("--relay-host", default="127.0.0.1")
    parser.add_argument("--relay-port", type=int, default=9003)
    parser.add_argument("--backend-host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=9005)
    parser.add_argument("--ui-url", default="http://127.0.0.1:9005")
    parser.add_argument("--browser", default="chromium")
    parser.add_argument("--track-name", default="Video")
    parser.add_argument("--agent-id")
    parser.add_argument("--task-id")
    parser.add_argument("--watch-timeout", type=float, default=120.0)
    parser.add_argument("--playback-timeout", type=float, default=120.0)
    parser.add_argument("--screenshot")
    args = parser.parse_args()

    ensure_tooling()

    unique_suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    agent_id = args.agent_id or f"test-video-agent-{unique_suffix}"
    task_id = args.task_id or f"test-video-task-{unique_suffix}"

    backend_url = f"http://{args.backend_host}:{args.backend_port}"
    namespace = f"/{task_id}/{agent_id}"
    normalized_track_name = args.track_name.lower()
    track_id = f"{agent_id}_{task_id}_{normalized_track_name}"
    session_name = f"moq-video-webui-{unique_suffix}"
    screenshot_path = Path(args.screenshot) if args.screenshot else REPO_ROOT / "logs" / f"{session_name}.png"

    logger.info("Starting MOQ WebUI video E2E test")
    logger.info("Relay: %s:%s", args.relay_host, args.relay_port)
    logger.info("Backend: %s", backend_url)
    logger.info("UI: %s", args.ui_url)
    logger.info("Track id: %s", track_id)
    logger.info("Screenshot path: %s", screenshot_path)

    try:
        tracks_payload = http_json(f"{backend_url}/api/moq/tracks")
    except Exception as exc:
        raise RuntimeError(
            f"WebUI backend is not reachable at {backend_url}: {exc}"
        ) from exc

    logger.info(
        "Backend reachable, currently reporting %d video tracks",
        len(tracks_payload.get("tracks", [])),
    )

    track_name = FullTrackName([namespace.encode()], args.track_name.encode())
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

    browser_opened = False
    stream_task: Optional[asyncio.Task] = None
    stop_event = asyncio.Event()

    try:
        if not await publisher.connect():
            raise RuntimeError("Failed to connect publisher to MOQ relay")

        if not await publisher.publish(track_name):
            raise RuntimeError(f"Failed to publish track: {track_name}")

        send_subscribe_track_announcement(
            backend_url=backend_url,
            agent_id=agent_id,
            task_id=task_id,
            namespace=namespace,
            track_name=args.track_name,
        )

        await wait_for_track_discovered(
            backend_url=backend_url,
            track_id=track_id,
            timeout_seconds=args.watch_timeout,
        )
        logger.info("Track discovered by WebUI")

        await browser_open_and_watch(
            session_name=session_name,
            ui_url=args.ui_url,
            browser_name=args.browser,
            track_name=args.track_name,
            agent_id=agent_id,
            task_id=task_id,
        )
        browser_opened = True
        logger.info("Browser clicked Watch for the discovered track")

        await wait_for_watch_request(
            backend_url=backend_url,
            track_id=track_id,
            timeout_seconds=args.watch_timeout,
        )
        logger.info("Backend watch request detected")

        stream_task = asyncio.create_task(
            publish_video_stream(
                publisher,
                track_name,
                stop_event=stop_event,
            )
        )

        stream_info = await wait_for_stream_frames(
            backend_url=backend_url,
            track_id=track_id,
            timeout_seconds=args.playback_timeout,
        )
        logger.info("Backend reports active frames: %s", stream_info)

        browser_details = await browser_assert_video_rendering(
            session_name=session_name,
            screenshot_path=screenshot_path,
        )
        logger.info("Browser rendering details: %s", browser_details)

        await asyncio.sleep(2.0)
        logger.info("SUCCESS: WebUI is rendering the MOQ video stream")
    finally:
        stop_event.set()
        if stream_task is not None:
            try:
                await asyncio.wait_for(stream_task, timeout=10.0)
            except asyncio.TimeoutError:
                stream_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await stream_task
            except Exception as exc:
                logger.warning("Publisher stream task ended with error: %s", exc)

        try:
            await close_live_subgroup(publisher, track_name, GROUP_ID, SUBGROUP_ID)
        except Exception as exc:
            logger.warning("Error closing subgroup stream: %s", exc)

        try:
            await publisher.unpublish(track_name, "webui video e2e stopped")
        except Exception as exc:
            logger.warning("Error during unpublish: %s", exc)

        publisher.disconnect()

        if browser_opened:
            try:
                await asyncio.to_thread(
                    run_playwright,
                    session_name,
                    "close",
                    timeout_seconds=30.0,
                )
            except Exception as exc:
                logger.warning("Error closing browser session: %s", exc)


if __name__ == "__main__":
    asyncio.run(main())
