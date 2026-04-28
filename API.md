# ACN WebUI Backend API 文档

后端服务运行在 `9005` 端口。

Base URL:

```text
https://<host>:9005
```

当前 WebUI 使用本地缓存数据库 `logs/webui_local_state.db` 维护 agent/task 状态，不再读取外部 AgentGW 数据库。

## 1. 系统状态

### GET /api/health

健康检查。

响应示例：

```json
{
  "status": "healthy",
  "timestamp": "2026-04-28T10:00:00.000000",
  "websocket_clients": 1
}
```

## 2. Dashboard 快照

### GET /api/dashboard/overview

获取 WebUI 当前 dashboard 快照。

响应主要字段：

- `metrics`: Overview 指标卡
- `topology.agents`: Agents 页签使用的 agent 列表
- `topology.links`: 拓扑连线
- `elements`: 网络组件状态
- `messages`: 消息流展示项

说明：

- `System Latency` 是基于当前 dashboard active links 计算出的平均展示时延，不是实际网络探测 RTT。
- `topology.agents[].priority` 来自 `PublishAgent.content.priority`。
- `topology.agents[].tasks` 来自本地 `tasks` 表中该 agent 的任务记录。
- `topology.agents[].tracks` 来自 `PublisherTrackAdd/PublisherTrackDel` 维护的 `agents.track_info`。

## 3. Agent 查询

### GET /api/agents

返回本地 WebUI 已知 agents。

响应示例：

```json
{
  "agents": [
    {
      "agent_id": "did:acn:agent:001",
      "agent_name": "Drone Alpha",
      "agent_capability": ["surveillance", "tracking"],
      "agent_status": "online",
      "work_status": "working",
      "current_task": "Inspect target area",
      "priority": "5",
      "consent": {
        "need_consumer_ue_authorization": false,
        "need_producer_authorization": true,
        "support_producer_ue_authorization": false
      },
      "track_info": [
        {
          "task_id": "task-001",
          "namespace": "/task-001/did:acn:agent:001",
          "track": "Video",
          "updated_at": "2026-04-28T10:00:00Z"
        }
      ]
    }
  ],
  "timestamp": "2026-04-28T10:00:00.000000"
}
```

状态说明：

- `agent_status`: 直接使用 `PublishAgent.content.agent_status`，当前预期值为 `online` 或 `offline`。
- `work_status`: 由任务状态维护。该 agent 存在 `processing` 任务时为 `working`，否则为 `idle`。
- 页面展示状态 `busy` 由 dashboard 派生：`agent_status != offline` 且 `work_status=working` 时显示为 `busy`。

## 4. 日志查询

### GET /api/logs?limit=100

获取后端运行日志。

参数：

- `limit`: 返回日志条数，默认 `100`

响应示例：

```json
{
  "logs": [
    {
      "time": "2026-04-28T10:00:00.000000",
      "level": "info",
      "message": "[AgentGW] did:acn:agent:001: TaskExecution: Inspect target area"
    }
  ],
  "total": 1,
  "timestamp": "2026-04-28T10:00:00.000000"
}
```

### GET /api/network-element-logs

获取网络组件日志分组。

说明：

- 该接口读取后端聚合的组件日志。
- 执行 WebUI clear 后，后端会记录日志偏移，只展示 clear 之后的新日志；不会删除源日志文件。

## 5. ACN 回调入口

### POST /acn/v3/pipeline-logs

接收流程日志，用于 Message Flow / 日志展示。

当前该接口只记录和广播 pipeline log，不再维护 `agents` 表或 `tasks` 表。

请求示例：

```json
{
  "source": "AgentGW",
  "destination": "IDM",
  "timestamp": "2026-04-28T10:00:00Z",
  "task_id": "task-001",
  "protocol": "HTTP/2",
  "headers": {
    "Content-Type": "application/json"
  },
  "abstract": "Identity verification completed",
  "content": "VC issued successfully"
}
```

响应示例：

```json
{
  "status": "success",
  "message": "Log received and broadcasted",
  "timestamp": "2026-04-28T10:00:00.000000"
}
```

### POST /acn/v3/element-logs

接收 AgentGW element log，并根据指定消息类型维护本地 `agents` 和 `tasks` 表。

