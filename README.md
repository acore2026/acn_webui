# ACN WebUI

ACN WebUI is a FastAPI + React dashboard for monitoring ACN agents, network elements, task activity, backend logs, and live message flow between `ACN SDK`, `ACN Agent`, `IDM`, and `AgentGW`.

It serves a built frontend from the FastAPI backend on port `9005` and uses WebSocket updates for live dashboard refreshes.

## What It Does

- Overview dashboard with live metrics, network element status, React Flow topology, and system events
- Agent roster with per-agent detail modal
- Network page with backend logs and per-element log viewers
- Control page for clear/demo actions and task dispatch/stop
- WebSocket-driven live updates for agents, dashboard snapshots, and task changes
- Receives external pipeline and element logs through ACN callback endpoints

## Runtime Ports

- WebUI API: `http://localhost:9005`
- WebUI WebSocket: `ws://localhost:9005/ws`
- ACN Agent status probe: `9010`
- AgentGW services:
  - `ARF`: `9001`
  - `ACF`: `9002`
  - `Relay`: `9003`
- IDM status probe: `9020`

## Project Layout

```text
webui/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── moq_video.py
│   │   └── video_stream.py
│   ├── requirements.txt
│   └── start.sh
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── dashboard/
│   │   │   ├── components/
│   │   │   ├── pages/
│   │   │   ├── i18n.ts
│   │   │   └── types.ts
│   │   ├── styles/
│   │   ├── App.tsx
│   │   └── index.tsx
│   ├── package.json
│   └── build/
├── logs/
├── test/
├── API.md
└── start_all.sh
```

## Stack

### Frontend

- React 18
- TypeScript
- Tailwind CSS
- `@xyflow/react` for topology/message-flow diagrams

### Backend

- FastAPI
- WebSockets
- `httpx`
- SQLite-backed agent/task reads
- Uvicorn

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

The script:

- builds the React frontend
- starts the FastAPI backend on `9005`
- serves the built frontend from the backend

### Frontend development mode

```bash
cd /root/lpx/webui/frontend
npm install
npm start
```

This starts the React dev server on `http://localhost:9006`.

### Backend only

```bash
cd /root/lpx/webui/backend
/root/lpx/webui/.venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9005
```

## Main API Surface

### Core

- `GET /api/health`
- `GET /api/agents`
- `GET /api/logs`
- `GET /api/network-element-logs`
- `GET /api/dashboard/overview`
- `WS /ws`

### Control

- `POST /api/control/clear`
- `POST /api/control/test-messages/topology-demo`
- `POST /api/control/test-messages/topology-demo/pause`
- `POST /api/control/test-messages/topology-demo/resume`
- `POST /api/control/test-messages/full-demo`
- `GET /api/control/tasks`
- `POST /api/control/tasks`
- `POST /api/control/tasks/{task_id}/stop`

### Incoming ACN callbacks

- `POST /acn/v3/pipeline-logs`
- `POST /acn/v3/element-logs`
- `POST /api/acn/v3/subscribe_track`

### MOQ / video

- `GET /api/moq/status`
- `POST /api/moq/subscribe`
- `POST /api/moq/unsubscribe/{track_id}`
- `GET /api/moq/tracks/{track_id}/frames`
- `POST /api/moq/auto-subscribe/{agent_id}`
- `GET /api/video/streams`
- `GET /api/video/streams/{agent_id}`
- `POST /api/video/streams/{agent_id}/register`
- `POST /api/video/webrtc/offer`
- `POST /api/video/webrtc/answer`
- `POST /api/video/webrtc/ice`

More detail is in [API.md](/root/lpx/webui/API.md:1).

## Data Sources And External Dependencies

The dashboard is not self-contained. It reads from external ACN services and files:

- Agent/task database:
  - `/home/acn/zqm/acn_gw/agent_gw/agent_gw.db`
- ACN Agent log:
  - `/home/acn/cxr/acn_agent/.acn_agent.log`
- AgentGW logs:
  - `/home/acn/zqm/acn_gw/agent_gw/logs`
- IDM logs:
  - `/home/acn/cx/idm/logs`
- ARF clear endpoint:
  - `http://localhost:9001/clear`

The Overview `Network Element Status` section checks local reachability of these services. That check is real, but it is a port-level availability check, not a full application health check.

## Frontend Pages

- `Overview`
  - live metrics
  - network element status
  - React Flow topology/message paths
  - critical events feed
- `Agents`
  - current agent roster
  - click a card to view details
- `Network`
  - backend logs
  - tabbed ACN Agent / AgentGW / IDM logs
  - inter-agent link summary
- `Control`
  - clear action with confirmation
  - demo/test triggers
  - task list and task dispatch/stop
- `Settings`
  - UI copy and policy-oriented informational settings

## Test And Demo Utilities

The repo includes test utilities under `test/`.

Most useful for the current UI:

```bash
cd /root/lpx/webui
python3 test/test_messages.py --topology-demo --host 127.0.0.1 --port 9005
python3 test/test_messages.py --full-demo --host 127.0.0.1 --port 9005
```

The WebUI also exposes demo buttons in the UI for:

- topology test flow
- full dashboard demo flow

## Logs

WebUI runtime logs are written to:

- backend log: `logs/backend.log`
- frontend build log: `logs/frontend_build.log`

## Common Problems

### WebUI does not start

Check:

```bash
./start_all.sh status
tail -f logs/backend.log
tail -f logs/frontend_build.log
```

### Frontend cannot reach backend in development mode

Use the React dev server on `9006` and make sure the backend is running on `9005`.

### Overview status looks wrong

The `Network Element Status` cards only show whether the local port/listener is reachable. A process can still be unhealthy while showing `online`.

### Clear does not fully remove visible agents

The WebUI merges database-backed agent identity with live runtime cache. If you change the external AgentGW/ARF data source, the WebUI reflects the database view plus fresh runtime events.

## Notes

- The current dashboard is localized for English and Chinese.
- Theme defaults to light mode.
- The React Flow topology is intentionally presentation-oriented and driven by recent message-flow events rather than a full persisted network graph.
