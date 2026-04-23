# MOQ Video Test 运行指南

## 当前推荐的测试

这个目录现在保留两条主路径：

1. **WebUI 手动演示**
   脚本：`moq_video_ui_demo.py`
   封装：`run_moq_video_ui_demo.sh`

2. **WebUI 自动化端到端测试**
   脚本：`moq_video_webui_e2e.py`

另外保留了一组低层 MOQ 工具：
- `moq_relay.py`
- `moq_publisher.py`
- `moq_subscriber.py`
- `run_test.sh`

## 环境要求

1. **FFmpeg**
   ```bash
   apt-get update && apt-get install -y ffmpeg
   ```

2. **WebUI 后端**
   默认地址：`http://localhost:9005`

3. **MOQ Relay**
   当前测试默认使用 AgentGW 的 relay：`127.0.0.1:9003`

4. **Playwright CLI**
   只有自动化 E2E 测试需要

## 1. 手动演示：moq_video_ui_demo.py

这是当前最适合人工联调 WebUI 的脚本。

启动：
```bash
cd /root/lpx/webui
./test/run_moq_video_ui_demo.sh start
```

查看状态：
```bash
./test/run_moq_video_ui_demo.sh status
```

停止：
```bash
./test/run_moq_video_ui_demo.sh stop
```

日志：
```bash
tail -f /root/lpx/webui/logs/moq_video_ui_demo.log
```

这个脚本会：
- 用 `ffmpeg` 生成实时 H.264 fMP4 测试流
- 发布到 MOQ relay `9003`
- 调用 `/api/acn/v3/subscribe_track`
- 在 WebUI 中生成一个 `Video` 轨道卡片
- 等待你在 WebUI 中点击 `Watch`

默认轨道：
- `agent_id = did:acn:agent:test-video`
- `task_id = task-video-demo`
- `track_name = Video`

在 WebUI 中操作：
1. 打开 `http://localhost:9005`
2. 进入 `Agents`
3. 找到 `Video` 卡片
4. 点击 `Watch`

## 2. 自动化端到端：moq_video_webui_e2e.py

这个脚本会自动：
- 发布视频
- 通知后端发现轨道
- 打开 WebUI
- 点击 `Agents -> Watch`
- 校验页面开始渲染

运行：
```bash
cd /root/lpx/webui
python3 test/moq_video_webui_e2e.py
```

如果 Playwright Chromium 未安装：
```bash
HOME=/tmp XDG_CACHE_HOME=/tmp playwright-cli install-browser chromium
```

## 3. 低层 MOQ 联调

如果你只想验证 MOQ pub/sub，不关心 WebUI：

```bash
cd /root/lpx/webui/test

# 终端 1
python3 moq_relay.py

# 终端 2
python3 moq_subscriber.py

# 终端 3
python3 moq_publisher.py
```

或直接：
```bash
./run_test.sh
```

说明：
- `moq_relay.py` 使用测试 relay 端口 `9004`
- `moq_publisher.py` 发布测试对象到 `9004`
- `moq_subscriber.py` 默认订阅的是 `9003` 上的真实 relay，和上面两个脚本不是同一套端口

因此如果你要把这三者一起跑，先确认端口配置一致。

## 4. 其他保留测试

### test_moq_integration.py
隔离的 relay -> publisher -> subscriber 集成检查：
```bash
python3 test/test_moq_integration.py
```

### test_multi_format.py
后端视频网关格式处理测试：
```bash
python3 test/test_multi_format.py
```

### test_messages.py
往后端注入 pipeline / element 日志，验证看板消息与状态展示：
```bash
python3 test/test_messages.py --all --count 1
```

## 常用排查命令

查看后端 MOQ 状态：
```bash
curl -s http://localhost:9005/api/moq/status | python3 -m json.tool
```

查看轨道列表：
```bash
curl -s http://localhost:9005/api/moq/tracks | python3 -m json.tool
```

查看单个轨道帧缓存：
```bash
curl -s http://localhost:9005/api/moq/tracks/<track_id>/frames | python3 -m json.tool
```

查看视频流状态：
```bash
curl -s http://localhost:9005/api/video/stream/<track_id>/info | python3 -m json.tool
```

查看后端日志：
```bash
tail -f /root/lpx/webui/logs/backend.log | grep -i "moq\\|video\\|watch\\|fragment\\|jpeg"
```

## 常见问题

### Q: WebUI 没看到新轨道
- 确认脚本已经成功调用 `/api/acn/v3/subscribe_track`
- 执行：
  ```bash
  curl -s http://localhost:9005/api/moq/tracks | python3 -m json.tool
  ```
- 如果轨道已经存在但 `watchState` 是 `available`，说明还没有点击 `Watch`

### Q: 点击 Watch 后页面没有画面
- 检查：
  ```bash
  curl -s http://localhost:9005/api/video/stream/<track_id>/info | python3 -m json.tool
  ```
- 重点看：
  - `has_metadata`
  - `has_init_segment`
  - `fragment_count`
  - `has_frame`
  - `jpeg_sequence`

### Q: relay 9003 不通
- 检查 AgentGW 是否在运行
- 检查 WebUI 后端是否已连接 relay：
  ```bash
  curl -s http://localhost:9005/api/moq/status | python3 -m json.tool
  ```

### Q: 需要停止手动 demo
```bash
cd /root/lpx/webui
./test/run_moq_video_ui_demo.sh stop
```

## 当前建议

如果你要测 WebUI 视频链路，优先用下面两种：

1. 手动联调：
   ```bash
   ./test/run_moq_video_ui_demo.sh start
   ```

2. 自动化联调：
   ```bash
   python3 test/moq_video_webui_e2e.py
   ```
