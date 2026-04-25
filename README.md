# ACN WebUI

本 README 已合并中文和英文内容，中文部分是当前维护的主要说明，英文部分保留对应说明便于对照。

## 中文

ACN WebUI 是一个基于 FastAPI + React 的监控看板，用于展示 ACN agents、任务、网络组件、后端日志、证书、服务生命周期控制以及 MOQ 视频轨道。

当前主路径是集成式 WebUI，运行在 `9005` 端口。它由 FastAPI 提供后端和静态前端，并通过 WebSocket 推送实时更新。

## 运行端口概览

- 主 WebUI: `https://localhost:9005`
- 主 WebSocket: `wss://localhost:9005/ws`
- 可选独立视频服务: `http://localhost:9006`
- AgentGW `ARF`: `9001`
- AgentGW `ACF`: `9002`
- AgentGW `Relay`: `9003`
- ACN Agent 状态探测: `9010`
- IDM 状态探测: `9020`

## 当前架构

### 主后端 (`9005`)

集成后端入口在 [backend/app/main.py](/root/lpx/webui/backend/app/main.py:1)。

它负责：
- 提供构建后的 React 前端
- 暴露 dashboard API
- 从外部 SQLite 数据库读取 agents 和 tasks
- 汇总后端日志与网络组件日志
- 在 WebUI clear 之后隐藏旧的组件日志显示，但不修改源日志文件
- 管理证书上传/删除元数据，并把证书请求转发给 IDM
- 通过脚本控制 ACN Agent、AgentGW 和 IDM 的启动、停止、重启
- 管理 MOQ 轨道发现、订阅、取消订阅和浏览器播放
- 通过 WebSocket 推送 dashboard 快照和任务更新

相关后端模块：
- [backend/app/moq_video.py](/root/lpx/webui/backend/app/moq_video.py:1)：MOQ 订阅器、发现轨道注册表、WebTransport 桥接、MJPEG 桥接状态
- [backend/app/video_gateway.py](/root/lpx/webui/backend/app/video_gateway.py:1)：共享的视频接入 / 帧缓存 / 转码辅助模块
- [backend/app/video_stream.py](/root/lpx/webui/backend/app/video_stream.py:1)：仍由 `main.py` 暴露的旧版流注册和 WebRTC 信令辅助模块

### 可选独立视频服务 (`9006`)

独立的 `9006` 视频服务位于 [backend/app/video_9006/service.py](/root/lpx/webui/backend/app/video_9006/service.py:1)，由 [start_video_service.sh](/root/lpx/webui/start_video_service.sh:1) 启动。

它不是主 WebUI 必需组件，而是一条基于共享 [backend/app/video_gateway.py](/root/lpx/webui/backend/app/video_gateway.py:1) 的独立视频测试/服务路径。

注意：
- React 开发服务器也使用 `9006`
- 不要同时运行 `npm start` 和 `start_video_service.sh`，除非你手动改端口

## 项目结构

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

## 快速开始

### 推荐方式：启动集成 WebUI

```bash
cd /root/lpx/webui
./start_all.sh start
```

常用命令：

```bash
./start_all.sh restart
./start_all.sh status
./start_all.sh logs
./start_all.sh stop
```

`start_all.sh` 会做这些事：
- 构建 React 前端
- 启动 `9005` 上的 FastAPI
- 由后端直接提供已构建的前端页面

### 只启动后端

```bash
cd /root/lpx/webui/backend
/root/lpx/webui/.venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9005
```

### 前端开发模式

```bash
cd /root/lpx/webui/frontend
npm install
npm start
```

这会在 `http://localhost:9006` 启动 React 开发服务器。

### 可选：启动独立视频服务 (`9006`)

```bash
cd /root/lpx/webui
./start_video_service.sh
```

它会暴露这些接口：
- `GET /health`
- `GET /video/streams`
- `GET /video/player/{track_id}`
- `GET /video/stream/{track_id}/mjpeg`
- `GET /video/stream/{track_id}/latest`
- `GET /video/stream/{track_id}/info`
- `POST /video/ingest/{track_id}`

## 主 API（`9005`）

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

网络组件生命周期控制支持：
- `element_id`: `acn-agent`、`agent-gw`、`idm` 或 `all`
- `action`: `start`、`stop` 或 `restart`
- `all/start` 只启动当前显示为离线的组件
- `all/restart` 会重启所有受控组件

后端会执行这些脚本：
- ACN Agent: `/home/acn/cxr/acn_agent/start_acn_agent.sh`
- AgentGW: `/home/acn/zqm/acn_gw/start_agent_gw.sh`
- IDM: `/home/acn/cx/idm/start_idm.sh`

