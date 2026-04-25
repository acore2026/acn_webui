import { FormEvent, useCallback, useEffect, useState } from 'react';
import { CertificateUploadModal } from '../components/CertificateUploadModal';
import { SectionCard } from '../components/SectionCard';
import { LanguageMode, shellCopy } from '../i18n';
import { CertificateRecord, DatabaseSourceConfig, DirectDemoCameraConfig } from '../types';

interface SettingsPageProps {
  dataSourceConfig: DatabaseSourceConfig | null;
  language: LanguageMode;
}

export const SettingsPage = ({ dataSourceConfig, language }: SettingsPageProps) => {
  const isZh = language === 'zh';
  const certCopy = shellCopy[language].certificates;
  const directDemoCopy = shellCopy[language].directDemoCamera;
  const virtualAgentCopy = shellCopy[language].virtualAgent;
  const [certificates, setCertificates] = useState<CertificateRecord[]>([]);
  const [certificatesLoading, setCertificatesLoading] = useState(true);
  const [certificatesError, setCertificatesError] = useState<string | null>(null);
  const [certificatesMessage, setCertificatesMessage] = useState<string | null>(null);
  const [uploadStatusMessage, setUploadStatusMessage] = useState<string | null>(null);
  const [uploadStatusTone, setUploadStatusTone] = useState<'success' | 'error' | null>(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingCertId, setDeletingCertId] = useState<string | null>(null);
  const [directDemoConfig, setDirectDemoConfig] = useState<DirectDemoCameraConfig | null>(null);
  const [directDemoLoading, setDirectDemoLoading] = useState(true);
  const [directDemoBusy, setDirectDemoBusy] = useState(false);
  const [directDemoMessage, setDirectDemoMessage] = useState<string | null>(null);
  const [directDemoError, setDirectDemoError] = useState<string | null>(null);
  const [virtualAgentDraft, setVirtualAgentDraft] = useState({
    agentName: '',
    agentId: '',
    capabilities: '',
    status: 'online',
    currentTask: ''
  });
  const [virtualAgentBusy, setVirtualAgentBusy] = useState(false);
  const [virtualAgentMessage, setVirtualAgentMessage] = useState<string | null>(null);
  const [virtualAgentError, setVirtualAgentError] = useState<string | null>(null);

  const settingsGroups = [
    {
      title: isZh ? '外观' : 'Appearance',
      items: isZh
        ? ['在浅色与深色模式之间切换', '刷新后保留当前主题', '保证卡片、图表和标签的对比度清晰']
        : ['Switch between dark mode and light mode', 'Keep the current theme saved after refresh', 'Use clear contrast for cards, charts, and labels']
    },
    {
      title: isZh ? '布局' : 'Layout',
      items: isZh
        ? ['保持左侧边栏固定', '以清晰的纵向结构展示指标、拓扑和消息', '在小屏幕上保留合理的响应式间距']
        : ['Keep the sidebar fixed on the left', 'Show metrics, topology, and messages in a clean vertical flow', 'Preserve responsive spacing on smaller screens']
    },
    {
      title: isZh ? '通知' : 'Notifications',
      items: isZh
        ? ['清晰突出重要系统消息', '从视觉上区分信息、警告和错误状态', '让最近活动一眼可扫']
        : ['Highlight important system messages clearly', 'Separate info, warning, and error states visually', 'Keep recent activity easy to scan at a glance']
    },
    {
      title: isZh ? '数据源' : 'Data Source',
      items: isZh
        ? [
            dataSourceConfig?.useExternalDb
              ? '当前配置为读取外部 SQLite 数据库。'
              : '当前配置为使用 WebUI 本地缓存数据库。',
            `当前生效来源：${
              dataSourceConfig?.activeSource === 'external'
                ? '外部数据库'
                : dataSourceConfig?.activeSource === 'local'
                  ? '本地缓存'
                  : '本地兜底'
            }`,
            `外部数据库路径：${dataSourceConfig?.externalDbPath || '未加载'}`,
            `本地缓存路径：${dataSourceConfig?.localDbPath || '未加载'}`
          ]
        : [
            dataSourceConfig?.useExternalDb
              ? 'The dashboard is currently configured to read an external SQLite database.'
              : 'The dashboard is currently configured to use the WebUI local cache database.',
            `Current active source: ${
              dataSourceConfig?.activeSource === 'external'
                ? 'External DB'
                : dataSourceConfig?.activeSource === 'local'
                  ? 'Local cache'
                  : 'Local fallback'
            }`,
            `External DB path: ${dataSourceConfig?.externalDbPath || 'Unavailable'}`,
            `Local cache path: ${dataSourceConfig?.localDbPath || 'Unavailable'}`
          ]
    }
  ];

  const fetchCertificates = useCallback(async () => {
    setCertificatesLoading(true);
    try {
      const response = await fetch('/api/settings/certificates');
      const payload = (await response.json()) as {
        certificates?: CertificateRecord[];
        detail?: string;
      };

      if (!response.ok) {
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }

      setCertificates(Array.isArray(payload.certificates) ? payload.certificates : []);
      setCertificatesError(null);
      return true;
    } catch (error) {
      console.error('Failed to load certificates:', error);
      setCertificatesError(
        error instanceof Error ? error.message : certCopy.loadFailed
      );
      return false;
    } finally {
      setCertificatesLoading(false);
    }
  }, [certCopy.loadFailed]);

  useEffect(() => {
    void fetchCertificates();
  }, [fetchCertificates]);

  const fetchDirectDemoConfig = useCallback(async () => {
    setDirectDemoLoading(true);
    try {
      const response = await fetch('/api/settings/direct-demo-camera');
      const payload = (await response.json()) as {
        config?: DirectDemoCameraConfig;
        detail?: string;
      };

      if (!response.ok) {
        throw new Error(payload.detail || `HTTP ${response.status}`);
      }

      setDirectDemoConfig(payload.config ?? null);
      setDirectDemoError(null);
      return true;
    } catch (error) {
      console.error('Failed to load Direct Demo Camera settings:', error);
      setDirectDemoError(error instanceof Error ? error.message : directDemoCopy.failed);
      return false;
    } finally {
      setDirectDemoLoading(false);
    }
  }, [directDemoCopy.failed]);

  useEffect(() => {
    void fetchDirectDemoConfig();
  }, [fetchDirectDemoConfig]);

  const handleUploadCertificate = useCallback(
    async ({ file, filePath }: { file: File | null; filePath: string }) => {
      setUploading(true);
      setCertificatesMessage(null);
      setCertificatesError(null);
      setUploadStatusMessage(null);
      setUploadStatusTone(null);

      try {
        const formData = new FormData();
        if (file) {
          formData.append('file', file);
        }
        if (filePath) {
          formData.append('filePath', filePath);
        }

        const response = await fetch('/api/settings/certificates/upload', {
          method: 'POST',
          body: formData
        });
        const payload = (await response.json()) as {
          certificates?: CertificateRecord[];
          message?: string;
          detail?: string;
        };

        if (!response.ok) {
          throw new Error(payload.detail || `HTTP ${response.status}`);
        }

        setCertificates(Array.isArray(payload.certificates) ? payload.certificates : []);
        const successMessage = payload.message || certCopy.uploadSuccess;
        setCertificatesMessage(successMessage);
        setUploadStatusMessage(successMessage);
        setUploadStatusTone('success');
      } catch (error) {
        console.error('Failed to upload certificate:', error);
        const failureMessage =
          error instanceof Error ? `${certCopy.uploadFailed}: ${error.message}` : certCopy.uploadFailed;
        setCertificatesError(failureMessage);
        setUploadStatusMessage(failureMessage);
        setUploadStatusTone('error');
      } finally {
        setUploading(false);
      }
    },
    [certCopy.uploadFailed, certCopy.uploadSuccess]
  );

  const handleDeleteCertificate = useCallback(
    async (certId: string) => {
      setDeletingCertId(certId);
      setCertificatesMessage(null);
      setCertificatesError(null);

      try {
        const response = await fetch(`/api/settings/certificates/${encodeURIComponent(certId)}`, {
          method: 'DELETE'
        });
        const payload = (await response.json()) as {
          certificates?: CertificateRecord[];
          message?: string;
          detail?: string;
        };

        if (!response.ok) {
          throw new Error(payload.detail || `HTTP ${response.status}`);
        }

        setCertificates(Array.isArray(payload.certificates) ? payload.certificates : []);
        setCertificatesMessage(payload.message || certCopy.deleteSuccess);
      } catch (error) {
        console.error('Failed to delete certificate:', error);
        setCertificatesError(
          error instanceof Error ? `${certCopy.deleteFailed}: ${error.message}` : certCopy.deleteFailed
        );
      } finally {
        setDeletingCertId(null);
      }
    },
    [certCopy.deleteFailed, certCopy.deleteSuccess]
  );

  const handleDirectDemoToggle = useCallback(
    async (enabled: boolean) => {
      setDirectDemoBusy(true);
      setDirectDemoMessage(null);
      setDirectDemoError(null);

      try {
        const response = await fetch('/api/settings/direct-demo-camera', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ enabled })
        });
        const payload = (await response.json()) as {
          config?: DirectDemoCameraConfig;
          message?: string;
          detail?: string;
        };

        if (!response.ok) {
          throw new Error(payload.detail || `HTTP ${response.status}`);
        }

        setDirectDemoConfig(payload.config ?? null);
        setDirectDemoMessage(
          payload.message || (enabled ? directDemoCopy.openSuccess : directDemoCopy.closeSuccess)
        );
      } catch (error) {
        console.error('Failed to update Direct Demo Camera settings:', error);
        setDirectDemoError(error instanceof Error ? error.message : directDemoCopy.failed);
      } finally {
        setDirectDemoBusy(false);
      }
    },
    [directDemoCopy.closeSuccess, directDemoCopy.failed, directDemoCopy.openSuccess]
  );

  const handleVirtualAgentSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const agentName = virtualAgentDraft.agentName.trim();
      if (!agentName) {
        setVirtualAgentError(virtualAgentCopy.required);
        return;
      }

      setVirtualAgentBusy(true);
      setVirtualAgentMessage(null);
      setVirtualAgentError(null);

      try {
        const response = await fetch('/api/settings/virtual-agents', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            agentName,
            agentId: virtualAgentDraft.agentId.trim(),
            capabilities: virtualAgentDraft.capabilities,
            status: virtualAgentDraft.status,
            currentTask: virtualAgentDraft.currentTask.trim()
          })
        });
        const payload = (await response.json()) as {
          message?: string;
          detail?: string;
        };

        if (!response.ok) {
          throw new Error(payload.detail || `HTTP ${response.status}`);
        }

        setVirtualAgentDraft({
          agentName: '',
          agentId: '',
          capabilities: '',
          status: 'online',
          currentTask: ''
        });
        setVirtualAgentMessage(payload.message || virtualAgentCopy.success);
      } catch (error) {
        console.error('Failed to add virtual agent:', error);
        setVirtualAgentError(error instanceof Error ? error.message : virtualAgentCopy.failed);
      } finally {
        setVirtualAgentBusy(false);
      }
    },
    [virtualAgentCopy.failed, virtualAgentCopy.required, virtualAgentCopy.success, virtualAgentDraft]
  );

  return (
    <>
      <SectionCard
        eyebrow={isZh ? '设置' : 'Settings'}
        title={isZh ? '仪表盘设置' : 'Dashboard Settings'}
        description={isZh ? '用于控制主题、布局以及信息呈现方式的通用界面选项。' : 'General interface options for theme, layout, and how information is presented.'}
      >
        <div className="grid gap-4 xl:grid-cols-3">
          {settingsGroups.map((group) => (
            <div key={group.title} className="theme-card-muted p-5">
              <h3 className="theme-title text-lg font-semibold">{group.title}</h3>
              <ul className="theme-copy mt-4 space-y-3 text-sm leading-6">
                {group.items.map((item) => (
                  <li key={item} className="theme-subtle-card px-4 py-3">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-6 rounded-[28px] border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] p-5 md:p-6">
          <div>
            <p className="panel-eyebrow">{virtualAgentCopy.title}</p>
            <h3 className="theme-title mt-2 text-xl font-semibold">{virtualAgentCopy.add}</h3>
            <p className="theme-soft mt-2 max-w-3xl text-sm leading-6">{virtualAgentCopy.description}</p>
          </div>

          <form className="mt-5 grid gap-4" onSubmit={handleVirtualAgentSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                  {virtualAgentCopy.agentName}
                </span>
                <input
                  value={virtualAgentDraft.agentName}
                  onChange={(event) => setVirtualAgentDraft((current) => ({ ...current, agentName: event.target.value }))}
                  placeholder={virtualAgentCopy.agentNamePlaceholder}
                  className="mt-2 w-full rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] px-4 py-3 text-sm text-[color:var(--text-main)] outline-none transition placeholder:text-[color:var(--text-muted)] focus:border-[color:var(--border-strong)]"
                  disabled={virtualAgentBusy}
                />
              </label>

              <label className="block">
                <span className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                  {virtualAgentCopy.agentId}
                </span>
                <input
                  value={virtualAgentDraft.agentId}
                  onChange={(event) => setVirtualAgentDraft((current) => ({ ...current, agentId: event.target.value }))}
                  placeholder={virtualAgentCopy.agentIdPlaceholder}
                  className="mt-2 w-full rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] px-4 py-3 text-sm text-[color:var(--text-main)] outline-none transition placeholder:text-[color:var(--text-muted)] focus:border-[color:var(--border-strong)]"
                  disabled={virtualAgentBusy}
                />
              </label>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                  {virtualAgentCopy.capabilities}
                </span>
                <input
                  value={virtualAgentDraft.capabilities}
                  onChange={(event) => setVirtualAgentDraft((current) => ({ ...current, capabilities: event.target.value }))}
                  placeholder={virtualAgentCopy.capabilitiesPlaceholder}
                  className="mt-2 w-full rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] px-4 py-3 text-sm text-[color:var(--text-main)] outline-none transition placeholder:text-[color:var(--text-muted)] focus:border-[color:var(--border-strong)]"
                  disabled={virtualAgentBusy}
                />
              </label>

              <label className="block">
                <span className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                  {virtualAgentCopy.status}
                </span>
                <select
                  value={virtualAgentDraft.status}
                  onChange={(event) => setVirtualAgentDraft((current) => ({ ...current, status: event.target.value }))}
                  className="mt-2 w-full rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] px-4 py-3 text-sm text-[color:var(--text-main)] outline-none transition focus:border-[color:var(--border-strong)]"
                  disabled={virtualAgentBusy}
                >
                  <option value="online">{virtualAgentCopy.statusOnline}</option>
                  <option value="busy">{virtualAgentCopy.statusBusy}</option>
                  <option value="offline">{virtualAgentCopy.statusOffline}</option>
                </select>
              </label>
            </div>

            <label className="block">
              <span className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                {virtualAgentCopy.currentTask}
              </span>
              <input
                value={virtualAgentDraft.currentTask}
                onChange={(event) => setVirtualAgentDraft((current) => ({ ...current, currentTask: event.target.value }))}
                placeholder={virtualAgentCopy.currentTaskPlaceholder}
                className="mt-2 w-full rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] px-4 py-3 text-sm text-[color:var(--text-main)] outline-none transition placeholder:text-[color:var(--text-muted)] focus:border-[color:var(--border-strong)]"
                disabled={virtualAgentBusy}
              />
            </label>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-h-[1.5rem] text-sm">
                {virtualAgentError ? (
                  <span className="text-[color:var(--accent-rose-text)]">{virtualAgentError}</span>
                ) : virtualAgentMessage ? (
                  <span className="theme-copy">{virtualAgentMessage}</span>
                ) : null}
              </div>
              <button
                type="submit"
                disabled={virtualAgentBusy}
                className={['theme-top-button px-5 py-3', virtualAgentBusy ? 'cursor-wait opacity-70' : ''].join(' ')}
              >
                {virtualAgentBusy ? virtualAgentCopy.adding : virtualAgentCopy.add}
              </button>
            </div>
          </form>
        </div>

        <div className="mt-6 rounded-[28px] border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] p-5 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="panel-eyebrow">{directDemoCopy.title}</p>
              <h3 className="theme-title mt-2 text-xl font-semibold">{directDemoCopy.statusTitle}</h3>
              <p className="theme-soft mt-2 max-w-3xl text-sm leading-6">{directDemoCopy.description}</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => {
                  void handleDirectDemoToggle(true);
                }}
                disabled={directDemoBusy || directDemoConfig?.enabled}
                className={[
                  'theme-top-button px-5 py-3',
                  directDemoBusy ? 'cursor-wait opacity-70' : '',
                  directDemoConfig?.enabled ? 'opacity-60' : ''
                ].join(' ')}
              >
                {directDemoBusy && !directDemoConfig?.enabled ? directDemoCopy.opening : directDemoCopy.open}
              </button>
              <button
                type="button"
                onClick={() => {
                  void handleDirectDemoToggle(false);
                }}
                disabled={directDemoBusy || directDemoConfig?.enabled === false}
                className={[
                  'theme-top-button px-5 py-3',
                  directDemoBusy ? 'cursor-wait opacity-70' : '',
                  directDemoConfig?.enabled === false ? 'opacity-60' : ''
                ].join(' ')}
              >
                {directDemoBusy && directDemoConfig?.enabled ? directDemoCopy.closing : directDemoCopy.close}
              </button>
            </div>
          </div>

          <div className="mt-5 min-h-[1.5rem] text-sm">
            {directDemoError ? (
              <span className="text-[color:var(--accent-rose-text)]">{directDemoError}</span>
            ) : directDemoMessage ? (
              <span className="theme-copy">{directDemoMessage}</span>
            ) : null}
          </div>

          {directDemoLoading ? (
            <div className="theme-subtle-card mt-4 px-4 py-5 text-sm">
              {isZh ? '正在加载直连演示相机状态...' : 'Loading Direct Demo Camera status...'}
            </div>
          ) : (
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div className="theme-subtle-card px-4 py-4">
                <p className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                  {directDemoCopy.statusTitle}
                </p>
                <p className="theme-title mt-2 text-sm font-medium">
                  {directDemoConfig?.enabled ? directDemoCopy.statusEnabled : directDemoCopy.statusDisabled}
                </p>
              </div>
              <div className="theme-subtle-card px-4 py-4">
                <p className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                  Runtime
                </p>
                <p className="theme-title mt-2 text-sm font-medium">
                  {directDemoConfig?.running ? directDemoCopy.runtimeRunning : directDemoCopy.runtimeStopped}
                </p>
              </div>
              <div className="theme-subtle-card px-4 py-4">
                <p className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                  Track
                </p>
                <p className="theme-title mt-2 text-sm font-medium">
                  {directDemoConfig?.trackAvailable ? directDemoCopy.trackAvailable : directDemoCopy.trackUnavailable}
                </p>
              </div>
              <div className="theme-subtle-card px-4 py-4">
                <p className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                  {directDemoCopy.trackName}
                </p>
                <p className="theme-title mt-2 text-sm font-medium">
                  {directDemoConfig?.trackName || '-'}
                </p>
                <p className="theme-copy mt-2 break-all text-xs">
                  {directDemoCopy.trackId}: {directDemoConfig?.trackId || '-'}
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="mt-6 rounded-[28px] border border-[color:var(--border-soft)] bg-[color:var(--surface-soft-solid)] p-5 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="panel-eyebrow">{certCopy.title}</p>
              <h3 className="theme-title mt-2 text-xl font-semibold">{certCopy.listTitle}</h3>
              <p className="theme-soft mt-2 max-w-3xl text-sm leading-6">{certCopy.listDescription}</p>
            </div>
            <button
              type="button"
              onClick={() => {
                setCertificatesMessage(null);
                setCertificatesError(null);
                setUploadStatusMessage(null);
                setUploadStatusTone(null);
                setUploadModalOpen(true);
              }}
              className="theme-top-button px-5 py-3"
            >
              {certCopy.upload}
            </button>
          </div>

          <div className="mt-5 min-h-[1.5rem] text-sm">
            {certificatesError ? (
              <span className="text-[color:var(--accent-rose-text)]">{certificatesError}</span>
            ) : certificatesMessage ? (
              <span className="theme-copy">{certificatesMessage}</span>
            ) : null}
          </div>

          {certificatesLoading ? (
            <div className="theme-subtle-card mt-4 px-4 py-5 text-sm">{certCopy.loading}</div>
          ) : certificates.length === 0 ? (
            <div className="theme-subtle-card mt-4 px-4 py-5 text-sm">{certCopy.empty}</div>
          ) : (
            <div className="mt-4 space-y-3">
              {certificates.map((certificate) => {
                const deleting = deletingCertId === certificate.certID;
                return (
                  <div
                    key={certificate.certID}
                    className="theme-subtle-card flex flex-col gap-4 px-4 py-4 lg:flex-row lg:items-center lg:justify-between"
                  >
                    <div className="grid flex-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                      <div>
                        <p className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                          {certCopy.certName}
                        </p>
                        <p className="theme-title mt-2 break-all text-sm font-medium">
                          {certificate.certName}
                        </p>
                      </div>
                      <div>
                        <p className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                          {certCopy.authority}
                        </p>
                        <p className="theme-copy mt-2 break-all text-sm">{certificate.authority}</p>
                      </div>
                      <div>
                        <p className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                          {certCopy.validity}
                        </p>
                        <p className="theme-copy mt-2 text-sm">{certificate.validity}</p>
                      </div>
                      <div>
                        <p className="theme-muted text-xs font-semibold uppercase tracking-[0.18em]">
                          {certCopy.certId}
                        </p>
                        <p className="theme-copy mt-2 break-all text-sm">{certificate.certID}</p>
                      </div>
                    </div>

                    <div className="flex justify-end">
                      <button
                        type="button"
                        onClick={() => {
                          void handleDeleteCertificate(certificate.certID);
                        }}
                        disabled={deleting}
                        className={[
                          'theme-top-button px-4 py-2',
                          deleting ? 'cursor-wait opacity-70' : ''
                        ].join(' ')}
                      >
                        {deleting ? certCopy.deleting : certCopy.delete}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </SectionCard>

      <CertificateUploadModal
        open={uploadModalOpen}
        busy={uploading}
        language={language}
        statusMessage={uploadStatusMessage}
        statusTone={uploadStatusTone}
        onClose={() => setUploadModalOpen(false)}
        onSubmit={handleUploadCertificate}
      />
    </>
  );
};
