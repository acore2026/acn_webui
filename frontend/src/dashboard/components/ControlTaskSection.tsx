import { ControlTask } from '../types';
import { LanguageMode } from '../i18n';
import { TaskIcon, WarningIcon } from './icons';

interface ControlTaskSectionProps {
  tasks: ControlTask[];
  loading: boolean;
  error: string | null;
  language: LanguageMode;
  dispatchInProgress: boolean;
  stoppingTaskId: string | null;
  onOpenDispatch: () => void;
  onStopTask: (taskId: string) => Promise<void>;
}

const statusStyles = {
  processing: 'theme-badge-cyan',
  finished: 'theme-badge-emerald'
};

const formatTime = (value: string) => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  const pad = (part: number) => String(part).padStart(2, '0');
  return [
    parsed.getUTCFullYear(),
    '-',
    pad(parsed.getUTCMonth() + 1),
    '-',
    pad(parsed.getUTCDate()),
    ' ',
    pad(parsed.getUTCHours()),
    ':',
    pad(parsed.getUTCMinutes()),
    ':',
    pad(parsed.getUTCSeconds()),
    ' UTC'
  ].join('');
};

export const ControlTaskSection = ({
  tasks,
  loading,
  error,
  language,
  dispatchInProgress,
  stoppingTaskId,
  onOpenDispatch,
  onStopTask
}: ControlTaskSectionProps) => {
  const isZh = language === 'zh';
  return (
    <div className="theme-card-muted p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="panel-eyebrow">{isZh ? '任务控制' : 'Task Control'}</p>
          <h3 className="theme-title mt-2 text-xl font-semibold">{isZh ? '任务队列状态' : 'Task Queue Status'}</h3>
          <p className="theme-copy mt-3 max-w-2xl text-sm leading-6">
            {isZh ? '查看当前活动任务、检查每个任务关联的智能体、派发新任务，并在运维控制台中停止正在执行的任务。' : 'Monitor active work items, inspect the agents attached to each task, dispatch new work, and stop active tasks from the operator console.'}
          </p>
        </div>
        <button
          type="button"
          onClick={onOpenDispatch}
          className={['theme-top-button px-5 py-3', dispatchInProgress ? 'cursor-wait opacity-70' : ''].join(' ')}
          disabled={dispatchInProgress}
        >
          <span className="theme-accent-icon flex h-8 w-8 items-center justify-center rounded-2xl">
            <TaskIcon className="h-4 w-4" />
          </span>
          {dispatchInProgress ? (isZh ? '派发中...' : 'Dispatching...') : (isZh ? '派发新任务' : 'Dispatch New Task')}
        </button>
      </div>

      <div className="mt-5 h-[420px] overflow-y-auto rounded-3xl border border-[color:var(--border-soft)] p-3">
        {error ? (
          <div className="flex h-full items-center justify-center rounded-2xl border border-[color:var(--accent-rose-border)] bg-[color:var(--accent-rose-bg)] px-4 text-sm text-[color:var(--accent-rose-text)]">
            {error}
          </div>
        ) : loading ? (
          <div className="flex h-full items-center justify-center text-sm text-[color:var(--text-soft)]">
            {isZh ? '正在加载任务状态...' : 'Loading task status...'}
          </div>
        ) : tasks.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-[color:var(--border-soft)] px-4 text-sm text-[color:var(--text-soft)]">
            {isZh ? '当前还没有登记任务。' : 'No tasks are registered yet.'}
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => (
              <article key={task.id} className="theme-subtle-card px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="theme-title break-words text-base font-semibold">{task.id}</h4>
                      <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${statusStyles[task.status]}`}>
                        {isZh ? (task.status === 'processing' ? '处理中' : '已完成') : task.status}
                      </span>
                      <span className="theme-chip px-3 py-1 text-[11px] font-medium uppercase tracking-[0.16em]">
                        {task.taskType}
                      </span>
                    </div>
                    <p className="theme-copy mt-2 text-sm leading-6">{task.description}</p>
                  </div>

                  {task.status === 'processing' ? (
                    <button
                      type="button"
                      onClick={() => {
                        void onStopTask(task.id);
                      }}
                      disabled={stoppingTaskId === task.id}
                      className={[
                        'theme-top-button px-4 py-3',
                        stoppingTaskId === task.id ? 'cursor-wait opacity-70' : ''
                      ].join(' ')}
                    >
                      <span className="theme-badge-rose flex h-8 w-8 items-center justify-center rounded-2xl border">
                        <WarningIcon className="h-4 w-4" />
                      </span>
                      {stoppingTaskId === task.id ? (isZh ? '停止中...' : 'Stopping...') : (isZh ? '停止任务' : 'Stop Task')}
                    </button>
                  ) : null}
                </div>

                <div className="mt-4 space-y-3">
                  <div className="theme-card-muted p-4">
                    <p className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '协作智能体' : 'Cooperation Agents'}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {task.involvedAgents.map((agent) => (
                        <span key={`${task.id}-${agent.id}`} className="theme-chip px-3 py-1 text-xs font-medium">
                          {agent.name}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="theme-card-muted p-4">
                      <p className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '创建时间' : 'Created Time'}</p>
                      <p className="theme-title mt-3 text-sm font-medium">{formatTime(task.createdAt)}</p>
                    </div>
                    <div className="theme-card-muted p-4">
                      <p className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '更新时间' : 'Updated Time'}</p>
                      <p className="theme-title mt-3 text-sm font-medium">{formatTime(task.updatedAt)}</p>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <div className="theme-subtle-card p-4">
          <p className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '处理中' : 'Processing'}</p>
          <p className="theme-title mt-2 text-2xl font-semibold">
            {tasks.filter((task) => task.status === 'processing').length}
          </p>
        </div>
        <div className="theme-subtle-card p-4">
          <p className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '已完成' : 'Finished'}</p>
          <p className="theme-title mt-2 text-2xl font-semibold">
            {tasks.filter((task) => task.status === 'finished').length}
          </p>
        </div>
        <div className="theme-subtle-card p-4">
          <p className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '已分配智能体' : 'Assigned Agents'}</p>
          <p className="theme-title mt-2 text-2xl font-semibold">
            {tasks.reduce((total, task) => total + task.involvedAgents.length, 0)}
          </p>
        </div>
      </div>
    </div>
  );
};
