import { DashboardMockData } from "../types";

export const dashboardMockData: DashboardMockData = {
  metrics: [
    {
      id: "latency",
      title: "System Latency",
      value: "24ms",
      detail: "Nominal cross-region stream latency",
      tone: "healthy",
      trend: "Stable under 30ms target"
    },
    {
      id: "agents",
      title: "Active Agents",
      value: "1,024 / 1,050",
      detail: "Fleet participation in the current mesh",
      tone: "warning",
      trend: "+2.3% from yesterday"
    },
    {
      id: "tasks",
      title: "Running Tasks",
      value: "342",
      detail: "118 collaborative and 24 high-priority operations",
      tone: "healthy",
      trend: "17 escalated workflows"
    }
  ],
  topology: {
    agents: [
      {
        id: "mission-core",
        name: "Mission Core",
        role: "Orchestration Hub",
        status: "online",
        region: "Singapore Edge",
        throughput: "18.4 Gbps",
        summary: "Primary coordination node responsible for task routing, policy sync, and mesh-wide scheduling.",
        uptime: "21d 04h",
        lastHeartbeat: "2s ago",
        taskCount: 86,
        capabilities: ["Task orchestration", "Policy sync", "Failover routing", "Telemetry aggregation"],
        alerts: ["No active alerts", "Redundancy channel healthy"],
        position: { x: 470, y: 170 }
      },
      {
        id: "agent-alpha",
        name: "Agent Alpha",
        role: "Recon Cluster",
        status: "busy",
        region: "Harbor North",
        throughput: "5.2 Gbps",
        summary: "Field recon agent focused on shoreline scans, target acquisition, and short-range video relay.",
        uptime: "08d 11h",
        lastHeartbeat: "4s ago",
        taskCount: 19,
        capabilities: ["Recon sweep", "Thermal scan", "Object detection", "Video uplink"],
        alerts: ["Task queue near 80%", "Thermal sensor calibration due in 4h"],
        position: { x: 130, y: 70 }
      },
      {
        id: "agent-beta",
        name: "Agent Beta",
        role: "Response Team",
        status: "online",
        region: "Coastal Ring",
        throughput: "4.7 Gbps",
        summary: "Response-focused node used for incident handling, route recovery, and operator escalation workflows.",
        uptime: "15d 02h",
        lastHeartbeat: "1s ago",
        taskCount: 27,
        capabilities: ["Incident response", "Fallback routing", "Priority dispatch", "Operator handoff"],
        alerts: ["Recovered packet loss event", "Standby reserve available"],
        position: { x: 130, y: 270 }
      },
      {
        id: "agent-gamma",
        name: "Agent Gamma",
        role: "AI Assist Relay",
        status: "online",
        region: "Central Core",
        throughput: "6.1 Gbps",
        summary: "Inference relay node that handles assistive model calls and distributes summarization workloads.",
        uptime: "12d 18h",
        lastHeartbeat: "3s ago",
        taskCount: 31,
        capabilities: ["AI inference", "Transcript summarization", "Context relay", "Queue balancing"],
        alerts: ["Inference load normal", "No model saturation detected"],
        position: { x: 810, y: 80 }
      },
      {
        id: "agent-delta",
        name: "Agent Delta",
        role: "Spectrum Monitor",
        status: "offline",
        region: "Sector West",
        throughput: "0.0 Gbps",
        summary: "Spectrum observer assigned to radio health monitoring and interference analysis across the western band.",
        uptime: "Unavailable",
        lastHeartbeat: "14m ago",
        taskCount: 0,
        capabilities: ["Spectrum scan", "Interference alerting", "Link diagnostics", "Band health reports"],
        alerts: ["Heartbeat timeout", "Awaiting remote restart"],
        position: { x: 810, y: 270 }
      },
      {
        id: "agent-epsilon",
        name: "Agent Epsilon",
        role: "Routing Sentinel",
        status: "busy",
        region: "Cross-Border Mesh",
        throughput: "7.8 Gbps",
        summary: "Routing guard node that validates border traffic, manages failover rules, and monitors route drift.",
        uptime: "17d 09h",
        lastHeartbeat: "2s ago",
        taskCount: 41,
        capabilities: ["Route validation", "Border policy enforcement", "Path failover", "Traffic shaping"],
        alerts: ["Border route drift detected", "Secondary path available"],
        position: { x: 470, y: 360 }
      }
    ],
    links: [
      {
        id: "alpha-core",
        source: "agent-alpha",
        target: "mission-core",
        latency: "12ms",
        active: true
      },
      {
        id: "beta-core",
        source: "agent-beta",
        target: "mission-core",
        latency: "18ms",
        active: true
      },
      {
        id: "core-gamma",
        source: "mission-core",
        target: "agent-gamma",
        latency: "24ms",
        active: true
      },
      {
        id: "core-delta",
        source: "mission-core",
        target: "agent-delta",
        latency: "61ms",
        active: false
      },
      {
        id: "core-epsilon",
        source: "mission-core",
        target: "agent-epsilon",
        latency: "16ms",
        active: true
      },
      {
        id: "epsilon-delta",
        source: "agent-epsilon",
        target: "agent-delta",
        latency: "44ms",
        active: false
      }
    ]
  },
  messages: [
    {
      id: "msg-1",
      level: "info",
      title: "Network Join Completed",
      message: "New agent [Agent-X] successfully joined the network and synchronized route policies.",
      timestamp: "09:14:08",
      source: "Control Plane"
    },
    {
      id: "msg-2",
      level: "warning",
      title: "Latency Spike Detected",
      message: "High latency detected on Node A. Transit path has shifted to the secondary corridor.",
      timestamp: "09:17:42",
      source: "Telemetry"
    },
    {
      id: "msg-3",
      level: "error",
      title: "Unexpected Disconnect",
      message: "Agent Delta disconnected unexpectedly after heartbeat retries expired.",
      timestamp: "09:19:55",
      source: "Health Monitor"
    },
    {
      id: "msg-4",
      level: "info",
      title: "Task Volume Rebalanced",
      message: "Task scheduler redistributed 17 workloads away from saturated inference agents.",
      timestamp: "09:22:11",
      source: "Scheduler"
    },
    {
      id: "msg-5",
      level: "warning",
      title: "Backpressure On Stream",
      message: "Mission Core reported transient queue growth on the video uplink ring.",
      timestamp: "09:24:30",
      source: "Streaming"
    },
    {
      id: "msg-6",
      level: "info",
      title: "Recovery Workflow Armed",
      message: "Agent Beta established a fallback tunnel and recovered packet loss below 0.3%.",
      timestamp: "09:26:02",
      source: "Network Control"
    }
  ]
};