WebUI 对 stop/restart 操作会弹出二次确认。只有组件离线时才允许点击 Start。

### Settings

- `GET /api/settings/data-source`
- `POST /api/settings/data-source`
- `GET /api/settings/certificates`
- `POST /api/settings/certificates/upload`
- `DELETE /api/settings/certificates/{cert_id}`
- `POST /api/settings/virtual-agents`

证书上传行为：
- 后端按 X.509 解码上传的证书文件
- 只有 IDM 返回 `200 OK` 后，才把证书元数据保存到 WebUI 本地证书数据库
- 证书上传/删除请求会转发给 IDM
- IDM 失败响应会显示在 WebUI，并写入后端日志

### MOQ / 视频轨道管理

- `GET /api/moq/status`
- `GET /api/moq/tracks`
- `POST /api/subscriber/start`
- `DELETE /api/moq/tracks/{track_id}`
- `POST /api/acn/v3/subscribe_track`

### 视频播放接口

- `GET /api/video/stream/{track_id}/mjpeg`
- `GET /api/video/stream/{track_id}/latest`
- `GET /api/video/stream/{track_id}/info`

### 较旧的流 / WebRTC 接口

这些接口仍然由 `main.py` 暴露，但不是当前 MOQ/WebUI 主路径：

- `GET /api/video/streams`
- `GET /api/video/streams/{agent_id}`
- `POST /api/video/streams/{agent_id}/register`
- `DELETE /api/video/streams/{stream_id}`
- `POST /api/video/webrtc/offer`
- `POST /api/video/webrtc/answer`
- `POST /api/video/webrtc/ice`

### ACN 回调入口

- `POST /acn/v3/pipeline-logs`
- `POST /acn/v3/element-logs`

更详细的接口说明见 [API.md](/root/lpx/webui/API.md:1)。

## 数据来源

这个 dashboard 不是自包含系统。当前后端会读取外部服务和文件：

- agent/task 数据库：
  - `/home/acn/zqm/acn_gw/agent_gw/agent_gw.db`
- ACN Agent 日志：
  - `/home/acn/cxr/acn_agent/.acn_agent.log`
- AgentGW 日志：
  - `/home/acn/zqm/acn_gw/agent_gw/logs`
- IDM 日志：
  - `/home/acn/cx/idm/logs`
- ARF 清理接口：
  - `http://localhost:9001/clear`
- WebUI 本地状态数据库：
  - `logs/webui_local_state.db`
- WebUI 证书数据库：
  - `logs/certificates.db`
- WebUI 证书文件缓存：
  - `logs/cert_store`
- WebUI 运行时设置：
  - `logs/data_source_settings.json`
  - `logs/direct_demo_settings.json`

重要日志行为：
- WebUI clear 不会截断或删除源组件日志文件
- 成功执行 `/api/control/clear` 后，WebUI 会在内存中记录当前源日志文件偏移量
- 之后 `/api/network-element-logs` 只返回 clear 之后新追加的日志行
- 如果重启 WebUI 后端，内存中的偏移量会丢失，旧的文件日志可能再次显示

## Agent 与 Task 如何同步

### Agents

- `agents` 表是 agent 存在性的真实来源
- 后端会基于数据库内容加上瞬时运行态缓存重建 dashboard agent 数据
- 前端主要跟随 `GET /api/dashboard/overview` 和 WebSocket 的 `DASHBOARD_SNAPSHOT`

### Tasks

- 活跃任务来自数据库里的 `tasks` 表
- 后端会把数据库任务和内存中的任务元数据、最近完成任务历史组合起来
- 前端会轮询 `GET /api/control/tasks`，同时也会响应 WebSocket 的 `TASKS_UPDATED`

这意味着当前没有直接监听 SQLite 变更，而是依靠后端重复读取数据库，再配合 WebSocket 更新。

## 视频 / MOQ 说明

当前 WebUI 视频链路是：

1. publisher 向 MOQ relay 发布视频轨道
2. 在 Agents 页签的 Videos 区域输入 `Namespace` 和 `Track Name`
3. 点击 `Subscribe` 后，前端调用 `POST /api/subscriber/start`
4. 后端根据输入的 `namespace` 和 `trackName` 订阅真实 MOQ 轨道
5. 后端把当前订阅切换到浏览器预览桥接 `/wt/preview`
6. 浏览器通过 WebTransport 接收媒体数据，并使用 MediaSource Extensions 渲染视频
7. `Subscribed Tracks` 用于在多个已订阅轨道之间切换当前预览

`Namespace` 和 `Track Name` 都是必填项，并且必须和 publisher 发布到 relay 的轨道完全匹配。后端订阅 MOQ relay 的地址由环境变量控制：

