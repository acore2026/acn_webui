# ACN WebUI

[English Version](./README.md)

ACN WebUI 是一个基于 FastAPI + React 的监控看板，用于展示 ACN agents、任务、网络组件、后端日志、证书、服务生命周期控制以及 MOQ 视频轨道。

当前主路径是集成式 WebUI，运行在 `9005` 端口。它由 FastAPI 提供后端和静态前端，并通过 WebSocket 推送实时更新。

## 运行端口概览

- 主 WebUI: `http://localhost:9005`
- 主 WebSocket: `ws://localhost:9005/ws`
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
- `GET /api/settings/direct-demo-camera`
- `POST /api/settings/direct-demo-camera`
- `POST /api/settings/virtual-agents`

证书上传行为：
- 后端按 X.509 解码上传的证书文件
- 只有 IDM 返回 `200 OK` 后，才把证书元数据保存到 WebUI 本地证书数据库
- 证书上传/删除请求会转发给 IDM
- IDM 失败响应会显示在 WebUI，并写入后端日志

### MOQ / 视频轨道管理

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

1. publisher 发布或通告一个 MOQ 轨道
2. 后端发现该轨道，或者手动注册一个轨道卡片
3. Agents 页面展示该轨道卡片
4. 点击 `Watch` 会触发 `POST /api/moq/watch/{track_id}`
5. 后端根据保存的 `namespace` 和 `trackName` 去订阅真实 MOQ 轨道
6. 浏览器通过 WebUI 的播放桥接进行渲染

Manage Track 表单可以新增或删除轨道卡片。手动新增的卡片只有在 `namespace` 和 `trackName` 与真实发布轨道完全匹配时才能成功播放。

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
curl -s http://localhost:9005/api/moq/tracks | python3 -m json.tool
curl -s http://localhost:9005/api/video/stream/<track_id>/info | python3 -m json.tool
```

重点看：
- `watchState`
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
