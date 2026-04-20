# Frontend API Summary

This document summarizes the API surface a replacement frontend should use in this project.

It is based on the actual code in `backend/app/main.py` and the current React frontend in `frontend/src`, not only on the older `API.md`.

## 1. Base URLs

### Main web UI backend

- HTTP: `http://<host>:9005`
- WebSocket: `ws://<host>:9005/ws`

This is the backend that serves the current React app and exposes the live `/api/*` routes.

### Separate video service modules

The repository also contains standalone video HTTP APIs in:

- `backend/app/video_http_server.py`
- `backend/app/video_service.py`

Those files define routes such as `/video/stream/{track_id}/mjpeg` and `/video/stream/{track_id}/info`, but they are not mounted inside `backend/app/main.py`.

If you build another frontend against the main app on port `9005`, do not assume those `/api/video/stream/*` routes exist unless the backend is changed to include them.

## 2. What The Current Frontend Actually Uses

### Live integrations used by `App.jsx`

- WebSocket `/ws`
- `GET /api/logs`

### Code exists but is not currently wired into the main screen

- `GET /api/video/stream/{track_id}/info`
- `GET /api/video/stream/{track_id}/mjpeg`
- `POST /api/video/webrtc/offer`

Those calls appear in reusable video components/hooks, but those components are not imported into `App.jsx` today.

## 3. Main Backend REST APIs On Port 9005

### `GET /api/health`

Purpose:
- Health check

Response:

```json
{
  "status": "healthy",
  "timestamp": "2026-04-20T10:00:00.000000",
  "websocket_clients": 1
}
```

### `GET /api/agents`

Purpose:
- Returns all agents from SQLite
- Used as the base agent list sent over WebSocket

Response:

