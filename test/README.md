# WebUI 测试工具目录

## 目录结构

```
test/
├── README.md                      # 本文件
├── init_test_db.py                # 初始化测试数据库脚本
├── test_messages.py               # 消息发送测试脚本
├── test_agent_gw.db               # 测试用的SQLite数据库
│
├── moq_1080p_test/               # 1080p MOQ视频流测试
│   ├── README.md                 # 1080p测试说明
│   ├── test_1080p.h264          # 1080p测试视频
│   ├── publish_1080p.py         # MOQ Publisher
│   ├── video_server_9006.py     # MOQ Subscriber + Web Server
│   └── run_1080p_pipeline.sh    # 一键启动脚本
│
├── moq_publisher.py              # MOQ发布者示例
├── moq_subscriber.py             # MOQ订阅者示例
├── moq_relay.py                  # MOQ中继示例
├── mjpeg_publisher.py            # MJPEG发布者
├── moq_to_mjpeg.py               # MOQ转MJPEG
├── test_h264_video.py            # H.264视频测试
├── test_mjpeg_display.py         # MJPEG显示测试
├── test_basic_moq.py             # 基础MOQ测试
├── test_moq_integration.py       # MOQ集成测试
├── test_multi_format.py          # 多格式测试
├── webrtc_publisher.py           # WebRTC发布者
├── webrtc_simple.py              # 简化版WebRTC
└── ...                           # 其他测试脚本
```

## 主要测试分类

### 1. MOQ 协议测试 (moq_*.py)
基础MOQ协议功能测试，包括发布、订阅、中继。

### 2. 视频流测试
- **1080p MOQ测试** (`moq_1080p_test/`): 完整端到端1080p视频流测试
- **H.264测试** (`test_h264_video.py`): FFmpeg生成H.264并推送
- **MJPEG测试** (`test_mjpeg_display.py`): MJPEG视频流测试

### 3. 消息流测试
- **test_messages.py**: Agent工作消息流测试
- **test_moq_integration.py**: MOQ集成测试

### 4. 前端显示测试
- **test_agent_gw.db**: 测试数据库
- **init_test_db.py**: 数据库初始化脚本

## 快速开始

### 1080p MOQ视频流测试
```bash
cd /root/lpx/webui/test/moq_1080p_test
./run_1080p_pipeline.sh
```
访问 http://localhost:9006 查看视频

### 前端显示效果测试

**初始化测试数据库**
```bash
cd /root/lpx/webui/test
python3 init_test_db.py
```

## 快速开始

### 1. 初始化测试数据库

```bash
cd /root/lpx/webui/test
python3 init_test_db.py
```

这会创建一个包含10个测试agent和4个任务的测试数据库。

### 2. 确保后端服务正在运行

```bash
curl http://localhost:9050/api/health
```

如果后端未运行，请启动：
```bash
cd /root/lpx/webui
./start.sh
```

### 3. 运行测试脚本

#### 发送所有类型的消息（默认）
```bash
python3 test_messages.py
```

#### 只发送 Pipeline Logs (Message Flow)
```bash
python3 test_messages.py --pipeline
```

#### 只发送 Element Logs (Agent Status)
```bash
python3 test_messages.py --element
```

#### 发送多轮消息
```bash
python3 test_messages.py --count 5 --delay 3
```
这会发送5轮消息，每轮间隔3秒。

## 测试内容说明

### Pipeline Logs (Message Flow)
测试消息包括：
- Agent GW → IDM: 申请数字身份
- IDM → Agent GW: 身份验证完成
- Agent GW → ARF: 代理发现请求
- Drone Alpha → MOQT Relay: 订阅视频流
- Drone Beta → ACF: 状态更新
- 等等...

### Element Logs (Agent Work Status)
测试以下log_type：
- **ApplyProfile**: 申请数字身份 → work_status: working
- **PublishAgent**: 能力注册 → work_status: working
- **SetupConnection**: 入网连接 → work_status: online
- **LLMMessage**: LLM处理 → work_status: working

### Mixed Scenario (综合场景)
模拟完整的agent生命周期：
1. 申请数字身份
2. IDM验证
3. 注册能力
4. 建立连接
5. 开始任务
6. 任务执行中

## 前端显示位置

运行脚本后，在前端页面查看：

1. **左侧边栏 (Registered Agents)**
   - 显示数据库中的agent列表
   - 有任务的agent显示为 working 状态

2. **中间上部 (Agent Work Status)**
   - 显示element logs更新的agent状态
   - 包含work_status、current_task、operation logs

3. **中间下部 (Message Flow)**
   - 显示pipeline logs消息流
   - 包含source → destination: content

## 数据库内容

### Agents (10个)
- Drone Alpha, Drone Beta (在线，有任务)
- Ground Unit 1 (离线)
- Marine Unit A, RobotDog (在线)
- RobotARM (工作中)
- 等等...

### Tasks (4个)
- task-001: Patrolling sector 7
- task-002: Tracking target T-001
- task-003: Sorting items in warehouse
- task-004: Health monitoring active

## 完整测试流程

```bash
# 1. 进入测试目录
cd /root/lpx/webui/test

# 2. 初始化数据库
python3 init_test_db.py

# 3. 修改后端使用测试数据库（可选）
# 编辑 /root/lpx/webui/backend/app/main.py
# 修改 DB_PATH = "/root/lpx/webui/test/test_agent_gw.db"

# 4. 重启后端服务
pkill -f "uvicorn.*9050"
cd /root/lpx/webui/backend
source /root/lpx/acn_gw/venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9050 &

# 5. 构建前端
cd /root/lpx/webui/frontend
npm run build

# 6. 运行测试
python3 test_messages.py --all --count 3 --delay 2
```

然后打开浏览器访问 http://localhost:9050 查看效果。
