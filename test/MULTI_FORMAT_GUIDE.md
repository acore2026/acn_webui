# 多格式视频传输方案指南

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        输入层 (Input)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ H.264/MOQT  │  │ MJPEG/HTTP  │  │ JPEG/HTTP   │              │
│  │ WebRTC      │  │ WebSocket   │  │ Raw Binary  │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
└─────────┼────────────────┼────────────────┼──────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    视频网关 (Video Gateway)                       │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  格式检测 (Format Detector)                          │       │
│  │  - 自动识别 H.264/MJPEG/JPEG                        │       │
│  └────────────────────┬────────────────────────────────┘       │
                       │                                          │
          ┌────────────┼────────────┐                            │
          ▼            ▼            ▼                            │
  ┌──────────────┐ ┌──────────┐ ┌──────────┐                    │
  │ H.264 Buffer │ │MJPEG Buf │ │JPEG Buf  │                    │
  └──────┬───────┘ └────┬─────┘ └────┬─────┘                    │
         │              │            │                            │
         └──────────────┼────────────┘                            │
                       │                                          │
                       ▼                                          │
  ┌─────────────────────────────────────────────────────┐       │
  │  实时转码器 (Real-time Transcoder)                   │       │
  │  - H.264 → JPEG (FFmpeg)                           │       │
  │  - JPEG → MJPEG                                     │       │
  │  - 缓存管理                                         │       │
  └────────────────────┬────────────────────────────────┘       │
└──────────────────────┼──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    输出层 (Output)                               │
│  ┌─────────────────────────────────────────────────────┐       │
│  │  HTTP Endpoints                                      │       │
│  │  ├─ /api/video/stream/{id}/mjpeg   (MJPEG Stream)   │       │
│  │  ├─ /api/video/stream/{id}/latest  (Single Frame)   │       │
│  │  ├─ /api/video/stream/{id}/info    (Metadata)       │       │
│  │  └─ /api/video/player/{id}         (HTML Player)    │       │
│  └─────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## 支持的格式

### 1. H.264 (输入)
- **来源**: MOQ 订阅、文件、网络流
- **处理**: 自动转码为 MJPEG
- **延迟**: ~100-300ms (取决于转码性能)
- **适用场景**: 高压缩率传输、带宽受限

### 2. MJPEG (输入/输出)
- **来源**: HTTP POST、WebSocket
- **处理**: 原生支持，无需转码
- **延迟**: ~50-100ms
- **适用场景**: 浏览器兼容、简单实现

### 3. JPEG (输入/输出)
- **来源**: HTTP POST、相机直接捕获
- **处理**: 包装为 MJPEG 流
- **延迟**: ~30-80ms
- **适用场景**: 单帧捕获、静态图像序列

### 4. WebRTC (计划中)
- **来源**: 浏览器、移动端
- **处理**: P2P 直连
- **延迟**: <50ms
- **适用场景**: 超低延迟实时通信

## 使用方法

### 方法一: 从 MOQ 接收 H.264 并转为 MJPEG

```python
# backend/app/moq_video.py
from backend.app.video_gateway import ingest_h264_frame

async def on_moq_frame_received(frame: VideoFrame):
    # 自动检测为 H.264 并存储
    await ingest_h264_frame(
        track_id=frame.track_name,
        h264_data=frame.payload
    )
```

前端使用:
```html
<img src="/api/video/stream/{track_id}/mjpeg" width="640" height="360">
```

### 方法二: 直接接收 MJPEG

```python
# 接收 HTTP POST 的 MJPEG 数据
@app.post("/video/ingest/{track_id}")
async def ingest_video(track_id: str, request: Request):
    data = await request.body()
    await gateway.ingest_frame(track_id, data)
    return {"status": "ok"}
```

### 方法三: 混合输入 (推荐)

```python
# 支持任意格式自动检测
@app.post("/video/ingest/{track_id}")
async def ingest_any_format(track_id: str, request: Request):
    data = await request.body()
    
    # 自动检测格式 (H.264/MJPEG/JPEG)
    success = await gateway.ingest_frame(track_id, data)
    
    return {
        "status": "success" if success else "error",
        "format_detected": gateway.get_latest_frame(track_id).format.value
    }
```

## API 端点

### 1. MJPEG 流 (实时)
```
GET /api/video/stream/{track_id}/mjpeg
Content-Type: multipart/x-mixed-replace
```
前端:
```html
<img src="/api/video/stream/agent123_task456_video/mjpeg">
```

