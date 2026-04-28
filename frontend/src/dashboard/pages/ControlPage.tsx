import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { ControlTaskSection } from '../components/ControlTaskSection';
import { TaskDispatchModal } from '../components/TaskDispatchModal';
import { InfoIcon, WarningIcon } from '../components/icons';
import { LanguageMode } from '../i18n';
import {
  ControlTask,
  NetworkElementControlAction,
  NetworkElementControlModel,
  NetworkElementControlResult,
  TopologyAgentModel
} from '../types';

interface ControlPageProps {
  agents: TopologyAgentModel[];
  tasks: ControlTask[];
  tasksLoading: boolean;
  tasksError: string | null;
  language: LanguageMode;
  dispatchInProgress: boolean;
  stoppingTaskId: string | null;
  onDispatchTask: (payload: {
    taskName?: string;
    taskType: string;
    taskDescription: string;
    agentIds: string[];
  }) => Promise<void>;
  onStopTask: (taskId: string) => Promise<void>;
  networkElements: NetworkElementControlModel[];
  networkElementBusyKey: string | null;
  networkElementLastResult: NetworkElementControlResult | null;
  onControlNetworkElement: (
    elementId: string,
    action: NetworkElementControlAction
  ) => Promise<void>;
  websocketConnected: boolean;
  apiHealthy: boolean;
}

const elementStatusStyles = {
  online: 'theme-badge-emerald',
  degraded: 'theme-badge-amber',
  offline: 'theme-badge-rose'
};

const actionLabels = {
  start: {
    en: 'Start',
    zh: '启动'
  },
  stop: {
    en: 'Stop',
    zh: '停止'
  },
  restart: {
    en: 'Restart',
    zh: '重启'
  }
};

