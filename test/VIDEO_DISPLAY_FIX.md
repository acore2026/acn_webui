# H.264 视频显示修复指南

## 问题原因

前端无法显示 H.264 视频的原因是：**`payload_base64` 字段在数据流中丢失了**

### 数据流分析

```
Backend (main.py)          Frontend (App.jsx)           Frontend (SidebarRight.jsx)
      |                            |                                  |
      |-- VIDEO_FRAME ------------>|                                  |
      |   payload_base64           |-- setMoqFrames                   |
      |                            |   (缺少 payload_base64!)         |
      |                            |         |                        |
      |                            |         v                        |
      |                            |   moqFrames[track_id]            |
      |                            |   (没有 payload_base64)          |
      |                            |         |                        |
      |                            |         v                        |
      |                            |------------------------------->  |
      |                            |    frameInfo                     |
      |                            |    (缺少 payload_base64)         |
      |                            |                                  |
      |                            |                       H264VideoCard
      |                            |                       期望: payload_base64
      |                            |                       实际: undefined
```

### 修复内容

**文件**: `/root/lpx/webui/frontend/src/App.jsx`

**修改**: 在 `VIDEO_FRAME` 处理中添加了 `payload_base64` 字段

```javascript
case 'VIDEO_FRAME':
  if (data.payload) {
    const { payload_base64, ... } = data.payload;  // 提取 payload_base64
    setMoqFrames(prev => ({
      ...prev,
      [track_id]: {
        ...,
        payload_base64,  // <-- 添加这一行
        ...
      }
    }));
  }
```

## 修复验证

### 1. 检查修复是否已应用

```bash
# 查看 App.jsx 中是否包含 payload_base64
grep -n "payload_base64" /root/lpx/webui/frontend/src/App.jsx
```

**预期输出**:
```
181:                payload_base64,
```

### 2. 检查前端构建

```bash
# 查看构建时间
ls -la /root/lpx/webui/frontend/build/static/js/main.*.js
```

构建时间应该是刚刚的。

### 3. 运行测试

```bash
# 方式 1: 使用测试脚本
cd /root/lpx/webui/test
./test_video_display.sh

# 方式 2: 直接运行
python3 /root/lpx/webui/test/test_h264_video.py
```

### 4. 浏览器验证

1. **打开浏览器**: http://localhost:9005
2. **打开开发者工具**: F12
3. **查看 Console**:
   - 搜索 `[WebSocket] Received` 确认收到 VIDEO_FRAME
   - 搜索 `[MOQ H264]` 查看解码器状态
4. **检查视频卡片**:
   - 状态应该从 "Waiting for data..." 变为 "Decoding" 或 "LIVE H264"
   - Canvas 应该显示解码后的视频

## 调试技巧

### 浏览器 Console 检查

```javascript
// 检查 moqFrames 是否包含 payload_base64
JSON.parse(localStorage.getItem('debug_moq_frames') || '{}')

// 检查 WebSocket 消息
// 在 Console 中过滤: VIDEO_FRAME
```

### 后端日志检查

```bash
tail -f /root/lpx/webui/logs/backend.log | grep -E "VIDEO_FRAME|payload"
```

### 网络检查

```bash
# 检查 WebSocket 连接
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Host: localhost:9005" \
  -H "Origin: http://localhost:9005" \
  http://localhost:9005/ws
```

## 常见问题

### Q: 刷新页面后还是不显示

**A**: 检查以下几点:
1. 确认前端已重新构建: `npm run build`
2. 清除浏览器缓存: Ctrl+Shift+R 强制刷新
3. 检查 WebSocket 连接: Console 中搜索 `[WebSocket] Connected`

### Q: Console 显示 "WebCodecs unavailable"

**A**: 浏览器不支持 WebCodecs API。解决方案:
1. 使用 Chrome 94+ 或 Edge 94+
2. 检查是否开启了实验性功能: chrome://flags/#enable-webcodecs

### Q: 显示 "waiting SPS/PPS"

**A**: H.264 流缺少序列参数集。需要:
1. 确保 Publisher 发送的流包含 SPS (NAL type 7) 和 PPS (NAL type 8)
2. 检查 H.264 编码参数: `-profile:v baseline -level 3.0`

### Q: 显示 "decoder error"

**A**: 解码器配置错误。检查:
1. H.264 格式是否为 Annex B (带 start code: 00 00 00 01)
2. 浏览器是否支持该 profile/level
3. 查看 Console 中的详细错误信息

## 完整的测试流程

```bash
# 1. 启动后端 (如果未运行)
cd /root/lpx/webui/backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9005 &

# 2. 运行 H.264 测试
python3 /root/lpx/webui/test/test_h264_video.py

# 3. 在浏览器中查看
# 打开 http://localhost:9005
# 按 F12 打开开发者工具
# 查看 Console 和 Network 标签
```

## 文件清单

| 文件 | 说明 |
|------|------|
| `/root/lpx/webui/frontend/src/App.jsx` | 修复后的主应用文件 |
| `/root/lpx/webui/frontend/src/components/SidebarRight/SidebarRight.jsx` | 视频卡片组件 |
| `/root/lpx/webui/test/test_h264_video.py` | H.264 视频测试脚本 |
| `/root/lpx/webui/test/test_video_display.sh` | 视频显示测试脚本 |
| `/root/lpx/webui/test/rebuild_frontend.sh` | 前端构建脚本 |

## 预期结果

修复成功后，你应该看到:

1. **Publisher**: 
   ```
   [✓] Published 1521 NAL units
   ```

2. **Backend**:
   ```
   [VIDEO_FRAME] track=... mime=video/h264 codec=h264 size=...
   ```

3. **Browser Console**:
   ```
   [WebSocket] Received: {type: "VIDEO_FRAME", payload: {...}}
   [MOQ H264] Configured decoder with codec: avc1.42e01e
   ```

4. **Video Card**:
   - 状态: "LIVE H264"
   - Canvas 显示动态视频画面
   - FPS 统计显示正常
