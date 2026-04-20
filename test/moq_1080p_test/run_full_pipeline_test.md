# 1080p MOQ 视频流完整测试方案

## 当前状态

### ✅ 已运行组件
1. **MOQ Relay** (agent_gw): 运行在 localhost:9003
2. **Publisher**: 读取 test_1080p.h264 并推送到 Relay
3. **HTTP Server (9006)**: 已创建，但订阅未收到数据

### ❌ 问题
Subscriber订阅成功但收不到数据，可能是因为Relay的路由机制需要特定的namespace格式。

## 推荐测试方案

### 方案1: 使用WebUI Backend现有的MOQ订阅机制

WebUI backend (port 9005) 已经有完整的MOQ订阅实现。我们可以：

1. **修改Publisher** 使用WebUI期望的namespace格式
2. **通过WebUI Backend** 订阅视频
3. **通过WebUI Frontend** 显示视频

### 方案2: 直接使用FFmpeg生成MJPEG流

绕过MOQ，直接用FFmpeg生成MJPEG并通过HTTP 9006提供：

```bash
ffmpeg -re -i test_1080p.h264 -f mjpeg -q:v 5 http://localhost:9006/mjpeg
```

### 方案3: 启动专用的MOQ Relay进行测试

使用webui目录下的moq relay，而不是agent_gw的relay：

```bash
cd /root/lpx/webui
python3 -m moq.relay.relay --port 9004
```

## 下一步

请问您希望我采用哪个方案继续测试？

- **方案1**: 最符合您的原始需求（端到端MOQ测试）
- **方案2**: 最快验证视频显示功能
- **方案3**: 使用独立的Relay进行隔离测试