export const ControlPage = ({
  agents,
  tasks,
  tasksLoading,
  tasksError,
  language,
  dispatchInProgress,
  stoppingTaskId,
  onDispatchTask,
  onStopTask,
  networkElements,
  networkElementBusyKey,
  networkElementLastResult,
  onControlNetworkElement,
  websocketConnected,
  apiHealthy
}: ControlPageProps) => {
  const [dispatchModalOpen, setDispatchModalOpen] = useState(false);
  const [networkConfirm, setNetworkConfirm] = useState<{
    elementId: string;
    elementName: string;
    action: NetworkElementControlAction;
  } | null>(null);
  const isZh = language === 'zh';
  const offlineElementCount = networkElements.filter((element) => element.status === 'offline').length;

  useEffect(() => {
    if (!networkConfirm) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !networkElementBusyKey) {
        setNetworkConfirm(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [networkConfirm, networkElementBusyKey]);

  const networkConfirmDialog =
    networkConfirm && typeof document !== 'undefined'
      ? createPortal(
          <div
            className="fixed inset-0 z-[250] flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
            role="presentation"
            onClick={() => {
              if (!networkElementBusyKey) {
                setNetworkConfirm(null);
              }
            }}
          >
            <div
              className="glass-panel w-full max-w-xl p-6 md:p-7"
              role="dialog"
              aria-modal="true"
              aria-labelledby="network-action-confirm-title"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-start gap-4">
                <span className="theme-badge-rose flex h-12 w-12 items-center justify-center rounded-2xl border">
                  <WarningIcon className="h-5 w-5" />
                </span>
                <div>
                  <p className="panel-eyebrow">{isZh ? '二次确认' : 'Confirmation Required'}</p>
                  <h3 id="network-action-confirm-title" className="theme-title mt-2 text-xl font-semibold">
                    {isZh
                      ? `确认${actionLabels[networkConfirm.action].zh} ${networkConfirm.elementName}？`
                      : `Confirm ${actionLabels[networkConfirm.action].en} for ${networkConfirm.elementName}?`}
                  </h3>
                  <p className="theme-copy mt-3 text-sm leading-6">
                    {isZh
                      ? '此操作会执行服务器上的控制脚本，并可能中断正在运行的网络服务。请确认当前可以执行。'
                      : 'This runs the server-side control script and may interrupt an active network service. Confirm that it is safe to proceed.'}
                  </p>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap justify-end gap-3">
                <button
                  type="button"
                  className="theme-top-button px-5 py-3"
                  onClick={() => setNetworkConfirm(null)}
                  disabled={Boolean(networkElementBusyKey)}
                >
                  {isZh ? '取消' : 'Cancel'}
                </button>
                <button
                  type="button"
                  className={[
                    'theme-top-button px-5 py-3 theme-badge-rose border',
                    networkElementBusyKey ? 'cursor-wait opacity-70' : ''
                  ].join(' ')}
                  disabled={Boolean(networkElementBusyKey)}
                  onClick={() => {
                    void onControlNetworkElement(networkConfirm.elementId, networkConfirm.action);
                    setNetworkConfirm(null);
                  }}
                >
                  <WarningIcon className="h-4 w-4" />
                  {isZh ? '确认执行' : 'Confirm Action'}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )
      : null;

  return (
    <>
      <div id="task-control-section" className="mb-4">
        <ControlTaskSection
          tasks={tasks}
          loading={tasksLoading}
          error={tasksError}
          language={language}
          dispatchInProgress={dispatchInProgress}
          stoppingTaskId={stoppingTaskId}
          onOpenDispatch={() => setDispatchModalOpen(true)}
          onStopTask={onStopTask}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.9fr]">
        <div className="space-y-4">
            <div className="theme-card-muted p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="panel-eyebrow">{isZh ? '网络控制' : 'Network Control'}</p>
                  <p className="theme-copy mt-3 max-w-2xl text-sm leading-6">
                    {isZh
                      ? '通过后端执行服务器上的控制脚本，管理 ACN Agent、AgentGW 与 IDM。操作会刷新网络元素状态。'
                      : 'Runs the server-side control scripts through the backend to manage ACN Agent, AgentGW, and IDM. Element status refreshes after each action.'}
                  </p>
                </div>
                <div className="flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    className={[
                      'theme-top-button px-4 py-2.5 text-sm',
                      networkElementBusyKey ? 'cursor-wait opacity-70' : ''
                    ].join(' ')}
                    disabled={Boolean(networkElementBusyKey) || offlineElementCount === 0}
                    onClick={() => {
                      void onControlNetworkElement('all', 'start');
                    }}
                  >
                    {isZh ? `启动全部离线 (${offlineElementCount})` : `Start All Offline (${offlineElementCount})`}
                  </button>
                  <button
                    type="button"
                    className={[
                      'theme-top-button px-4 py-2.5 text-sm theme-badge-rose border',
                      networkElementBusyKey ? 'cursor-wait opacity-70' : ''
                    ].join(' ')}
                    disabled={Boolean(networkElementBusyKey) || networkElements.length === 0}
                    onClick={() => {
                      setNetworkConfirm({
                        elementId: 'all',
                        elementName: isZh ? '全部网络元素' : 'All Network Elements',
                        action: 'restart'
                      });
                    }}
                  >
                    {isZh ? '重启全部' : 'Restart All'}
                  </button>
                </div>
              </div>

              <div className="mt-5 grid gap-3">
                {networkElements.map((element) => (
                  <article key={element.id} className="theme-subtle-card p-4">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="theme-title text-base font-semibold">{element.name}</h4>
                          <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${elementStatusStyles[element.status]}`}>
                            {isZh
                              ? element.status === 'online'
                                ? '在线'
                                : element.status === 'degraded'
                                  ? '部分在线'
                                  : '离线'
                              : element.status}
                          </span>
                          {!element.scriptExists ? (
                            <span className="theme-badge-rose rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]">
                              {isZh ? '脚本缺失' : 'script missing'}
                            </span>
                          ) : null}
                        </div>
                        <p className="theme-copy mt-2 text-sm leading-6">{element.description}</p>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {(['start', 'stop', 'restart'] as NetworkElementControlAction[]).map((action) => {
                          const busy = networkElementBusyKey === `${element.id}:${action}`;
                          const startBlocked = action === 'start' && element.status !== 'offline';
                          return (
                            <button
                              key={`${element.id}-${action}`}
                              type="button"
                              className={[
                                'theme-top-button px-4 py-2.5 text-sm',
                                busy ? 'cursor-wait opacity-70' : '',
                                action === 'stop' || action === 'restart' ? 'theme-badge-rose border' : ''
                              ].join(' ')}
                              disabled={Boolean(networkElementBusyKey) || !element.scriptExists || startBlocked}
                              onClick={() => {
                                if (action === 'stop' || action === 'restart') {
                                  setNetworkConfirm({
                                    elementId: element.id,
                                    elementName: element.name,
                                    action
                                  });
                                  return;
                                }
                                void onControlNetworkElement(element.id, action);
                              }}
                            >
                              {busy
                                ? isZh
                                  ? '执行中...'
                                  : 'Running...'
                                : actionLabels[action][isZh ? 'zh' : 'en']}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div className="mt-4">
                      <div className="theme-card-muted p-4">
                        <p className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '状态摘要' : 'Status Summary'}</p>
                        <p className="theme-copy mt-2 text-sm leading-6">{element.summary}</p>
                      </div>
                    </div>
                  </article>
                ))}
              </div>

              {networkElementLastResult ? (
                <div className="theme-card-muted mt-5 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="panel-eyebrow">{isZh ? '最近执行结果' : 'Last Command Result'}</p>
                      <h4 className="theme-title mt-2 text-base font-semibold">
                        {networkElementLastResult.elementName} · {actionLabels[networkElementLastResult.action][isZh ? 'zh' : 'en']}
                      </h4>
                    </div>
                    <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${networkElementLastResult.exitCode === 0 ? 'theme-badge-emerald' : 'theme-badge-rose'}`}>
                      exit {networkElementLastResult.exitCode}
                    </span>
                  </div>

                  <div className="mt-4 grid gap-3 lg:grid-cols-2">
                    <div className="theme-subtle-card p-4">
                      <p className="theme-muted text-xs uppercase tracking-[0.18em]">stdout</p>
                      <pre className="theme-copy mt-3 max-h-44 overflow-auto whitespace-pre-wrap break-words rounded-2xl border border-[color:var(--border-soft)] p-3 text-xs leading-5">
                        {networkElementLastResult.stdout || (isZh ? '无输出' : 'No output')}
                      </pre>
                    </div>
                    <div className="theme-subtle-card p-4">
                      <p className="theme-muted text-xs uppercase tracking-[0.18em]">stderr</p>
                      <pre className="theme-copy mt-3 max-h-44 overflow-auto whitespace-pre-wrap break-words rounded-2xl border border-[color:var(--border-soft)] p-3 text-xs leading-5">
                        {networkElementLastResult.stderr || (isZh ? '无错误输出' : 'No error output')}
                      </pre>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>

        </div>

        <div className="grid gap-4">
            <div className="theme-card-muted p-5">
              <div className="flex items-center gap-3">
                <span className="theme-accent-icon flex h-10 w-10 items-center justify-center rounded-2xl">
                  <InfoIcon />
                </span>
                <div>
                  <h3 className="theme-title text-lg font-semibold">{isZh ? '连接状态' : 'Connection Status'}</h3>
                  <p className="theme-soft text-sm">{isZh ? '控制操作依赖的 API 与 WebSocket 可用状态。' : 'API and WebSocket availability for control actions.'}</p>
                </div>
              </div>

              <div className="mt-4 space-y-3">
                <div className="theme-subtle-card flex items-center justify-between px-4 py-3">
                  <span className="theme-copy text-sm">{isZh ? 'API 接口' : 'API route'}</span>
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${apiHealthy ? 'theme-badge-emerald' : 'theme-badge-rose'}`}>
                    {apiHealthy ? (isZh ? '可达' : 'reachable') : (isZh ? '错误' : 'error')}
                  </span>
                </div>
                <div className="theme-subtle-card flex items-center justify-between px-4 py-3">
                  <span className="theme-copy text-sm">{isZh ? 'WebSocket 广播' : 'WebSocket broadcast'}</span>
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${websocketConnected ? 'theme-badge-emerald' : 'theme-badge-amber'}`}>
                    {websocketConnected ? (isZh ? '实时' : 'live') : (isZh ? '重连中' : 'reconnecting')}
                  </span>
                </div>
                <div className="theme-subtle-card flex items-center justify-between px-4 py-3">
                  <span className="theme-copy text-sm">{isZh ? '任务控制接口' : 'Task control API'}</span>
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${tasksError ? 'theme-badge-rose' : 'theme-badge-cyan'}`}>
                    {tasksError ? (isZh ? '降级' : 'degraded') : (isZh ? '就绪' : 'ready')}
                  </span>
                </div>
              </div>
            </div>

            <div className="theme-card-muted p-5">
              <div className="flex items-center gap-3">
                <span className="theme-accent-icon flex h-10 w-10 items-center justify-center rounded-2xl">
                  <WarningIcon />
                </span>
                <div>
                  <h3 className="theme-title text-lg font-semibold">{isZh ? '操作说明' : 'Operation Notes'}</h3>
                  <p className="theme-soft text-sm">
                    {isZh ? '停止与清理会改动共享后端状态，请谨慎执行。' : 'Use stop and clear carefully because they change shared backend state.'}
                  </p>
                </div>
              </div>

              <ul className="theme-copy mt-4 space-y-3 text-sm leading-6">
                <li className="theme-subtle-card px-4 py-3">
                  {isZh ? (
                    <>
                      派发任务会为所选智能体向共享 <code className="theme-code-chip rounded px-1.5 py-0.5">tasks</code> 表写入记录。
                    </>
                  ) : (
                    <>
                      Dispatch writes rows into the shared <code className="theme-code-chip rounded px-1.5 py-0.5">tasks</code> table for the selected agents.
                    </>
                  )}
                </li>
                <li className="theme-subtle-card px-4 py-3">
                  {isZh
                    ? '停止任务会将选中任务从活动任务表中移除，并在运维历史列表中标记为已完成。'
                    : 'Stop removes the selected task from the active task table and marks it finished in the operator history list.'}
                </li>
                <li className="theme-subtle-card px-4 py-3">
                  {isZh
                    ? 'Clear 会重置环境，并为所有打开中的 WebUI 会话刷新仪表盘。'
                    : 'Clear resets the environment and refreshes the dashboard for all open WebUI sessions.'}
                </li>
              </ul>
            </div>
        </div>
      </div>

      <TaskDispatchModal
        open={dispatchModalOpen}
        agents={agents}
        busy={dispatchInProgress}
        language={language}
        onClose={() => setDispatchModalOpen(false)}
        onSubmit={onDispatchTask}
      />
      {networkConfirmDialog}
    </>
  );
};
