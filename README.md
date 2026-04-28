# ACN WebUI

本 README 是当前维护的中文说明。

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
- [backend/app/moq_video.py](/root/lpx/webui/backend/app/moq_video.py:1)：MOQ 订阅器、发现轨道注册表、WebTransport 桥接和 MSE 播放数据转发

## 项目结构

```text
webui/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   └── moq_video.py
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
└── start_all.sh
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

`POST /api/control/clear` 会向 ARF 转发：

```json
{
  "method": "POST",
  "url": "/clear",
  "body": {}
}
```

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

- `GET /api/settings/certificates`
- `POST /api/settings/certificates/upload`
- `DELETE /api/settings/certificates/{cert_id}`
- `POST /api/settings/virtual-agents`

证书上传行为：
- 后端按 X.509 解码上传的证书文件
- 只有 IDM 返回 `200 OK` 后，才把证书元数据保存到 WebUI 本地证书数据库
- 上传会转发 `POST /idm/v1/cert-upload`，格式为 `multipart/form-data`，字段为 `certID`、`certName`、`file`
- 删除会转发 `POST /idm/v1/cert-delete`，格式为 JSON，字段为 `certID`、`certName`
- IDM 失败响应会显示在 WebUI，并写入后端日志

### MOQ / 视频轨道管理

- `GET /api/moq/status`
- `GET /api/moq/tracks`
- `POST /api/subscriber/start`
- `DELETE /api/moq/tracks/{track_id}`

### ACN 回调入口

- `POST /acn/v3/pipeline-logs`
- `POST /acn/v3/element-logs`

### WebSocket 消息

客户端可发送：

- `DISPATCH_TASK`
- `EMERGENCY_LAND`
- `ABORT_ALL`
- `PING`
- `REFRESH`

后端会发送：

- `AGENT_LIST`
- `DASHBOARD_SNAPSHOT`
- `TASKS_UPDATED`
- `VIDEO_TRACKS_AVAILABLE`
- `REFRESH_COMPLETE`
- `REFRESH_ERROR`
- `PIPELINE_LOG`
- `AGENT_STATUS_UPDATE`
- `TASK_DISPATCHED`
- `EMERGENCY_LAND`
- `ABORT_ALL`
- `PONG`

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

当前测试说明见 [test/README.md](/root/lpx/webui/test/README.md:1)。

最常用的当前路径：

### Agent / Task 消息流

```bash
cd /root/lpx/webui
python3 test/agent_task_message_flow.py --base-url https://127.0.0.1:9005 --interactive
```

### Dashboard 消息 / 演示流程

```bash
cd /root/lpx/webui
python3 test/test_messages.py --topology-demo --host 127.0.0.1 --port 9005
python3 test/test_messages.py --full-demo --host 127.0.0.1 --port 9005
```

## 日志

常用运行日志：
- backend log: `logs/backend.log`
- frontend build log: `logs/frontend_build.log`

## 常见问题

### WebUI 无法启动

检查：

```bash
./start_all.sh status
tail -f logs/backend.log
tail -f logs/frontend_build.log
```

### 轨道卡片存在但播放不出来

检查：

```bash
curl -sk https://localhost:9005/api/moq/status | python3 -m json.tool
curl -sk https://localhost:9005/api/moq/tracks | python3 -m json.tool
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
