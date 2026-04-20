# 视频服务 - 端口 9006

## ✅ 服务状态

**端口**: 9006  
**服务**: Video Service (多格式视频传输)  
**状态**: ✅ 运行中

## 🚀 快速启动

```bash
# 启动服务
./start_video_service.sh

# 或在后台运行
python3 backend/app/video_service.py &
```

## 📡 API 端点

### 1. 健康检查
```bash
curl http://localhost:9006/health
```
返回:
```json
{
    "status": "healthy",
    "gateway": true,
    "streams": 0
}
```

### 2. MJPEG 流 (实时)
```
GET /video/stream/{track_id}/mjpeg
```
**前端使用**:
```html
<img src="http://localhost:9006/video/stream/agent123_task456_video/mjpeg" width="640" height="360">
```

### 3. 最新帧 (单张)
```
GET /video/stream/{track_id}/latest
```
**前端使用**:
```javascript
// 轮询刷新
setInterval(() => {
    img.src = `http://localhost:9006/video/stream/${trackId}/latest?${Date.now()}`;
}, 100);
```

### 4. 流信息
```
GET /video/stream/{track_id}/info
```
返回:
```json
{
    "track_id": "agent123_task456_video",
    "status": "active",
    "format": "h264",
    "width": 640,
    "height": 360,
    "timestamp": 1234567890,
    "data_size": 15234
}
```

### 5. HTML 播放器
```
GET /video/player/{track_id}
```
**前端使用**:
```html
<iframe src="http://localhost:9006/video/player/agent123_task456_video" width="640" height="480"></iframe>
```

### 6. 注入 JPEG 数据 (测试)
```bash
curl -X POST http://localhost:9006/video/test/ingest-jpeg/test-track-001
```

### 7. 注入 H.264 数据 (测试)
```bash
curl -X POST http://localhost:9006/video/test/ingest-h264/test-track-001
```

### 8. 列出所有流
```bash
curl http://localhost:9006/video/streams
```

## 🧪 测试页面

打开测试页面:
```
file:///root/lpx/webui/test_video_9006.html
```

或者在浏览器中访问:
```
http://localhost:9006/video/player/test-mjpeg-001
```

## 🔧 功能特性

### 自动格式检测
服务自动检测输入格式:
- H.264 (0x00 0x00 0x00 0x01 开头)
- JPEG (0xFF 0xD8 开头)
- MJPEG (Content-Type: image/jpeg)

### 实时转码
- H.264 → JPEG (使用 FFmpeg)
- JPEG → MJPEG 流

### 多格式支持
| 格式 | 输入 | 输出 | 延迟 |
|------|------|------|------|
| H.264 | ✅ | ✅ (转码后) | ~100-300ms |
| MJPEG | ✅ | ✅ | ~50-100ms |
| JPEG | ✅ | ✅ | ~30-80ms |
| WebRTC | 🔄 | 🔄 | 计划中 |

## 📝 使用示例

### 场景 1: 从 MOQ 接收 H.264 并显示

**后端** (9005):
```python
from backend.app.video_gateway import ingest_h264_frame

async def on_moq_frame(track_id, h264_data):
    await ingest_h264_frame(track_id, h264_data)
```

**前端**:
```html
<!-- 自动转码为 MJPEG -->
<img src="http://localhost:9006/video/stream/{track_id}/mjpeg">
```

### 场景 2: 直接推送 JPEG

```bash
curl -X POST http://localhost:9006/video/ingest/my-track \
    --data-binary @frame.jpg \
    -H "Content-Type: image/jpeg"
```

然后前端显示:
```html
<img src="http://localhost:9006/video/stream/my-track/mjpeg">
```

### 场景 3: 混合模式 (推荐)

**前端 UniversalVideoCard**:
```jsx
<UniversalVideoCard
    trackId="agent123_task456_video"
    preferredFormat="auto"  // 自动选择 MJPEG/H.264
/>
```

## 🔍 故障排除

### 检查服务状态
```bash
# 查看端口占用
lsof -ti:9006

# 健康检查
curl http://localhost:9006/health

# 查看日志
ps aux | grep video_service
tail -f /root/lpx/webui/logs/video_service.log
```

### 服务无法启动
```bash
# 确保端口空闲
lsof -ti:9006 | xargs kill -9

# 重新启动
python3 backend/app/video_service.py &
```

### MJPEG 流不显示
1. 检查 track_id 是否正确
2. 确认数据已注入: `curl http://localhost:9006/video/streams`
3. 直接访问流 URL 测试

## 📂 文件位置

- 服务代码: `backend/app/video_service.py`
- 网关代码: `backend/app/video_gateway.py`
- 启动脚本: `start_video_service.sh`
- 测试页面: `test_video_9006.html`

## 🎯 与现有 WebUI 集成

现有 WebUI 运行在 **9005** 端口，视频服务在 **9006** 端口。

**无需重启现有服务！**

前端可以直接访问 9006 的 API:
```javascript
// 在 WebUI 前端代码中添加
const VIDEO_API = 'http://localhost:9006';

// 获取 MJPEG 流
const mjpegUrl = `${VIDEO_API}/video/stream/${trackId}/mjpeg`;

// 获取最新帧
const latestUrl = `${VIDEO_API}/video/stream/${trackId}/latest`;
```

## ✅ 总结

- ✅ 服务在 9006 端口运行
- ✅ 不重启现有 9005 服务
- ✅ 支持 H.264/MJPEG/JPEG 多种格式
- ✅ 自动格式检测和转码
- ✅ 所有浏览器兼容 (使用 MJPEG)
- ✅ 简单的 `<img>` 标签显示
