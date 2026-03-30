# ACN Agent Monitor

Full-stack monitoring system with React frontend and Python backend.

## Architecture

```
/root/lpx/webui/
├── backend/              # Python FastAPI Backend
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py       # FastAPI application + WebSocket
│   ├── requirements.txt
│   └── start.sh
├── frontend/             # React Frontend
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── hooks/        # Custom hooks (useWebSocket)
│   │   ├── styles/       # CSS files
│   │   ├── utils/        # Mock data & utilities
│   │   ├── App.jsx
│   │   └── index.js
│   └── package.json
└── start.sh             # Main start script
```

## Quick Start

### 1. Start Backend

```bash
cd /root/lpx/webui
./start.sh
```

Backend will start on:
- API: http://0.0.0.0:9050
- WebSocket: ws://0.0.0.0:9050/ws

### 2. Start Frontend (Development)

```bash
cd /root/lpx/webui/frontend
npm install
npm start
```

Frontend will start on http://localhost:3000

### 3. Build for Production

```bash
cd /root/lpx/webui/frontend
npm run build
```

The build will be created in `/root/lpx/webui/frontend/build/`

## Features

### Frontend (React)
- **TopBar**: System metrics (latency, bandwidth, active agents, clock)
- **SidebarLeft**: Registered agents list with capabilities
- **CenterContent**:
  - Agent Work Status with operation logs
  - Message Flow (real-time communication logs)
  - Control Center (dispatch tasks, emergency controls)
- **SidebarRight**: Live video feeds with Canvas animation
- **TaskModal**: Task dispatch interface

### Backend (Python/FastAPI)
- REST API for agent data
- WebSocket for real-time communication
- CORS enabled for frontend integration
- Automatic reconnection handling

## API Endpoints

- `GET /api/agents` - Get all registered agents
- `GET /api/health` - Health check
- `WS /ws` - WebSocket endpoint

## WebSocket Messages

### Client to Server:
- `DISPATCH_TASK` - Dispatch a task to an agent
- `EMERGENCY_LAND` - Emergency landing command
- `ABORT_ALL` - Abort all tasks
- `PING` - Keep-alive ping

### Server to Client:
- `AGENT_LIST` - Updated agent list
- `TASK_DISPATCHED` - Task dispatch confirmation
- `EMERGENCY_LAND` - Emergency landing broadcast
- `ABORT_ALL` - Abort all broadcast
- `PONG` - Ping response

## Mock Data

The system includes 7 business agents:
- Drone Alpha, Beta, Gamma
- Ground Unit 1
- Marine Unit A
- RobotDog
- RobotARM

Plus 3 service agents (IDM, ARF, ACF) - hidden from UI.

## Technology Stack

### Frontend
- React 18
- CSS Modules
- WebSocket API
- Canvas API for video simulation

### Backend
- FastAPI
- WebSockets
- SQLite (for agent data)
- Uvicorn (ASGI server)

## Development

### Adding New Components

1. Create component directory: `src/components/ComponentName/`
2. Create `ComponentName.jsx` and `ComponentName.css`
3. Import and use in `App.jsx`

### Adding New API Endpoints

1. Edit `/root/lpx/webui/backend/app/main.py`
2. Add new route with `@app.get()` or `@app.post()`
3. Restart backend server

## Troubleshooting

### Backend won't start
- Check if port 9050 is available: `ss -tlnp | grep 9050`
- Check backend log: `tail -f /tmp/webui_backend.log`
- Ensure virtual environment is activated

### Frontend won't connect
- Verify backend is running: `curl http://localhost:9050/api/health`
- Check CORS configuration in backend
- Verify WebSocket URL in `useWebSocket.js`

### No data displayed
- Check browser console for errors
- Verify WebSocket connection status
- Check mock data is loaded correctly
