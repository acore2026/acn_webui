import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { LanguageMode, shellCopy } from '../i18n';
import { ControlIcon, SignalIcon } from './icons';

export type DemoStage = 'register' | 'task' | 'cooperate' | 'deregister';

interface DemoConfigModalProps {
  open: boolean;
  busy: boolean;
  initialStages: DemoStage[];
  initialIncludeTopologyTest: boolean;
  initialTestFlowSpeed: number;
  language: LanguageMode;
  onClose: () => void;
  onSubmit: (config: {
    stages: DemoStage[];
    includeTopologyTest: boolean;
    testFlowSpeed: number;
  }) => Promise<void>;
}

const stageOrder: DemoStage[] = ['register', 'task', 'cooperate', 'deregister'];

export const DemoConfigModal = ({
  open,
  busy,
  initialStages,
  initialIncludeTopologyTest,
  initialTestFlowSpeed,
  language,
  onClose,
  onSubmit
}: DemoConfigModalProps) => {
  const copy = shellCopy[language].demoConfig;
  const isZh = language === 'zh';
  const [selectedStages, setSelectedStages] = useState<DemoStage[]>(initialStages);
  const [includeTopologyTest, setIncludeTopologyTest] = useState(initialIncludeTopologyTest);
  const [testFlowSpeed, setTestFlowSpeed] = useState(initialTestFlowSpeed);
  const [error, setError] = useState<string | null>(null);

  const stageItems = useMemo(
    () => [
      {
        id: 'register' as const,
        label: copy.registerLabel,
        description: copy.registerDescription
      },
      {
        id: 'task' as const,
        label: copy.taskLabel,
        description: copy.taskDescription
      },
      {
        id: 'cooperate' as const,
        label: copy.cooperateLabel,
        description: copy.cooperateDescription
      },
      {
        id: 'deregister' as const,
        label: copy.deregisterLabel,
        description: copy.deregisterDescription
      }
    ],
    [copy.cooperateDescription, copy.cooperateLabel, copy.deregisterDescription, copy.deregisterLabel, copy.registerDescription, copy.registerLabel, copy.taskDescription, copy.taskLabel]
  );

  useEffect(() => {
    if (open) {
      return;
    }

    setSelectedStages(initialStages);
    setIncludeTopologyTest(initialIncludeTopologyTest);
    setTestFlowSpeed(initialTestFlowSpeed);
    setError(null);
  }, [initialIncludeTopologyTest, initialStages, initialTestFlowSpeed, open]);

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

  if (!open) {
    return null;
  }

  const toggleStage = (stage: DemoStage) => {
    setError(null);
    setSelectedStages((current) => {
      if (stage === 'deregister') {
        return current.includes(stage) ? [] : ['deregister'];
      }

      const next = current.filter((value) => value !== 'deregister');
      return next.includes(stage)
        ? next.filter((value) => value !== stage)
        : [...next, stage].sort(
            (left, right) => stageOrder.indexOf(left) - stageOrder.indexOf(right)
          );
    });
  };

  const handleSubmit = async () => {
    if (selectedStages.length === 0 && !includeTopologyTest) {
      setError(copy.required);
      return;
    }

    onClose();
    await onSubmit({
      stages: selectedStages,
      includeTopologyTest,
      testFlowSpeed
    });
  };

  return createPortal(
    <div
      className="fixed inset-0 z-[260] flex items-center justify-center bg-slate-950/68 p-4 backdrop-blur-sm"
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
        aria-labelledby="demo-config-title"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="panel-eyebrow">{copy.eyebrow}</p>
            <h3 id="demo-config-title" className="theme-title mt-2 text-2xl font-semibold">
              {copy.title}
            </h3>
            <p className="theme-soft mt-2 text-sm leading-6">{copy.description}</p>
          </div>
          <span className="theme-accent-icon flex h-12 w-12 items-center justify-center rounded-2xl">
            <SignalIcon />
          </span>
        </div>

        <div className="mt-6 grid gap-3">
          {stageItems.map((stage) => {
            const checked = selectedStages.includes(stage.id);
            return (
              <button
                key={stage.id}
                type="button"
                onClick={() => toggleStage(stage.id)}
                className={[
                  'theme-subtle-card flex items-start justify-between gap-4 px-4 py-4 text-left transition',
                  checked ? 'border-cyan-300/30 bg-cyan-300/8' : ''
                ].join(' ')}
              >
                <div>
                  <p className="theme-title text-sm font-semibold">{stage.label}</p>
                  <p className="theme-soft mt-2 text-sm leading-6">{stage.description}</p>
                </div>
                <span
                  className={[
                    'rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]',
                    checked ? 'theme-badge-cyan' : 'theme-chip'
                  ].join(' ')}
                >
                  {checked ? (isZh ? '已启用' : 'Enabled') : (isZh ? '未启用' : 'Off')}
                </span>
              </button>
            );
          })}
        </div>

        <div className="mt-6">
          <p className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
            {copy.topologyLabel}
          </p>
          <button
            type="button"
            onClick={() => {
              setError(null);
              setIncludeTopologyTest((current) => !current);
            }}
            className={[
              'theme-subtle-card mt-3 flex items-start justify-between gap-4 px-4 py-4 text-left transition',
              includeTopologyTest ? 'border-cyan-300/30 bg-cyan-300/8' : ''
            ].join(' ')}
          >
            <div>
              <p className="theme-title text-sm font-semibold">{copy.topologyFlowLabel}</p>
              <p className="theme-soft mt-2 text-sm leading-6">{copy.topologyFlowDescription}</p>
            </div>
            <span
              className={[
                'rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]',
                includeTopologyTest ? 'theme-badge-cyan' : 'theme-chip'
              ].join(' ')}
            >
              {includeTopologyTest ? (isZh ? '已启用' : 'Enabled') : (isZh ? '未启用' : 'Off')}
            </span>
          </button>

          <label className="mt-4 block">
            <span className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
              {copy.testSpeedLabel}
            </span>
            <select
              value={testFlowSpeed}
              onChange={(event) => setTestFlowSpeed(Number(event.target.value))}
              className="mt-2 w-full rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-strong)] px-4 py-3 text-sm text-[color:var(--text-main)] outline-none"
            >
              {[0.1, 0.25, 0.5, 0.75, 1, 1.25, 1.5, 2].map((speed) => (
                <option key={speed} value={speed}>
                  {speed.toFixed(speed < 1 ? 2 : speed % 1 === 0 ? 1 : 2)}x
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <span className="theme-chip px-3 py-1 text-xs font-medium">
            {selectedStages.length} {copy.selected}
          </span>
          {error ? (
            <span className="text-sm text-[color:var(--accent-rose-text)]">{error}</span>
          ) : null}
        </div>

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button
            type="button"
            className="theme-top-button px-5 py-3"
            onClick={onClose}
            disabled={busy}
          >
            {copy.close}
          </button>
          <button
            type="button"
            className={['theme-top-button px-5 py-3', busy ? 'cursor-wait opacity-70' : ''].join(' ')}
            onClick={() => {
              void handleSubmit();
            }}
            disabled={busy}
          >
            <span className="theme-accent-icon flex h-8 w-8 items-center justify-center rounded-2xl">
              <ControlIcon className="h-4 w-4" />
            </span>
            {busy ? copy.running : copy.run}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};
