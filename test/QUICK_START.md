# 快速开始 - MOQ 视频测试

## 🚀 一键运行测试

```bash
cd /root/lpx/webui/test
./run_h264_test.sh
```

## 📝 常用命令

### 检查环境
```bash
# 检查 FFmpeg
ffmpeg -version | head -1

# 检查 WebUI 状态
curl -s http://localhost:9005/api/moq/status | python3 -m json.tool

# 检查 Relay
curl -s http://localhost:9003 2>/dev/null || echo "Relay may be running (UDP)"
```

### 运行测试

#### 方法 1：H.264 视频测试（推荐）
```bash
python3 /root/lpx/webui/test/test_h264_video.py
```
**输出：** 生成 10 秒 H.264 视频并通过 MOQ 发送

#### 方法 2：简单图片测试（快速）
```bash
python3 /root/lpx/webui/test/test_simple_moq.py
```
**输出：** 发送 100 个 PNG 图片

#### 方法 3：独立测试（带 relay）
```bash
# 终端 1
python3 /root/lpx/webui/test/moq_relay.py

# 终端 2
python3 /root/lpx/webui/test/moq_subscriber.py

# 终端 3
python3 /root/lpx/webui/test/moq_publisher.py
```

### 查看结果

```bash
# 查看 MOQ 状态
curl -s http://localhost:9005/api/moq/status | python3 -m json.tool

# 获取 track ID
TRACK_ID=$(curl -s http://localhost:9005/api/moq/status | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['subscribed_tracks'][0])")
echo $TRACK_ID

# 查看帧数据
curl -s "http://localhost:9005/api/moq/tracks/$TRACK_ID/frames" | python3 -m json.tool | head -30
```

## 🎯 验证成功

成功运行后，你应该看到：

1. **Publisher 输出：**
   ```
   [✓] Published 1521 NAL units in 52.1s
   ```

2. **WebUI 状态：**
   ```json
   {
     "object_count": 123,
     "buffered_frames": 30,
     "state": "received"
   }
   ```

3. **浏览器显示：**
   - 打开 http://localhost:9005
   - 视频卡片区域显示视频（需要 WebCodecs 支持）

## 🔧 故障排除

### FFmpeg 未安装
```bash
apt-get update && apt-get install -y ffmpeg
```

### Relay 未运行
```bash
# 方法 1：启动 agent_gw（推荐）
cd /home/acn/zqm/acn_gw && python3 agent_gw.py

# 方法 2：使用独立 relay
python3 /root/lpx/webui/test/moq_relay.py
```

### WebUI 未启动
```bash
cd /root/lpx/webui/backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9005
```

### 端口冲突
```bash
# 检查端口占用
lsof -i :9003  # relay
lsof -i :9005  # webui

# 杀死进程
pkill -f agent_gw
pkill -f "uvicorn app.main"
```

## 📊 测试参数修改

编辑 `/root/lpx/webui/test/test_h264_video.py`：

```python
# 视频设置
VIDEO_DURATION = 10      # 时长（秒）
VIDEO_FPS = 30          # 帧率
VIDEO_WIDTH = 640       # 宽度
VIDEO_HEIGHT = 360      # 高度
VIDEO_BITRATE = "500k"  # 码率

# MOQ 设置
RELAY_HOST = "localhost"
RELAY_PORT = 9003       # relay 端口
TASK_ID = "task-c2a09"  # 任务 ID（必须与 WebUI 订阅的一致）
AGENT_ID = "did:udid:..."  # Agent ID
```

## 🐛 调试

### 后端日志
```bash
tail -f /root/lpx/webui/logs/backend.log | grep -E "moq|video|object|frame"
```

### 浏览器调试
1. 打开 http://localhost:9005
2. 按 F12 打开开发者工具
3. 查看 Console 和 Network 标签
4. 检查 WebSocket 消息

### 测试数据格式
```bash
# 查看帧大小分布
curl -s http://localhost:9005/api/moq/tracks/$TRACK_ID/frames | python3 -c "
import json,sys
data = json.load(sys.stdin)
sizes = [f['payload_size'] for f in data['frames']]
print('Frame sizes:', sorted(set(sizes)))
"
```

## 📚 相关文件

- `test_h264_video.py` - H.264 视频测试
- `test_simple_moq.py` - 简单图片测试
- `test_moq_integration.py` - 集成测试
- `moq_relay.py` - 独立 relay
- `moq_publisher.py` - 独立 publisher
- `moq_subscriber.py` - 独立 subscriber
- `README_TEST.md` - 详细测试文档
- `H264_TEST_RESULTS.md` - H.264 测试结果
