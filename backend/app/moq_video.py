#!/usr/bin/env python3
"""
MOQ video track registry and browser playback bridge.

This module matches the newer MOQ demo flow:
- track discovery is separated from actual subscription
- subscribed video objects are treated as metadata + init segment + fMP4 fragments
- browser playback uses WebTransport + MediaSource
"""

import asyncio
import base64
import contextlib
import hashlib
import inspect
import json
import logging
import ipaddress
import tempfile
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.utils import formatdate
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote, unquote

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import (
    DatagramReceived,
    H3Event,
    HeadersReceived,
    WebTransportStreamDataReceived,
)
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import ConnectionTerminated, ProtocolNegotiated, QuicEvent
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

import sys
import os

WEBUI_ROOT = "/root/lpx/webui"
MOQ_PATH = os.path.join(WEBUI_ROOT, "moq")

original_path = sys.path.copy()
sys.path = []
sys.path.insert(0, WEBUI_ROOT)
sys.path.insert(0, MOQ_PATH)

for path_item in original_path:
    if "moq" in path_item.lower() and not path_item.startswith(WEBUI_ROOT):
        continue
    if path_item not in sys.path:
        sys.path.append(path_item)

os.environ["PYTHONPATH"] = WEBUI_ROOT + ":" + os.environ.get("PYTHONPATH", "")

import moq

moq_module_path = getattr(moq, "__file__", None) or ""
if moq_module_path and "/root/lpx/webui/moq" not in moq_module_path:
    raise ImportError(
        f"错误的moq模块被加载: {moq_module_path}. 请确保使用 /root/lpx/webui/moq"
    )

from moq.sub.subscriber import MOQSubscriber, ReceivedObject
from moq.encoding import FullTrackName
from moq.messages import ObjectStatus

logger = logging.getLogger(__name__)

WEBTRANSPORT_HOST = "127.0.0.1"
WEBTRANSPORT_PORT = 4433
WEBTRANSPORT_PATH_PREFIX = "/wt"
WEBTRANSPORT_CERT_VALIDITY_DAYS = 7
MAX_REPLAY_FRAGMENTS = 8
DEFAULT_MSE_CODEC = "avc1.64001F"
SETTINGS_WT_MAX_SESSIONS = 0x14E9CD29
WT_MAX_SESSIONS = 24

FRAME_TYPE_JSON = 0x01
FRAME_TYPE_INIT = 0x02
FRAME_TYPE_FRAGMENT = 0x03
FRAME_TYPE_END = 0x04

ALLOWED_WEB_ORIGINS = {
    "http://127.0.0.1:9005",
    "http://localhost:9005",
}


@dataclass
class VideoFrameData:
    track_name: str
    group_id: int
    object_id: int
    timestamp: datetime
    payload: bytes
    frame_type: str


VideoFrame = VideoFrameData


@dataclass
class DiscoveredVideoTrack:
    track_id: str
    namespace: str
    namespace_parts: List[str]
    track_name: str
    normalized_track_name: str
    agent_id: str
    task_id: str
    discovered_at: datetime
    last_seen: datetime
    seen_count: int = 1
    watch_state: str = "available"
    last_error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    last_object_at: Optional[datetime] = None
    source: str = "moq"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "trackId": self.track_id,
            "namespace": self.namespace,
            "trackName": self.track_name,
            "normalizedTrackName": self.normalized_track_name,
            "agentId": self.agent_id,
            "taskId": self.task_id,
            "discoveredAt": self.discovered_at.isoformat(),
            "lastSeen": self.last_seen.isoformat(),
            "seenCount": self.seen_count,
            "watchState": self.watch_state,
            "lastError": self.last_error,
            "metadata": self.metadata,
            "lastObjectAt": self.last_object_at.isoformat()
            if self.last_object_at
            else None,
            "source": self.source,
        }


def pack_frame(frame_type: int, payload: bytes = b"") -> bytes:
    return bytes([frame_type]) + len(payload).to_bytes(4, "big") + payload


def infer_avc1_codec_from_init_segment(init_segment: bytes) -> Optional[str]:
    avcc_offset = init_segment.find(b"avcC")
    if avcc_offset < 4 or avcc_offset + 8 > len(init_segment):
        return None

    profile = init_segment[avcc_offset + 5]
    compatibility = init_segment[avcc_offset + 6]
    level = init_segment[avcc_offset + 7]
    return f"avc1.{profile:02X}{compatibility:02X}{level:02X}"


def looks_like_mp4_init_segment(payload: bytes) -> bool:
    if len(payload) < 16:
        return False

    first_box_size = int.from_bytes(payload[0:4], "big")
    first_box_type = payload[4:8]
    if first_box_size < 8 or first_box_size > len(payload):
        return False
    if first_box_type != b"ftyp":
        return False

    return b"moov" in payload[: min(len(payload), 4096)]


