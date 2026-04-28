import { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { DemoConfigModal, DemoStage } from './dashboard/components/DemoConfigModal';
import { WarningIcon } from './dashboard/components/icons';
import { SidebarNav } from './dashboard/components/SidebarNav';
import { ThemeMode } from './dashboard/components/ThemeSettingsButton';
import { AgentsPage } from './dashboard/pages/AgentsPage';
import { ControlPage } from './dashboard/pages/ControlPage';
import { NetworkPage } from './dashboard/pages/NetworkPage';
import { OverviewPage } from './dashboard/pages/OverviewPage';
import { SettingsPage } from './dashboard/pages/SettingsPage';
import { LanguageMode, shellCopy } from './dashboard/i18n';
import useWebSocket from './hooks/useWebSocket';
import {
  BackendLogEntry,
  ControlTask,
  DashboardMockData,
  NavKey,
  NetworkElementLogGroup,
  NetworkElementControlAction,
  NetworkElementControlModel,
  NetworkElementControlResult,
  VideoTrackDraft,
  VideoPlayerConfig,
  VideoPlayerBootstrap,
  VideoTrackModel
} from './dashboard/types';

const emptyDashboardData: DashboardMockData = {
  metrics: [],
  elements: [],
  messageFlow: {
    nodes: [],
    edges: []
  },
  topology: {
    agents: [],
    links: []
  },
  messages: []
};
const defaultDemoStages: DemoStage[] = ['register', 'task', 'cooperate'];
const TOPOLOGY_TEST_SPEED_STORAGE_KEY = 'topology-test-speed-v2';
const DEMO_INCLUDE_TOPOLOGY_TEST_STORAGE_KEY = 'dashboard-demo-include-topology-test';
const buildDemoTiming = (speed: number) => {
  const safeSpeed = Number.isFinite(speed) && speed > 0 ? speed : 1;
  const displayTtlSeconds = Math.max(1.2, Number((2.4 / safeSpeed).toFixed(3)));

  return {
    fullDemoDelaySeconds: Number((0.22 / safeSpeed).toFixed(3)),
    topologyDelaySeconds: Number((1.2 / safeSpeed).toFixed(3)),
    displayTtlSeconds,
    displayActiveSeconds: displayTtlSeconds
  };
};

const parseOptionalJson = async <T,>(response: Response): Promise<T | null> => {
  const text = await response.text();
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }

  try {
    return JSON.parse(trimmed) as T;
  } catch {
    throw new Error(trimmed.slice(0, 300));
  }
};

