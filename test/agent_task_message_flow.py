#!/usr/bin/env python3
"""
Send element-log messages that exercise local agents/tasks CRUD behavior.

Default target:
  http://127.0.0.1:9005

The script intentionally pauses between steps so the WebUI can be observed.
"""

from __future__ import annotations

import argparse
import ssl
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


EXPECTED_CONTENT_KEYS = {
    "PublishAgent": {
        "agent_name",
        "agent_id",
        "agent_capability",
        "agent_status",
        "priority",
        "consent",
    },
    "DeleteAgent": {
        "agent_name",
        "agent_id",
        "agent_capability",
        "agent_status",
        "priority",
        "consent",
    },
    "TaskExecution": {"agent_id", "task_id", "task_description"},
    "TaskExecutionTermination": {"agent_id", "task_id", "task_description"},
    "PublisherTrackAdd": {"src_agent_id", "task_id", "track_list"},
    "PublisherTrackDel": {"src_agent_id", "task_id", "track_list"},
}

EXPECTED_TRACK_KEYS = {"namespace", "track"}
EXPECTED_PAYLOAD_KEYS = {"method", "url", "headers", "body"}
EXPECTED_BODY_KEYS = {"element_id", "log_type", "timestamp", "content"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
    verify_tls: bool = True,
) -> dict[str, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    context = None if verify_tls else ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc

    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"raw": body}


def post_element_log(
    base_url: str,
    log_type: str,
    content: dict[str, Any],
    *,
    verify_tls: bool,
) -> dict[str, Any]:
    validate_element_log_content(log_type, content)
    payload = {
        "method": "POST",
        "url": "/acn/v3/element-logs",
        "headers": {"Content-Type": "application/json"},
        "body": {
            "element_id": "AgentGW",
            "log_type": log_type,
            "timestamp": utc_now(),
            "content": content,
        },
    }
    validate_element_log_payload(payload)
    return request_json(
        "POST",
        f"{base_url}/acn/v3/element-logs",
        payload,
        verify_tls=verify_tls,
    )


def validate_element_log_payload(payload: dict[str, Any]) -> None:
    if set(payload.keys()) != EXPECTED_PAYLOAD_KEYS:
        raise ValueError(
            f"Element log payload keys must be {sorted(EXPECTED_PAYLOAD_KEYS)}, got {sorted(payload.keys())}"
        )
    if payload.get("method") != "POST":
        raise ValueError("Element log payload.method must be POST")
    if payload.get("url") != "/acn/v3/element-logs":
        raise ValueError("Element log payload.url must be /acn/v3/element-logs")
    if payload.get("headers") != {"Content-Type": "application/json"}:
        raise ValueError('Element log payload.headers must be {"Content-Type": "application/json"}')
    body = payload.get("body")
    if not isinstance(body, dict) or set(body.keys()) != EXPECTED_BODY_KEYS:
        actual_keys = sorted(body.keys()) if isinstance(body, dict) else type(body).__name__
        raise ValueError(
            f"Element log payload.body keys must be {sorted(EXPECTED_BODY_KEYS)}, got {actual_keys}"
        )
    if body.get("element_id") != "AgentGW":
        raise ValueError("Element log payload.body.element_id must be AgentGW")


def validate_element_log_content(log_type: str, content: dict[str, Any]) -> None:
    expected_keys = EXPECTED_CONTENT_KEYS.get(log_type)
    if expected_keys is None:
        raise ValueError(f"Unsupported log_type in test script: {log_type}")
    actual_keys = set(content.keys())
    if actual_keys != expected_keys:
        raise ValueError(
            f"{log_type} content keys must be {sorted(expected_keys)}, got {sorted(actual_keys)}"
        )
    if log_type in {"PublisherTrackAdd", "PublisherTrackDel"}:
        track_list = content.get("track_list")
        if not isinstance(track_list, list):
            raise ValueError(f"{log_type}.content.track_list must be a list")
        for index, track in enumerate(track_list):
            if not isinstance(track, dict) or set(track.keys()) != EXPECTED_TRACK_KEYS:
                raise ValueError(
                    f"{log_type}.content.track_list[{index}] keys must be {sorted(EXPECTED_TRACK_KEYS)}"
                )


def print_snapshot(
    base_url: str,
    agent_id: str,
    task_ids: list[str],
    *,
    verify_tls: bool,
) -> None:
    agents_payload = request_json("GET", f"{base_url}/api/agents", verify_tls=verify_tls)
    tasks_payload = request_json("GET", f"{base_url}/api/control/tasks", verify_tls=verify_tls)

    agents = agents_payload.get("agents", [])
    tasks = tasks_payload.get("tasks", [])
    agent = next((item for item in agents if item.get("agent_id") == agent_id), None)

    print("  agent:")
    if agent:
        print(
            json.dumps(
                {
                    "agent_id": agent.get("agent_id"),
                    "agent_name": agent.get("agent_name"),
                    "agent_status": agent.get("agent_status"),
                    "work_status": agent.get("work_status"),
                    "current_task": agent.get("current_task"),
                    "agent_capability": agent.get("agent_capability"),
                    "priority": agent.get("priority"),
                    "consent": agent.get("consent"),
                    "track_info": agent.get("track_info"),
                },
                ensure_ascii=False,
                indent=4,
            )
        )
    else:
        print("    <not found>")

    print("  tasks:")
    for task_id in task_ids:
        task = next((item for item in tasks if item.get("id") == task_id), None)
        print(f"    {task_id}:")
        if task:
            print(json.dumps(task, ensure_ascii=False, indent=8))
        else:
            print("        <not found>")


def wait_for_observation(args: argparse.Namespace) -> None:
    if args.interactive:
        input("Press Enter for next step...")
    elif args.pause > 0:
        time.sleep(args.pause)


