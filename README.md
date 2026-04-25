# ACN WebUI

[中文说明](./README.zh-CN.md)

ACN WebUI is a FastAPI + React dashboard for monitoring ACN agents, tasks, network elements, backend logs, certificates, service lifecycle controls, and MOQ video tracks.

The main product path is the integrated WebUI on port `9005`. It serves the built frontend from the FastAPI backend and pushes live updates over WebSocket.

## Runtime Overview

- Main WebUI: `http://localhost:9005`
- Main WebSocket: `ws://localhost:9005/ws`
- Optional standalone video service: `http://localhost:9006`
- AgentGW `ARF`: `9001`
- AgentGW `ACF`: `9002`
- AgentGW `Relay`: `9003`
- ACN Agent status probe: `9010`
- IDM status probe: `9020`

## Current Architecture

### Main backend (`9005`)

The integrated backend lives in [backend/app/main.py](/root/lpx/webui/backend/app/main.py:1).

It is responsible for:
- serving the built React app
- exposing the dashboard APIs
- reading agents and tasks from the external SQLite database
- collecting backend and element logs
- filtering element-log display after WebUI clear without modifying source log files
- managing certificate upload/delete metadata and forwarding certificate requests to IDM
- running script-backed lifecycle controls for ACN Agent, AgentGW, and IDM
- managing MOQ track discovery, watch, unsubscribe, and browser playback
- pushing dashboard snapshots and task updates over WebSocket

Related backend modules:
- [backend/app/moq_video.py](/root/lpx/webui/backend/app/moq_video.py:1): MOQ subscriber, discovered-track registry, WebTransport bridge, MJPEG bridge state
- [backend/app/video_gateway.py](/root/lpx/webui/backend/app/video_gateway.py:1): shared video ingestion / frame / transcoding helper
- [backend/app/video_stream.py](/root/lpx/webui/backend/app/video_stream.py:1): older stream registry and WebRTC signaling helpers still exposed by `main.py`

### Optional standalone video service (`9006`)

The separate `9006` service lives in [backend/app/video_9006/service.py](/root/lpx/webui/backend/app/video_9006/service.py:1) and is started by [start_video_service.sh](/root/lpx/webui/start_video_service.sh:1).

This is not required for the main WebUI. It is a standalone video test/service path built on the shared [backend/app/video_gateway.py](/root/lpx/webui/backend/app/video_gateway.py:1).

Important:
- the React development server also uses port `9006`
- do not run `npm start` and `start_video_service.sh` at the same time unless you change one of the ports

## Project Layout

```text
webui/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── moq_video.py
│   │   ├── video_gateway.py
│   │   ├── video_stream.py
│   │   └── video_9006/
│   │       ├── __init__.py
│   │       └── service.py
│   ├── requirements.txt
│   └── start.sh
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── build/
├── logs/
├── test/
├── API.md
├── start_all.sh
└── start_video_service.sh
```

## Quick Start

### Recommended: run the integrated WebUI

```bash
cd /root/lpx/webui
./start_all.sh start
```

Useful commands:

```bash
./start_all.sh restart
./start_all.sh status
./start_all.sh logs
./start_all.sh stop
```

What `start_all.sh` does:
- builds the React frontend
- starts FastAPI on `9005`
- serves the built frontend from the backend

### Backend only

```bash
cd /root/lpx/webui/backend
/root/lpx/webui/.venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9005
```

### Frontend development mode

```bash
cd /root/lpx/webui/frontend
npm install
npm start
```

This starts the React development server on `http://localhost:9006`.

### Optional standalone video service on `9006`

```bash
cd /root/lpx/webui
./start_video_service.sh
```

It exposes:
- `GET /health`
- `GET /video/streams`
- `GET /video/player/{track_id}`
- `GET /video/stream/{track_id}/mjpeg`
- `GET /video/stream/{track_id}/latest`
- `GET /video/stream/{track_id}/info`
- `POST /video/ingest/{track_id}`