const App = () => {
  const [activeTab, setActiveTab] = useState<NavKey>('overview');
  const [dashboardData, setDashboardData] = useState<DashboardMockData>(emptyDashboardData);
  const [isLoading, setIsLoading] = useState(true);
  const [dataError, setDataError] = useState<string | null>(null);
  const [controlBusy, setControlBusy] = useState(false);
  const [, setControlMessage] = useState<string | null>(null);
  const [, setControlTone] = useState<'success' | 'warning' | 'error' | null>(null);
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [backendLogs, setBackendLogs] = useState<BackendLogEntry[]>([]);
  const [backendLogsLoading, setBackendLogsLoading] = useState(true);
  const [backendLogsError, setBackendLogsError] = useState<string | null>(null);
  const [elementLogs, setElementLogs] = useState<NetworkElementLogGroup[]>([]);
  const [elementLogsLoading, setElementLogsLoading] = useState(true);
  const [elementLogsError, setElementLogsError] = useState<string | null>(null);
  const [networkElementControls, setNetworkElementControls] = useState<NetworkElementControlModel[]>([]);
  const [networkElementBusyKey, setNetworkElementBusyKey] = useState<string | null>(null);
  const [networkElementLastResult, setNetworkElementLastResult] = useState<NetworkElementControlResult | null>(null);
  const [controlTasks, setControlTasks] = useState<ControlTask[]>([]);
  const [controlTasksLoading, setControlTasksLoading] = useState(true);
  const [controlTasksError, setControlTasksError] = useState<string | null>(null);
  const [videoTracks, setVideoTracks] = useState<VideoTrackModel[]>([]);
  const [videoTracksLoading, setVideoTracksLoading] = useState(true);
  const [videoTracksError, setVideoTracksError] = useState<string | null>(null);
  const [dispatchBusy, setDispatchBusy] = useState(false);
  const [stoppingTaskId, setStoppingTaskId] = useState<string | null>(null);
  const [topologyTestSpeed, setTopologyTestSpeed] = useState<number>(() => {
    const stored = window.localStorage.getItem(TOPOLOGY_TEST_SPEED_STORAGE_KEY);
    const parsed = stored ? Number(stored) : 1;
    return Number.isFinite(parsed) && parsed >= 0.1 && parsed <= 2 ? parsed : 1;
  });
  const [demoIncludeTopologyTest, setDemoIncludeTopologyTest] = useState<boolean>(() => {
    return window.localStorage.getItem(DEMO_INCLUDE_TOPOLOGY_TEST_STORAGE_KEY) === 'true';
  });
  const [fullDemoBusy, setFullDemoBusy] = useState(false);
  const [fullDemoMessage, setFullDemoMessage] = useState<string | null>(null);
  const [demoConfigOpen, setDemoConfigOpen] = useState(false);
  const [demoConfigStages, setDemoConfigStages] = useState<DemoStage[]>(() => {
    const stored = window.localStorage.getItem('dashboard-demo-stages');
    if (!stored) {
      return defaultDemoStages;
    }

    try {
      const parsed = JSON.parse(stored);
      return Array.isArray(parsed) && parsed.length > 0 ? parsed as DemoStage[] : defaultDemoStages;
    } catch {
      return defaultDemoStages;
    }
  });
  const [pendingScrollTarget, setPendingScrollTarget] = useState<string | null>(null);
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const stored = window.localStorage.getItem('dashboard-theme');
    return stored === 'dark' ? 'dark' : 'light';
  });
  const [language, setLanguage] = useState<LanguageMode>(() => {
    const stored = window.localStorage.getItem('dashboard-language');
    return stored === 'zh' ? 'zh' : 'en';
  });
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
  const { connected, lastMessage } = useWebSocket(wsUrl);
  const copy = shellCopy[language];
  const isZh = language === 'zh';

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem('dashboard-theme', theme);
  }, [theme]);

  useEffect(() => {
    window.localStorage.setItem('dashboard-language', language);
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
  }, [language]);

  useEffect(() => {
    window.localStorage.setItem(TOPOLOGY_TEST_SPEED_STORAGE_KEY, String(topologyTestSpeed));
  }, [topologyTestSpeed]);

  useEffect(() => {
    window.localStorage.setItem(
      DEMO_INCLUDE_TOPOLOGY_TEST_STORAGE_KEY,
      demoIncludeTopologyTest ? 'true' : 'false'
    );
  }, [demoIncludeTopologyTest]);

  useEffect(() => {
    window.localStorage.setItem('dashboard-demo-stages', JSON.stringify(demoConfigStages));
  }, [demoConfigStages]);

  useEffect(() => {
    if (!pendingScrollTarget) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      const element = document.getElementById(pendingScrollTarget);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        setPendingScrollTarget(null);
      }
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [activeTab, pendingScrollTarget]);

  const applySnapshot = useCallback((snapshot: Partial<DashboardMockData> | null | undefined) => {
    if (!snapshot) {
      return;
    }

    const topology = snapshot.topology;
    const messageFlow = snapshot.messageFlow;
    const rawAgents = topology?.agents;
    const rawLinks = topology?.links;
    const agents = Array.isArray(rawAgents) ? rawAgents : [];
    const links = Array.isArray(rawLinks) ? rawLinks : [];
    const flowNodes = messageFlow && Array.isArray(messageFlow.nodes) ? messageFlow.nodes : [];
    const flowEdges = messageFlow && Array.isArray(messageFlow.edges) ? messageFlow.edges : [];

    setDashboardData({
      metrics: Array.isArray(snapshot.metrics) ? snapshot.metrics : [],
      elements: Array.isArray(snapshot.elements) ? snapshot.elements : [],
      messageFlow: {
        nodes: flowNodes,
        edges: flowEdges
      },
      topology: {
        agents,
        links
      },
      messages: Array.isArray(snapshot.messages) ? snapshot.messages : []
    });
    setIsLoading(false);
    setDataError(null);
  }, []);

  const fetchDashboard = useCallback(async () => {
    try {
      const response = await fetch('/api/dashboard/overview');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const snapshot = (await response.json()) as DashboardMockData;
      applySnapshot(snapshot);
      return true;
    } catch (error) {
      console.error('Failed to load dashboard snapshot:', error);
      setDataError(isZh ? '无法加载实时仪表盘数据。' : 'Unable to load live dashboard data.');
      setIsLoading(false);
      return false;
    }
  }, [applySnapshot, isZh]);

  useEffect(() => {
    void fetchDashboard();
    const interval = window.setInterval(() => {
      void fetchDashboard();
    }, 15000);

    return () => window.clearInterval(interval);
  }, [fetchDashboard]);

  const fetchBackendLogs = useCallback(async () => {
    try {
      const response = await fetch('/api/logs?limit=80');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = (await response.json()) as { logs?: BackendLogEntry[] };
      setBackendLogs(Array.isArray(payload.logs) ? payload.logs.slice().reverse() : []);
      setBackendLogsLoading(false);
      setBackendLogsError(null);
      return true;
    } catch (error) {
      console.error('Failed to load backend logs:', error);
      setBackendLogsLoading(false);
      setBackendLogsError(isZh ? '无法加载后端日志。' : 'Unable to load backend logs.');
      return false;
    }
  }, [isZh]);

  useEffect(() => {
    void fetchBackendLogs();
    const interval = window.setInterval(() => {
      void fetchBackendLogs();
    }, 5000);

    return () => window.clearInterval(interval);
  }, [fetchBackendLogs]);

  const fetchNetworkElementLogs = useCallback(async () => {
    try {
      const response = await fetch('/api/network-element-logs?limit=40');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = (await response.json()) as { elements?: NetworkElementLogGroup[] };
      setElementLogs(Array.isArray(payload.elements) ? payload.elements : []);
      setElementLogsLoading(false);
      setElementLogsError(null);
      return true;
    } catch (error) {
      console.error('Failed to load network element logs:', error);
      setElementLogsLoading(false);
      setElementLogsError(
        isZh ? '无法加载网络组件日志。' : 'Unable to load network element logs.'
      );
      return false;
    }
  }, [isZh]);

  const fetchNetworkElementControls = useCallback(async () => {
    try {
      const response = await fetch('/api/control/network-elements');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = (await response.json()) as { elements?: NetworkElementControlModel[] };
      setNetworkElementControls(Array.isArray(payload.elements) ? payload.elements : []);
      return true;
    } catch (error) {
      console.error('Failed to load network element controls:', error);
      return false;
    }
  }, []);

  useEffect(() => {
    void fetchNetworkElementLogs();
    const interval = window.setInterval(() => {
      void fetchNetworkElementLogs();
    }, 6000);

    return () => window.clearInterval(interval);
  }, [fetchNetworkElementLogs]);

  const fetchControlTasks = useCallback(async () => {
    try {
      const response = await fetch('/api/control/tasks');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = (await response.json()) as { tasks?: ControlTask[] };
      setControlTasks(Array.isArray(payload.tasks) ? payload.tasks : []);
      setControlTasksLoading(false);
      setControlTasksError(null);
      return true;
    } catch (error) {
      console.error('Failed to load control tasks:', error);
      setControlTasksLoading(false);
      setControlTasksError(isZh ? '无法加载任务状态。' : 'Unable to load task status.');
      return false;
    }
  }, [isZh]);

  useEffect(() => {
    void fetchControlTasks();
    const interval = window.setInterval(() => {
      void fetchControlTasks();
    }, 8000);

    return () => window.clearInterval(interval);
  }, [fetchControlTasks]);

  const fetchVideoTracks = useCallback(async () => {
    try {
      const response = await fetch('/api/moq/tracks');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = (await response.json()) as { tracks?: VideoTrackModel[] };
      setVideoTracks(Array.isArray(payload.tracks) ? payload.tracks : []);
      setVideoTracksLoading(false);
      setVideoTracksError(null);
      return true;
    } catch (error) {
      console.error('Failed to load video tracks:', error);
      setVideoTracksLoading(false);
      setVideoTracksError(isZh ? '无法加载视频轨道。' : 'Unable to load video tracks.');
      return false;
    }
  }, [isZh]);

  useEffect(() => {
    void fetchVideoTracks();
    const interval = window.setInterval(() => {
      void fetchVideoTracks();
    }, 7000);

    return () => window.clearInterval(interval);
  }, [fetchVideoTracks]);

  useEffect(() => {
    void fetchNetworkElementControls();
  }, [fetchNetworkElementControls]);

  useEffect(() => {
    if (!lastMessage) {
      return;
    }

    try {
      const data = JSON.parse(lastMessage) as {
        type?: string;
        payload?: unknown;
      };

      if (data.type === 'DASHBOARD_SNAPSHOT') {
        applySnapshot(data.payload as DashboardMockData);
        return;
      }

      if (data.type === 'REFRESH_COMPLETE' && data.payload && typeof data.payload === 'object') {
        const payload = data.payload as { dashboard?: DashboardMockData; tasks?: ControlTask[] };
        applySnapshot(payload.dashboard);
        if (Array.isArray(payload.tasks)) {
          setControlTasks(payload.tasks);
          setControlTasksError(null);
          setControlTasksLoading(false);
        }
        setControlBusy(false);
        setControlTone('success');
        setControlMessage(
          isZh
            ? '环境清理已完成，仪表盘快照已刷新。'
            : 'Environment clear completed and the dashboard snapshot was refreshed.'
        );
        void fetchVideoTracks();
        return;
      }

      if (data.type === 'TASKS_UPDATED' && data.payload && typeof data.payload === 'object') {
        const payload = data.payload as { dashboard?: DashboardMockData; tasks?: ControlTask[] };
        if (Array.isArray(payload.tasks)) {
          setControlTasks(payload.tasks);
          setControlTasksError(null);
          setControlTasksLoading(false);
        }
        applySnapshot(payload.dashboard);
        setDispatchBusy(false);
        setStoppingTaskId(null);
        void fetchVideoTracks();
        return;
      }

      if (data.type === 'VIDEO_TRACKS_AVAILABLE') {
        void fetchVideoTracks();
        return;
      }

      if (data.type === 'REFRESH_ERROR') {
        setControlBusy(false);
        setControlTone('error');
        setControlMessage(isZh ? '后端刷新失败。' : 'Backend refresh failed.');
        setDataError(isZh ? '后端刷新失败。' : 'Backend refresh failed.');
      }
    } catch (error) {
      console.error('Failed to parse dashboard WebSocket payload:', error);
    }
  }, [applySnapshot, fetchVideoTracks, isZh, lastMessage]);

  const handleClearEnvironment = useCallback(async () => {
    setControlBusy(true);
    setControlTone('warning');
    setControlMessage(isZh ? '正在执行环境清理...' : 'Running environment clear...');

    try {
      const response = await fetch('/api/control/clear', { method: 'POST' });
      const payload = await parseOptionalJson<{
        message?: string;
        dashboard?: DashboardMockData;
        detail?: string | { error?: string; detail?: string };
      }>(response);

      if (!response.ok) {
        const detail = payload?.detail;
        const errorMessage =
          (typeof detail === 'string' ? detail : detail?.error || detail?.detail) ||
          payload?.message ||
          `Control request failed with HTTP ${response.status}.`;
        throw new Error(errorMessage);
      }

      if (payload?.dashboard) {
        applySnapshot(payload.dashboard);
      }
      if (Array.isArray((payload as { tasks?: ControlTask[] } | null)?.tasks)) {
        setControlTasks((payload as { tasks?: ControlTask[] }).tasks ?? []);
        setControlTasksLoading(false);
        setControlTasksError(null);
      }

      setControlBusy(false);
      setControlTone('success');
      setControlMessage(payload?.message || (isZh ? '环境清理成功。' : 'Environment cleared successfully.'));
      setDataError(null);
    } catch (error) {
      console.error('Failed to clear environment:', error);
      setControlBusy(false);
      setControlTone('error');
      setControlMessage(
        error instanceof Error
          ? error.message
          : isZh
            ? '环境清理失败。'
            : 'Failed to clear environment.'
      );
    }
  }, [applySnapshot, isZh]);

  useEffect(() => {
    if (!clearConfirmOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !controlBusy) {
        setClearConfirmOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [clearConfirmOpen, controlBusy]);

  const handleDispatchTask = useCallback(
    async (payload: { taskName?: string; taskType: string; taskDescription: string; agentIds: string[] }) => {
      setDispatchBusy(true);
      setControlTone('warning');
      setControlMessage(isZh ? '正在派发任务...' : 'Dispatching task...');

      try {
        const response = await fetch('/api/control/tasks', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            task_name: payload.taskName,
            task_type: payload.taskType,
            task_description: payload.taskDescription,
            agent_ids: payload.agentIds
          })
        });
        const body = (await response.json()) as {
          message?: string;
          tasks?: ControlTask[];
          dashboard?: DashboardMockData;
          detail?: string;
        };

        if (!response.ok) {
          throw new Error(body.detail || `Dispatch failed with HTTP ${response.status}.`);
        }

        if (Array.isArray(body.tasks)) {
          setControlTasks(body.tasks);
          setControlTasksLoading(false);
          setControlTasksError(null);
        }
        if (body.dashboard) {
          applySnapshot(body.dashboard);
        }

        setDispatchBusy(false);
        setControlTone('success');
        setControlMessage(body.message || (isZh ? '任务派发成功。' : 'Task dispatched successfully.'));
      } catch (error) {
        console.error('Failed to dispatch task:', error);
        setDispatchBusy(false);
        setControlTone('error');
        setControlMessage(
          error instanceof Error
            ? error.message
            : isZh
              ? '任务派发失败。'
              : 'Failed to dispatch task.'
        );
        throw error;
      }
    },
    [applySnapshot, isZh]
  );

  const handleStopTask = useCallback(
    async (taskId: string) => {
      setStoppingTaskId(taskId);
      setControlTone('warning');
      setControlMessage(isZh ? `正在停止 ${taskId}...` : `Stopping ${taskId}...`);

      try {
        const response = await fetch(`/api/control/tasks/${encodeURIComponent(taskId)}/stop`, {
          method: 'POST'
        });
        const body = (await response.json()) as {
          message?: string;
          tasks?: ControlTask[];
          dashboard?: DashboardMockData;
          detail?: string;
        };

        if (!response.ok) {
          throw new Error(body.detail || `Stop failed with HTTP ${response.status}.`);
        }

        if (Array.isArray(body.tasks)) {
          setControlTasks(body.tasks);
          setControlTasksLoading(false);
          setControlTasksError(null);
        }
        if (body.dashboard) {
          applySnapshot(body.dashboard);
        }

        setStoppingTaskId(null);
        setControlTone('success');
        setControlMessage(body.message || (isZh ? '任务已停止。' : 'Task stopped.'));
      } catch (error) {
        console.error('Failed to stop task:', error);
        setStoppingTaskId(null);
        setControlTone('error');
        setControlMessage(
          error instanceof Error
            ? error.message
            : isZh
              ? '停止任务失败。'
              : 'Failed to stop task.'
        );
      }
    },
    [applySnapshot, isZh]
  );

  const handleControlNetworkElement = useCallback(
    async (elementId: string, action: NetworkElementControlAction) => {
      const busyKey = `${elementId}:${action}`;
      setNetworkElementBusyKey(busyKey);
      setControlTone('warning');
      setControlMessage(
        isZh
          ? `正在执行 ${elementId} ${action}...`
          : `Running ${action} for ${elementId}...`
      );

      try {
        const response = await fetch(
          `/api/control/network-elements/${encodeURIComponent(elementId)}/${encodeURIComponent(action)}`,
          { method: 'POST' }
        );
        const payload = await parseOptionalJson<{
          success?: boolean;
          message?: string;
          result?: NetworkElementControlResult;
          elements?: NetworkElementControlModel[];
          dashboard?: DashboardMockData;
          detail?: string | { error?: string; detail?: string; exitCode?: number };
        }>(response);

        if (!response.ok) {
          const detail = payload?.detail;
          const errorMessage =
            (typeof detail === 'string' ? detail : detail?.error || detail?.detail) ||
            payload?.message ||
            `Element control failed with HTTP ${response.status}.`;
          throw new Error(errorMessage);
        }

        const returnedElements = payload?.elements;
        if (Array.isArray(returnedElements)) {
          setNetworkElementControls(returnedElements);
        } else {
          void fetchNetworkElementControls();
        }
        if (payload?.dashboard) {
          applySnapshot(payload.dashboard);
        }
        if (payload?.result) {
          setNetworkElementLastResult(payload.result);
        }
        void fetchBackendLogs();
        void fetchNetworkElementLogs();

        setNetworkElementBusyKey(null);
        setControlTone(payload?.success === false ? 'error' : 'success');
        setControlMessage(
          payload?.message ||
            (payload?.success === false
              ? isZh
                ? '网络元素控制命令执行完成，但有失败。'
                : 'Network element control command completed with failures.'
              : isZh
                ? '网络元素控制命令执行完成。'
                : 'Network element control command completed.')
        );
      } catch (error) {
        console.error('Failed to control network element:', error);
        setNetworkElementBusyKey(null);
        setNetworkElementLastResult({
          elementId,
          elementName: elementId,
          action,
          exitCode: -1,
          stderr:
            error instanceof Error
              ? error.message
              : isZh
                ? '网络元素控制命令失败。'
                : 'Network element control command failed.'
        });
        setControlTone('error');
        setControlMessage(
          error instanceof Error
            ? error.message
            : isZh
              ? '网络元素控制命令失败。'
              : 'Network element control command failed.'
        );
      }
    },
    [applySnapshot, fetchBackendLogs, fetchNetworkElementControls, fetchNetworkElementLogs, isZh]
  );

  const agentSummary = useMemo(() => {
    const agents = dashboardData.topology.agents;

    return {
      online: agents.filter((agent) => agent.status === 'online').length,
      busy: agents.filter((agent) => agent.status === 'busy').length,
      offline: agents.filter((agent) => agent.status === 'offline').length
    };
  }, [dashboardData.topology.agents]);

  const handleOverviewMetricSelect = useCallback((metricId: string) => {
    if (metricId === 'agents') {
      setActiveTab('agents');
      setPendingScrollTarget('agents-section');
      return;
    }

    if (metricId === 'tasks') {
      setActiveTab('control');
      setPendingScrollTarget('task-control-section');
    }
  }, []);

  const handleRunConfiguredDemo = useCallback(async (config: {
    stages: DemoStage[];
    includeTopologyTest: boolean;
    testFlowSpeed: number;
  }) => {
    setDemoConfigStages(config.stages);
    setDemoIncludeTopologyTest(config.includeTopologyTest);
    setTopologyTestSpeed(config.testFlowSpeed);
    setFullDemoBusy(true);
    setFullDemoMessage(copy.demoAction.running);
    const timing = buildDemoTiming(config.testFlowSpeed);

    try {
      let message = '';

      if (config.stages.length > 0) {
        const response = await fetch('/api/control/test-messages/full-demo', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            rounds: 1,
            step_delay_seconds: timing.fullDemoDelaySeconds,
            display_ttl_seconds: timing.displayTtlSeconds,
            display_active_seconds: timing.displayActiveSeconds,
            stages: config.stages
          })
        });
        const payload = (await response.json()) as {
          message?: string;
          dashboard?: DashboardMockData;
          tasks?: ControlTask[];
          detail?: string;
        };

        if (!response.ok) {
          throw new Error(payload.detail || `Full demo failed with HTTP ${response.status}.`);
        }

        if (payload.dashboard) {
          applySnapshot(payload.dashboard);
        }
        if (Array.isArray(payload.tasks)) {
          setControlTasks(payload.tasks);
          setControlTasksError(null);
          setControlTasksLoading(false);
        }
        message = payload.message || copy.demoAction.success;
      }

      if (config.includeTopologyTest) {
        const response = await fetch('/api/control/test-messages/topology-demo', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            rounds: 1,
            step_delay_seconds: timing.topologyDelaySeconds,
            display_ttl_seconds: timing.displayTtlSeconds,
            display_active_seconds: timing.displayActiveSeconds
          })
        });
        const payload = (await response.json()) as {
          message?: string;
          dashboard?: DashboardMockData;
          detail?: string;
        };

        if (!response.ok) {
          throw new Error(payload.detail || `Topology test failed with HTTP ${response.status}.`);
        }

        if (payload.dashboard) {
          applySnapshot(payload.dashboard);
        }
        message = message
          ? `${message} ${payload.message || ''}`.trim()
          : payload.message || (isZh ? '拓扑测试消息已注入。' : 'Topology test messages injected.');
      }

      await fetchBackendLogs();
      await fetchNetworkElementLogs();

      setFullDemoBusy(false);
      setFullDemoMessage(message || copy.demoAction.success);
    } catch (error) {
      console.error('Failed to run configured demo:', error);
      setFullDemoBusy(false);
      setFullDemoMessage(
        error instanceof Error ? error.message : copy.demoAction.failed
      );
    }
  }, [applySnapshot, copy.demoAction.failed, copy.demoAction.running, copy.demoAction.success, fetchBackendLogs, fetchNetworkElementLogs, isZh]);

  const handleQuickRunDemo = useCallback(() => {
    void handleRunConfiguredDemo({
      stages: demoConfigStages,
      includeTopologyTest: demoIncludeTopologyTest,
      testFlowSpeed: topologyTestSpeed
    });
  }, [demoConfigStages, demoIncludeTopologyTest, handleRunConfiguredDemo, topologyTestSpeed]);

  const handleSubscribeVideoTrack = useCallback(
    async (
      draft: VideoTrackDraft
    ): Promise<{ player: VideoPlayerConfig; bootstrap?: VideoPlayerBootstrap; track?: VideoTrackModel }> => {
      const response = await fetch('/api/subscriber/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(draft)
      });

      const payload = (await response.json()) as {
        detail?: string;
        message?: string;
        track?: VideoTrackModel;
        player?: VideoPlayerConfig;
        bootstrap?: VideoPlayerBootstrap;
      };

      if (!response.ok || !payload.player) {
        throw new Error(
          payload.detail ||
            payload.message ||
            (isZh ? '视频订阅失败。' : 'Failed to subscribe to the selected video track.')
        );
      }

      if (payload.track) {
        setVideoTracks((current) => {
          const exists = current.some((track) => track.trackId === payload.track?.trackId);
          if (exists) {
            return current.map((track) => (track.trackId === payload.track?.trackId ? payload.track : track));
          }
          return [payload.track as VideoTrackModel, ...current];
        });
      }
      void fetchVideoTracks();

      return {
        player: payload.player,
        bootstrap: payload.bootstrap,
        track: payload.track
      };
    },
    [fetchVideoTracks, isZh]
  );

  const handleDeleteVideoTrack = useCallback(
    async (trackId: string): Promise<void> => {
      const response = await fetch(`/api/moq/tracks/${encodeURIComponent(trackId)}`, {
        method: 'DELETE'
      });

      const payload = (await response.json()) as {
        detail?: string;
        message?: string;
      };

      if (!response.ok) {
        throw new Error(
          payload.detail ||
            payload.message ||
            (isZh ? '视频轨道删除失败。' : 'Failed to delete the video track.')
        );
      }

      await fetchVideoTracks();
    },
    [fetchVideoTracks, isZh]
  );

  const renderPage = () => {
    switch (activeTab) {
      case 'agents':
        return (
          <AgentsPage
            agents={dashboardData.topology.agents}
            videoTracks={videoTracks}
            videoTracksLoading={videoTracksLoading}
            videoTracksError={videoTracksError}
            language={language}
            onDeleteTrack={handleDeleteVideoTrack}
            onSubscribeTrack={handleSubscribeVideoTrack}
          />
        );
      case 'network':
        return (
          <NetworkPage
            backendLogs={backendLogs}
            backendLogsLoading={backendLogsLoading}
            backendLogsError={backendLogsError}
            elementLogs={elementLogs}
            elementLogsLoading={elementLogsLoading}
            elementLogsError={elementLogsError}
            language={language}
          />
        );
      case 'control':
        return (
          <ControlPage
            agents={dashboardData.topology.agents}
            tasks={controlTasks}
            tasksLoading={controlTasksLoading}
            tasksError={controlTasksError}
            language={language}
            dispatchInProgress={dispatchBusy}
            stoppingTaskId={stoppingTaskId}
            onDispatchTask={handleDispatchTask}
            onStopTask={handleStopTask}
            networkElements={networkElementControls}
            networkElementBusyKey={networkElementBusyKey}
            networkElementLastResult={networkElementLastResult}
            onControlNetworkElement={handleControlNetworkElement}
            websocketConnected={connected}
            apiHealthy={!dataError}
          />
        );
      case 'settings':
        return <SettingsPage language={language} />;
      case 'overview':
      default:
        return (
          <OverviewPage
            data={dashboardData}
            language={language}
            onMetricSelect={handleOverviewMetricSelect}
          />
        );
    }
  };

  const clearConfirmDialog =
    clearConfirmOpen && typeof document !== 'undefined'
      ? createPortal(
          <div
            className="fixed inset-0 z-[250] flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
            role="presentation"
            onClick={() => {
              if (!controlBusy) {
                setClearConfirmOpen(false);
              }
            }}
          >
            <div
              className="glass-panel w-full max-w-xl p-6 md:p-7"
              role="dialog"
              aria-modal="true"
              aria-labelledby="clear-confirm-title"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-start gap-4">
                <span className="theme-badge-rose flex h-12 w-12 items-center justify-center rounded-2xl border">
                  <WarningIcon className="h-5 w-5" />
                </span>
                <div>
                  <p className="panel-eyebrow">{isZh ? '二次确认' : 'Confirmation Required'}</p>
                  <h3 id="clear-confirm-title" className="theme-title mt-2 text-xl font-semibold">
                    {isZh ? '确认清理环境？' : 'Confirm environment clear?'}
                  </h3>
                  <p className="theme-copy mt-3 text-sm leading-6">
                    {isZh
                      ? '此操作会调用后端 /clear，重置共享环境状态，并刷新所有已连接 WebUI 会话。请确认当前确实需要执行。'
                      : 'This action calls the backend /clear route, resets shared environment state, and refreshes all connected WebUI sessions. Confirm that you really want to run it.'}
                  </p>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap justify-end gap-3">
                <button
                  type="button"
                  className="theme-top-button px-5 py-3"
                  onClick={() => setClearConfirmOpen(false)}
                  disabled={controlBusy}
                >
                  {isZh ? '取消' : 'Cancel'}
                </button>
                <button
                  type="button"
                  className={[
                    'theme-top-button px-5 py-3',
                    controlBusy ? 'cursor-wait opacity-70' : ''
                  ].join(' ')}
                  onClick={() => {
                    void handleClearEnvironment();
                    setClearConfirmOpen(false);
                  }}
                  disabled={controlBusy}
                >
                  <span className="theme-badge-rose flex h-8 w-8 items-center justify-center rounded-2xl border">
                    <WarningIcon className="h-4 w-4" />
                  </span>
                  {controlBusy ? (isZh ? '环境清理中...' : 'Clearing environment...') : (isZh ? '确认执行 Clear' : 'Confirm Clear')}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )
      : null;

  return (
    <div className="theme-shell relative min-h-screen">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-10 top-10 h-64 w-64 rounded-full bg-emerald-400/10 blur-3xl" />
        <div className="absolute right-8 top-0 h-96 w-96 rounded-full bg-blue-500/10 blur-3xl" />
      </div>

      <div className="relative flex min-h-screen flex-col md:flex-row">
        <SidebarNav
          activeTab={activeTab}
          language={language}
          theme={theme}
          fullDemoBusy={fullDemoBusy}
          fullDemoMessage={fullDemoMessage}
          onLanguageChange={setLanguage}
          onOpenDemoConfig={() => setDemoConfigOpen(true)}
          onQuickRunDemo={handleQuickRunDemo}
          onSelect={setActiveTab}
          onThemeChange={setTheme}
        />

        <main className="flex-1 md:ml-72">
          <div className="flex min-h-screen flex-col p-4 md:p-8">
            <header className="glass-panel relative z-40 mb-6 flex flex-col gap-6 px-6 py-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-3xl">
                <p className="panel-eyebrow">{copy.shellStatus.missionEyebrow}</p>
                <h2 className="theme-title mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                  {copy.pageMeta[activeTab].title}
                </h2>
                <p className="theme-copy mt-3 max-w-2xl text-sm leading-7 md:text-base">
                  {copy.pageMeta[activeTab].description}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <span className={`rounded-full border px-3 py-1 text-xs font-medium ${connected ? 'theme-badge-emerald' : 'theme-badge-rose'}`}>
                    {connected ? copy.shellStatus.websocketLive : copy.shellStatus.websocketReconnect}
                  </span>
                  <span className={`rounded-full border px-3 py-1 text-xs font-medium ${dataError ? 'theme-badge-rose' : 'theme-badge-cyan'}`}>
                    {dataError ? dataError : isLoading ? copy.shellStatus.apiLoading : copy.shellStatus.apiConnected}
                  </span>
                </div>
              </div>

              <div className="flex flex-col items-stretch gap-3 lg:items-end">
                {activeTab === 'control' ? (
                  <button
                    type="button"
                    className={[
                      'theme-top-button justify-center px-5 py-3 theme-badge-rose border',
                      controlBusy ? 'cursor-wait opacity-70' : ''
                    ].join(' ')}
                    onClick={() => setClearConfirmOpen(true)}
                    disabled={controlBusy}
                  >
                    Clear
                  </button>
                ) : null}
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="theme-card-muted px-4 py-4">
                    <p className="theme-muted text-xs uppercase tracking-[0.22em]">{copy.shellStatus.online}</p>
                    <p className="theme-title mt-2 text-2xl font-semibold">{agentSummary.online}</p>
                  </div>
                  <div className="theme-card-muted px-4 py-4">
                    <p className="theme-muted text-xs uppercase tracking-[0.22em]">{copy.shellStatus.busy}</p>
                    <p className="theme-title mt-2 text-2xl font-semibold">{agentSummary.busy}</p>
                  </div>
                  <div className="theme-card-muted px-4 py-4">
                    <p className="theme-muted text-xs uppercase tracking-[0.22em]">{copy.shellStatus.offline}</p>
                    <p className="theme-title mt-2 text-2xl font-semibold">{agentSummary.offline}</p>
                  </div>
                </div>
              </div>
            </header>

            <div className="flex-1">{renderPage()}</div>
          </div>
        </main>
      </div>

      {clearConfirmDialog}
      <DemoConfigModal
        open={demoConfigOpen}
        busy={fullDemoBusy}
        initialStages={demoConfigStages}
        initialIncludeTopologyTest={demoIncludeTopologyTest}
        initialTestFlowSpeed={topologyTestSpeed}
        language={language}
        onClose={() => setDemoConfigOpen(false)}
        onSubmit={handleRunConfiguredDemo}
      />
    </div>
  );
};

export default App;
