# 1080p MOQ 视频流测试

本目录包含1080p H.264视频通过MOQ协议传输的完整测试套件。

## 目录结构

```
test/moq_1080p_test/
├── README.md                 # 本文件
├── test_1080p.h264          # 1080p测试视频文件 (1920x1080, 30fps, 10s)
├── publish_1080p.py         # Publisher: 读取H.264并推送到MOQ Relay
├── video_server_9006.py     # Subscriber + Web Server: 订阅MOQ并转码为MJPEG提供HTTP 9006
├── run_1080p_pipeline.sh    # 一键启动脚本
└── run_full_pipeline_test.md # 测试文档
```

## 测试组件

### 1. Publisher (publish_1080p.py)
- **功能**: 读取test_1080p.h264文件，分割为NAL单元，通过MOQ推送到Relay
- **配置**:
  - RELAY_HOST: localhost
  - RELAY_PORT: 9008 (使用独立Relay)
  - TASK_ID: test-ffmpeg-video
  - AGENT_ID: ffmpeg-publisher
  - Track: Video
  - FPS: 30

### 2. Subscriber + Web Server (video_server_9006.py)
- **功能**:
  - 订阅MOQ track接收H.264视频
  - 使用FFmpeg实时转码H.264 → MJPEG
  - 通过HTTP 9006端口提供Web界面
- **端点**:
  - `/` - Web界面
  - `/mjpeg` - MJPEG视频流
  - `/status` - JSON状态信息

### 3. Relay
使用webui/moq/relay实现，在9008端口独立运行。

## 快速开始

### 方法1: 使用启动脚本
```bash
cd /root/lpx/webui/test/moq_1080p_test
./run_1080p_pipeline.sh
```

### 方法2: 手动启动

**1. 启动Relay (如果未运行)**
```bash
cd /root/lpx/webui
python3 -c "
import sys
sys.path.insert(0, '.')
from moq.relay.relay import MOQRelay
import asyncio

async def run():
    relay = MOQRelay(host='0.0.0.0', port=9008, cache_dir='/tmp/moq_relay_9008')
    await relay.start()
    print('Relay started on 9008')
    while True:
        await asyncio.sleep(1)

asyncio.run(run())
"
```

**2. 启动Publisher**
```bash
cd /root/lpx/webui
python3 test/moq_1080p_test/publish_1080p.py
```

**3. 启动Subscriber/Web Server**
```bash
cd /root/lpx/webui
python3 test/moq_1080p_test/video_server_9006.py
```

**4. 访问测试页面**
打开浏览器访问: http://localhost:9006

## 日志监控

```bash
# Publisher日志
tail -f /tmp/moq_1080p_test/publisher.log

# Server日志
tail -f /tmp/moq_1080p_test/server.log

# Relay日志
tail -f /tmp/moq_relay_9008.log
```

## 视频规格

- **分辨率**: 1920x1080 (1080p Full HD)
- **编码**: H.264 (Baseline Profile, Level 4.0)
- **帧率**: 30 fps
- **时长**: 10秒
- **总帧数**: 300帧 (2 I-frames + 298 P-frames)
- **文件大小**: ~1.6 MB
- **内容**: FFmpeg testsrc生成的测试图案

## 故障排除

### Publisher无法连接Relay
- 检查Relay是否在9008端口运行: `lsof -i :9008`
- 检查防火墙设置

### Subscriber收不到数据
- 确认Publisher和Subscriber使用相同的namespace
- 检查Relay日志查看订阅和转发状态
- 确认track已成功发布和订阅

### 浏览器无法显示视频
- 检查9006端口是否可访问: `curl http://localhost:9006/`
- 检查MJPEG流: `curl http://localhost:9006/mjpeg`
- 查看浏览器开发者工具网络面板

## 停止测试

```bash
# 停止所有相关进程
pkill -f "publish_1080p.py"
pkill -f "video_server_9006.py"
pkill -f "MOQRelay"
```
