# ACN Agent Monitor Backend API 文档

后端服务运行在 **端口 9005**

Base URL: `https://<host>:9005`

---

## 1. 系统状态接口

### GET /api/health
健康检查

**响应示例：**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-10T10:00:00.000000",
  "websocket_clients": 1
}
```

---

## 2. Agent 管理接口

### GET /api/agents
获取所有注册的 agent

**响应示例：**
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
  "timestamp": "2026-04-10T10:00:00.000000"
}
```

---

## 3. 日志接口

### GET /api/logs?limit=100
获取后端日志

**参数：**
- `limit`: 返回日志条数（默认100）

**响应示例：**
```json
{
  "logs": [
    {
      "time": "2026-04-10T10:00:00.000000",
      "level": "info",
      "message": "Agent GW -> IDM: Test message"
    }
  ],
  "total": 1,
  "timestamp": "2026-04-10T10:00:00.000000"
}
```

---

## 4. 流程日志接口 (Pipeline Logs)

### POST /acn/v3/pipeline-logs
接收流程日志消息，用于 Message Flow 显示

**请求格式：**
```json
{
  "source": "Agent GW",
  "destination": "IDM",
  "timestamp": "2025-07-29T18:35:40Z",
  "task_id": "task-12345",
  "protocol": "HTTP/2",
  "headers": {"Content-Type": "application/json"},
  "abstract": "Agent registration request",
  "content": "Requesting digital identity"
}
```

**字段说明：**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source | string | 是 | 消息发送方 |
| destination | string | 是 | 消息接收方 |
| timestamp | string | 否 | ISO 8601 时间戳 |
| task_id | string | 否 | 任务ID |
| protocol | string | 否 | 协议类型 |
| headers | object | 否 | 消息头 |
| abstract | string | 否 | 消息摘要 |
| content | string | 否 | 详细内容 |

**响应示例：**
```json
{
  "status": "success",
  "message": "Log received and broadcasted",
  "timestamp": "2026-04-10T10:00:00.000000"
}
```

---

## 5. Agent 状态日志接口 (Element Logs)

### POST /acn/v3/element-logs
接收 agent 状态更新，用于 Agent Work Status 显示

**请求格式：**
```json
{
  "element_id": "IDM",
  "log_type": "ApplyProfile",
  "timestamp": "2025-07-29T18:35:40Z",
  "content": {
    "agent_id": "did:acn:agent:987654321",
    "agent_name": "Alice的个人助手",
    "agent_capability": "跌倒监测-手环",
    "owner": "user-001",
    "network_capability": "6G业务开通"
  }
}
```

**log_type 取值及对应状态：**
| log_type | work_status | 说明 |
|----------|-------------|------|
| ApplyProfile | working | 申请数字身份 |
| PublishAgent | working | 注册 agent 能力 |
| SetupConnection | online | 建立连接 |
| LLMMessage | working | LLM 处理消息 |

**content 字段说明：**
| 字段 | 类型 | 说明 |
|------|------|------|
| agent_id | string | Agent 唯一标识 |
| agent_name | string | Agent 名称 |
| agent_capability | string/array | Agent 能力 |
| owner | string | 所有者 |
| network_capability | string | 网络能力 |

**响应示例：**
```json
{
  "status": "success",
  "timestamp": "2026-04-10T10:00:00.000000"
}
```

---

## 6. MOQ 视频流接口

当前 Agents 页签的 Videos 区域使用集成在 9005 WebUI 内的 MOQ 订阅和浏览器播放桥接。订阅入口是 `POST /api/subscriber/start`，浏览器预览通过 WebTransport `/wt/preview` 接收 metadata、MP4 init segment 和 fMP4 fragments，并通过 MediaSource Extensions 渲染。

### GET /api/moq/status
获取 MOQ 订阅状态

**响应示例：**
```json
{
  "status": "available",
  "connected": true,
  "relay_host": "localhost",
  "relay_port": 9003,
  "subscribed_tracks": ["manual_video_h264-live"],
  "discovered_tracks": [],
  "subscription_debug": [],
  "timestamp": "2026-04-10T10:00:00.000000"
}
```

### GET /api/moq/tracks
获取当前 WebUI 已知的视频轨道和已订阅轨道。