def build_browser_metadata(
    metadata: Dict[str, Any], init_segment: Optional[bytes] = None
) -> Dict[str, Any]:
    browser_metadata = dict(metadata)
    inferred_codec = (
        infer_avc1_codec_from_init_segment(init_segment)
        if init_segment is not None
        else None
    )
    mse_codec = (
        browser_metadata.get("mse_codec")
        or inferred_codec
        or DEFAULT_MSE_CODEC
    )

    browser_metadata["mse_codec"] = mse_codec
    browser_metadata["mime_type"] = browser_metadata.get(
        "mime_type", f'video/mp4; codecs="{mse_codec}"'
    )
    return browser_metadata


def generate_webtransport_certificate(
    host: str,
) -> tuple[str, str, str, tempfile.TemporaryDirectory]:
    temp_dir = tempfile.TemporaryDirectory(prefix="moq-webtransport-")
    cert_path = f"{temp_dir.name}/cert.pem"
    key_path = f"{temp_dir.name}/key.pem"

    key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])

    san_values = [x509.DNSName("localhost")]
    try:
        san_values.append(x509.IPAddress(ipaddress.ip_address(host)))
    except ValueError:
        san_values.append(x509.DNSName(host))

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
        .not_valid_after(
            datetime.utcnow()
            + timedelta(days=WEBTRANSPORT_CERT_VALIDITY_DAYS)
        )
        .add_extension(x509.SubjectAlternativeName(san_values), critical=False)
        .sign(key, hashes.SHA256())
    )

    Path(cert_path).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    Path(key_path).write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    cert_hash = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
    return cert_path, key_path, cert_hash, temp_dir


class TrackBridgeState:
    def __init__(self, track_id: str):
        self.track_id = track_id
        self.metadata: Optional[Dict[str, Any]] = None
        self.init_segment: Optional[bytes] = None
        self.recent_fragments: deque[bytes] = deque(maxlen=MAX_REPLAY_FRAGMENTS)
        self.latest_jpeg: Optional[bytes] = None
        self.latest_jpeg_fragment_count = 0
        self.latest_jpeg_sequence = 0
        self.jpeg_lock = asyncio.Lock()
        self.transcoder_process: Optional[asyncio.subprocess.Process] = None
        self.transcoder_stdout_task: Optional[asyncio.Task] = None
        self.transcoder_stderr_task: Optional[asyncio.Task] = None
        self.transcoder_write_lock = asyncio.Lock()
        self.sessions: set["BrowserWebTransportSession"] = set()
        self.total_bytes = 0
        self.total_fragments = 0

    def add_session(self, session: "BrowserWebTransportSession"):
        self.sessions.add(session)
        if self.metadata is not None:
            session.send_json({"type": "metadata", "metadata": self.metadata})
        if self.init_segment is not None:
            session.send_binary(FRAME_TYPE_INIT, self.init_segment)
        for fragment in self.recent_fragments:
            session.send_binary(FRAME_TYPE_FRAGMENT, fragment)

    def remove_session(self, session: "BrowserWebTransportSession"):
        self.sessions.discard(session)

    def close_all_sessions(self):
        for session in tuple(self.sessions):
            session.close()
        self.sessions.clear()

    def reset(self):
        self.metadata = None
        self.init_segment = None
        self.recent_fragments.clear()
        self.latest_jpeg = None
        self.latest_jpeg_fragment_count = 0
        self.latest_jpeg_sequence = 0
        self.total_bytes = 0
        self.total_fragments = 0

    def set_metadata(self, metadata: Dict[str, Any]):
        self.metadata = metadata
        self.init_segment = None
        self.recent_fragments.clear()
        self.total_bytes = 0
        self.total_fragments = 0
        for session in tuple(self.sessions):
            session.send_json({"type": "metadata", "metadata": metadata})

    def set_init_segment(self, payload: bytes):
        self.init_segment = payload
        self.latest_jpeg = None
        self.latest_jpeg_fragment_count = 0
        self.latest_jpeg_sequence = 0
        self.total_bytes += len(payload)
        for session in tuple(self.sessions):
            session.send_binary(FRAME_TYPE_INIT, payload)

    def push_fragment(self, payload: bytes):
        self.recent_fragments.append(payload)
        self.total_bytes += len(payload)
        self.total_fragments += 1
        for session in tuple(self.sessions):
            session.send_binary(FRAME_TYPE_FRAGMENT, payload)

    def end_stream(self):
        for session in tuple(self.sessions):
            session.send_json({"type": "end"})
            session.send_binary(FRAME_TYPE_END, b"")


