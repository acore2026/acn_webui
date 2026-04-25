import { createPortal } from 'react-dom';
import { useEffect, useMemo, useRef, useState } from 'react';
import { LanguageMode, shellCopy } from '../i18n';
import { DatabaseSourceConfig } from '../types';
import { DatabaseIcon } from './icons';

interface DatabaseSettingsButtonProps {
  config: DatabaseSourceConfig | null;
  language: LanguageMode;
  onSave: (next: { useExternalDb: boolean; externalDbPath: string }) => Promise<void>;
}

export const DatabaseSettingsButton = ({
  config,
  language,
  onSave
}: DatabaseSettingsButtonProps) => {
  const copy = shellCopy[language].databaseMenu;
  const isZh = language === 'zh';
  const [open, setOpen] = useState(false);
  const [useExternalDb, setUseExternalDb] = useState(config?.useExternalDb ?? true);
  const [externalDbPath, setExternalDbPath] = useState(config?.externalDbPath ?? '');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [panelPosition, setPanelPosition] = useState<{ left: number; bottom: number } | null>(null);

  useEffect(() => {
    setUseExternalDb(config?.useExternalDb ?? true);
    setExternalDbPath(config?.externalDbPath ?? '');
  }, [config]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      const clickedButton = rootRef.current?.contains(target);
      const clickedPanel = panelRef.current?.contains(target);
      if (!clickedButton && !clickedPanel) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    const updatePosition = () => {
      const rect = rootRef.current?.getBoundingClientRect();
      if (!rect) {
        return;
      }
      setPanelPosition({
        left: Math.max(16, rect.left),
        bottom: Math.max(16, window.innerHeight - rect.top + 12)
      });
    };

    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open]);

  const activeSourceLabel = useMemo(() => {
    switch (config?.activeSource) {
      case 'external':
        return copy.activeExternal;
      case 'local':
        return copy.activeLocal;
      default:
        return copy.activeFallback;
    }
  }, [config?.activeSource, copy.activeExternal, copy.activeFallback, copy.activeLocal]);

  const statusText = error || message;
  const inputClassName =
    'w-full rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] px-4 py-3 text-sm text-[color:var(--text-main)] outline-none transition placeholder:text-[color:var(--text-muted)] focus:border-[color:var(--border-strong)]';
  const popover =
    open && typeof document !== 'undefined' && panelPosition
      ? createPortal(
        <div
          ref={panelRef}
          className="fixed z-[400] w-[22rem] rounded-[28px] border border-[color:var(--border-strong)] bg-[color:var(--surface-solid)] p-5 shadow-[0_28px_90px_rgba(8,15,30,0.34)]"
          style={{
            left: `${panelPosition.left}px`,
              bottom: `${panelPosition.bottom}px`
            }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="panel-eyebrow">{copy.title}</p>
                <p className="theme-copy mt-2 text-sm leading-6">{copy.description}</p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="theme-top-button px-3 py-2 text-xs"
              >
                {copy.close}
              </button>
            </div>

            <div className="mt-4 space-y-3">
              <button
                type="button"
                onClick={() => setUseExternalDb(true)}
                className={[
                  'w-full rounded-2xl border px-4 py-3 text-left transition',
                  useExternalDb ? 'theme-nav-active' : 'theme-nav-button'
                ].join(' ')}
              >
                <div className="text-sm font-medium">{copy.externalLabel}</div>
                <div className="theme-muted mt-1 text-xs leading-5">{copy.externalDescription}</div>
              </button>

              <button
                type="button"
                onClick={() => setUseExternalDb(false)}
                className={[
                  'w-full rounded-2xl border px-4 py-3 text-left transition',
                  !useExternalDb ? 'theme-nav-active' : 'theme-nav-button'
                ].join(' ')}
              >
                <div className="text-sm font-medium">{copy.localLabel}</div>
                <div className="theme-muted mt-1 text-xs leading-5">{copy.localDescription}</div>
              </button>
            </div>

            <label className="mt-4 block">
              <span className="theme-muted mb-2 block text-xs uppercase tracking-[0.18em]">
                {copy.pathLabel}
              </span>
              <input
                value={externalDbPath}
                onChange={(event) => setExternalDbPath(event.target.value)}
                className={inputClassName}
                placeholder={copy.pathPlaceholder}
                disabled={!useExternalDb || saving}
              />
            </label>

            <div className="mt-4 grid gap-3">
              <div className="rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] px-4 py-3 text-sm">
                <div className="theme-muted text-xs uppercase tracking-[0.18em]">
                  {copy.activeSourceLabel}
                </div>
                <div className="theme-title mt-2 font-medium">{activeSourceLabel}</div>
              </div>
              <div className="rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] px-4 py-3 text-sm">
                <div className="theme-title font-medium">{copy.localPathLabel}</div>
                <div className="theme-copy mt-2 break-all text-xs leading-5">
                  {config?.localDbPath || (isZh ? '未返回路径' : 'Path unavailable')}
                </div>
                <div className="theme-muted mt-2 text-xs">
                  {config?.localDbExists ? copy.localExists : copy.localMissing}
                </div>
              </div>
              <div className="rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] px-4 py-3 text-sm">
                <div className="theme-title font-medium">{copy.pathLabel}</div>
                <div className="theme-copy mt-2 break-all text-xs leading-5">
                  {config?.externalDbPath || externalDbPath || (isZh ? '未设置路径' : 'Path unavailable')}
                </div>
                <div className="theme-muted mt-2 text-xs">
                  {config?.externalDbExists ? copy.externalExists : copy.externalMissing}
                </div>
              </div>
            </div>

            <div className="theme-copy mt-4 min-h-[1.5rem] text-sm">{statusText}</div>

            <div className="mt-3 flex justify-end">
              <button
                type="button"
                disabled={saving}
                onClick={async () => {
                  setSaving(true);
                  setMessage(null);
                  setError(null);
                  try {
                    await onSave({ useExternalDb, externalDbPath });
                    setMessage(copy.saved);
                  } catch (saveError) {
                    setError(saveError instanceof Error ? saveError.message : copy.failed);
                  } finally {
                    setSaving(false);
                  }
                }}
                className={['theme-top-button px-4 py-2', saving ? 'cursor-wait opacity-70' : ''].join(' ')}
              >
                {saving ? copy.saving : copy.save}
              </button>
            </div>
          </div>,
          document.body
        )
      : null;

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="theme-top-button h-12 w-12 justify-center rounded-2xl px-0 py-0"
        aria-label={copy.buttonLabel}
        title={copy.buttonLabel}
        >
          <span className="theme-accent-icon flex h-10 w-10 items-center justify-center rounded-2xl">
            <DatabaseIcon />
          </span>
        </button>
      {popover}
    </div>
  );
};