- `MOQ_RELAY_HOST`：默认 `localhost`
- `MOQ_RELAY_PORT`：默认 `9003`
- `MOQ_WEBTRANSPORT_PORT`：默认跟随 `BACKEND_PORT`，当前集成 WebUI 默认为 `9005`

### 浏览器播放实现

浏览器播放主路径是 `WebTransport + MediaSource Extensions`：

- 后端 WebTransport bridge 监听在当前 WebUI HTTPS 服务上，浏览器连接路径为 `/wt/preview`
- WebTransport 要求页面运行在 HTTPS 或 localhost 环境
- 后端向浏览器发送内部帧：metadata JSON、MP4 init segment、fMP4 media fragments、end
- 前端根据 metadata 中的 `mime_type` / `mse_codec` 创建 `MediaSource` 和 `SourceBuffer`
- 前端会调用 `MediaSource.isTypeSupported(mime_type)`，浏览器不支持该 MIME / codec 时无法播放
- 如果 metadata 没有提供 `mse_codec`，前后端会尝试从 init segment 的 `avcC` 中推断 `avc1.xxxxxx`

当前 WebUI 还保留 MJPEG fallback / snapshot 辅助路径，后端会把已收到的 fMP4 数据送入 ffmpeg 转码成 MJPEG。但 Agents 页签的视频预览主路径仍是 WebTransport + MSE。

### Publisher 输出约束

当前浏览器预览期望 publisher 输出的是 H.264 fMP4 流，而不是任意视频 payload。推荐对象顺序是：

1. metadata JSON，建议作为 track 的第一个对象
2. fMP4 init segment，必须包含 `ftyp` 和 `moov`
3. 连续 fMP4 media fragments，通常是可追加到 MSE 的 `moof` / `mdat` 片段

推荐 metadata 示例：

```json
{
  "container": "fMP4",
  "codec": "H.264",
  "mime_type": "video/mp4; codecs=\"avc1.64001F\"",
  "mse_codec": "avc1.64001F",
  "width": 1280,
  "height": 720,
  "fps": 30
}
```

当前不适合直接作为浏览器预览输入的格式包括：

- raw H.264 Annex-B 裸流
- RTP / RTSP
- MPEG-TS
- 普通完整 MP4 文件一次性对象流
- WebM 或其他容器，除非后端和前端 metadata / MSE 处理逻辑同步适配

后端识别 init segment 的条件是：payload 第一个 box 为 `ftyp`，并且前 4096 字节内包含 `moov`。后续 fragment 必须和 init segment 中声明的 codec、track 和时间信息保持一致，否则浏览器 `SourceBuffer` 可能报错或无法出画。

## 测试

当前测试说明见 [test/README_TEST.md](/root/lpx/webui/test/README_TEST.md:1)。

最常用的当前路径：

### Dashboard 消息 / 演示流程

```bash
cd /root/lpx/webui
python3 test/test_messages.py --topology-demo --host 127.0.0.1 --port 9005
python3 test/test_messages.py --full-demo --host 127.0.0.1 --port 9005
```

### 手动 MOQ WebUI 视频演示

```bash
cd /root/lpx/webui
./test/run_moq_video_ui_demo.sh start
./test/run_moq_video_ui_demo.sh status
./test/run_moq_video_ui_demo.sh stop
```

### 自动化 MOQ WebUI E2E

```bash
cd /root/lpx/webui
python3 test/moq_video_webui_e2e.py
```

## 日志

常用运行日志：
- backend log: `logs/backend.log`
- frontend build log: `logs/frontend_build.log`
- MOQ 手动 demo log: `logs/moq_video_ui_demo.log`

## 常见问题

### WebUI 无法启动

检查：

```bash
./start_all.sh status
tail -f logs/backend.log
tail -f logs/frontend_build.log
```

### 前端开发模式和独立视频服务冲突

两者都想占用 `9006`。

同一时间只运行一个：
- `cd frontend && npm start`
- `./start_video_service.sh`

### 轨道卡片存在但播放不出来

检查：

```bash
curl -sk https://localhost:9005/api/moq/status | python3 -m json.tool
curl -sk https://localhost:9005/api/moq/tracks | python3 -m json.tool
curl -sk https://localhost:9005/api/video/stream/<track_id>/info | python3 -m json.tool
```

重点看：
- `connected`
- `relay_host` / `relay_port`
- `watchState`
- `subscription_debug`
- `has_metadata`
- `has_init_segment`
- `fragment_count`
- `has_frame`

### Overview 状态看起来不对

Network Element Status 卡片只表示本地端口是否可达，不代表完整应用健康。

### Clear 之后 agent 没完全消失