支持两种请求形式：

- 直接提交 body 内容
- 按测试脚本格式提交 `{ "method", "url", "headers", "body" }`，后端会读取其中的 `body`

当前用于维护状态的 `log_type`：

- `PublishAgent`
- `DeleteAgent`
- `TaskExecution`
- `TaskExecutionTermination`
- `PublisherTrackAdd`
- `PublisherTrackDel`

其他 `log_type` 会被记录和广播，但不会维护 agent/task 状态。

#### PublishAgent

新增或更新 agent。

```json
{
  "method": "POST",
  "url": "/acn/v3/element-logs",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "element_id": "AgentGW",
    "log_type": "PublishAgent",
    "timestamp": "2026-04-28T10:00:00Z",
    "content": {
      "agent_name": "Test Agent",
      "agent_id": "did:acn:agent:001",
      "agent_capability": ["video-publish", "task-execution"],
      "agent_status": "online",
      "priority": "5",
      "consent": {
        "need_consumer_ue_authorization": false,
        "need_producer_authorization": true,
        "support_producer_ue_authorization": false
      }
    }
  }
}
```

处理结果：

- upsert `agents`
- 覆盖 `agent_name`
- 覆盖 `agent_capability`
- `agents.agent_status = content.agent_status`
- `agents.priority = content.priority`
- `agents.consent = content.consent`
- 如果该 agent 当前有 `processing` 任务，则 `work_status=working`，否则 `work_status=idle`

#### DeleteAgent

删除 agent 及相关任务信息。

```json
{
  "method": "POST",
  "url": "/acn/v3/element-logs",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "element_id": "AgentGW",
    "log_type": "DeleteAgent",
    "timestamp": "2026-04-28T10:00:00Z",
    "content": {
      "agent_name": "Test Agent",
      "agent_id": "did:acn:agent:001",
      "agent_capability": ["video-publish", "task-execution"],
      "agent_status": "offline",
      "priority": "5",
      "consent": {
        "need_consumer_ue_authorization": false,
        "need_producer_authorization": true,
        "support_producer_ue_authorization": false
      }
    }
  }
}
```

处理结果：

- 删除 `agents.agent_id = content.agent_id`
- 删除 `tasks.agent_id = content.agent_id`
- 清理内存中的任务注册信息
- 清理 Task Queue Status 中该 agent 相关的已完成任务历史

#### TaskExecution

创建或更新任务，任务状态为 `processing`。

```json
{
  "method": "POST",
  "url": "/acn/v3/element-logs",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "element_id": "AgentGW",
    "log_type": "TaskExecution",
    "timestamp": "2026-04-28T10:00:00Z",
    "content": {
      "agent_id": "did:acn:agent:001",
      "task_id": "task-001",
      "task_description": "Inspect target area"
    }
  }
}
```

处理结果：

- upsert `tasks`，key 为 `(task_id, agent_id)`
- `tasks.status = processing`
- 更新任务描述
- 对应 agent 存在 processing 任务时，`agents.work_status = working`

#### TaskExecutionTermination

标记任务完成，不删除 task 记录。

```json
{
  "method": "POST",
  "url": "/acn/v3/element-logs",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "element_id": "AgentGW",
    "log_type": "TaskExecutionTermination",
    "timestamp": "2026-04-28T10:00:00Z",
    "content": {
      "agent_id": "did:acn:agent:001",
      "task_id": "task-001",
      "task_description": "Inspect target area completed"
    }
  }
}
```

处理结果：

- upsert `tasks`
- `tasks.status = finished`
- 不删除 task 记录
- 如果该 agent 已没有其他 `processing` 任务，则 `agents.work_status = idle`
- 同步 Task Queue Status 的已完成任务历史

#### PublisherTrackAdd

为 agent 增加发布 track 信息。业务上应在对应任务存在后发送。

```json
{
  "method": "POST",
  "url": "/acn/v3/element-logs",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "element_id": "AgentGW",
    "log_type": "PublisherTrackAdd",
    "timestamp": "2026-04-28T10:00:00Z",
    "content": {
      "src_agent_id": "did:acn:agent:001",
      "task_id": "task-001",
      "track_list": [
        {
          "namespace": "/task-001/did:acn:agent:001",
          "track": "Video"
        }
      ]
    }
  }
}
```

