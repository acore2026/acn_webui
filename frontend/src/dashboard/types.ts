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

export interface TopologyAgentTrackModel {
  id: string;
  name: string;
  taskId: string;
  namespace: string;
  watchState: string;
  lastSeen: string;
}

export interface TopologyAgentModel {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  region: string;
  trackSummary: string;
  tracks: TopologyAgentTrackModel[];
  summary: string;
  uptime: string;
  launchTime: string;
  offlineTime: string;
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

export interface DatabaseSourceConfig {
  useExternalDb: boolean;
  externalDbPath: string;
  externalDbExists: boolean;
  localDbPath: string;
  localDbExists: boolean;
  activeSource: 'external' | 'local' | 'local-fallback' | string;
}

export interface CertificateRecord {
  certID: string;
  certName: string;
  authority: string;
  validity: string;
  uploadedAt?: string;
}

export interface DirectDemoCameraConfig {
  enabled: boolean;
  running: boolean;
  trackAvailable: boolean;
  trackId: string;
  trackName: string;
}

export interface VideoTrackModel {
  trackId: string;
  namespace: string;
  trackName: string;
  normalizedTrackName: string;
  source?: 'moq' | 'manual' | 'direct';
  agentId: string;
  taskId: string;
  discoveredAt: string;
  lastSeen: string;
  seenCount: number;
  watchState: 'available' | 'requested' | 'pending' | 'subscribed' | 'error';
  lastError?: string | null;
  metadata?: {
    codec?: string;
    fps?: number;
    generated_at?: string;
    height?: number;
    mime_type?: string;
    mse_codec?: string;
    width?: number;
  } | null;
  lastObjectAt?: string | null;
}

export interface VideoTrackDraft {
  agentId: string;
  taskId: string;
  trackName: string;
  namespace?: string;
}

export interface VideoPlayerConfig {
  trackId: string;
  host: string;
  port: number;
  path: string;
  certHash: string;
  mjpegUrl?: string;
}

export interface VideoPlayerBootstrap {
  metadata?: {
    codec?: string;
    fps?: number;
    generated_at?: string;
    height?: number;
    mime_type?: string;
    mse_codec?: string;
    width?: number;
  } | null;
  initSegmentBase64?: string | null;
  recentFragmentsBase64?: string[];
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

export type NetworkElementControlAction = 'start' | 'stop' | 'restart';

export interface NetworkElementControlModel {
  id: string;
  name: string;
  description: string;
  scriptPath: string;
  scriptExists: boolean;
  status: ElementStatus;
  summary: string;
  components: ElementComponentModel[];
}

export interface NetworkElementControlResult {
  elementId: string;
  elementName: string;
  action: NetworkElementControlAction;
  exitCode: number;
  stdout?: string;
  stderr?: string;
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