def run_step(
    args: argparse.Namespace,
    title: str,
    log_type: str,
    content: dict[str, Any],
) -> None:
    print(f"\n=== {title} ===")
    print(f"POST /acn/v3/element-logs log_type={log_type}")
    response = post_element_log(
        args.base_url,
        log_type,
        content,
        verify_tls=args.verify_tls,
    )
    print(f"  response: {json.dumps(response, ensure_ascii=False)}")
    time.sleep(args.settle)
    print_snapshot(
        args.base_url,
        args.agent_id,
        [args.task_id, args.second_task_id],
        verify_tls=args.verify_tls,
    )
    wait_for_observation(args)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exercise PublishAgent/DeleteAgent/TaskExecution/Track messages against WebUI."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:9005")
    parser.add_argument("--agent-id", default="did:acn:agent:test-message-flow")
    parser.add_argument("--task-id", default="task-message-flow-001")
    parser.add_argument("--second-task-id", default="task-message-flow-002")
    parser.add_argument("--pause", type=float, default=1.5, help="Seconds to wait between steps.")
    parser.add_argument("--settle", type=float, default=0.25, help="Seconds to wait before querying snapshots.")
    parser.add_argument("--interactive", action="store_true", help="Wait for Enter between steps.")
    parser.add_argument(
        "--verify-tls",
        action="store_true",
        help="Verify HTTPS certificates. By default, self-signed localhost certificates are accepted.",
    )
    args = parser.parse_args()
    args.base_url = args.base_url.rstrip("/")

    try:
        print(f"Target WebUI backend: {args.base_url}")
        request_json("GET", f"{args.base_url}/api/health", verify_tls=args.verify_tls)

        consent = {
            "need_consumer_ue_authorization": False,
            "need_producer_authorization": True,
            "support_producer_ue_authorization": False,
        }

        run_step(
            args,
            "1. Create agent with PublishAgent",
            "PublishAgent",
            {
                "agent_name": "Test Message Flow Agent",
                "agent_id": args.agent_id,
                "agent_capability": ["video-publish", "task-execution"],
                "agent_status": "online",
                "priority": "5",
                "consent": consent,
            },
        )

        run_step(
            args,
            "2. Update agent with PublishAgent",
            "PublishAgent",
            {
                "agent_name": "Test Message Flow Agent Updated",
                "agent_id": args.agent_id,
                "agent_capability": ["thermal-video", "handover-support"],
                "agent_status": "online",
                "priority": "9",
                "consent": consent,
            },
        )

        run_step(
            args,
            "3. Create processing task with TaskExecution",
            "TaskExecution",
            {
                "task_id": args.task_id,
                "agent_id": args.agent_id,
                "task_description": "Inspect target area and publish video track",
            },
        )

        run_step(
            args,
            "4. Add published tracks with PublisherTrackAdd",
            "PublisherTrackAdd",
            {
                "src_agent_id": args.agent_id,
                "task_id": args.task_id,
                "track_list": [
                    {"namespace": f"/{args.task_id}/{args.agent_id}", "track": "Video"},
                    {"namespace": f"/{args.task_id}/{args.agent_id}", "track": "Location"},
                ],
            },
        )

        run_step(
            args,
            "5. Update processing task description with TaskExecution",
            "TaskExecution",
            {
                "agent_id": args.agent_id,
                "task_id": args.task_id,
                "task_description": "Inspect target area, continue video publishing",
            },
        )

        run_step(
            args,
            "6. Remove one published track with PublisherTrackDel",
            "PublisherTrackDel",
            {
                "src_agent_id": args.agent_id,
                "task_id": args.task_id,
                "track_list": [
                    {"namespace": f"/{args.task_id}/{args.agent_id}", "track": "Location"},
                ],
            },
        )

        run_step(
            args,
            "7. Finish task with TaskExecutionTermination",
            "TaskExecutionTermination",
            {
                "agent_id": args.agent_id,
                "task_id": args.task_id,
                "task_description": "Inspect target area completed",
            },
        )

        run_step(
            args,
            "8. Create second processing task with TaskExecution",
            "TaskExecution",
            {
                "agent_id": args.agent_id,
                "task_id": args.second_task_id,
                "task_description": "Inspect backup area and publish video track",
            },
        )

        run_step(
            args,
            "9. Add second task published tracks with PublisherTrackAdd",
            "PublisherTrackAdd",
            {
                "src_agent_id": args.agent_id,
                "task_id": args.second_task_id,
                "track_list": [
                    {"namespace": f"/{args.second_task_id}/{args.agent_id}", "track": "Video"},
                    {"namespace": f"/{args.second_task_id}/{args.agent_id}", "track": "Telemetry"},
                ],
            },
        )

        run_step(
            args,
            "10. Remove one second task track with PublisherTrackDel",
            "PublisherTrackDel",
            {
                "src_agent_id": args.agent_id,
                "task_id": args.second_task_id,
                "track_list": [
                    {"namespace": f"/{args.second_task_id}/{args.agent_id}", "track": "Telemetry"},
                ],
            },
        )

        run_step(
            args,
            "11. Finish second task with TaskExecutionTermination",
            "TaskExecutionTermination",
            {
                "agent_id": args.agent_id,
                "task_id": args.second_task_id,
                "task_description": "Inspect backup area completed",
            },
        )

        run_step(
            args,
            "12. Delete agent and associated task rows with DeleteAgent",
            "DeleteAgent",
            {
                "agent_name": "Test Message Flow Agent Updated",
                "agent_id": args.agent_id,
                "agent_capability": ["thermal-video", "handover-support"],
                "agent_status": "offline",
                "priority": "9",
                "consent": consent,
            },
        )

        print("\nDone. The final step should remove the test agent and its task rows from the UI.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