class BrowserWebTransportSession:
    def __init__(
        self,
        protocol: "BrowserBridgeProtocol",
        session_id: int,
        bridge: TrackBridgeState,
        origin: Optional[str] = None,
    ):
        self.protocol = protocol
        self.bridge = bridge
        self.origin = origin
        self.session_id = session_id
        self.closed = False
        self.output_stream_id = protocol.http.create_webtransport_stream(
            session_id=session_id,
            is_unidirectional=True,
        )
        self.protocol.transmit()

    def send_binary(self, frame_type: int, payload: bytes):
        if self.closed:
            return
        try:
            self.protocol.http._quic.send_stream_data(
                self.output_stream_id,
                pack_frame(frame_type, payload),
                end_stream=False,
            )
            self.protocol.transmit()
        except Exception:
            logger.debug("Failed to send browser frame", exc_info=True)
            self.protocol.drop_session(self.session_id, reason="send failure")

    def send_json(self, payload: Dict[str, Any]):
        self.send_binary(FRAME_TYPE_JSON, json.dumps(payload).encode("utf-8"))

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.protocol.http._quic.send_stream_data(
                self.output_stream_id, b"", end_stream=True
            )
            self.protocol.transmit()
        except Exception:
            logger.debug("Failed to close browser output stream", exc_info=True)


class BrowserH3Connection(H3Connection):
    def _get_local_settings(self) -> Dict[int, int]:
        settings = super()._get_local_settings()
        settings[SETTINGS_WT_MAX_SESSIONS] = WT_MAX_SESSIONS
        return settings


class BrowserBridgeProtocol(QuicConnectionProtocol):
    def __init__(
        self,
        *args,
        subscriber: "MOQVideoSubscriber",
        allowed_origins: set[str],
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._subscriber = subscriber
        self._allowed_origins = allowed_origins
        self._http: Optional[H3Connection] = None
        self._sessions: Dict[int, BrowserWebTransportSession] = {}

    @property
    def http(self) -> H3Connection:
        assert self._http is not None
        return self._http

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, ProtocolNegotiated) and event.alpn_protocol in H3_ALPN:
            self._http = BrowserH3Connection(self._quic, enable_webtransport=True)
        elif isinstance(event, ConnectionTerminated):
            self._close_all_sessions(
                reason=f"quic terminated error_code={event.error_code}"
            )

        if self._http is None:
            return

        for http_event in self._http.handle_event(event):
            self._handle_http_event(http_event)

    def _handle_http_event(self, event: H3Event):
        if isinstance(event, HeadersReceived):
            self._handle_headers(event)
        elif isinstance(event, DatagramReceived):
            logger.debug("Ignoring WebTransport datagram")
        elif isinstance(event, WebTransportStreamDataReceived):
            logger.debug("Ignoring browser stream data")

    def _handle_headers(self, event: HeadersReceived):
        headers = {name: value for name, value in event.headers}
        method = headers.get(b":method", b"").decode("utf-8", errors="ignore")
        path = headers.get(b":path", b"").decode("utf-8", errors="ignore")
        protocol = headers.get(b":protocol", b"").decode("utf-8", errors="ignore")
        origin = headers.get(b"origin", b"").decode("utf-8", errors="ignore")

        if method != "CONNECT" or not path.startswith(WEBTRANSPORT_PATH_PREFIX):
            self._reject_session(event.stream_id, 404)
            return

        if protocol not in {"webtransport", "webtransport-h3"}:
            self._reject_session(event.stream_id, 400)
            return

        if origin and origin not in self._allowed_origins:
            self._reject_session(event.stream_id, 403)
            return

        track_id = unquote(path[len(WEBTRANSPORT_PATH_PREFIX) :].lstrip("/"))
        if not track_id:
            self._reject_session(event.stream_id, 400)
            return

        bridge = self._subscriber.get_or_create_bridge(track_id)
        self.http.send_headers(
            stream_id=event.stream_id,
            headers=[
                (b":status", b"200"),
                (b"server", b"moq-webtransport-bridge"),
                (
                    b"date",
                    formatdate(timeval=None, localtime=False, usegmt=True).encode(
                        "ascii"
                    ),
                ),
                (b"sec-webtransport-http3-draft", b"draft02"),
            ],
        )
        session = BrowserWebTransportSession(
            protocol=self,
            session_id=event.stream_id,
            bridge=bridge,
            origin=origin or None,
        )
        self._sessions[event.stream_id] = session
        bridge.add_session(session)

    def _reject_session(self, stream_id: int, status: int):
        self.http.send_headers(
            stream_id=stream_id,
            headers=[(b":status", str(status).encode("ascii"))],
            end_stream=True,
        )
        self.transmit()

    def drop_session(self, session_id: int, reason: str = "unspecified"):
        session = self._sessions.pop(session_id, None)
        if session is None:
            return
        session.bridge.remove_session(session)
        session.close()
        logger.info(
            "[MOQ WT] Closed browser session %s for track=%s (%s)",
            session_id,
            session.bridge.track_id,
            reason,
        )

    def _close_all_sessions(self, reason: str = "connection shutdown"):
        for session_id in tuple(self._sessions):
            self.drop_session(session_id, reason=reason)


