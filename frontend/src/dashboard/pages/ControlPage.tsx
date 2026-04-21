import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { ControlTaskSection } from '../components/ControlTaskSection';
import { TaskDispatchModal } from '../components/TaskDispatchModal';
import { ControlIcon, InfoIcon, WarningIcon } from '../components/icons';
import { SectionCard } from '../components/SectionCard';
import { LanguageMode } from '../i18n';
import { ControlTask, TopologyAgentModel } from '../types';

interface ControlPageProps {
  agents: TopologyAgentModel[];
  tasks: ControlTask[];
  tasksLoading: boolean;
  tasksError: string | null;
  language: LanguageMode;
  clearInProgress: boolean;
  dispatchInProgress: boolean;
  stoppingTaskId: string | null;
  onClearEnvironment: () => Promise<void>;
  onDispatchTask: (payload: {
    taskName?: string;
    taskType: string;
    taskDescription: string;
    agentIds: string[];
  }) => Promise<void>;
  onReloadSnapshot: () => Promise<void>;
  onStopTask: (taskId: string) => Promise<void>;
  websocketConnected: boolean;
  apiHealthy: boolean;
  statusMessage: string | null;
  statusTone: 'success' | 'warning' | 'error' | null;
}

const statusStyles = {
  success: 'theme-badge-emerald',
  warning: 'theme-badge-amber',
  error: 'theme-badge-rose'
};

export const ControlPage = ({
  agents,
  tasks,
  tasksLoading,
  tasksError,
  language,
  clearInProgress,
  dispatchInProgress,
  stoppingTaskId,
  onClearEnvironment,
  onDispatchTask,
  onReloadSnapshot,
  onStopTask,
  websocketConnected,
  apiHealthy,
  statusMessage,
  statusTone
}: ControlPageProps) => {
  const [dispatchModalOpen, setDispatchModalOpen] = useState(false);
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const isZh = language === 'zh';

  useEffect(() => {
    if (!clearConfirmOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !clearInProgress) {
        setClearConfirmOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [clearConfirmOpen, clearInProgress]);

  const clearConfirmDialog =
    clearConfirmOpen && typeof document !== 'undefined'
      ? createPortal(
          <div
            className="fixed inset-0 z-[250] flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
            role="presentation"
            onClick={() => {
              if (!clearInProgress) {
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
                  disabled={clearInProgress}
                >
                  {isZh ? '取消' : 'Cancel'}
                </button>
                <button
                  type="button"
                  className={[
                    'theme-top-button px-5 py-3',
                    clearInProgress ? 'cursor-wait opacity-70' : ''
                  ].join(' ')}
                  onClick={() => {
                    void onClearEnvironment();
                    setClearConfirmOpen(false);
                  }}
                  disabled={clearInProgress}
                >
                  <span className="theme-badge-rose flex h-8 w-8 items-center justify-center rounded-2xl border">
                    <WarningIcon className="h-4 w-4" />
                  </span>
                  {clearInProgress ? (isZh ? '环境清理中...' : 'Clearing environment...') : (isZh ? '确认执行 Clear' : 'Confirm Clear')}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )
      : null;

  return (
    <>
      <SectionCard
        eyebrow={isZh ? '控制' : 'Control'}
        title={isZh ? '运维控制台' : 'Operator Controls'}
        description={
          isZh
            ? '在同一处执行后端控制操作、管理运维派发任务，并在环境需要干预时停止当前工作。'
            : 'Run backend control actions from one place, manage operator-dispatched tasks, and stop work when the active environment needs intervention.'
        }
      >
        <div className="grid gap-4 xl:grid-cols-[1.35fr_0.9fr]">
          <div className="space-y-4">
            <div id="task-control-section">
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

            <div className="theme-card-muted p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="panel-eyebrow">{isZh ? '主操作' : 'Primary Action'}</p>
                  <h3 className="theme-title mt-2 text-xl font-semibold">{isZh ? '清理环境' : 'Clear Environment'}</h3>
                  <p className="theme-copy mt-3 max-w-2xl text-sm leading-6">
                    {isZh ? (
                      <>
                        调用后端控制接口执行 ARF 的 <code>/clear</code> 操作，然后刷新智能体名册与仪表盘快照。
                      </>
                    ) : (
                      <>
                        Calls the backend control route for the ARF <code>/clear</code> operation, then refreshes the agent roster and dashboard snapshot.
                      </>
                    )}
                  </p>
                </div>
                <span className="theme-accent-icon flex h-12 w-12 items-center justify-center rounded-2xl">
                  <ControlIcon />
                </span>
              </div>

              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => setClearConfirmOpen(true)}
                  disabled={clearInProgress}
                  className={[
                    'theme-top-button px-5 py-3',
                    clearInProgress ? 'cursor-wait opacity-70' : ''
                  ].join(' ')}
                >
                  <span className="theme-badge-rose flex h-8 w-8 items-center justify-center rounded-2xl border">
                    <WarningIcon className="h-4 w-4" />
                  </span>
                  {clearInProgress ? (isZh ? '环境清理中...' : 'Clearing environment...') : (isZh ? '执行 Clear' : 'Run Clear')}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    void onReloadSnapshot();
                  }}
                  className="theme-top-button px-5 py-3"
                >
                  {isZh ? '刷新快照' : 'Reload Snapshot'}
                </button>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <div className="theme-subtle-card p-4">
                  <p className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '后端接口' : 'Backend Route'}</p>
                  <p className="theme-title mt-2 text-sm font-medium">POST /api/control/clear</p>
                </div>
                <div className="theme-subtle-card p-4">
                  <p className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '作用' : 'Effect'}</p>
                  <p className="theme-copy mt-2 text-sm leading-6">
                    {isZh
                      ? '重置当前环境，并向所有已连接客户端广播新的仪表盘快照。'
                      : 'Resets the environment and broadcasts a fresh dashboard snapshot to all connected clients.'}
                  </p>
                </div>
              </div>

              {statusMessage ? (
                <div className={`mt-5 rounded-3xl border px-4 py-4 text-sm leading-6 ${statusTone ? statusStyles[statusTone] : 'theme-chip'}`}>
                  {statusMessage}
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
                  <h3 className="theme-title text-lg font-semibold">{isZh ? '控制面状态' : 'Control Surface Status'}</h3>
                  <p className="theme-soft text-sm">{isZh ? '当前控制操作的连接状态。' : 'Current connection state for control actions.'}</p>
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
                  <h3 className="theme-title text-lg font-semibold">{isZh ? '运维提示' : 'Operator Note'}</h3>
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
      </SectionCard>

      <TaskDispatchModal
        open={dispatchModalOpen}
        agents={agents}
        busy={dispatchInProgress}
        language={language}
        onClose={() => setDispatchModalOpen(false)}
        onSubmit={onDispatchTask}
      />
      {clearConfirmDialog}
    </>
  );
};
