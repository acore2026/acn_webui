# WebUI视频显示问题修复指南

## 问题诊断结果

### 发现的问题

1. **发送端已停止**: `demo_task_initiator_video_production.py` 进程不在运行
2. **连接不稳定**: 检测到11次`Disconnected from MOQ Relay`
3. **没有视频帧日志**: 后端日志中没有`VIDEO_FRAME`日志，说明没有收到视频帧
4. **修改可能未生效**: webui进程在修改前就已启动

### 根本原因

webui的`moq_video.py`接收数据后传递给`main.py`的`handle_moq_video_frame`，但：
- **原来**: 直接发送原始payload给前端（带52字节VideoFrame头部，前端无法解码）
- **修复后**: 解析VideoFrame头部，提取纯H264数据给前端

## 已完成的修复

### 1. 创建VideoFrame解析器
**文件**: `/root/lpx/webui/backend/app/video_frame_parser.py`

功能:
- 解析`demo_task_initiator_video_production.py`发送的VideoFrame结构
- 提取纯H264数据
- 向后兼容原始H264数据

### 2. 修改main.py
**文件**: `/root/lpx/webui/backend/app/main.py`

修改内容:
```python
async def handle_moq_video_frame(frame: "VideoFrame"):
    # 尝试解析VideoFrame结构
    from .video_frame_parser import try_parse_video_frame, extract_h264_data
    
    video_frame = try_parse_video_frame(frame.payload)
    if video_frame:
        # 提取纯H264数据
        h264_payload = video_frame.data
        print(f"[VIDEO_FRAME] Parsed VideoFrame: frame_id={video_frame.frame_id}, ...")
    else:
        # 不是VideoFrame格式，使用原始数据
        h264_payload = frame.payload
    
    # 发送纯H264数据给前端
    ...
```

## 需要执行的操作

### 步骤1: 重启WebUI服务（必须）

webui进程在修改前就已启动，需要重启以加载新代码：

```bash
# 查找webui进程
ps aux | grep "uvicorn.*app.main:app.*9005"

# 停止webui（根据实际启动方式）
# 方式1: 如果使用systemd
systemctl restart webui

# 方式2: 如果是手动启动
kill <pid>
cd /root/lpx/webui
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9005 --log-level info

# 方式3: 如果使用supervisor
supervisorctl restart webui
```

### 步骤2: 启动视频发送端

重新启动视频发送：

```bash
cd /home/acn/zqm/acn_sdk

# 方式1: 使用production_video_streamer.py
export VIDEO_PATH="/path/to/your/1080p_video.mp4"
python3 examples/production_video_streamer.py

# 方式2: 使用demo_task_initiator_video_production.py
python3 examples/demo_task_initiator_video_production.py \
    --video /path/to/your/1080p_video.mp4 \
    --fps 30 \
    --bitrate 4M \
    --target-agent "webui-agent-id"
```

### 步骤3: 验证接收

在webui后端日志中查看：

```bash
# 实时查看日志
tail -f /root/lpx/webui/logs/backend.log | grep -E "VIDEO_FRAME|Parsed VideoFrame"
```

应该看到：
```
[VIDEO_FRAME] Parsed VideoFrame: frame_id=1, gop_id=0, 1920x1080, fps=30, keyframe=True
```

### 步骤4: 前端验证

1. 打开webui前端页面
2. 查看视频是否正确显示
3. 检查浏览器开发者工具中的WebSocket消息

## 如果仍然无法显示

### 检查清单

1. **检查VideoFrame解析器是否加载**
   ```bash
   python3 -c "from backend.app.video_frame_parser import VideoFrame; print('OK')"
   ```

2. **检查main.py是否包含修改**
   ```bash
   grep "try_parse_video_frame" /root/lpx/webui/backend/app/main.py
   ```

3. **检查日志输出**
   ```bash
   tail -100 /root/lpx/webui/logs/backend.log | grep -E "VIDEO_FRAME|Parsed"
   ```

4. **检查发送端是否正确发送**
   ```bash
   ps aux | grep -E "production_video|demo_task_initiator"
   ```

### 常见问题

#### Q1: 修改已重启但还是不显示？
**A**: 检查：
1. 发送端是否正确发送VideoFrame格式数据
2. 检查namespace和track_name是否匹配
3. 查看webui是否正确订阅了track

#### Q2: 前端显示黑屏？
**A**: 可能是：
1. 前端解码器不支持H264
2. 数据格式不正确
3. 需要刷新前端页面

#### Q3: 连接频繁断开？
**A**: 
1. 确保使用的是修改后的MOQ代码（PING帧保活）
2. 检查网络稳定性
3. 增加心跳间隔

## 数据流向

```
SDK发送端 (demo_task_initiator_video_production.py)
    ↓ 发送 VideoFrame(头部+ H264数据)
MOQ Relay
    ↓ 转发
WebUI后端 (moq_video.py → main.py)
    ↓ 解析VideoFrame，提取H264数据
WebSocket
    ↓ 发送纯H264数据
前端浏览器
    ↓ 解码并显示
用户看到视频
```

## 关键日志

**成功的标志**:
```
[Subscribe Track] Subscribing to video track: ...
[VIDEO_FRAME] Parsed VideoFrame: frame_id=1, gop_id=0, 1920x1080, fps=30, keyframe=True
[VIDEO_FRAME] track=... mime=video/h264 codec=h264 size=...
```

**失败的标志**:
```
Disconnected from MOQ Relay
# 或者没有任何VIDEO_FRAME日志
```

## 联系支持

如有问题，请联系开发团队。

**最后更新**: 2026-04-16