### 2. 最新帧 (单张)
```
GET /api/video/stream/{track_id}/latest
Content-Type: image/jpeg
```
前端:
```javascript
// 轮询刷新
setInterval(() => {
    img.src = `/api/video/stream/${trackId}/latest?` + Date.now();
}, 100);
```

### 3. 流信息
```
GET /api/video/stream/{track_id}/info
```
返回:
```json
{
    "track_id": "agent123_task456_video",
    "status": "active",
    "format": "h264",
    "width": 640,
    "height": 360,
    "timestamp": "2024-01-15T10:30:00",
    "is_keyframe": true,
    "data_size": 15234
}
```

### 4. 播放器页面
```
GET /api/video/player/{track_id}
```
返回完整的 HTML 播放器页面，可直接在浏览器中打开或嵌入 iframe。

## 前端组件

### UniversalVideoCard (推荐)

```jsx
import UniversalVideoCard from './components/UniversalVideoCard';

function App() {
    return (
        <UniversalVideoCard
            trackId="agent123_task456_video"
            title="Drone Camera 1"
            width={640}
            height={360}
            preferredFormat="auto"  // 自动选择最佳格式
        />
    );
}
```

特性:
- ✅ 自动检测浏览器能力
- ✅ 优先使用 MJPEG (兼容性最好)
- ✅ 支持 H.264 WebCodecs 解码
- ✅ 支持 WebRTC (计划中)
- ✅ 自动重连
- ✅ 显示格式和状态

## 性能对比

| 格式 | 延迟 | CPU占用 | 带宽 | 浏览器兼容 | 实现复杂度 |
|------|------|---------|------|------------|-----------|
| H.264 → MJPEG | 100-300ms | 高 (转码) | 中 | ⭐⭐⭐ 所有 | ⭐⭐ 中等 |
| MJPEG 原生 | 50-100ms | 低 | 高 | ⭐⭐⭐ 所有 | ⭐ 简单 |
| JPEG 轮询 | 30-80ms | 低 | 高 | ⭐⭐⭐ 所有 | ⭐ 简单 |
| WebRTC | <50ms | 中 | 自适应 | ⭐⭐ 现代浏览器 | ⭐⭐⭐ 复杂 |

## 部署建议

### 场景 1: 兼容第一
```
MOQ (H.264) → Gateway (转码) → MJPEG → Browser
```
- ✅ 所有浏览器支持
- ✅ 无需 WebCodecs
- ⚠️ 需要转码服务器

### 场景 2: 性能优先
```
MOQ (H.264) → Browser (WebCodecs解码)
```
- ✅ 低延迟
- ✅ 低CPU占用
- ⚠️ 仅现代浏览器

### 场景 3: 混合模式 (推荐)
```
MOQ (H.264) → Gateway
                   ├─ MJPEG (旧浏览器)
                   └─ H.264 WebCodecs (新浏览器)
```
- ✅ 自适应
- ✅ 最佳兼容性
- ✅ 渐进增强

## 测试命令

```bash
# 运行多格式测试
python3 test/test_multi_format.py

# 启动测试 H.264 流
python3 test/test_h264_video.py

# 启动 MJPEG 服务器
python3 test/test_mjpeg_display.py

# 查看所有流
curl http://localhost:9005/api/video/streams

# 查看流信息
curl http://localhost:9005/api/video/stream/{track_id}/info
```

## 故障排除

### H.264 转码失败
```bash
# 检查 FFmpeg
ffmpeg -version

# 手动测试转码
ffmpeg -f h264 -i input.h264 -vf scale=640:360 -q:v 5 output.jpg
```

### MJPEG 流不显示
1. 检查 HTTP 端点是否可达
2. 确认 `Content-Type: multipart/x-mixed-replace`
3. 尝试 `<img>` 标签而不是 `<video>`

### 高延迟
1. 使用 JPEG 轮询代替 MJPEG (更低延迟)
2. 减少转码质量参数 `-q:v 10`
3. 使用 WebRTC (最低延迟)

## 下一步

1. ✅ 基础 H.264 支持
2. ✅ MJPEG 流输出
3. ✅ 自动格式检测
4. ✅ HTTP API
5. 🔄 WebRTC 支持 (开发中)
6. 🔄 GPU 硬件加速转码 (计划中)
