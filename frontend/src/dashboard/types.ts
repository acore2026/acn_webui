export type NavKey = 'overview' | 'agents' | 'network' | 'control' | 'settings';

export type MetricTone = 'healthy' | 'warning' | 'critical';

export interface MetricCardModel {
  id: string;
  title: string;
  value: string;
  detail: string;
  tone: MetricTone;
  trend?: string;
}

export type AgentStatus = 'online' | 'busy' | 'offline';

export interface TopologyAgentModel {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  region: string;
  throughput: string;
  summary: string;
  uptime: string;
  lastHeartbeat: string;
  taskCount: number;
  capabilities: string[];
  alerts: string[];
  position: {
    x: number;
    y: number;
  };
}

export interface TopologyLinkModel {
  id: string;
  source: string;
  target: string;
  latency: string;
  active: boolean;
}

export type MessageLevel = 'info' | 'warning' | 'error';
export type ElementStatus = 'online' | 'offline' | 'degraded';

export interface MessageFeedItem {
  id: string;
  level: MessageLevel;
  title: string;
  message: string;
  timestamp: string;
  source: string;
}

export interface BackendLogEntry {
  time?: string;
  level?: string;
  message: string;
}

export interface NetworkElementLogSource {
  id: string;
  name: string;
  path: string;
  entries: BackendLogEntry[];
  error?: string | null;
}

export interface NetworkElementLogGroup {
  id: string;
  name: string;
  path: string;
  entries: BackendLogEntry[];
  subLogs?: NetworkElementLogSource[];
  error?: string | null;
}

export interface ControlTaskAgent {
  id: string;
  name: string;
}

export interface ControlTask {
  id: string;
  taskName: string;
  taskType: string;
  description: string;
  status: 'processing' | 'finished';
  involvedAgents: ControlTaskAgent[];
  createdAt: string;
  updatedAt: string;
}

export interface ElementComponentModel {
  id: string;
  name: string;
  port: number;
  protocol: string;
  status: 'online' | 'offline';
  description: string;
}

export interface ElementGroupModel {
  id: string;
  name: string;
  status: ElementStatus;
  summary: string;
  components: ElementComponentModel[];
}

export interface MessageFlowNodeModel {
  id: string;
  name: string;
  status: 'online' | 'offline';
  position: {
    x: number;
    y: number;
  };
}

export interface MessageFlowEdgeModel {
  id: string;
  source: string;
  target: string;
  count: number;
  lastMessage: string;
  lastTimestamp?: string;
  active: boolean;
}

export interface DashboardMockData {
  metrics: MetricCardModel[];
  elements: ElementGroupModel[];
  messageFlow: {
    nodes: MessageFlowNodeModel[];
    edges: MessageFlowEdgeModel[];
  };
  topology: {
    agents: TopologyAgentModel[];
    links: TopologyLinkModel[];
  };
  messages: MessageFeedItem[];
}