处理结果：

- 维护 `agents.track_info`
- 每个 track 记录以 `task_id + namespace + track` 为一组
- Agent 详情页 `Published Track Info` 显示这些信息

#### PublisherTrackDel

从 agent 的发布 track 信息中删除指定 track。

```json
{
  "method": "POST",
  "url": "/acn/v3/element-logs",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "element_id": "AgentGW",
    "log_type": "PublisherTrackDel",
    "timestamp": "2026-04-28T10:00:00Z",
    "content": {
      "src_agent_id": "did:acn:agent:001",
      "task_id": "task-001",
      "track_list": [
        {
          "namespace": "/task-001/did:acn:agent:001",
          "track": "Video"
        }
      ]
    }
  }
}
```

处理结果：

- 从 `agents.track_info` 中移除匹配的 `task_id + namespace + track`

#### element-logs 响应

响应示例：

```json
{
  "status": "success",
  "message": "Log received and broadcasted",
  "timestamp": "2026-04-28T10:00:00.000000"
}
```

状态变更后，后端会广播：

- `AGENT_STATUS_UPDATE`
- `DASHBOARD_SNAPSHOT`
- `TASKS_UPDATED`

## 6. Control 接口

### POST /api/control/clear

清理 WebUI 本地环境状态。

处理内容包括：

- 清空本地 agent/task 运行态
- 清空 pipeline/message/task 相关内存缓存
- 调用 ARF `/clear`
- 广播新的 dashboard snapshot 和 tasks

#### 转发给 ARF 的 clear 消息

WebUI 后端会向 ARF 发送：

```http
POST http://localhost:9001/clear
Content-Type: application/json
```

请求体：

```json
{
  "method": "POST",
  "url": "/clear",
  "body": {}
}
```

响应处理：

- ARF 返回 `HTTP 200` 时，WebUI 认为 clear 成功，并读取 ARF JSON 响应写入 `/api/control/clear` 的 `arf_response`。
- ARF 返回非 `200` 时，WebUI 返回 `502`，错误信息写入后端日志。
- ARF 连接失败时，WebUI 返回 `502`，并在错误详情中包含连接失败原因。

### GET /api/control/network-elements

获取 ACN Agent、AgentGW、IDM 等受控组件状态。

### POST /api/control/network-elements/{element_id}/{action}

控制网络组件生命周期。

参数：

- `element_id`: `acn-agent`、`agent-gw`、`idm` 或 `all`
- `action`: `start`、`stop`、`restart`

说明：

- `all/start` 只启动当前显示为 offline 的组件。
- stop/restart 操作通常由前端弹窗二次确认。

### GET /api/control/tasks

获取 Task Queue Status 数据。

返回内容由两部分组合：

- 本地 `tasks` 表中的任务
- 内存中最近完成任务历史

响应示例：

```json
{
  "tasks": [
    {
      "id": "task-001",
      "taskName": "Inspect target area",
      "taskType": "TaskExecution",
      "description": "Inspect target area",
      "status": "processing",
      "involvedAgents": [
        {
          "id": "did:acn:agent:001",
          "name": "Test Agent"
        }
      ],
      "createdAt": "2026-04-28T10:00:00Z",
      "updatedAt": "2026-04-28T10:00:00Z"
    }
  ],
  "timestamp": "2026-04-28T10:00:00.000000"
}
```

### POST /api/control/tasks

通过 WebUI 手动派发任务。

请求示例：

```json
{
  "task_name": "Manual inspection",
  "task_type": "Inspection",
  "task_description": "Inspect selected area",
  "agent_ids": ["did:acn:agent:001"]
}
```

说明：

- 这是 WebUI 本地控制入口，不等同于 AgentGW 的 `TaskExecution` 消息。
- 成功后会写入本地 `tasks` 表，并广播 `TASKS_UPDATED`。

### POST /api/control/tasks/{task_id}/stop

停止 WebUI 当前认为正在处理的任务。

处理结果：

