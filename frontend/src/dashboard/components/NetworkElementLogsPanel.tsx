import { useEffect, useMemo, useState } from 'react';
import {
  BackendLogEntry,
  MessageLevel,
  NetworkElementLogGroup,
  NetworkElementLogSource
} from '../types';
import { LanguageMode } from '../i18n';
import { ErrorIcon, InfoIcon, WarningIcon } from './icons';

interface NetworkElementLogsPanelProps {
  groups: NetworkElementLogGroup[];
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

  const normalized = value.replace(',', '.');
  const parsed = new Date(normalized.includes('T') ? normalized : normalized.replace(' ', 'T'));
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

const renderEntries = (entries: BackendLogEntry[], language: LanguageMode) => {
  const isZh = language === 'zh';

  if (entries.length === 0) {
    return (
      <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-[color:var(--border-soft)] px-4 text-sm text-[color:var(--text-soft)]">
        {isZh ? '当前没有可显示的日志内容。' : 'No log lines available yet.'}
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-3 font-mono text-sm">
      {entries.map((entry, index) => {
        const tone = resolveTone(entry.level);
        const toneStyle = toneStyles[tone];
        const Icon = toneStyle.icon;

        return (
          <div
            key={`${entry.time ?? 'log'}-${index}`}
            className="theme-subtle-card flex min-w-0 gap-3 px-4 py-3"
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
                  {formatTime(entry.time)}
                </span>
              </div>
              <p className="theme-copy mt-2 break-words leading-6 [overflow-wrap:anywhere]">{entry.message}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export const NetworkElementLogsPanel = ({
  groups,
  loading,
  error,
  language
}: NetworkElementLogsPanelProps) => {
  const isZh = language === 'zh';
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null);
  const [activeSubLogId, setActiveSubLogId] = useState<string | null>(null);
  const activeGroup = useMemo(
    () => groups.find((group) => group.id === activeGroupId) ?? groups[0] ?? null,
    [activeGroupId, groups]
  );
  const activeSource = useMemo<NetworkElementLogSource | NetworkElementLogGroup | null>(() => {
    if (!activeGroup) {
      return null;
    }

    const subLogs = activeGroup.subLogs ?? [];
    if (subLogs.length === 0) {
      return activeGroup;
    }

    return subLogs.find((item) => item.id === activeSubLogId) ?? subLogs[0] ?? activeGroup;
  }, [activeGroup, activeSubLogId]);

  useEffect(() => {
    if (groups.length === 0) {
      setActiveGroupId(null);
      setActiveSubLogId(null);
      return;
    }

    if (!activeGroupId || !groups.some((group) => group.id === activeGroupId)) {
      setActiveGroupId(groups[0].id);
    }
  }, [activeGroupId, groups]);

  useEffect(() => {
    if (!activeGroup || !activeGroup.subLogs || activeGroup.subLogs.length === 0) {
      setActiveSubLogId(null);
      return;
    }

    if (!activeSubLogId || !activeGroup.subLogs.some((item) => item.id === activeSubLogId)) {
      setActiveSubLogId(activeGroup.subLogs[0].id);
    }
  }, [activeGroup, activeSubLogId]);

  return (
    <section className="theme-card-muted min-w-0 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="theme-title text-lg font-semibold">{isZh ? '网络组件日志' : 'Network Element Logs'}</h3>
          <p className="theme-soft mt-1 text-sm">
            {isZh
              ? '读取 ACN Agent、AgentGW 与 IDM 的最新日志文件，便于直接检查各网络组件运行状态。'
              : 'Reads the latest ACN Agent, AgentGW, and IDM log files so you can inspect each network element directly.'}
          </p>
        </div>
        <span className="theme-chip shrink-0 px-3 py-1 text-xs font-medium">
          {loading ? (isZh ? '刷新中…' : 'Refreshing…') : (isZh ? `${groups.length} 个组件` : `${groups.length} elements`)}
        </span>
      </div>

      {error ? (
        <div className="mt-4 flex min-h-[120px] items-center justify-center rounded-2xl border border-[color:var(--accent-rose-border)] bg-[color:var(--accent-rose-bg)] px-4 text-sm text-[color:var(--accent-rose-text)]">
          {error}
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-2">
            {groups.map((group) => {
              const isActive = group.id === activeGroup?.id;

              return (
                <button
                  key={group.id}
                  type="button"
                  onClick={() => setActiveGroupId(group.id)}
                  className={[
                    'flex max-w-full min-w-0 items-center gap-3 rounded-2xl border px-4 py-3 text-left transition',
                    isActive ? 'theme-nav-active shadow-glow' : 'theme-nav-button'
                  ].join(' ')}
                >
                  <span className="min-w-0 truncate text-sm font-medium">{group.name}</span>
                  <span className="theme-muted shrink-0 text-xs">
                    {isZh ? `${group.entries.length} 条` : `${group.entries.length} lines`}
                  </span>
                </button>
              );
            })}
          </div>

          {activeGroup?.subLogs && activeGroup.subLogs.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {activeGroup.subLogs.map((subLog) => {
                const isActive = subLog.id === activeSource?.id;

                return (
                  <button
                    key={subLog.id}
                    type="button"
                    onClick={() => setActiveSubLogId(subLog.id)}
                    className={[
                      'flex max-w-full min-w-0 items-center gap-3 rounded-2xl border px-4 py-2.5 text-left transition',
                      isActive ? 'theme-nav-active shadow-glow' : 'theme-nav-button'
                    ].join(' ')}
                  >
                    <span className="min-w-0 truncate text-sm font-medium">{subLog.name}</span>
                    <span className="theme-muted shrink-0 text-xs">
                      {isZh ? `${subLog.entries.length} 条` : `${subLog.entries.length} lines`}
                    </span>
                  </button>
                );
              })}
            </div>
          ) : null}

          {activeSource ? (
            <article className="theme-subtle-card flex min-h-[420px] min-w-0 flex-col p-4">
              <div className="border-b border-[color:var(--border-soft)] pb-3">
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <h4 className="theme-title min-w-0 break-words text-base font-semibold [overflow-wrap:anywhere]">
                    {activeGroup?.subLogs && activeGroup.subLogs.length > 0
                      ? `${activeGroup.name} / ${activeSource.name}`
                      : activeSource.name}
                  </h4>
                  <span className="theme-chip shrink-0 px-2.5 py-1 text-[11px] font-medium">
                    {isZh ? `${activeSource.entries.length} 条` : `${activeSource.entries.length} lines`}
                  </span>
                </div>
                {activeSource.error ? (
                  <p className="mt-2 text-xs text-[color:var(--accent-rose-text)]">{activeSource.error}</p>
                ) : null}
              </div>

              <div className="mt-4 h-[360px] max-w-full overflow-x-hidden overflow-y-auto rounded-3xl border border-[color:var(--border-soft)] bg-[color:var(--surface-strong)]/80 p-3">
                {activeSource.error ? (
                  <div className="flex h-full items-center justify-center rounded-2xl border border-[color:var(--accent-rose-border)] bg-[color:var(--accent-rose-bg)] px-4 text-sm text-[color:var(--accent-rose-text)]">
                    {activeSource.error}
                  </div>
                ) : (
                  renderEntries(activeSource.entries, language)
                )}
              </div>
            </article>
          ) : (
            <div className="flex min-h-[180px] items-center justify-center rounded-2xl border border-dashed border-[color:var(--border-soft)] px-4 text-sm text-[color:var(--text-soft)]">
              {isZh ? '当前没有可用的网络组件日志。' : 'No network element logs available yet.'}
            </div>
          )}
        </div>
      )}
    </section>
  );
};
