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

export interface MessageFeedItem {
  id: string;
  level: MessageLevel;
  title: string;
  message: string;
  timestamp: string;
  source: string;
}

export interface DashboardMockData {
  metrics: MetricCardModel[];
  topology: {
    agents: TopologyAgentModel[];
    links: TopologyLinkModel[];
  };
  messages: MessageFeedItem[];
}