## Main API Surface (`9005`)

### Core

- `GET /api/health`
- `GET /api/agents`
- `GET /api/logs`
- `GET /api/network-element-logs`
- `GET /api/dashboard/overview`
- `WS /ws`

### Control

- `POST /api/control/clear`
- `GET /api/control/network-elements`
- `POST /api/control/network-elements/{element_id}/{action}`
- `POST /api/control/test-messages/topology-demo`
- `POST /api/control/test-messages/topology-demo/pause`
- `POST /api/control/test-messages/topology-demo/resume`
- `POST /api/control/test-messages/full-demo`
- `GET /api/control/tasks`
- `POST /api/control/tasks`
- `POST /api/control/tasks/{task_id}/stop`

Network element lifecycle actions support:
- `element_id`: `acn-agent`, `agent-gw`, `idm`, or `all`
- `action`: `start`, `stop`, or `restart`
- `all/start` starts only elements currently shown as offline
- `all/restart` restarts all managed elements

The backend executes these scripts:
- ACN Agent: `/home/acn/cxr/acn_agent/start_acn_agent.sh`
- AgentGW: `/home/acn/zqm/acn_gw/start_agent_gw.sh`
- IDM: `/home/acn/cx/idm/start_idm.sh`

The WebUI asks for secondary confirmation before stop/restart actions. Start is enabled only for offline elements.

### Settings

- `GET /api/settings/data-source`
- `POST /api/settings/data-source`
- `GET /api/settings/certificates`
- `POST /api/settings/certificates/upload`
- `DELETE /api/settings/certificates/{cert_id}`
- `GET /api/settings/direct-demo-camera`
- `POST /api/settings/direct-demo-camera`
- `POST /api/settings/virtual-agents`

Certificate upload behavior:
- backend decodes uploaded cert files as X.509
- stores metadata in the local WebUI certificate DB only after IDM returns `200 OK`
- forwards certificate upload/delete requests to IDM
- failed IDM responses are shown in the WebUI and logged in backend logs

### MOQ / video track management

- `GET /api/moq/status`
- `GET /api/moq/tracks`
- `POST /api/moq/tracks`
- `DELETE /api/moq/tracks/{track_id}`
- `POST /api/moq/subscribe`
- `POST /api/moq/watch/{track_id}`
- `POST /api/moq/unsubscribe/{track_id}`
- `GET /api/moq/tracks/{track_id}/frames`
- `POST /api/moq/auto-subscribe/{agent_id}`
- `POST /api/acn/v3/subscribe_track`

### Video playback endpoints

- `GET /api/video/stream/{track_id}/mjpeg`
- `GET /api/video/stream/{track_id}/latest`
- `GET /api/video/stream/{track_id}/info`

### Older stream / WebRTC endpoints

These are still exposed from `main.py`, but they are not the primary MOQ/WebUI path:

- `GET /api/video/streams`
- `GET /api/video/streams/{agent_id}`
- `POST /api/video/streams/{agent_id}/register`
- `DELETE /api/video/streams/{stream_id}`
- `POST /api/video/webrtc/offer`
- `POST /api/video/webrtc/answer`
- `POST /api/video/webrtc/ice`

### Incoming ACN callbacks

- `POST /acn/v3/pipeline-logs`
- `POST /acn/v3/element-logs`

More detail is in [API.md](/root/lpx/webui/API.md:1).

## Data Sources

The dashboard is not self-contained. The current backend reads from external services and files:

- agent/task database:
  - `/home/acn/zqm/acn_gw/agent_gw/agent_gw.db`
- ACN Agent log:
  - `/home/acn/cxr/acn_agent/.acn_agent.log`
- AgentGW logs:
  - `/home/acn/zqm/acn_gw/agent_gw/logs`
- IDM logs:
  - `/home/acn/cx/idm/logs`
- ARF clear endpoint:
  - `http://localhost:9001/clear`
