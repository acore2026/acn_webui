import { BackendLogEntry, MessageLevel } from '../types';
import { LanguageMode } from '../i18n';
import { ErrorIcon, InfoIcon, WarningIcon } from './icons';

interface BackendLogPanelProps {
  logs: BackendLogEntry[];
  loading: boolean;
  error: string | null;
  language: LanguageMode;
}

const resolveTone = (level?: string): MessageLevel => {
  if (level === 'error') {
    return 'error';
  }

  if (level === 'warning' || level === 'warn') {
    return 'warning';
  }

  return 'info';
};

const toneStyles: Record<
  MessageLevel,
  { badge: string; icon: typeof InfoIcon; label: string }
> = {
  info: {
    badge: 'theme-badge-cyan',
    icon: InfoIcon,
    label: 'Info'
  },
  warning: {
    badge: 'theme-badge-amber',
    icon: WarningIcon,
    label: 'Warn'
  },
  error: {
    badge: 'theme-badge-rose',
    icon: ErrorIcon,
    label: 'Error'
  }
};

const formatTime = (value?: string) => {
  if (!value) {
    return '--:--:--';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
};

export const BackendLogPanel = ({ logs, loading, error, language }: BackendLogPanelProps) => {
  const isZh = language === 'zh';
  return (
    <section className="theme-card-muted p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="theme-title text-lg font-semibold">{isZh ? '后端日志' : 'Backend Logs'}</h3>
          <p className="theme-soft mt-1 text-sm">
            {isZh ? <>来自 <code className="theme-code-chip rounded px-1.5 py-0.5">/api/logs</code> 的最近后端运行输出。</> : <>Recent backend runtime output from <code className="theme-code-chip rounded px-1.5 py-0.5">/api/logs</code>.</>}
          </p>
        </div>
        <span className="theme-chip px-3 py-1 text-xs font-medium">
          {loading ? (isZh ? '刷新中…' : 'Refreshing…') : (isZh ? `${logs.length} 条记录` : `${logs.length} entries`)}
        </span>
      </div>

      <div className="mt-4 h-[420px] overflow-y-auto rounded-3xl border border-[color:var(--border-soft)] bg-[color:var(--surface-strong)]/80 p-3">
        {error ? (
          <div className="flex h-full items-center justify-center rounded-2xl border border-[color:var(--accent-rose-border)] bg-[color:var(--accent-rose-bg)] px-4 text-sm text-[color:var(--accent-rose-text)]">
            {error}
          </div>
        ) : logs.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-[color:var(--border-soft)] px-4 text-sm text-[color:var(--text-soft)]">
            {isZh ? '当前还没有可用的后端日志。' : 'No backend logs available yet.'}
          </div>
        ) : (
          <div className="space-y-3 font-mono text-sm">
            {logs.map((log, index) => {
              const tone = resolveTone(log.level);
              const toneStyle = toneStyles[tone];
              const Icon = toneStyle.icon;

              return (
                <div
                  key={`${log.time ?? 'log'}-${index}`}
                  className="theme-subtle-card flex gap-3 px-4 py-3"
                >
                  <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl ${toneStyle.badge}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${toneStyle.badge}`}>
                        {toneStyle.label}
                      </span>
                      <span className="theme-muted text-xs uppercase tracking-[0.18em]">
                        {formatTime(log.time)}
                      </span>
                    </div>
                    <p className="theme-copy mt-2 break-words leading-6">{log.message}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
};