```json
{
  "agents": [
    {
      "agent_id": "did:acn:agent:001",
      "agent_name": "Drone Alpha",
      "agent_status": "online",
      "agent_capability": ["surveillance", "tracking"],
      "priority": 5,
      "work_status": "working"
    }
  ],
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

Notes:
- `agent_status` is derived partly from DB state.
- `agent_capability` may be parsed from JSON stored in the DB.

### `GET /api/logs?limit=100`

Purpose:
- Returns backend log buffer
- Used by the current debug panel

Response:

```json
{
  "logs": [
    {
      "time": "2026-04-20T10:00:00.000000",
      "level": "info",
      "message": "ACF subscribe_track received: agent=... task=... tracks=1"
    }
  ],
  "total": 1,
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

### `GET /api/moq/status`

Purpose:
- Returns MoQ subscriber state

Response:

```json
{
  "status": "available",
  "connected": true,
  "relay_host": "localhost",
  "relay_port": 9003,
  "subscribed_tracks": ["did:acn:agent:001_task-123_video"],
  "subscription_debug": {},
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

### `POST /api/moq/subscribe`

Purpose:
- Manually subscribe to a MoQ track

Request body:

```json
{
  "track_id": "did:acn:agent:001_task-123_video",
  "namespace": ["task-123", "did:acn:agent:001"],
  "track_name": "Video"
}
```

Success response:

```json
{
  "status": "success",
  "track_id": "did:acn:agent:001_task-123_video",
  "namespace": ["task-123", "did:acn:agent:001"],
  "track_name": "Video",
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

### `POST /api/moq/unsubscribe/{track_id}`

Purpose:
- Unsubscribe one MoQ track

Response:

```json
{
  "status": "success",
  "track_id": "did:acn:agent:001_task-123_video",
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

### `GET /api/moq/tracks/{track_id}/frames?limit=10`

Purpose:
- Debug endpoint for recent received frames

Response:

```json
{
  "track_id": "did:acn:agent:001_task-123_video",
  "frame_count": 30,
  "frames": [
    {
      "group_id": 1,
      "object_id": 5,
      "timestamp": "2026-04-20T10:00:00.000000",
      "frame_type": "keyframe",
      "payload_size": 45000
    }
  ],
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

### `POST /api/moq/auto-subscribe/{agent_id}`

Purpose:
- Deprecated endpoint

Actual behavior:
- Returns a warning and tells callers to use `/api/acn/v3/subscribe_track`

### `POST /api/acn/v3/subscribe_track`

Purpose:
- Main entrypoint for ACF to announce track metadata
- Backend filters video tracks and subscribes to them automatically
- On success, backend also broadcasts `VIDEO_TRACKS_AVAILABLE` over WebSocket

Accepted body shapes:
- Direct payload
- Nested `{ "body": { ... } }`
- Several key aliases for `track_list`

Typical request body:

```json
{
  "body": {
    "payload": {
      "src_agent_id": "ACF",
      "dst_agent_id": "did:acn:agent:001",
      "task_id": "task-123",
      "track_list": [
        {
          "namespace": "/task-123/did:acn:agent:001",
          "track": "Video"
        }
      ]
    }
  }
}
```

Typical response:

```json
{
  "status": "success",
  "agent_id": "did:acn:agent:001",
  "task_id": "task-123",
  "total_tracks": 1,
  "video_tracks": [
    {
      "track_id": "did:acn:agent:001_task-123_video",
      "namespace": "/task-123/did:acn:agent:001",
      "track_name": "Video",
      "success": true
    }
  ],
  "subscribed_count": 1,
  "subscription_debug": {},
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

## 4. Inbound Event APIs From Other Services

These are not called by the React frontend. They are called by upstream ACN services, and the backend converts them into WebSocket pushes for the UI.

### `POST /acn/v3/pipeline-logs`

Purpose:
- Sends message-flow events into the UI

Accepted request shape:

```json
{
  "source": "Agent GW",
  "destination": "IDM",
  "timestamp": "2026-04-20T10:00:00Z",
  "task_id": "task-123",
  "protocol": "HTTP/2",
  "headers": {
    "Content-Type": "application/json"
  },
  "abstract": "Register agent identity",
  "content": {
    "agent_id": "did:acn:agent:001",
    "agent_name": "Drone Alpha"
  }
}
```

Also supported:

```json
{
  "body": {
    "...": "same fields"
  }
}
```

Response:

```json
{
  "status": "success",
  "message": "Log received and broadcasted",
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

Side effects:
- Adds an item into `/api/logs`
- Broadcasts `PIPELINE_LOG`
- May also broadcast `AGENT_STATUS_UPDATE` if `abstract` maps to a known status

### `POST /acn/v3/element-logs`

Purpose:
- Sends per-agent status updates into the UI

Request body:

```json
{
  "element_id": "IDM",
  "log_type": "ApplyProfile",
  "timestamp": "2026-04-20T10:00:00Z",
  "content": {
    "agent_id": "did:acn:agent:001",
    "agent_name": "Drone Alpha",
    "agent_capability": ["surveillance", "tracking"]
  }
}
```

Also supported:

```json
{
  "body": {
    "...": "same fields"
  }
}
```

Response:

```json
{
  "status": "success",
  "message": "Element log received and agent status updated",
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

Side effects:
- Adds an item into `/api/logs`
- Updates in-memory agent status cache
- Broadcasts `AGENT_STATUS_UPDATE`

## 5. WebSocket Contract

Endpoint:

- `ws://<host>:9005/ws`

### Messages client can send

#### `PING`

```json
{
  "type": "PING"
}
```

Server reply:

```json
{
  "type": "PONG",
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

#### `DISPATCH_TASK`

Purpose:
- UI-originated control event
- Backend only re-broadcasts it; there is no deeper task execution API behind it here

Example:

```json
{
  "type": "DISPATCH_TASK",
  "payload": {
    "agentId": "did:acn:agent:001",
    "taskType": "tracking",
    "description": "Track target",
    "timestamp": "2026-04-20T10:00:00.000000"
  }
}
```

Broadcast result:

```json
{
  "type": "TASK_DISPATCHED",
  "payload": {
    "...": "same payload"
  }
}
```

#### `EMERGENCY_LAND`

```json
{
  "type": "EMERGENCY_LAND",
  "payload": {
    "timestamp": "2026-04-20T10:00:00.000000"
  }
}
```

Broadcast result:

```json
{
  "type": "EMERGENCY_LAND",
  "payload": {
    "timestamp": "2026-04-20T10:00:00.000000"
  }
}
```

#### `ABORT_ALL`

```json
{
  "type": "ABORT_ALL",
  "payload": {
    "timestamp": "2026-04-20T10:00:00.000000"
  }
}
```

Broadcast result:

```json
{
  "type": "ABORT_ALL",
  "payload": {
    "timestamp": "2026-04-20T10:00:00.000000"
  }
}
```

#### `REFRESH`

Purpose:
- Triggers backend call to ARF `/clear`

Example:

```json
{
  "type": "REFRESH",
  "payload": {
    "timestamp": "2026-04-20T10:00:00.000000"
  }
}
```

Success broadcast:

```json
{
  "type": "REFRESH_COMPLETE",
  "payload": {
    "timestamp": "2026-04-20T10:00:00.000000",
    "agents": [],
    "arf_response": {}
  }
}
```

Failure reply to requester:

```json
{
  "type": "REFRESH_ERROR",
  "payload": {
    "timestamp": "2026-04-20T10:00:00.000000",
    "error": "Cannot connect to ARF service",
    "detail": "..."
  }
}
```

### Messages server pushes

#### `AGENT_LIST`

Sent:
- Immediately after WebSocket connect
- Periodically every second while clients are connected

Shape:

```json
{
  "type": "AGENT_LIST",
  "payload": {
    "agents": []
  }
}
```

#### `PIPELINE_LOG`

Shape:

```json
{
  "type": "PIPELINE_LOG",
  "payload": {
    "source": "Agent GW",
    "destination": "IDM",
    "timestamp": "2026-04-20T10:00:00Z",
    "task_id": "task-123",
    "protocol": "HTTP/2",
    "headers": {},
    "abstract": "Register agent identity",
    "content": {}
  }
}
```

#### `AGENT_STATUS_UPDATE`

Shape:

```json
{
  "type": "AGENT_STATUS_UPDATE",
  "payload": {
    "agent_id": "did:acn:agent:001",
    "agent_name": "Drone Alpha",
    "work_status": "working",
    "current_task": "Applying for digital identity",
    "log_type": "ApplyProfile",
    "element_id": "IDM",
    "timestamp": "2026-04-20T10:00:00Z",
    "agent": {}
  }
}
```

#### `VIDEO_TRACKS_AVAILABLE`

Triggered by:
- `POST /api/acn/v3/subscribe_track`

Shape:

```json
{
  "type": "VIDEO_TRACKS_AVAILABLE",
  "payload": {
    "agent_id": "did:acn:agent:001",
    "task_id": "task-123",
    "tracks": [
      {
        "track_id": "did:acn:agent:001_task-123_video",
        "namespace": "/task-123/did:acn:agent:001",
        "track_name": "Video",
        "success": true
      }
    ],
    "timestamp": "2026-04-20T10:00:00.000000"
  }
}
```

#### `VIDEO_FRAME`

Triggered by:
- Incoming MoQ video frames

Shape:

```json
{
  "type": "VIDEO_FRAME",
  "payload": {
    "track_id": "did:acn:agent:001_task-123_video",
    "group_id": 1,
    "object_id": 5,
    "timestamp": "2026-04-20T10:00:00.000000",
    "frame_type": "keyframe",
    "payload_size": 45000,
    "mime_type": "image/jpeg",
    "codec": null,
    "payload_base64": "...",
    "data_url": "data:image/jpeg;base64,..."
  }
}
```

Notes:
- `mime_type` can be `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `video/h264`, or `application/octet-stream`.
- The current UI renders images directly from `data_url`.
- For `video/h264`, the current main app pushes the encoded payload over WebSocket but does not expose a stable mounted HTTP playback endpoint on port `9005`.

#### `VIDEO_STREAM_LIST`

Shape:

```json
{
  "type": "VIDEO_STREAM_LIST",
  "payload": {
    "streams": []
  }
}
```

#### `VIDEO_STREAM_UPDATE`

Shape:

```json
{
  "type": "VIDEO_STREAM_UPDATE",
  "payload": {
    "stream_id": "agent001_camera",
    "agent_id": "agent001",
    "agent_name": "Drone Alpha",
    "stream_type": "camera",
    "status": "streaming",
    "resolution": "1920x1080",
    "fps": 30,
    "bitrate": 4500,
    "viewers": 0
  }
}
```

#### `WEBRTC_ICE_CANDIDATE`

Shape:

```json
{
  "type": "WEBRTC_ICE_CANDIDATE",
  "payload": {
    "stream_id": "agent001_camera",
    "candidate": {},
    "from_agent": true
  }
}
```

Note:
- The frontend hook also listens for `WEBRTC_ANSWER`, but the backend in `main.py` does not currently broadcast that event.

## 6. Video Management APIs On Port 9005

These endpoints are present in `main.py`, but the current `App.jsx` does not actively call them.

### `GET /api/video/streams`

Response:

```json
{
  "streams": [
    {
      "stream_id": "agent001_camera",
      "agent_id": "agent001",
      "agent_name": "Drone Alpha",
      "stream_type": "camera",
      "status": "idle",
      "resolution": "1920x1080",
      "fps": 30,
      "bitrate": 4500,
      "viewers": 0
    }
  ],
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

### `GET /api/video/streams/{agent_id}`

Response:

```json
{
  "agent_id": "agent001",
  "streams": [],
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

### `POST /api/video/streams/{agent_id}/register`

Request body:

```json
{
  "agent_name": "Drone Alpha",
  "stream_type": "camera",
  "resolution": "1920x1080",
  "fps": 30
}
```

Response:

```json
{
  "status": "success",
  "stream": {
    "stream_id": "agent001_camera",
    "agent_id": "agent001",
    "agent_name": "Drone Alpha",
    "stream_type": "camera",
    "status": "idle",
    "resolution": "1920x1080",
    "fps": 30,
    "bitrate": 4500,
    "viewers": 0
  },
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

### `POST /api/video/webrtc/offer`

Request body:

```json
{
  "stream_id": "agent001_camera",
  "offer": {}
}
```

Behavior:
- Saves the offer in memory
- Broadcasts `VIDEO_STREAM_UPDATE`
- Returns success only if the stream already exists

Important:
- Despite the frontend comments, this endpoint behaves like "register viewer or agent SDP state in memory", not a full WebRTC signaling implementation.

### `POST /api/video/webrtc/answer`

Request body:

```json
{
  "stream_id": "agent001_camera",
  "answer": {}
}
```

Behavior:
- Saves the answer in memory
- Marks stream status as `streaming`
- Broadcasts `VIDEO_STREAM_UPDATE`

### `POST /api/video/webrtc/ice`

Request body:

```json
{
  "stream_id": "agent001_camera",
  "candidate": {},
  "is_agent": true
}
```

Behavior:
- Stores ICE candidate in memory
- Broadcasts `WEBRTC_ICE_CANDIDATE`

### `DELETE /api/video/streams/{stream_id}`

Response:

```json
{
  "status": "success",
  "stream_id": "agent001_camera",
  "timestamp": "2026-04-20T10:00:00.000000"
}
```

## 7. Unmounted Or Auxiliary Video HTTP APIs

These routes exist in `video_http_server.py` and `video_service.py`, but they are not part of the main app route table in `backend/app/main.py`.

Defined routes include:

- `GET /video/stream/{track_id}/mjpeg`
- `GET /video/stream/{track_id}/latest`
- `GET /video/stream/{track_id}/info`
- `GET /video/streams`
- `POST /video/ingest/{track_id}`
- `GET /video/player/{track_id}`

There is also a separate MJPEG router in `mjpeg_server.py`:

- `GET /mjpeg/{track_id}`
- `GET /mjpeg/{track_id}/latest`
- `GET /mjpeg/{track_id}/status`
- `GET /mjpeg`

If a new frontend needs HTTP-based video playback, choose one of these approaches:

1. Mount `video_http_server.router` into the main FastAPI app under `/api`.
2. Run a separate video service and document its base URL independently.
3. Use only WebSocket `VIDEO_FRAME` messages for image-based rendering.

## 8. Recommended Integration For A New Frontend

If the goal is to replace the current React UI without changing backend behavior, use this contract first:

1. Open `ws://<host>:9005/ws`.
2. Treat `AGENT_LIST` as the source of truth for the agent roster.
3. Render message flow from `PIPELINE_LOG`.
4. Render work status from `AGENT_STATUS_UPDATE`.
5. Render MoQ track discovery from `VIDEO_TRACKS_AVAILABLE`.
6. Render image frames from `VIDEO_FRAME.data_url` when `mime_type` starts with `image/`.
7. Poll `GET /api/logs` only for debug tooling, not as the main data plane.

If the new frontend also needs MJPEG or snapshot URLs, backend changes are required before relying on `/api/video/stream/*` on port `9005`.