后端会把数据库里的 agent 身份信息和运行态缓存合并。如果外部 AgentGW/ARF 侧仍然保留这些 agent，它们可能在刷新后再次出现。

## 备注

- 当前 dashboard 支持英文和中文
- 默认产品路径是集成式 `9005` WebUI
- `9006` 服务是可选的，主要用于独立视频测试

---

## English

ACN WebUI is a FastAPI + React dashboard for monitoring ACN agents, tasks, network elements, backend logs, certificates, service lifecycle controls, and MOQ video tracks.

The main product path is the integrated WebUI on port `9005`. It serves the built frontend from the FastAPI backend and pushes live updates over WebSocket.

## Runtime Overview

- Main WebUI: `https://localhost:9005`
- Main WebSocket: `wss://localhost:9005/ws`
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
- managing MOQ track discovery, subscription, deletion, and browser playback
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
- `POST /api/settings/virtual-agents`

Certificate upload behavior:
- backend decodes uploaded cert files as X.509
- stores metadata in the local WebUI certificate DB only after IDM returns `200 OK`
- forwards certificate upload/delete requests to IDM
- failed IDM responses are shown in the WebUI and logged in backend logs

### MOQ / video track management

- `GET /api/moq/status`
- `GET /api/moq/tracks`
- `POST /api/subscriber/start`
- `DELETE /api/moq/tracks/{track_id}`
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

1. the publisher publishes a video track to the MOQ relay
2. the user enters `Namespace` and `Track Name` in Agents > Videos
3. clicking `Subscribe` calls `POST /api/subscriber/start`
4. the backend subscribes to the real MOQ track using the submitted `namespace` and `trackName`
5. the backend switches the browser preview bridge to `/wt/preview`
6. the browser receives media data over WebTransport and renders it with MediaSource Extensions
7. `Subscribed Tracks` switches the current preview between active subscriptions

Both `Namespace` and `Track Name` are required, and they must exactly match the track published to the relay. MOQ relay settings are controlled by environment variables:

- `MOQ_RELAY_HOST`: defaults to `localhost`
- `MOQ_RELAY_PORT`: defaults to `9003`
- `MOQ_WEBTRANSPORT_PORT`: defaults to `BACKEND_PORT`; the integrated WebUI default is `9005`

### Browser Playback Implementation

The primary browser playback path is `WebTransport + MediaSource Extensions`:

- the backend WebTransport bridge runs on the current WebUI HTTPS service, with browser path `/wt/preview`
- WebTransport requires an HTTPS page or localhost
- the backend sends internal frames to the browser: metadata JSON, MP4 init segment, fMP4 media fragments, and end
- the frontend creates a `MediaSource` and `SourceBuffer` from `mime_type` / `mse_codec` in metadata
- the frontend calls `MediaSource.isTypeSupported(mime_type)`; unsupported MIME / codec combinations cannot play
- if metadata does not include `mse_codec`, the backend/frontend try to infer `avc1.xxxxxx` from `avcC` in the init segment

The WebUI also keeps an MJPEG fallback / snapshot helper path. The backend can feed received fMP4 data into ffmpeg and transcode it to MJPEG, but the Agents tab preview path is still WebTransport + MSE.

### Publisher Output Contract

The current browser preview expects an H.264 fMP4 stream, not arbitrary video payloads. Recommended object order:

1. metadata JSON, preferably as the first track object
2. fMP4 init segment, which must contain `ftyp` and `moov`
3. continuous fMP4 media fragments, usually MSE-appendable `moof` / `mdat` segments

Recommended metadata:

```json
{
  "container": "fMP4",
  "codec": "H.264",
  "mime_type": "video/mp4; codecs=\"avc1.64001F\"",
  "mse_codec": "avc1.64001F",
  "width": 1280,
  "height": 720,
  "fps": 30
}
```

Formats that are not suitable as direct input for the current browser preview include:

- raw H.264 Annex-B elementary streams
- RTP / RTSP
- MPEG-TS
- one-shot complete MP4 file objects
- WebM or other containers unless the backend and frontend metadata / MSE handling are adapted together

The backend recognizes an init segment when the payload's first box is `ftyp` and `moov` appears within the first 4096 bytes. Subsequent fragments must stay consistent with the codec, track, and timing information declared by the init segment, otherwise the browser `SourceBuffer` may fail or never render frames.


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
curl -sk https://localhost:9005/api/moq/status | python3 -m json.tool
curl -sk https://localhost:9005/api/moq/tracks | python3 -m json.tool
curl -sk https://localhost:9005/api/video/stream/<track_id>/info | python3 -m json.tool
```

Look at:
- `connected`
- `relay_host` / `relay_port`
- `watchState`
- `subscription_debug`
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
