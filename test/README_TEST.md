# MOQ Video Test 运行指南

## 测试环境要求

1. **FFmpeg** - 用于生成 H.264 测试视频
   ```bash
   apt-get update && apt-get install -y ffmpeg
   ```

2. **Python 依赖** - webui 目录下的 MOQ 模块
   ```bash
   cd /root/lpx/webui
   pip install -e .  # 或确保依赖已安装
   ```

3. **MOQ Relay** - 使用 agent_gw 的 relay（端口 9003）

## 测试脚本说明

### 1. H.264 视频测试（推荐）

生成真实 H.264 视频并通过 MOQ 传输：

```bash
cd /root/lpx/webui/test
python3 test_h264_video.py
```

**参数配置（在脚本内修改）：**
- `VIDEO_DURATION = 10` - 视频时长（秒）
- `VIDEO_FPS = 30` - 帧率
- `VIDEO_WIDTH = 640` - 宽度
- `VIDEO_HEIGHT = 360` - 高度
- `TASK_ID = "task-c2a09"` - 任务 ID（需与 WebUI 订阅的一致）
- `AGENT_ID = "did:udid:..."` - Agent ID

### 2. 简单测试（快速验证）

发送简单的 PNG 图片：

```bash
cd /root/lpx/webui/test
python3 test_simple_moq.py
```

### 3. 基础 MOQ 测试（独立 relay）

启动独立 relay 并测试 pub/sub：

```bash
cd /root/lpx/webui/test

# 终端 1：启动 relay
python3 moq_relay.py

# 终端 2：启动 subscriber
python3 moq_subscriber.py

# 终端 3：启动 publisher
python3 moq_publisher.py
```

或使用自动化脚本：
```bash
chmod +x run_test.sh
./run_test.sh
```

## 验证测试结果

### 1. 检查 WebUI 状态

```bash
curl -s http://localhost:9005/api/moq/status | python3 -m json.tool
```

**期望输出：**
```json
{
  "connected": true,
  "subscribed_tracks": ["..._task-c2a09_video"],
  "subscription_debug": [{
    "state": "received",
    "object_count": 123,
    "buffered_frames": 30
  }]
}
```

### 2. 查看接收到的帧

```bash
curl -s http://localhost:9005/api/moq/tracks/<track_id>/frames | python3 -m json.tool
```

获取 track_id：
```bash
curl -s http://localhost:9005/api/moq/status | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['subscribed_tracks'][0])"
```

### 3. 在浏览器中查看

1. 打开 `http://localhost:9005`
2. 登录 WebUI
3. 查看视频卡片区域
4. 打开浏览器开发者工具（F12）
5. 检查 Console 和 Network 标签

## 常见问题

### Q: FFmpeg 未安装
```bash
# Ubuntu/Debian
apt-get update && apt-get install -y ffmpeg

# CentOS/RHEL
yum install -y ffmpeg

# 或从源码编译
```

### Q: 端口 9003 被占用
```bash
# 检查占用
lsof -i :9003

# 杀死进程（如果是 agent_gw）
pkill -f agent_gw

# 或修改测试脚本使用其他端口
RELAY_PORT = 9004  # 在 test_h264_video.py 中修改
```

### Q: WebUI 未订阅正确的 track
```bash
# 查看当前订阅
curl -s http://localhost:9005/api/moq/status | python3 -m json.tool

# 修改测试脚本中的 TASK_ID 和 AGENT_ID 匹配 WebUI 订阅
```

### Q: 前端不显示视频
1. 检查浏览器是否支持 WebCodecs API
2. 检查 Console 是否有解码错误
3. 检查 Network 中 WebSocket 连接

## 调试技巧

### 1. 查看后端日志
```bash
tail -f /root/lpx/webui/logs/backend.log | grep -i "moq\|video\|object"
```

### 2. 检查 MOQ 消息流
```bash
# 在浏览器开发者工具中过滤：
# WebSocket 消息包含 "MOQ_VIDEO" 或 "VIDEO_FRAME"
```

### 3. 测试数据格式
```bash
# 检查接收到的帧大小分布
curl -s http://localhost:9005/api/moq/tracks/<track_id>/frames | python3 -c "
import json,sys
data = json.load(sys.stdin)
for f in data['frames'][:5]:
    print(f\"ID: {f['object_id']}, Size: {f['payload_size']}, Type: {f['frame_type']}\")
"
```

## 自动化测试流程

一键运行完整测试：

```bash
cd /root/lpx/webui/test

# 1. 确保 agent_gw 在运行（或 WebUI 已连接到 relay）
curl -s http://localhost:9003 > /dev/null && echo "Relay OK" || echo "Relay not available"

# 2. 运行 H.264 测试
python3 test_h264_video.py

# 3. 检查结果
echo "=== Checking WebUI Status ==="
curl -s http://localhost:9005/api/moq/status | python3 -c "
import json,sys
d = json.load(sys.stdin)
for sub in d.get('subscription_debug', []):
    print(f\"Track: {sub['track_id']}\")
    print(f\"  State: {sub['state']}\")
    print(f\"  Objects: {sub['object_count']}\")
    print(f\"  Frames: {sub['buffered_frames']}\")
"

# 4. 打开浏览器查看（在本地机器上）
echo "=== Open browser at http://$(hostname -I | awk '{print $1}'):9005 ==="
```