- 删除本地 `tasks` 表中该 `task_id` 的记录
- 将任务加入完成历史
- 更新相关 agent 的 `work_status`
- 广播 `TASKS_UPDATED`

### 演示消息接口

- `POST /api/control/test-messages/topology-demo`
- `POST /api/control/test-messages/topology-demo/pause`
- `POST /api/control/test-messages/topology-demo/resume`
- `POST /api/control/test-messages/full-demo`

这些接口用于 WebUI 演示和测试。

## 7. Settings 接口

### POST /api/settings/virtual-agents

新增 WebUI 本地虚拟 Agent。

说明：

- 用于调试/演示。
- 不等同于 AgentGW `PublishAgent` 正式注册流程。
- 如果传入 `currentTask`，后端会同时创建本地任务记录。

请求示例：

```json
{
  "agentName": "Virtual Agent",
  "agentId": "did:acn:agent:virtual-001",
  "capabilities": ["demo"],
  "status": "online",
  "currentTask": "Optional local task"
}
```

### GET /api/settings/certificates

获取 WebUI 管理的证书列表。

### POST /api/settings/certificates/upload

上传证书。

支持：

- multipart `file`
- 表单字段 `filePath`

说明：

- 后端会解析 X.509 证书。
- 只有 IDM 返回成功后，才把证书元数据写入 WebUI 本地证书数据库。

#### 转发给 IDM 的 cert-upload 消息

WebUI 后端会向 IDM 发送：

```http
POST http://127.0.0.1:9020/idm/v1/cert-upload
Content-Type: multipart/form-data; boundary=<httpx自动生成>
```

表单字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `certID` | text | WebUI 生成的证书 ID，格式类似 `cert-12345678` |
| `certName` | text | 上传文件名或服务端路径中的文件名 |
| `file` | file | 证书文件内容，Content-Type 为 `application/octet-stream` |

等价 curl 示例：

```bash
curl -X POST http://127.0.0.1:9020/idm/v1/cert-upload \
  -F 'certID=cert-12345678' \
  -F 'certName=Robot_Factory_Cert.crt' \
  -F 'file=@/path/to/Robot_Factory_Cert.crt;type=application/octet-stream'
```

响应处理：

- 只有 IDM 返回 `HTTP 200` 时，WebUI 才认为上传成功。
- `HTTP 200` 响应体会先尝试解析为 JSON；如果不是 JSON，则按文本保存到 `/api/settings/certificates/upload` 响应的 `idmResponse.body`。
- IDM 返回非 `200` 时，WebUI 返回 `502`，不会保存证书到 `logs/cert_store/` 和 `logs/certificates.db`。
- IDM 连接失败或请求异常时，WebUI 返回 `502`，错误写入后端日志。
- WebUI 先完成 IDM 上传，成功后才写本地证书文件和本地证书 DB。

### DELETE /api/settings/certificates/{cert_id}

删除证书元数据，并向 IDM 转发删除请求。

#### 转发给 IDM 的 cert-delete 消息

WebUI 后端会先从本地证书 DB 查询 `certName`，然后向 IDM 发送：

```http
POST http://127.0.0.1:9020/idm/v1/cert-delete
Content-Type: application/json
```

请求体：

```json
{
  "certID": "cert-12345678",
  "certName": "Robot_Factory_Cert.crt"
}
```

响应处理：

- 只有 IDM 返回 `HTTP 200` 时，WebUI 才删除本地证书文件和本地证书 DB 记录。
- `HTTP 200` 响应体会先尝试解析为 JSON；如果不是 JSON，则按文本保存到删除接口响应的 `idmResponse.body`。
- IDM 返回非 `200`、连接失败或请求异常时，WebUI 返回 `502`，并保留本地证书记录。

## 8. MOQ / 视频接口

当前 Agents 页签 Videos 区域使用集成在 9005 WebUI 内的 MOQ 订阅和浏览器播放桥接。

### GET /api/moq/status

获取 MOQ 订阅状态。

响应示例：

```json
{
  "status": "available",
  "connected": true,
  "relay_host": "localhost",
  "relay_port": 9003,
  "subscribed_tracks": ["manual_video_h264-live"],
  "discovered_tracks": [],
  "subscription_debug": [],
  "timestamp": "2026-04-28T10:00:00.000000"
}
```

