import { useCallback, useEffect, useMemo, useState } from 'react';
import { SidebarNav } from './dashboard/components/SidebarNav';
import { ThemeMode, ThemeSettingsButton } from './dashboard/components/ThemeSettingsButton';
import { AgentsPage } from './dashboard/pages/AgentsPage';
import { ControlPage } from './dashboard/pages/ControlPage';
import { NetworkPage } from './dashboard/pages/NetworkPage';
import { OverviewPage } from './dashboard/pages/OverviewPage';
import { SettingsPage } from './dashboard/pages/SettingsPage';
import useWebSocket from './hooks/useWebSocket';
import { DashboardMockData, NavKey } from './dashboard/types';

const pageMeta: Record<NavKey, { title: string; description: string }> = {
  overview: {
    title: 'Operational Overview',
    description: 'A single-screen command view for live latency, active agents, route health, and critical operator messages.'
  },
  agents: {
    title: 'Agent Inventory',
    description: 'Roster-level visibility into the active mesh, including role assignment and field throughput.'
  },
  network: {
    title: 'Network Diagnostics',
    description: 'Inspect current routes, detect slow paths, and validate which streams are actively flowing.'
  },
  control: {
    title: 'Operator Controls',
    description: 'Run backend control actions such as environment reset and immediate snapshot refresh from a dedicated control surface.'
  },
  settings: {
    title: 'System Settings',
    description: 'Tune the guardrails and operator-facing presentation without leaving the dashboard.'
  }
};

const emptyDashboardData: DashboardMockData = {
  metrics: [],
  topology: {
    agents: [],
    links: []
  },
  messages: []
};