- WebUI local state DB:
  - `logs/webui_local_state.db`
- WebUI certificate DB:
  - `logs/certificates.db`
- WebUI certificate file cache:
  - `logs/cert_store`
- WebUI runtime settings:
  - `logs/data_source_settings.json`
  - `logs/direct_demo_settings.json`

Important log behavior:
- source element logs are never truncated or deleted by WebUI clear
- after a successful `/api/control/clear`, the WebUI records current source log offsets in memory
- `/api/network-element-logs` then returns only lines appended after that clear point
- restarting the WebUI backend resets those in-memory cutoffs, so older file-backed logs can appear again

## How Agent And Task Data Refresh

### Agents

- the database `agents` table is the source of truth for which agents exist
- the backend rebuilds dashboard agent data from the DB plus transient runtime cache
- the frontend mostly follows `GET /api/dashboard/overview` and `DASHBOARD_SNAPSHOT` WebSocket pushes

### Tasks

- active tasks come from the database `tasks` table
- the backend combines DB tasks with in-memory task metadata and recent finished-task history
- the frontend polls `GET /api/control/tasks` and also reacts to `TASKS_UPDATED` WebSocket pushes

This means there is no direct SQLite change watcher. Sync is done by repeated backend reads plus WebSocket events generated by the backend.

## Video / MOQ Notes

The current WebUI video flow is:

1. a publisher announces or publishes a MOQ track
2. the backend discovers or manually registers that track
3. the Agents page shows the track card
4. clicking `Watch` triggers `POST /api/moq/watch/{track_id}`
5. the backend subscribes to the real MOQ track using the saved `namespace` and `trackName`
6. the browser renders via the WebUI playback bridge

The Manage Track form can add or delete track cards. A manually added track only works if its `namespace` and `trackName` match the real published MOQ track.

## Tests

The current test guidance is in [test/README_TEST.md](/root/lpx/webui/test/README_TEST.md:1).

Most useful current paths:

### Dashboard message/demo flow

```bash
cd /root/lpx/webui
python3 test/test_messages.py --topology-demo --host 127.0.0.1 --port 9005
python3 test/test_messages.py --full-demo --host 127.0.0.1 --port 9005
```

### Manual MOQ WebUI video demo

```bash
cd /root/lpx/webui
./test/run_moq_video_ui_demo.sh start
./test/run_moq_video_ui_demo.sh status
./test/run_moq_video_ui_demo.sh stop
```

### Automated MOQ WebUI E2E

```bash
cd /root/lpx/webui
python3 test/moq_video_webui_e2e.py
```

## Logs

Useful runtime logs:
- backend log: `logs/backend.log`
- frontend build log: `logs/frontend_build.log`
- MOQ manual demo log: `logs/moq_video_ui_demo.log`

## Common Problems

### WebUI does not start

Check:

```bash
./start_all.sh status
tail -f logs/backend.log
tail -f logs/frontend_build.log
```

### Frontend dev mode conflicts with the standalone video service

Both want port `9006`.

Use one of these at a time:
- `cd frontend && npm start`
- `./start_video_service.sh`

### MOQ track card exists but playback does not start

Check:

```bash
curl -s http://localhost:9005/api/moq/tracks | python3 -m json.tool
curl -s http://localhost:9005/api/video/stream/<track_id>/info | python3 -m json.tool
```

Look at:
- `watchState`
- `has_metadata`
- `has_init_segment`
- `fragment_count`
- `has_frame`

### Overview status looks wrong

The Network Element Status cards only show local port reachability. A process can still be unhealthy while showing `online`.

### Clear does not fully remove visible agents

The backend merges database-backed identity with runtime cache. If the external AgentGW/ARF side still represents those agents, they can reappear after refresh.

## Notes

- the current dashboard supports English and Chinese
- the default product path is the integrated `9005` WebUI
- the `9006` service is optional and mainly useful for standalone video testing
