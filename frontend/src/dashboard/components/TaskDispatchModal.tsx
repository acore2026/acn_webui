import { FormEvent, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { LanguageMode } from '../i18n';
import { TopologyAgentModel } from '../types';
import { ControlIcon, TaskIcon } from './icons';

interface TaskDispatchModalProps {
  open: boolean;
  agents: TopologyAgentModel[];
  busy: boolean;
  language: LanguageMode;
  onClose: () => void;
  onSubmit: (payload: {
    taskName?: string;
    taskType: string;
    taskDescription: string;
    agentIds: string[];
  }) => Promise<void>;
}

const inputClassName =
  'w-full rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-strong)] px-4 py-3 text-sm text-[color:var(--text-main)] outline-none transition placeholder:text-[color:var(--text-muted)] focus:border-[color:var(--border-strong)]';

export const TaskDispatchModal = ({
  open,
  agents,
  busy,
  language,
  onClose,
  onSubmit
}: TaskDispatchModalProps) => {
  const [taskName, setTaskName] = useState('');
  const [taskType, setTaskType] = useState('');
  const [taskDescription, setTaskDescription] = useState('');
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const isZh = language === 'zh';

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [busy, onClose, open]);

  useEffect(() => {
    if (open) {
      return;
    }

    setTaskName('');
    setTaskType('');
    setTaskDescription('');
    setSelectedAgents([]);
  }, [open]);

  if (!open) {
    return null;
  }

  const toggleAgent = (agentId: string) => {
    setSelectedAgents((current) =>
      current.includes(agentId)
        ? current.filter((value) => value !== agentId)
        : [...current, agentId]
    );
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSubmit({
      taskName: taskName.trim() || undefined,
      taskType: taskType.trim(),
      taskDescription: taskDescription.trim(),
      agentIds: selectedAgents
    });
    onClose();
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[250] flex items-center justify-center bg-slate-950/68 p-4 backdrop-blur-sm"
      onClick={() => {
        if (!busy) {
          onClose();
        }
      }}
      role="presentation"
    >
      <div
        className="glass-panel w-full max-w-3xl p-6 md:p-7"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dispatch-task-title"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="panel-eyebrow">{isZh ? '任务派发' : 'Task Dispatch'}</p>
            <h3 id="dispatch-task-title" className="theme-title mt-2 text-2xl font-semibold">
              {isZh ? '派发新任务' : 'Dispatch New Task'}
            </h3>
            <p className="theme-soft mt-2 text-sm leading-6">
              {isZh
                ? '将一个任务分配给多个智能体，并写入共享控制任务表。'
                : 'Assign one task to multiple agents and write it into the shared control task table.'}
            </p>
          </div>
          <span className="theme-accent-icon flex h-12 w-12 items-center justify-center rounded-2xl">
            <TaskIcon />
          </span>
        </div>

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                {isZh ? '任务名称' : 'Task Name'}
              </span>
              <input
                className={`${inputClassName} mt-2`}
                value={taskName}
                onChange={(event) => setTaskName(event.target.value)}
                placeholder={isZh ? '可选的运维标签' : 'Optional operator label'}
              />
            </label>

            <label className="block">
              <span className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                {isZh ? '任务类型' : 'Task Type'}
              </span>
              <input
                className={`${inputClassName} mt-2`}
                value={taskType}
                onChange={(event) => setTaskType(event.target.value)}
                placeholder={isZh ? '巡检、巡逻、配送……' : 'Inspection, patrol, delivery...'}
                required
              />
            </label>
          </div>

          <label className="block">
            <span className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
              {isZh ? '任务描述' : 'Task Description'}
            </span>
            <textarea
              className={`${inputClassName} mt-2 min-h-[120px] resize-y`}
              value={taskDescription}
              onChange={(event) => setTaskDescription(event.target.value)}
              placeholder={isZh ? '描述所选智能体需要执行的工作。' : 'Describe what the selected agents need to do.'}
              required
            />
          </label>

          <div>
            <div className="flex items-center justify-between gap-3">
              <span className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                {isZh ? '分配智能体' : 'Assign Agents'}
              </span>
              <span className="theme-chip px-3 py-1 text-xs font-medium">
                {isZh ? `已选择 ${selectedAgents.length} 个` : `${selectedAgents.length} selected`}
              </span>
            </div>
            <div className="mt-3 grid max-h-[260px] gap-3 overflow-y-auto rounded-3xl border border-[color:var(--border-soft)] p-3 md:grid-cols-2">
              {agents.map((agent) => {
                const checked = selectedAgents.includes(agent.id);
                return (
                  <label
                    key={agent.id}
                    className={[
                      'theme-subtle-card flex cursor-pointer items-start gap-3 px-4 py-3 transition',
                      checked ? 'border-cyan-300/30 bg-cyan-300/8' : ''
                    ].join(' ')}
                  >
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 accent-cyan-400"
                      checked={checked}
                      onChange={() => toggleAgent(agent.id)}
                    />
                    <span className="min-w-0">
                      <span className="theme-title block text-sm font-medium">{agent.name}</span>
                      <span className="theme-soft mt-1 block text-xs leading-5">
                        {agent.role} · {agent.region}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="flex flex-wrap justify-end gap-3">
            <button
              type="button"
              className="theme-top-button px-5 py-3"
              onClick={onClose}
              disabled={busy}
            >
              {isZh ? '关闭' : 'Close'}
            </button>
            <button
              type="submit"
              className={['theme-top-button px-5 py-3', busy ? 'cursor-wait opacity-70' : ''].join(' ')}
              disabled={busy || selectedAgents.length === 0}
            >
              <span className="theme-accent-icon flex h-8 w-8 items-center justify-center rounded-2xl">
                <ControlIcon className="h-4 w-4" />
              </span>
              {busy ? (isZh ? '派发中...' : 'Dispatching...') : (isZh ? '确认派发' : 'Dispatch Task')}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
};