class MOQVideoSubscriber:
    def __init__(self, relay_host: str = "localhost", relay_port: int = 9003):
        self.relay_host = relay_host
        self.relay_port = relay_port

        self._subscriber: Optional[MOQSubscriber] = None
        self._running = False
        self._connection_task: Optional[asyncio.Task] = None
        self._processor_task: Optional[asyncio.Task] = None
        self._webtransport_server = None

        self._cert_dir: Optional[tempfile.TemporaryDirectory] = None
        self._cert_hash: Optional[str] = None

        self._video_tracks: Dict[str, FullTrackName] = {}
        self._track_states: Dict[str, str] = {}
        self._track_object_counts: Dict[str, int] = {}
        self._frame_buffers: Dict[str, List[VideoFrameData]] = {}
        self._bridges: Dict[str, TrackBridgeState] = {}
        self._discovered_tracks: Dict[str, DiscoveredVideoTrack] = {}
        self._watched_tracks: set[str] = set()

        self._object_queue: asyncio.Queue[ReceivedObject] = asyncio.Queue()

        self._on_frame_received: Optional[Callable[[VideoFrameData], None]] = None
        self._on_track_subscribed: Optional[Callable[[str], None]] = None
        self._on_track_unsubscribed: Optional[Callable[[str], None]] = None

        logger.info(
            "[MOQ] MOQVideoSubscriber initialized for %s:%s",
            relay_host,
            relay_port,
        )

    def set_callbacks(
        self,
        on_frame_received: Optional[Callable[[VideoFrameData], None]] = None,
        on_track_subscribed: Optional[Callable[[str], None]] = None,
        on_track_unsubscribed: Optional[Callable[[str], None]] = None,
    ):
        self._on_frame_received = on_frame_received
        self._on_track_subscribed = on_track_subscribed
        self._on_track_unsubscribed = on_track_unsubscribed

    def get_or_create_bridge(self, track_id: str) -> TrackBridgeState:
        bridge = self._bridges.get(track_id)
        if bridge is None:
            bridge = TrackBridgeState(track_id)
            self._bridges[track_id] = bridge
        return bridge

    async def start(self):
        if self._running:
            return

        self._running = True
        await self._start_webtransport_bridge()
        self._processor_task = asyncio.create_task(self._process_objects())
        self._connection_task = asyncio.create_task(self._connection_loop())

    async def stop(self):
        self._running = False

        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass

        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        if self._subscriber:
            self._subscriber.disconnect()
            self._subscriber = None

        if self._webtransport_server is not None:
            self._webtransport_server.close()
            await asyncio.sleep(0)
            self._webtransport_server = None

        for bridge in self._bridges.values():
            bridge.close_all_sessions()
            await self._shutdown_mjpeg_transcoder(bridge)

        if self._cert_dir is not None:
            self._cert_dir.cleanup()
            self._cert_dir = None

    async def _start_webtransport_bridge(self):
        cert_path, key_path, cert_hash, cert_dir = generate_webtransport_certificate(
            WEBTRANSPORT_HOST
        )
        quic_config = QuicConfiguration(
            alpn_protocols=H3_ALPN,
            is_client=False,
            max_datagram_frame_size=65536,
        )
        quic_config.load_cert_chain(cert_path, key_path)

        self._cert_hash = cert_hash
        self._cert_dir = cert_dir
        self._webtransport_server = await serve(
            WEBTRANSPORT_HOST,
            WEBTRANSPORT_PORT,
            configuration=quic_config,
            create_protocol=lambda *args, **kwargs: BrowserBridgeProtocol(
                *args,
                subscriber=self,
                allowed_origins=ALLOWED_WEB_ORIGINS,
                **kwargs,
            ),
        )
        logger.info(
            "[MOQ WT] Listening at https://%s:%d%s (cert sha256=%s)",
            WEBTRANSPORT_HOST,
            WEBTRANSPORT_PORT,
            WEBTRANSPORT_PATH_PREFIX,
            cert_hash,
        )

    async def _connection_loop(self):
        while self._running:
            try:
                if not self._subscriber:
                    logger.info(
                        "[MOQ] Connecting to MOQ Relay at %s:%s",
                        self.relay_host,
                        self.relay_port,
                    )

                    self._subscriber = MOQSubscriber(self.relay_host, self.relay_port)
                    self._subscriber.set_handlers(
                        on_connected=self._on_connected,
                        on_disconnected=self._on_disconnected,
                        on_object_received=self._on_object_received,
                        on_subscription_accepted=self._on_subscription_accepted,
                        on_subscription_rejected=self._on_subscription_rejected,
                    )

                    connected = await self._subscriber.connect()
                    if not connected:
                        logger.error("[MOQ] Failed to connect to relay")
                        self._subscriber = None
                        await asyncio.sleep(5)
                        continue

                    for track_id in list(self._watched_tracks):
                        await self._subscribe_registered_track(track_id)

                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("[MOQ] Connection loop error: %s", exc, exc_info=True)
                if self._subscriber:
                    self._subscriber.disconnect()
                    self._subscriber = None
                await asyncio.sleep(5)

    async def _subscribe_registered_track(self, track_id: str) -> bool:
        full_track_name = self._video_tracks.get(track_id)
        if not self._subscriber or full_track_name is None:
            return False

        try:
            request_id = await self._subscriber.fetch(
                full_track_name,
                start_group=1,
                start_object=1,
            )
            if request_id < 0:
                raise RuntimeError("fetch request was rejected locally")

            self._track_states[track_id] = "subscribed"
            discovered = self._discovered_tracks.get(track_id)
            if discovered:
                discovered.watch_state = "subscribed"
                discovered.last_error = None
            if self._on_track_subscribed:
                self._on_track_subscribed(track_id)
            return True
        except Exception as exc:
            logger.error("[MOQ] Failed to subscribe %s: %s", track_id, exc)
            self._track_states[track_id] = "error"
            discovered = self._discovered_tracks.get(track_id)
            if discovered:
                discovered.watch_state = "error"
                discovered.last_error = str(exc)
            return False

    async def subscribe_to_track(
        self, track_id: str, namespace: List[str], track_name: str
    ) -> bool:
        namespace_parts = [part for part in namespace if part]
        namespace_str = "/" + "/".join(namespace_parts) if namespace_parts else "/"
        full_track_name = FullTrackName(
            namespace=[namespace_str.encode()],
            track_name=track_name.encode()
            if isinstance(track_name, str)
            else track_name,
        )

        self._video_tracks[track_id] = full_track_name
        self._watched_tracks.add(track_id)
        self._track_states[track_id] = "requested"
        self._track_object_counts.setdefault(track_id, 0)
        self._frame_buffers.setdefault(track_id, [])
        self.get_or_create_bridge(track_id)

        discovered = self._discovered_tracks.get(track_id)
        if discovered:
            discovered.watch_state = "requested"
            discovered.last_error = None

        if self._subscriber:
            return await self._subscribe_registered_track(track_id)
        return True

    async def unsubscribe_from_track(self, track_id: str):
        if track_id not in self._video_tracks:
            return

        full_track_name = self._video_tracks[track_id]
        self._watched_tracks.discard(track_id)
        self._track_states[track_id] = "available"

        discovered = self._discovered_tracks.get(track_id)
        if discovered:
            discovered.watch_state = "available"

        bridge = self._bridges.get(track_id)
        if bridge:
            bridge.end_stream()
            await self._shutdown_mjpeg_transcoder(bridge)
            bridge.reset()

        if self._subscriber:
            try:
                await self._subscriber.unsubscribe(full_track_name)
            except Exception as exc:
                logger.error("[MOQ] Failed to unsubscribe from %s: %s", track_id, exc)

        if self._on_track_unsubscribed:
            self._on_track_unsubscribed(track_id)

    def get_subscribed_tracks(self) -> List[str]:
        return sorted(self._watched_tracks)

    def get_frame_buffer(self, track_id: str) -> List[VideoFrameData]:
        return self._frame_buffers.get(track_id, [])

    def get_track_debug_info(self) -> List[Dict[str, Any]]:
        rows = []
        for track_id, full_track_name in self._video_tracks.items():
            bridge = self._bridges.get(track_id)
            rows.append(
                {
                    "track_id": track_id,
                    "namespace": [part.decode() for part in full_track_name.namespace],
                    "track_name": full_track_name.track_name.decode()
                    if isinstance(full_track_name.track_name, bytes)
                    else str(full_track_name.track_name),
                    "state": self._track_states.get(track_id, "unknown"),
                    "object_count": self._track_object_counts.get(track_id, 0),
                    "buffered_frames": len(self._frame_buffers.get(track_id, [])),
                    "has_metadata": bool(bridge and bridge.metadata),
                    "has_init_segment": bool(bridge and bridge.init_segment),
                    "recent_fragments": len(bridge.recent_fragments) if bridge else 0,
                    "watching": track_id in self._watched_tracks,
                }
            )
        return rows

    def list_discovered_tracks(self) -> List[Dict[str, Any]]:
        items = sorted(
            self._discovered_tracks.values(),
            key=lambda item: item.last_seen,
            reverse=True,
        )
        return [item.as_dict() for item in items]

    def get_discovered_track(self, track_id: str) -> Optional[Dict[str, Any]]:
        item = self._discovered_tracks.get(track_id)
        return item.as_dict() if item else None

    def register_discovered_track(
        self,
        track_id: str,
        namespace: List[str] | str,
        track_name: str,
        agent_id: str,
        task_id: str,
        source: str = "moq",
    ) -> Dict[str, Any]:
        namespace_parts = (
            [part for part in namespace if part]
            if isinstance(namespace, list)
            else [part for part in str(namespace).split("/") if part]
        )
        namespace_str = "/" + "/".join(namespace_parts) if namespace_parts else "/"
        now = datetime.utcnow()

        existing = self._discovered_tracks.get(track_id)
        if existing:
            existing.namespace = namespace_str
            existing.namespace_parts = namespace_parts
            existing.track_name = track_name
            existing.normalized_track_name = track_name.lower()
            existing.agent_id = agent_id
            existing.task_id = task_id
            existing.last_seen = now
            existing.seen_count += 1
            existing.source = source
            return existing.as_dict()

        self._discovered_tracks[track_id] = DiscoveredVideoTrack(
            track_id=track_id,
            namespace=namespace_str,
            namespace_parts=namespace_parts,
            track_name=track_name,
            normalized_track_name=track_name.lower(),
            agent_id=agent_id,
            task_id=task_id,
            discovered_at=now,
            last_seen=now,
            source=source,
        )
        return self._discovered_tracks[track_id].as_dict()

    async def remove_discovered_track(self, track_id: str) -> bool:
        discovered = self._discovered_tracks.get(track_id)
        if discovered is None:
            return False

        if track_id in self._video_tracks:
            await self.unsubscribe_from_track(track_id)

        bridge = self._bridges.pop(track_id, None)
        if bridge:
            bridge.end_stream()
            bridge.close_all_sessions()
            await self._shutdown_mjpeg_transcoder(bridge)
            bridge.reset()

        self._watched_tracks.discard(track_id)
        self._video_tracks.pop(track_id, None)
        self._track_states.pop(track_id, None)
        self._track_object_counts.pop(track_id, None)
        self._frame_buffers.pop(track_id, None)
        self._discovered_tracks.pop(track_id, None)
        return True

    def get_player_config(self, track_id: str, host: Optional[str] = None) -> Dict[str, Any]:
        if self._cert_hash is None:
            raise RuntimeError("WebTransport bridge is not running")

        return {
            "trackId": track_id,
            "host": host or WEBTRANSPORT_HOST,
            "port": WEBTRANSPORT_PORT,
            "path": f"{WEBTRANSPORT_PATH_PREFIX}/{quote(track_id, safe='')}",
            "certHash": self._cert_hash,
        }

    async def get_latest_jpeg_frame(self, track_id: str) -> Optional[bytes]:
        bridge = self._bridges.get(track_id)
        if bridge is None:
            return None
        return bridge.latest_jpeg

    def get_mjpeg_track_status(self, track_id: str) -> Dict[str, Any]:
        bridge = self._bridges.get(track_id)
        discovered = self._discovered_tracks.get(track_id)
        metadata = (bridge.metadata if bridge else None) or (
            discovered.metadata if discovered else None
        )
        return {
            "track_id": track_id,
            "status": "active" if bridge and bridge.recent_fragments else "inactive",
            "watch_state": self._track_states.get(track_id, "unknown"),
            "has_metadata": bool(metadata),
            "has_init_segment": bool(bridge and bridge.init_segment),
            "fragment_count": bridge.total_fragments if bridge else 0,
            "has_frame": bool(bridge and bridge.latest_jpeg),
            "jpeg_sequence": bridge.latest_jpeg_sequence if bridge else 0,
            "width": metadata.get("width") if isinstance(metadata, dict) else None,
            "height": metadata.get("height") if isinstance(metadata, dict) else None,
            "metadata": metadata,
        }

    def get_bridge_snapshot(self, track_id: str) -> Dict[str, Any]:
        bridge = self._bridges.get(track_id)
        if bridge is None:
            return {
                "metadata": None,
                "initSegmentBase64": None,
                "recentFragmentsBase64": [],
            }

        return {
            "metadata": bridge.metadata,
            "initSegmentBase64": (
                base64.b64encode(bridge.init_segment).decode("ascii")
                if bridge.init_segment is not None
                else None
            ),
            "recentFragmentsBase64": [
                base64.b64encode(fragment).decode("ascii")
                for fragment in bridge.recent_fragments
            ],
        }

    def _on_connected(self):
        logger.info("[MOQ] Connected to MOQ Relay")

    def _on_disconnected(self):
        logger.warning("[MOQ] Disconnected from MOQ Relay")
        self._subscriber = None

    def _on_subscription_accepted(self, track_name: FullTrackName):
        for track_id, saved_track in self._video_tracks.items():
            if saved_track == track_name:
                self._track_states[track_id] = "subscribed"
                discovered = self._discovered_tracks.get(track_id)
                if discovered:
                    discovered.watch_state = "subscribed"
                    discovered.last_error = None
                logger.info("[MOQ] Subscription accepted for track: %s", track_id)
                if self._on_track_subscribed:
                    self._on_track_subscribed(track_id)
                break

    def _on_subscription_rejected(self, track_name: FullTrackName, reason: str):
        for track_id, saved_track in self._video_tracks.items():
            if saved_track == track_name:
                self._track_states[track_id] = "error"
                discovered = self._discovered_tracks.get(track_id)
                if discovered:
                    discovered.watch_state = "error"
                    discovered.last_error = reason
                logger.warning("[MOQ] Subscription rejected for %s: %s", track_id, reason)
                break

    def _on_object_received(self, obj: ReceivedObject):
        try:
            self._object_queue.put_nowait(obj)
        except asyncio.QueueFull:
            logger.warning("[MOQ] Object queue full; dropping object")

    async def _process_objects(self):
        while True:
            obj = await self._object_queue.get()
            try:
                track_id = self._resolve_track_id(obj.track_alias)
                if not track_id:
                    logger.warning(
                        "[MOQ] Received object for unknown track alias: %s",
                        obj.track_alias,
                    )
                    continue

                discovered = self._discovered_tracks.get(track_id)
                if discovered:
                    discovered.last_object_at = datetime.utcnow()

                if obj.group_id != 1:
                    logger.debug(
                        "[MOQ] Ignoring unexpected group for %s: %s",
                        track_id,
                        obj.group_id,
                    )
                    continue

                bridge = self.get_or_create_bridge(track_id)

                if obj.object_status == ObjectStatus.END_OF_SUBGROUP:
                    bridge.end_stream()
                    await self._shutdown_mjpeg_transcoder(bridge)
                    self._append_buffer(
                        track_id,
                        VideoFrameData(
                            track_name=track_id,
                            group_id=obj.group_id,
                            object_id=obj.object_id,
                            timestamp=datetime.utcnow(),
                            payload=b"",
                            frame_type="end",
                        ),
                    )
                    continue

                if obj.object_id == 1:
                    parsed_metadata = self._try_parse_metadata(obj.payload)
                    if parsed_metadata is not None:
                        metadata = build_browser_metadata(parsed_metadata)
                        bridge.set_metadata(metadata)
                        if discovered:
                            discovered.metadata = metadata
                        self._append_buffer(
                            track_id,
                            VideoFrameData(
                                track_name=track_id,
                                group_id=obj.group_id,
                                object_id=obj.object_id,
                                timestamp=datetime.utcnow(),
                                payload=obj.payload,
                                frame_type="metadata",
                            ),
                        )
                        continue

                if looks_like_mp4_init_segment(obj.payload):
                    if bridge.metadata is not None:
                        updated_metadata = build_browser_metadata(
                            bridge.metadata, init_segment=obj.payload
                        )
                        if updated_metadata != bridge.metadata:
                            bridge.set_metadata(updated_metadata)
                            if discovered:
                                discovered.metadata = updated_metadata
                    bridge.set_init_segment(obj.payload)
                    await self._restart_mjpeg_transcoder(track_id, bridge)
                    self._append_buffer(
                        track_id,
                        VideoFrameData(
                            track_name=track_id,
                            group_id=obj.group_id,
                            object_id=obj.object_id,
                            timestamp=datetime.utcnow(),
                            payload=obj.payload,
                            frame_type="init",
                        ),
                    )
                    continue

                if bridge.init_segment is None:
                    if bridge.metadata is not None:
                        updated_metadata = build_browser_metadata(
                            bridge.metadata, init_segment=obj.payload
                        )
                        if updated_metadata != bridge.metadata:
                            bridge.set_metadata(updated_metadata)
                            if discovered:
                                discovered.metadata = updated_metadata
                    bridge.set_init_segment(obj.payload)
                    await self._restart_mjpeg_transcoder(track_id, bridge)
                    self._append_buffer(
                        track_id,
                        VideoFrameData(
                            track_name=track_id,
                            group_id=obj.group_id,
                            object_id=obj.object_id,
                            timestamp=datetime.utcnow(),
                            payload=obj.payload,
                            frame_type="init",
                        ),
                    )
                    continue

                bridge.push_fragment(obj.payload)
                await self._push_fragment_to_mjpeg_transcoder(track_id, bridge, obj.payload)
                self._append_buffer(
                    track_id,
                    VideoFrameData(
                        track_name=track_id,
                        group_id=obj.group_id,
                        object_id=obj.object_id,
                        timestamp=datetime.utcnow(),
                        payload=obj.payload,
                        frame_type="fragment",
                    ),
                )
            except Exception as exc:
                logger.error("[MOQ] Error processing object: %s", exc, exc_info=True)

    def _resolve_track_id(self, track_alias: int) -> Optional[str]:
        if not self._subscriber or not hasattr(self._subscriber, "_track_aliases"):
            return None

        full_track_name = self._subscriber._track_aliases.get(track_alias)
        if full_track_name is None:
            return None

        for track_id, saved_track in self._video_tracks.items():
            if saved_track == full_track_name:
                return track_id
        return None

    def _append_buffer(self, track_id: str, frame: VideoFrameData):
        frames = self._frame_buffers.setdefault(track_id, [])
        frames.append(frame)
        if len(frames) > 30:
            self._frame_buffers[track_id] = frames[-30:]
        if self._on_frame_received:
            try:
                callback_result = self._on_frame_received(frame)
                if inspect.isawaitable(callback_result):
                    asyncio.create_task(callback_result)
            except Exception:
                logger.error(
                    "[MOQ] Failed to dispatch frame callback for %s",
                    track_id,
                    exc_info=True,
                )

    @staticmethod
    def _try_parse_metadata(payload: bytes) -> Optional[Dict[str, Any]]:
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    async def _restart_mjpeg_transcoder(
        self, track_id: str, bridge: TrackBridgeState
    ) -> None:
        await self._shutdown_mjpeg_transcoder(bridge)

        width = int((bridge.metadata or {}).get("width") or 960)
        height = int((bridge.metadata or {}).get("height") or 540)
        if width <= 0 or height <= 0:
            width, height = 960, 540

        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-loglevel",
            "error",
            "-fflags",
            "nobuffer",
            "-i",
            "pipe:0",
            "-vf",
            f"fps=12,scale={width}:{height}",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-q:v",
            "6",
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        bridge.transcoder_process = process
        bridge.transcoder_stdout_task = asyncio.create_task(
            self._read_mjpeg_stdout(track_id, bridge, process)
        )
        bridge.transcoder_stderr_task = asyncio.create_task(
            self._read_mjpeg_stderr(track_id, process)
        )

        if bridge.init_segment:
            await self._write_to_mjpeg_transcoder(bridge, bridge.init_segment)
        for fragment in list(bridge.recent_fragments):
            await self._write_to_mjpeg_transcoder(bridge, fragment)

    async def _shutdown_mjpeg_transcoder(self, bridge: TrackBridgeState) -> None:
        process = bridge.transcoder_process
        if process is None:
            return

        bridge.transcoder_process = None

        for task in (bridge.transcoder_stdout_task, bridge.transcoder_stderr_task):
            if task:
                task.cancel()
        for task_name in ("transcoder_stdout_task", "transcoder_stderr_task"):
            task = getattr(bridge, task_name)
            if task:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            setattr(bridge, task_name, None)

        with contextlib.suppress(Exception):
            if process.stdin and not process.stdin.is_closing():
                process.stdin.close()
        with contextlib.suppress(Exception):
            process.terminate()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(process.wait(), timeout=1.0)
        if process.returncode is None:
            with contextlib.suppress(Exception):
                process.kill()
            with contextlib.suppress(Exception):
                await process.wait()

    async def _push_fragment_to_mjpeg_transcoder(
        self, track_id: str, bridge: TrackBridgeState, fragment: bytes
    ) -> None:
        started = False
        if bridge.transcoder_process is None or bridge.transcoder_process.returncode is not None:
            await self._restart_mjpeg_transcoder(track_id, bridge)
            started = True
        if not started:
            await self._write_to_mjpeg_transcoder(bridge, fragment)

    async def _write_to_mjpeg_transcoder(
        self, bridge: TrackBridgeState, payload: bytes
    ) -> None:
        process = bridge.transcoder_process
        if process is None or process.stdin is None:
            return
        async with bridge.transcoder_write_lock:
            process.stdin.write(payload)
            await process.stdin.drain()

    async def _read_mjpeg_stdout(
        self, track_id: str, bridge: TrackBridgeState, process: asyncio.subprocess.Process
    ) -> None:
        if process.stdout is None:
            return

        buffer = bytearray()
        while True:
            chunk = await process.stdout.read(65536)
            if not chunk:
                return
            buffer.extend(chunk)

            while True:
                start = buffer.find(b"\xff\xd8")
                if start < 0:
                    if len(buffer) > 2:
                        del buffer[:-2]
                    break
                end = buffer.find(b"\xff\xd9", start + 2)
                if end < 0:
                    if start > 0:
                        del buffer[:start]
                    break

                jpeg_bytes = bytes(buffer[start : end + 2])
                del buffer[: end + 2]

                async with bridge.jpeg_lock:
                    bridge.latest_jpeg = jpeg_bytes
                    bridge.latest_jpeg_fragment_count = bridge.total_fragments
                    bridge.latest_jpeg_sequence += 1

    async def _read_mjpeg_stderr(
        self, track_id: str, process: asyncio.subprocess.Process
    ) -> None:
        if process.stderr is None:
            return
        while True:
            line = await process.stderr.readline()
            if not line:
                return
            logger.debug(
                "[MOQ MJPEG] %s ffmpeg: %s",
                track_id,
                line.decode("utf-8", errors="ignore").rstrip(),
            )


moq_video_subscriber = MOQVideoSubscriber()