**响应示例：**
```json
{
  "status": "success",
  "tracks": [],
  "subscribed_tracks": [],
  "timestamp": "2026-04-10T10:00:00.000000"
}
```

### POST /api/subscriber/start
订阅或切换一个浏览器预览轨道。`namespace` 和 `trackName` 都是必填项，且必须与 publisher 发布到 MOQ relay 的真实轨道匹配。

**请求格式：**
```json
{
  "namespace": "video",
  "trackName": "h264-live"
}
```

**响应示例：**
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
    "path": "/wt/preview",
    "certHash": "..."
  },
  "timestamp": "2026-04-10T10:00:00.000000"
}
```

### DELETE /api/moq/tracks/{track_id}
从 WebUI 轨道列表中移除一个轨道，并清理该轨道的订阅/预览状态。

**示例：** `DELETE /api/moq/tracks/manual_video_h264-live`

**响应示例：**
```json
{
  "status": "success",
  "trackId": "manual_video_h264-live",
  "timestamp": "2026-04-10T10:00:00.000000"
}
```

### GET /api/video/stream/{track_id}/info
获取某个轨道的浏览器播放/转码状态。

**示例：** `GET /api/video/stream/manual_video_h264-live/info`

**响应示例：**
```json
{
  "track_id": "manual_video_h264-live",
  "status": "active",
  "watch_state": "subscribed",
  "has_metadata": true,
  "has_init_segment": true,
  "fragment_count": 120,
  "has_frame": true,
  "width": 1280,
  "height": 720,
  "metadata": {
    "container": "fMP4",
    "codec": "H.264",
    "mime_type": "video/mp4; codecs=\"avc1.64001F\"",
    "mse_codec": "avc1.64001F"
  }
}
```

### GET /api/video/stream/{track_id}/mjpeg
HTTP MJPEG fallback 流。主预览路径仍是 WebTransport + MediaSource。

### GET /api/video/stream/{track_id}/latest
获取最新一帧 JPEG snapshot。

### 浏览器播放约束

publisher 输出建议为 H.264 fMP4：

1. metadata JSON，建议作为第一个对象
2. fMP4 init segment，必须包含 `ftyp` 和 `moov`
3. 连续 fMP4 media fragments，通常是可追加到 MSE 的 `moof` / `mdat`

metadata 推荐字段：

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

浏览器会通过 `MediaSource.isTypeSupported(mime_type)` 校验格式支持。不适合直接输入当前浏览器预览的格式包括 raw H.264 Annex-B、RTP/RTSP、MPEG-TS、一次性完整 MP4 文件对象流，以及未适配 metadata / MSE 逻辑的其他容器。

---

## 7. WebRTC 视频流接口

### GET /api/video/streams
获取所有视频流

### GET /api/video/streams/{agent_id}
获取指定 agent 的视频流

### POST /api/video/streams/{agent_id}/register
注册视频流

**请求格式：**
```json
{
  "agent_name": "Drone Alpha",
  "stream_type": "camera",
  "resolution": "1920x1080",
  "fps": 30
}
```

### POST /api/video/webrtc/offer
处理 WebRTC offer

**请求格式：**
```json
{
  "stream_id": "stream-001",
  "offer": "...SDP offer..."
}
```

### POST /api/video/webrtc/answer
处理 WebRTC answer

### POST /api/video/webrtc/ice
处理 ICE candidate

### DELETE /api/video/streams/{stream_id}
注销视频流

---

## 测试示例

```bash
# 1. 健康检查
curl -k https://localhost:9005/api/health

# 2. 发送流程日志
curl -k -X POST https://localhost:9005/acn/v3/pipeline-logs \
  -H "Content-Type: application/json" \
  -d '{
    "source": "Agent GW",
    "destination": "IDM",
    "abstract": "Test message"
  }'

# 3. 发送 Agent 状态更新
curl -k -X POST https://localhost:9005/acn/v3/element-logs \
  -H "Content-Type: application/json" \
  -d '{
    "element_id": "IDM",
    "log_type": "ApplyProfile",
    "content": {
      "agent_id": "agent001",
      "agent_name": "Test Agent"
    }
  }'

# 4. 获取日志
curl -k https://localhost:9005/api/logs

# 5. MOQ 视频订阅
curl -k -X POST https://localhost:9005/api/subscriber/start \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "video",
    "trackName": "h264-live"
  }'
```