### GET /api/moq/tracks

获取 WebUI 当前已知视频轨道和已订阅轨道。

### POST /api/subscriber/start

订阅或切换浏览器预览轨道。

请求字段：

- `namespace`: 必填，必须与 publisher 发布到 relay 的 namespace 匹配
- `trackName`: 必填，必须与 publisher 发布到 relay 的 track name 匹配
- `trackId`: 可选，不传时后端按 namespace/trackName 生成

请求示例：

```json
{
  "namespace": "video",
  "trackName": "h264-live"
}
```

响应示例：

```json
{
  "ok": true,
  "status": "success",
  "track": {
    "trackId": "manual_video_h264-live",
    "namespace": "/video",
    "trackName": "h264-live",
    "watchState": "subscribed"
  },
  "subscribed_tracks": ["manual_video_h264-live"],
  "player": {
    "trackId": "manual_video_h264-live",
    "host": "localhost",
    "port": 9005,
    "path": "/wt/preview"
  },
  "bootstrap": {},
  "timestamp": "2026-04-28T10:00:00.000000"
}
```

说明：

- MOQ relay 地址由环境变量控制：`MOQ_RELAY_HOST`、`MOQ_RELAY_PORT`。
- 正式 relay 默认端口为 `9003`。
- WebTransport bridge 与当前 WebUI HTTPS 服务共用端口，默认 `9005`。
- WebTransport 要求 HTTPS 或 localhost。

### DELETE /api/moq/tracks/{track_id}

从 WebUI 轨道列表中移除轨道，并清理该轨道订阅/预览状态。

### 浏览器播放约束

当前浏览器预览主路径是：

```text
WebTransport /wt/preview + MediaSource Extensions
```

publisher 输出建议为 H.264 fMP4：

1. metadata JSON，建议作为第一个对象
2. fMP4 init segment，必须包含 `ftyp` 和 `moov`
3. 连续 fMP4 media fragments，通常是 `moof` / `mdat`

推荐 metadata：

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

不适合直接作为当前浏览器预览输入的格式：

- raw H.264 Annex-B 裸流
- RTP / RTSP
- MPEG-TS
- 一次性完整 MP4 文件对象流
- 未适配 metadata / MSE 逻辑的其他容器

## 9. WebSocket

### WS /ws

WebUI 使用该 WebSocket 接收实时更新，也支持少量客户端控制消息。

连接建立后，后端会立即向该连接发送：

- `AGENT_LIST`
- `DASHBOARD_SNAPSHOT`

#### 客户端发送到 WebUI 后端

##### DISPATCH_TASK

本地 WebSocket 任务广播，不写入本地 DB。

```json
{
  "type": "DISPATCH_TASK",
  "payload": {
    "taskId": "task-001",
    "agentIds": ["did:acn:agent:001"]
  }
}
```

处理结果：后端向所有 WebSocket 客户端广播 `TASK_DISPATCHED`，payload 原样透传。

##### EMERGENCY_LAND

```json
{
  "type": "EMERGENCY_LAND"
}
```

处理结果：后端向所有 WebSocket 客户端广播 `EMERGENCY_LAND`，payload 包含 `timestamp`。

##### ABORT_ALL

```json
{
  "type": "ABORT_ALL"
}
```

处理结果：后端向所有 WebSocket 客户端广播 `ABORT_ALL`，payload 包含 `timestamp`。

##### PING

```json
{
  "type": "PING"
}
```

处理结果：后端仅向当前连接回复：

```json
{
  "type": "PONG",
  "timestamp": "2026-04-28T10:00:00.000000"
}
```

##### REFRESH

```json
{
  "type": "REFRESH"
}
```

处理结果：

- 后端调用 ARF `/clear`
- 清空 WebUI 本地 agent/task 运行态和内存缓存
- 成功时向所有 WebSocket 客户端广播 `REFRESH_COMPLETE`
- 失败时仅向当前连接发送 `REFRESH_ERROR`

#### WebUI 后端发送到客户端

##### AGENT_LIST

发送当前 agent 列表。

```json
{
  "type": "AGENT_LIST",
  "payload": {
    "agents": []
  }
}
```

