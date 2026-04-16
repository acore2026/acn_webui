"""
MOQ Transport - Subscriber Implementation
Subscriber for MOQT protocol.
"""

import asyncio
import logging
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass

from moq.session import MOQSession, Role, Subscription
from moq.messages import (
    SubscribeMessage,
    SubscribeOkMessage,
    RequestErrorMessage,
    ObjectHeader,
    ObjectDatagram,
    SubgroupHeader,
    SubgroupObject,
    FetchMessage,
    FetchOkMessage,
    ObjectStatus,
    StreamType,
    ErrorCode,
)
from moq.encoding import FullTrackName, Location, VarInt, Parameters
from moq.transport import QUICClient, StreamData, DatagramData
from moq.session import SETUP_AGENT_ID_PARAM

logger = logging.getLogger(__name__)


@dataclass
class ReceivedObject:
    """Object received from subscription."""

    track_alias: int
    group_id: int
    object_id: int
    publisher_priority: int
    payload: bytes
    object_status: ObjectStatus = ObjectStatus.NORMAL


class MOQSubscriber:
    """
    MOQ Subscriber.
    Subscribes to tracks from a relay or publisher.
    """

    def __init__(self, relay_host: str, relay_port: int):
        self.relay_host = relay_host
        self.relay_port = relay_port

        # Connection
        self._client: Optional[QUICClient] = None
        self._session: Optional[MOQSession] = None

        # Subscriptions
        self._subscriptions: Dict[FullTrackName, int] = {}  # track -> request_id
        self._active_subscriptions: Dict[int, FullTrackName] = {}  # request_id -> track

        # Track alias mapping
        self._track_aliases: Dict[int, FullTrackName] = {}  # track_alias -> track

        # Stream data buffer for handling fragmented stream data
        self._stream_buffers: Dict[int, bytes] = {}  # stream_id -> accumulated data

        # Stream parser state for incremental parsing
        # Each stream has: {
        #   'stage': 'init'|'type'|'header'|'objects',
        #   'type': StreamType,
        #   'header': SubgroupHeader|FetchHeader,
        #   'parsed_objects': set of (group_id, object_id) tuples
        #   'current_object': {  # For partial object parsing
        #       'id': object_id,
        #       'payload_len': int,
        #       'payload_received': int,
        #       'payload': bytes
        #   }
        # }
        self._stream_parser_state: Dict[int, Dict] = {}

        # Handlers
        self._on_connected: Optional[Callable] = None
        self._on_disconnected: Optional[Callable] = None
        self._on_object_received: Optional[Callable[[ReceivedObject], None]] = None
        self._on_subscription_accepted: Optional[Callable[[FullTrackName], None]] = None
        self._on_subscription_rejected: Optional[
            Callable[[FullTrackName, str], None]
        ] = None

        # Object delivery queue
        self._object_queue: asyncio.Queue = asyncio.Queue()
        self._control_buffer = b""

        logger.info(f"MOQSubscriber initialized for {relay_host}:{relay_port}")

    def set_handlers(
        self,
        on_connected: Optional[Callable] = None,
        on_disconnected: Optional[Callable] = None,
        on_object_received: Optional[Callable[[ReceivedObject], None]] = None,
        on_subscription_accepted: Optional[Callable[[FullTrackName], None]] = None,
        on_subscription_rejected: Optional[Callable[[FullTrackName, str], None]] = None,
    ):
        """Set event handlers."""
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._on_object_received = on_object_received
        self._on_subscription_accepted = on_subscription_accepted
        self._on_subscription_rejected = on_subscription_rejected

    async def connect(self, agent_id: Optional[str] = None) -> bool:
        """Connect to relay."""
        logger.info(f"Connecting to relay at {self.relay_host}:{self.relay_port}")

        try:
            # Create QUIC client
            self._client = QUICClient(self.relay_host, self.relay_port)
            self._client.set_handlers(
                on_stream_data=self._handle_stream_data,
                on_datagram=self._handle_datagram,
                on_close=self._handle_close,
            )

            connected = await self._client.connect()
            if not connected:
                logger.error("Failed to connect to relay")
                return False

            # Create MOQ session
            self._session = MOQSession(
                session_id=f"sub-{id(self)}", role=Role.SUBSCRIBER
            )
            self._session.set_send_callback(self._send_data)

            # Send SETUP
            setup_params = Parameters()
            if agent_id:
                setup_params.set(SETUP_AGENT_ID_PARAM, agent_id.encode("utf-8"))
            await self._session.send_setup(Role.SUBSCRIBER, parameters=setup_params)

            logger.info("Connected to relay")

            if self._on_connected:
                self._on_connected()

            # Start object processing task
            asyncio.create_task(self._process_objects())

            return True

        except Exception as e:
            logger.error(f"Error connecting to relay: {e}")
            return False

    def disconnect(self):
        """Disconnect from relay."""
        logger.info("Disconnecting from relay")

        if self._session:
            self._session.close()
            self._session = None

        if self._client:
            self._client.close()
            self._client = None

        if self._on_disconnected:
            self._on_disconnected()

    async def subscribe(
        self,
        track_name: FullTrackName,
        subscriber_priority: int = 128,
        start_group: Optional[int] = None,
        start_object: Optional[int] = None,
    ) -> bool:
        """
        Subscribe to a track.

        Args:
            track_name: Full track name to subscribe to
            subscriber_priority: Priority for this subscription (0-255)
            start_group: Starting group ID (None for latest)
            start_object: Starting object ID (None for latest)

        Returns:
            True if subscription initiated successfully
        """
        if not self._session:
            logger.error("Not connected")
            return False

        if track_name in self._subscriptions:
            logger.warning(f"Already subscribed to track: {track_name}")
            return False

        logger.info(f"Subscribing to track: {track_name}")

        from moq.messages import SubscribeFilter, GroupOrder

        # Determine filter type
        if start_group is None:
            filter_type = SubscribeFilter.LATEST_OBJECT
        else:
            filter_type = SubscribeFilter.ABSOLUTE_START

        # Send SUBSCRIBE message
        request_id = await self._session.subscribe(
            track_name=track_name,
            subscriber_priority=subscriber_priority,
            group_order=GroupOrder.ASCENDING,
            filter_type=filter_type,
            start_group=start_group,
            start_object=start_object,
        )

        self._subscriptions[track_name] = request_id

        return True

    async def unsubscribe(self, track_name: FullTrackName):
        """Unsubscribe from a track."""
        if track_name not in self._subscriptions:
            logger.warning(f"Not subscribed to track: {track_name}")
            return

        request_id = self._subscriptions[track_name]

        logger.info(f"Unsubscribing from track: {track_name}")

        # TODO: Send unsubscribe message when available in protocol

        if request_id in self._active_subscriptions:
            del self._active_subscriptions[request_id]

        del self._subscriptions[track_name]

    async def fetch(
        self,
        track_name: FullTrackName,
        start_group: int = 0,
        start_object: int = 0,
        end_group: Optional[int] = None,
        end_object: Optional[int] = None,
        subscriber_priority: int = 128,
    ) -> int:
        """
        Fetch specific objects from a track.

        Args:
            track_name: The track to fetch from
            start_group: Starting group ID (defaults to 0)
            start_object: Starting object ID (defaults to 0)
            end_group: Ending group ID (None means fetch until latest)
            end_object: Ending object ID (None means fetch until latest)
            subscriber_priority: Priority level (0-255)

        Returns:
            Request ID of the fetch
        """
        if not self._session:
            logger.error("Not connected")
            return -1

        logger.info(
            f"Fetching from track: {track_name}, range=[{start_group}:{start_object} to {end_group}:{end_object}]"
        )

        request_id = await self._session.fetch(
            track_name=track_name,
            start_group=start_group,
            start_object=start_object,
            end_group=end_group,
            end_object=end_object,
            subscriber_priority=subscriber_priority,
        )

        return request_id

    async def _send_data(self, data: bytes):
        """Send data over QUIC control stream."""
        if self._client:
            # Use stream 0 for control messages
            await self._client.send_stream_data(0, data)

    async def _handle_stream_data(self, protocol, data: StreamData):
        """Handle incoming stream data."""
        logger.debug(
            f"Received stream data: stream_id={data.stream_id}, length={len(data.data)}, end_stream={data.end_stream}"
        )

        if data.stream_id == 0:
            # Control stream
            await self._handle_control_data(data.data, end_stream=data.end_stream)
        else:
            # Data stream - accumulate data and process incrementally
            if data.stream_id not in self._stream_buffers:
                self._stream_buffers[data.stream_id] = b""
                self._stream_parser_state[data.stream_id] = {
                    "stage": "init",  # init -> type -> header -> objects
                    "type": None,
                    "header": None,
                    "objects": [],  # Track parsed object IDs to avoid duplicates
                }
            self._stream_buffers[data.stream_id] += data.data

            logger.debug(
                f"[STREAM] stream_id={data.stream_id} accumulated {len(self._stream_buffers[data.stream_id])} bytes, end_stream={data.end_stream}"
            )

            # Process available data immediately for streaming mode
            # This handles the case where end_stream may never be set
            await self._process_stream_buffer_incremental(data.stream_id)

            if data.end_stream:
                # Process any remaining data and clean up
                await self._process_stream_buffer_incremental(
                    data.stream_id, force=True
                )
                if data.stream_id in self._stream_buffers:
                    del self._stream_buffers[data.stream_id]
                if data.stream_id in self._stream_parser_state:
                    del self._stream_parser_state[data.stream_id]
                logger.debug(f"[STREAM] Stream ended: stream_id={data.stream_id}")

    async def _handle_control_data(self, data: bytes, end_stream: bool = False):
        """Handle control message data."""
        self._control_buffer += data

        while self._control_buffer:
            try:
                from moq.messages import decode_control_message

                msg, consumed = decode_control_message(self._control_buffer)
            except Exception as e:
                if end_stream:
                    logger.warning(f"Failed to decode control message: {e}")
                    self._control_buffer = b""
                break

            if isinstance(msg, SubscribeOkMessage):
                self._handle_subscribe_ok(msg)
            elif isinstance(msg, RequestErrorMessage):
                self._handle_request_error(msg)
            elif isinstance(msg, FetchOkMessage):
                self._handle_fetch_ok(msg)

            self._control_buffer = self._control_buffer[consumed:]

    def _handle_subscribe_ok(self, msg: SubscribeOkMessage):
        """Handle SUBSCRIBE_OK message."""
        logger.info(f"Subscription accepted: request_id={msg.request_id}")

        if self._session:
            self._session.handle_subscribe_ok(msg)

            subscription = self._session.get_subscription(msg.request_id)
            if subscription:
                track_name = subscription.full_track_name
                self._active_subscriptions[msg.request_id] = track_name
                self._track_aliases[subscription.track_alias] = track_name

                if self._on_subscription_accepted:
                    self._on_subscription_accepted(track_name)

    def _handle_request_error(self, msg: RequestErrorMessage):
        """Handle REQUEST_ERROR message."""
        logger.warning(
            f"Request error: request_id={msg.request_id}, code={msg.error_code}, reason={msg.reason}"
        )

        if self._session:
            self._session.handle_request_error(msg)

            subscription = self._session.get_subscription(msg.request_id)
            if subscription:
                track_name = subscription.full_track_name

                if track_name in self._subscriptions:
                    del self._subscriptions[track_name]

                if self._on_subscription_rejected:
                    self._on_subscription_rejected(track_name, msg.reason)

    def _handle_fetch_ok(self, msg: FetchOkMessage):
        """Handle FETCH_OK message."""
        logger.info(f"Fetch accepted: request_id={msg.request_id}")

        if self._session:
            fetch_request = self._session.fetches.get(msg.request_id)
            if fetch_request:
                track_name = fetch_request.full_track_name
                track_alias = self._session.track_aliases.get(track_name)
                if track_alias is not None:
                    self._track_aliases[track_alias] = track_name

    async def _process_stream_buffer_incremental(
        self, stream_id: int, force: bool = False
    ):
        """Process accumulated stream data incrementally."""
        buffer = self._stream_buffers.get(stream_id, b"")
        if not buffer:
            return

        state = self._stream_parser_state.get(stream_id)
        if not state:
            return

        try:
            stage = state["stage"]
            offset = 0

            # Stage 1: Parse stream type
            if stage == "init":
                stream_type, consumed = VarInt.decode(buffer, offset)
                offset += consumed
                state["type"] = stream_type
                state["stage"] = "type"
                stage = "type"
                logger.debug(f"[STREAM] stream_id={stream_id} type={stream_type}")

                # Update buffer to remove processed bytes
                buffer = buffer[offset:]
                self._stream_buffers[stream_id] = buffer
                offset = 0

            if stage == "type":
                if state["type"] == StreamType.SUBGROUP_HEADER:
                    state["stage"] = "header"
                    stage = "header"
                elif state["type"] == StreamType.FETCH_HEADER:
                    # Fetch streams wait for end_stream
                    if force:
                        _, consumed = VarInt.decode(buffer, 0)
                        await self._handle_fetch_stream(stream_id, buffer, consumed)
                    return
                else:
                    logger.warning(f"Unknown stream type: {state['type']}")
                    return

            if stage == "header" or stage == "objects":
                processed = await self._process_subgroup_stream_incremental(
                    stream_id, buffer, state, force
                )

                # Update buffer to remove processed data
                if processed > 0:
                    new_buffer = buffer[processed:]
                    self._stream_buffers[stream_id] = new_buffer
                    logger.debug(
                        f"[STREAM] Removed {processed} bytes, {len(new_buffer)} remaining"
                    )

        except Exception as e:
            # Not enough data yet to parse current stage
            logger.debug(f"[STREAM] Cannot decode stream stage {state['stage']}: {e}")

    async def _process_subgroup_stream_incremental(
        self, stream_id: int, data: bytes, state: Dict, force: bool = False
    ) -> int:
        """Process subgroup stream data incrementally with support for large payloads.

        Returns:
            Number of bytes processed from the data buffer.
        """
        try:
            offset = 0
            initial_len = len(data)

            # Stage: Parse header if not already done
            if state["stage"] == "header":
                try:
                    header, consumed = SubgroupHeader.decode(data, offset)
                    state["header"] = header
                    state["stage"] = "objects"
                    state["parsed_objects"] = set()
                    state["current_object"] = None
                    offset += consumed
                    logger.debug(
                        f"[STREAM] Parsed subgroup header: track_alias={header.track_alias}, group={header.group_id}"
                    )
                except Exception as e:
                    # Not enough data for header
                    logger.debug(f"[STREAM] Incomplete header: {e}")
                    return 0

            header = state["header"]
            if not header:
                return 0

            track_name = self._track_aliases.get(header.track_alias)
            if not track_name:
                logger.warning(f"Unknown track alias: {header.track_alias}")
                return 0

            # Get or initialize state
            if "parsed_objects" not in state:
                state["parsed_objects"] = set()
            if "current_object" not in state:
                state["current_object"] = None

            parsed_objects = state["parsed_objects"]
            current_object = state["current_object"]
            objects_parsed = 0

            # Process current partial object first if exists
            if current_object:
                remaining = (
                    current_object["payload_len"] - current_object["payload_received"]
                )
                available = len(data) - offset

                if available >= remaining:
                    # Complete the partial object
                    current_object["payload"] += data[offset : offset + remaining]
                    current_object["payload_received"] = current_object["payload_len"]
                    offset += remaining

                    obj = ReceivedObject(
                        track_alias=header.track_alias,
                        group_id=header.group_id,
                        object_id=current_object["id"],
                        publisher_priority=header.publisher_priority,
                        payload=current_object["payload"],
                        object_status=0x00,
                    )

                    obj_key = (current_object["id"], header.group_id)
                    if obj_key not in parsed_objects:
                        await self._object_queue.put(obj)
                        parsed_objects.add(obj_key)
                        objects_parsed += 1

                    state["current_object"] = None
                    current_object = None
                else:
                    # Still incomplete, accumulate what we have
                    current_object["payload"] += data[offset:]
                    current_object["payload_received"] += available
                    offset = len(data)
                    state["current_object"] = current_object
                    # Return all bytes as consumed (we kept the data in current_object)
                    return initial_len

            # Process new objects
            while offset < len(data):
                obj_start = offset
                try:
                    object_id, consumed = VarInt.decode(data, offset)
                    offset += consumed

                    next_val, consumed = VarInt.decode(data, offset)
                    offset += consumed

                    if next_val in (0x10, 0x11, 0x12, 0x13):  # ObjectStatus values
                        # Status-only object
                        obj = ReceivedObject(
                            track_alias=header.track_alias,
                            group_id=header.group_id,
                            object_id=object_id,
                            publisher_priority=header.publisher_priority,
                            payload=b"",
                            object_status=next_val,
                        )

                        obj_key = (object_id, header.group_id)
                        if obj_key not in parsed_objects:
                            await self._object_queue.put(obj)
                            parsed_objects.add(obj_key)
                            objects_parsed += 1

                    else:
                        # Object with payload
                        payload_len = next_val
                        payload_start = offset
                        available = len(data) - payload_start

                        if available >= payload_len:
                            # Complete object in buffer
                            payload = data[payload_start : payload_start + payload_len]
                            offset += payload_len

                            obj = ReceivedObject(
                                track_alias=header.track_alias,
                                group_id=header.group_id,
                                object_id=object_id,
                                publisher_priority=header.publisher_priority,
                                payload=payload,
                                object_status=0x00,
                            )

                            obj_key = (object_id, header.group_id)
                            if obj_key not in parsed_objects:
                                await self._object_queue.put(obj)
                                parsed_objects.add(obj_key)
                                objects_parsed += 1

                        else:
                            # Partial object - start tracking
                            state["current_object"] = {
                                "id": object_id,
                                "payload_len": payload_len,
                                "payload_received": available,
                                "payload": data[payload_start:],
                            }
                            offset = len(data)
                            break

                except Exception as e:
                    logger.debug(f"[STREAM] Cannot parse object at {obj_start}: {e}")
                    offset = obj_start
                    break

            logger.debug(f"[STREAM] Processed {objects_parsed} objects, {offset} bytes")
            return offset

        except Exception as e:
            logger.debug(f"[STREAM] Failed to process subgroup stream: {e}")
            return 0

    async def _handle_datagram(self, protocol, data: DatagramData):
        """Handle incoming datagram."""
        try:
            datagram, _ = ObjectDatagram.decode(data.data)

            track_name = self._track_aliases.get(datagram.header.track_alias)
            if not track_name:
                logger.warning(f"Unknown track alias: {datagram.header.track_alias}")
                return

            received_obj = ReceivedObject(
                track_alias=datagram.header.track_alias,
                group_id=datagram.header.group_id,
                object_id=datagram.header.object_id,
                publisher_priority=datagram.header.publisher_priority,
                payload=datagram.payload,
                object_status=datagram.header.object_status,
            )

            await self._object_queue.put(received_obj)

        except Exception as e:
            logger.warning(f"Failed to handle datagram: {e}")

    async def _handle_close(self, protocol, error_code: int, reason: str):
        """Handle connection close."""
        logger.info(f"Connection closed: error={error_code}, reason={reason}")
        self.disconnect()

    async def _process_objects(self):
        """Process received objects from queue."""
        while True:
            try:
                obj = await self._object_queue.get()

                if self._on_object_received:
                    self._on_object_received(obj)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing object: {e}")

    def get_active_subscriptions(self) -> List[FullTrackName]:
        """Get list of currently subscribed tracks."""
        return list(self._subscriptions.keys())

    def is_subscribed(self, track_name: FullTrackName) -> bool:
        """Check if subscribed to track."""
        return track_name in self._subscriptions

    async def get_next_object(
        self, timeout: Optional[float] = None
    ) -> Optional[ReceivedObject]:
        """Get next received object from queue."""
        try:
            return await asyncio.wait_for(self._object_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
