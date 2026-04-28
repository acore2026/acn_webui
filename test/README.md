# WebUI 测试工具目录

当前目录只保留 agent/task 和消息流相关测试工具。

## 当前保留文件

```text
test/
├── README.md
├── agent_task_message_flow.py
└── test_messages.py
```

## 推荐测试

### Agent / Task 消息流

覆盖当前 `PublishAgent`、`DeleteAgent`、`TaskExecution`、`TaskExecutionTermination`、`PublisherTrackAdd`、`PublisherTrackDel` 对本地 agent/task 表的维护逻辑。

```bash
cd /home/acn/cxr/acn_webui
python3 test/agent_task_message_flow.py --base-url https://127.0.0.1:9005 --interactive
```

默认使用自签名 HTTPS 证书时不校验证书。需要严格校验证书时添加：

```bash
--verify-tls
```

### Dashboard 消息 / 演示流程

```bash
cd /home/acn/cxr/acn_webui
python3 test/test_messages.py --topology-demo --host 127.0.0.1 --port 9005
python3 test/test_messages.py --full-demo --host 127.0.0.1 --port 9005
```

也可以发送一轮全部消息类型：

```bash
python3 test/test_messages.py --all --count 1
```

## 说明

- 当前 WebUI 主服务地址为 `https://127.0.0.1:9005`。
- 当前 agent/task 的正式测试入口是 `agent_task_message_flow.py`。