const App = () => {
  const [activeTab, setActiveTab] = useState<NavKey>('overview');
  const [dashboardData, setDashboardData] = useState<DashboardMockData>(emptyDashboardData);
  const [isLoading, setIsLoading] = useState(true);
  const [dataError, setDataError] = useState<string | null>(null);
  const [controlBusy, setControlBusy] = useState(false);
  const [controlMessage, setControlMessage] = useState<string | null>(null);
  const [controlTone, setControlTone] = useState<'success' | 'warning' | 'error' | null>(null);
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const stored = window.localStorage.getItem('dashboard-theme');
    return stored === 'light' ? 'light' : 'dark';
  });
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
  const { connected, lastMessage } = useWebSocket(wsUrl);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem('dashboard-theme', theme);
  }, [theme]);

  const applySnapshot = useCallback((snapshot: Partial<DashboardMockData> | null | undefined) => {
    if (!snapshot) {
      return;
    }

    const topology = snapshot.topology;
    const rawAgents = topology?.agents;
    const rawLinks = topology?.links;
    const agents = Array.isArray(rawAgents) ? rawAgents : [];
    const links = Array.isArray(rawLinks) ? rawLinks : [];

    setDashboardData({
      metrics: Array.isArray(snapshot.metrics) ? snapshot.metrics : [],
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
      setDataError('Unable to load live dashboard data.');
      setIsLoading(false);
      return false;
    }
  }, [applySnapshot]);

  useEffect(() => {
    void fetchDashboard();
    const interval = window.setInterval(() => {
      void fetchDashboard();
    }, 15000);

    return () => window.clearInterval(interval);
  }, [fetchDashboard]);

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
        applySnapshot((data.payload as { dashboard?: DashboardMockData }).dashboard);
        setControlBusy(false);
        setControlTone('success');
        setControlMessage('Environment clear completed and the dashboard snapshot was refreshed.');
        return;
      }

      if (data.type === 'REFRESH_ERROR') {
        setControlBusy(false);
        setControlTone('error');
        setControlMessage('Backend refresh failed.');
        setDataError('Backend refresh failed.');
      }
    } catch (error) {
      console.error('Failed to parse dashboard WebSocket payload:', error);
    }
  }, [applySnapshot, lastMessage]);

  const handleClearEnvironment = useCallback(async () => {
    setControlBusy(true);
    setControlTone('warning');
    setControlMessage('Running environment clear...');

    try {
      const response = await fetch('/api/control/clear', { method: 'POST' });
      const payload = (await response.json()) as {
        message?: string;
        dashboard?: DashboardMockData;
        detail?: { error?: string; detail?: string };
      };

      if (!response.ok) {
        const errorMessage =
          payload.detail?.error ||
          payload.detail?.detail ||
          `Control request failed with HTTP ${response.status}.`;
        throw new Error(errorMessage);
      }

      if (payload.dashboard) {
        applySnapshot(payload.dashboard);
      }

      setControlBusy(false);
      setControlTone('success');
      setControlMessage(payload.message || 'Environment cleared successfully.');
      setDataError(null);
    } catch (error) {
      console.error('Failed to clear environment:', error);
      setControlBusy(false);
      setControlTone('error');
      setControlMessage(error instanceof Error ? error.message : 'Failed to clear environment.');
    }
  }, [applySnapshot]);

  const handleReloadSnapshot = useCallback(async () => {
    setControlTone('warning');
    setControlMessage('Reloading dashboard snapshot...');
    setIsLoading(true);

    const success = await fetchDashboard();

    setControlTone(success ? 'success' : 'error');
    setControlMessage(success ? 'Dashboard snapshot reloaded.' : 'Snapshot reload failed.');
  }, [fetchDashboard]);

  const agentSummary = useMemo(() => {
    const agents = dashboardData.topology.agents;

    return {
      online: agents.filter((agent) => agent.status === 'online').length,
      busy: agents.filter((agent) => agent.status === 'busy').length,
      offline: agents.filter((agent) => agent.status === 'offline').length
    };
  }, [dashboardData.topology.agents]);

  const renderPage = () => {
    switch (activeTab) {
      case 'agents':
        return <AgentsPage agents={dashboardData.topology.agents} />;
      case 'network':
        return (
          <NetworkPage
            agents={dashboardData.topology.agents}
            links={dashboardData.topology.links}
          />
        );
      case 'control':
        return (
          <ControlPage
            clearInProgress={controlBusy}
            onClearEnvironment={handleClearEnvironment}
            onReloadSnapshot={handleReloadSnapshot}
            websocketConnected={connected}
            apiHealthy={!dataError}
            statusMessage={controlMessage}
            statusTone={controlTone}
          />
        );
      case 'settings':
        return <SettingsPage />;
      case 'overview':
      default:
        return <OverviewPage data={dashboardData} />;
    }
  };

  return (
    <div className="theme-shell relative min-h-screen">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-10 top-10 h-64 w-64 rounded-full bg-emerald-400/10 blur-3xl" />
        <div className="absolute right-8 top-0 h-96 w-96 rounded-full bg-blue-500/10 blur-3xl" />
      </div>

      <div className="relative flex min-h-screen flex-col md:flex-row">
        <SidebarNav activeTab={activeTab} onSelect={setActiveTab} />

        <main className="flex-1 md:ml-72">
          <div className="flex min-h-screen flex-col p-4 md:p-8">
            <header className="glass-panel relative z-40 mb-6 flex flex-col gap-6 px-6 py-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="max-w-3xl">
                <p className="panel-eyebrow">Mission Control Dashboard</p>
                <h2 className="theme-title mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
                  {pageMeta[activeTab].title}
                </h2>
                <p className="theme-copy mt-3 max-w-2xl text-sm leading-7 md:text-base">
                  {pageMeta[activeTab].description}
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <span className={`rounded-full border px-3 py-1 text-xs font-medium ${connected ? 'theme-badge-emerald' : 'theme-badge-rose'}`}>
                    {connected ? 'WebSocket live' : 'WebSocket reconnecting'}
                  </span>
                  <span className={`rounded-full border px-3 py-1 text-xs font-medium ${dataError ? 'theme-badge-rose' : 'theme-badge-cyan'}`}>
                    {dataError ? dataError : isLoading ? 'Loading API snapshot' : 'API snapshot connected'}
                  </span>
                </div>
              </div>

              <div className="flex flex-col items-stretch gap-3 lg:items-end">
                <ThemeSettingsButton theme={theme} onThemeChange={setTheme} />

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="theme-card-muted px-4 py-4">
                    <p className="theme-muted text-xs uppercase tracking-[0.22em]">Online</p>
                    <p className="theme-title mt-2 text-2xl font-semibold">{agentSummary.online}</p>
                  </div>
                  <div className="theme-card-muted px-4 py-4">
                    <p className="theme-muted text-xs uppercase tracking-[0.22em]">Busy</p>
                    <p className="theme-title mt-2 text-2xl font-semibold">{agentSummary.busy}</p>
                  </div>
                  <div className="theme-card-muted px-4 py-4">
                    <p className="theme-muted text-xs uppercase tracking-[0.22em]">Offline</p>
                    <p className="theme-title mt-2 text-2xl font-semibold">{agentSummary.offline}</p>
                  </div>
                </div>
              </div>
            </header>

            <div className="flex-1">{renderPage()}</div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default App;