##### DASHBOARD_SNAPSHOT

发送 dashboard 快照。payload 与 `GET /api/dashboard/overview` 返回结构一致。

##### TASKS_UPDATED

任务列表发生变化时发送。

```json
{
  "type": "TASKS_UPDATED",
  "payload": {
    "timestamp": "2026-04-28T10:00:00.000000",
    "tasks": [],
    "dashboard": {}
  }
}
```

##### VIDEO_TRACKS_AVAILABLE

视频轨道列表发生变化时发送。

```json
{
  "type": "VIDEO_TRACKS_AVAILABLE",
  "payload": {
    "tracks": [],
    "timestamp": "2026-04-28T10:00:00.000000"
  }
}
```

##### REFRESH_COMPLETE

clear/refresh 成功时发送。

```json
{
  "type": "REFRESH_COMPLETE",
  "payload": {
    "timestamp": "2026-04-28T10:00:00.000000",
    "agents": [],
    "arf_response": {},
    "dashboard": {},
    "tasks": []
  }
}
```

##### REFRESH_ERROR

WebSocket `REFRESH` 失败时发送给请求方。

```json
{
  "type": "REFRESH_ERROR",
  "payload": {
    "timestamp": "2026-04-28T10:00:00.000000",
    "error": "ARF clear failed with HTTP 500",
    "detail": "..."
  }
}
```

##### PIPELINE_LOG

收到 `/acn/v3/pipeline-logs` 后广播。

```json
{
  "type": "PIPELINE_LOG",
  "payload": {
    "source": "AgentGW",
    "destination": "IDM",
    "timestamp": "2026-04-28T10:00:00Z",
    "task_id": "task-001",
    "protocol": "HTTP/2",
    "headers": {},
    "abstract": "Identity verification completed",
    "content": "VC issued successfully"
  }
}
```

##### AGENT_STATUS_UPDATE

收到 `/acn/v3/element-logs` 后广播。

```json
{
  "type": "AGENT_STATUS_UPDATE",
  "payload": {
    "agent_id": "did:acn:agent:001",
    "log_type": "PublishAgent",
    "element_id": "AgentGW",
    "timestamp": "2026-04-28T10:00:00Z",
    "log": {
      "time": "10:00:00",
      "level": "info",
      "message": "PublishAgent: did:acn:agent:001"
    },
    "agent": {}
  }
}
```

##### TASK_DISPATCHED

收到 WebSocket `DISPATCH_TASK` 后广播，payload 为客户端传入的 payload。

##### EMERGENCY_LAND

收到 WebSocket `EMERGENCY_LAND` 后广播。

##### ABORT_ALL

收到 WebSocket `ABORT_ALL` 后广播。

##### PONG

收到 WebSocket `PING` 后，仅向当前连接回复。

## 10. 测试示例

### 健康检查

```bash
curl --noproxy '*' -sk https://127.0.0.1:9005/api/health
```

### 发送 PublishAgent

```bash
curl --noproxy '*' -sk -X POST https://127.0.0.1:9005/acn/v3/element-logs \
  -H "Content-Type: application/json" \
  -d '{
    "method": "POST",
    "url": "/acn/v3/element-logs",
    "headers": {
      "Content-Type": "application/json"
    },
    "body": {
      "element_id": "AgentGW",
      "log_type": "PublishAgent",
      "timestamp": "2026-04-28T10:00:00Z",
      "content": {
        "agent_name": "Test Agent",
        "agent_id": "did:acn:agent:001",
        "agent_capability": ["video-publish"],
        "agent_status": "online",
        "priority": "5",
        "consent": {
          "need_consumer_ue_authorization": false,
          "need_producer_authorization": true,
          "support_producer_ue_authorization": false
        }
      }
    }
  }'
```

### 运行完整 agent/task 消息流测试

```bash
python3 test/agent_task_message_flow.py --base-url https://127.0.0.1:9005 --interactive
```

该脚本会覆盖：

- `PublishAgent`
- `TaskExecution`
- `PublisherTrackAdd`
- `PublisherTrackDel`
- `TaskExecutionTermination`
- `DeleteAgent`
- 两个连续任务的创建、完成和最终清理
