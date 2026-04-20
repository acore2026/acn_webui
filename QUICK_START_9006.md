# 快速开始 - 9006 端口真实视频

## ✅ 服务状态

**端口**: 9006  
**状态**: 🟢 运行中  
**功能**: 实时生成 MJPEG 视频流（带动态蓝圈动画）

## 🚀 立即查看

### 方法 1: 浏览器直接打开

在浏览器中访问：
```
http://localhost:9006
```

你应该能看到：
- 🔴 "Live MJPEG Stream" 标题
- 一个动态视频画面（蓝色圆圈在移动）
- "✅ If you see moving blue circle, MJPEG is working!"

### 方法 2: 在 <img> 标签中使用

```html
<img src="http://localhost:9006/mjpeg" width="640" height="360">
```

### 方法 3: 在 React 组件中使用

```jsx
function VideoPlayer() {
    return (
        <img 
            src="http://localhost:9006/mjpeg"
            width={640}
            height={360}
            alt="Live Stream"
        />
    );
}
```

## 🧪 测试命令

```bash
# 检查服务状态
curl http://localhost:9006/

# 查看 MJPEG 流（返回二进制图片数据）
curl http://localhost:9006/mjpeg

# 检查端口占用
lsof -i :9006
```

## 🎯 实际应用场景

### 场景 1: WebUI 集成

在你的 WebUI 前端（端口 9005）中添加：

```html
<!-- 在 SidebarRight.jsx 中添加 -->
<div className="video-card">
    <img src="http://localhost:9006/mjpeg" width="640" height="360">
    <div className="video-info">
        <span>Live Stream (9006)</span>
    </div>
</div>
```

### 场景 2: 多路视频

启动多个服务（不同端口）：

```bash
# 第一个视频（已在运行）
# python3 test_mjpeg_generator.py  # 端口 9006

# 第二个视频（复制脚本修改 PORT=9007）
python3 test_mjpeg_generator_9007.py &
```

前端：
```html
<img src="http://localhost:9006/mjpeg">  <!-- 视频 1 -->
<img src="http://localhost:9007/mjpeg">  <!-- 视频 2 -->
```

### 场景 3: 替换真实 MOQ 数据

当有真实的 H.264 数据时：

```python
# backend/app/moq_video.py
from backend.app.video_gateway import ingest_h264_frame

async def on_moq_frame(frame):
    await ingest_h264_frame(
        track_id=frame.track_name,
        h264_data=frame.payload
    )
```

前端使用相同方式显示：
```html
<img src="http://localhost:9006/video/stream/{track_id}/mjpeg">
```

## 📊 视频参数

| 参数 | 值 |
|------|-----|
| 分辨率 | 640x360 |
| 帧率 | 30 FPS |
| 格式 | MJPEG |
| 动画 | 蓝色移动圆圈 + 网格背景 |
| 时间戳 | 实时显示 |

## 🔧 故障排除

### 看不到视频？

1. **检查服务是否运行**
   ```bash
   lsof -i :9006
   ```

2. **直接访问测试**
   ```bash
   curl -s http://localhost:9006/ | head
   ```

3. **重启服务**
   ```bash
   lsof -ti:9006 | xargs kill -9
   python3 /root/lpx/webui/test_mjpeg_generator.py &
   ```

### 视频不流畅？

- 降低帧率：修改 `FPS = 15`
- 降低分辨率：修改 `WIDTH = 320, HEIGHT = 180`
- 降低质量：修改 `quality=50`

## 💡 关键概念

**MJPEG 是什么？**
- 一张张 JPEG 图片连续播放
- 浏览器用 `<img>` 直接显示
- 所有浏览器都支持
- 无需解码器

**为什么用 9006 端口？**
- 9005 是 WebUI（不改动）
- 9006 是专门视频服务（新增）
- 两个服务独立运行

**怎么集成到现有系统？**
```
MOQ H.264 ──► video_gateway ──► MJPEG ──► Browser
                                ↑
                         在 9006 端口
```

## ✅ 验证步骤

1. ✅ 浏览器打开 `http://localhost:9006`
2. ✅ 看到动态蓝圈视频
3. ✅ 右键图片 → "在新标签页打开图片" → 能看到 MJPEG 流
4. ✅ 在 WebUI 页面嵌入 `<img src="http://localhost:9006/mjpeg">`

**现在你打开浏览器就能看到真实视频了！**
