#!/usr/bin/env python3
"""
测试数据库初始化脚本
创建测试用的SQLite数据库，包含agents和tasks表
"""

import sqlite3
import os

DB_PATH = "/root/lpx/webui/test/test_agent_gw.db"

def init_test_database():
    """Initialize test database with schema and sample data"""
    
    # Remove existing database
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database: {DB_PATH}")
    
    # Create new database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create agents table
    cursor.execute("""
        CREATE TABLE agents (
            agent_id VARCHAR PRIMARY KEY,
            agent_name VARCHAR,
            agent_capability JSON,
            agent_auth VARCHAR,
            agent_status VARCHAR,
            priority INTEGER
        )
    """)
    print("Created table: agents")
    
    # Create tasks table
    cursor.execute("""
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id VARCHAR,
            task_id VARCHAR,
            task_description VARCHAR,
            FOREIGN KEY(agent_id) REFERENCES agents (agent_id)
        )
    """)
    print("Created table: tasks")
    
    # Insert sample agents
    sample_agents = [
        ("did:acn:agent:001", "Drone Alpha", '["surveillance", "tracking", "thermal"]', None, "online", 5),
        ("did:acn:agent:002", "Drone Beta", '["patrol", "expel", "night_vision"]', None, "online", 4),
        ("did:acn:agent:003", "Ground Unit 1", '["inspection", "security", "barrier_detection"]', None, "offline", 3),
        ("did:acn:agent:004", "Marine Unit A", '["underwater", "sonar", "rescue"]', None, "online", 4),
        ("did:acn:agent:005", "RobotDog", '["patrol", "obstacle_avoidance", "terrain_adaptation"]', None, "online", 4),
        ("did:acn:agent:006", "RobotARM", '["manipulation", "precision_operation", "sorting"]', None, "working", 3),
        ("did:acn:agent:007", "Surveillance Cam", '["face_recognition", "motion_detection"]', None, "online", 3),
        ("did:acn:agent:008", "Alice的个人助手", '["跌倒监测-手环", "健康监测"]', None, "online", 2),
        ("did:acn:agent:009", "智能门锁", '["指纹识别", "远程开锁", "访客记录"]', None, "offline", 1),
        ("did:acn:agent:010", "环境监测器", '["温度", "湿度", "空气质量"]', None, "online", 2),
    ]
    
    cursor.executemany(
        "INSERT INTO agents (agent_id, agent_name, agent_capability, agent_auth, agent_status, priority) VALUES (?, ?, ?, ?, ?, ?)",
        sample_agents
    )
    print(f"Inserted {len(sample_agents)} sample agents")
    
    # Insert sample tasks (some agents with tasks will show as "working")
    sample_tasks = [
        ("did:acn:agent:001", "task-001", "Patrolling sector 7"),
        ("did:acn:agent:002", "task-002", "Tracking target T-001"),
        ("did:acn:agent:006", "task-003", "Sorting items in warehouse"),
        ("did:acn:agent:008", "task-004", "Health monitoring active"),
    ]
    
    cursor.executemany(
        "INSERT INTO tasks (agent_id, task_id, task_description) VALUES (?, ?, ?)",
        sample_tasks
    )
    print(f"Inserted {len(sample_tasks)} sample tasks")
    
    conn.commit()
    conn.close()
    
    print(f"\nTest database initialized successfully at: {DB_PATH}")
    print("\nAgents with tasks (will show as 'working'):")
    for agent_id, task_id, desc in sample_tasks:
        print(f"  - {agent_id}: {desc}")

if __name__ == "__main__":
    init_test_database()
