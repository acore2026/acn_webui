import { FormEvent, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { LanguageMode, shellCopy } from '../i18n';
import {
  TopologyAgentModel,
  VideoPlayerBootstrap,
  VideoPlayerConfig,
  VideoTrackDraft,
  VideoTrackModel
} from '../types';
import { SectionCard } from '../components/SectionCard';
import { MOQTrackPlayer } from '../components/MOQTrackPlayer';

interface AgentsPageProps {
  agents: TopologyAgentModel[];
  videoTracks: VideoTrackModel[];
  videoTracksLoading: boolean;
  videoTracksError: string | null;
  language: LanguageMode;
  onCreateTrack: (draft: VideoTrackDraft) => Promise<void>;
  onDeleteTrack: (trackId: string) => Promise<void>;
  onWatchTrack: (
    trackId: string
  ) => Promise<{ player: VideoPlayerConfig; bootstrap?: VideoPlayerBootstrap; track?: VideoTrackModel }>;
}

const statusTone = {
  online: 'theme-badge-emerald',
  busy: 'theme-badge-amber',
  offline: 'theme-badge-rose'
};

export const AgentsPage = ({
  agents,
  videoTracks,
  videoTracksLoading,
  videoTracksError,
  language,
  onCreateTrack,
  onDeleteTrack,
  onWatchTrack
}: AgentsPageProps) => {
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const [videoDialogOpen, setVideoDialogOpen] = useState(false);
  const [watchingTrackId, setWatchingTrackId] = useState<string | null>(null);
  const [activePlayerConfig, setActivePlayerConfig] = useState<VideoPlayerConfig | null>(null);
  const [activePlayerBootstrap, setActivePlayerBootstrap] = useState<VideoPlayerBootstrap | null>(null);
  const [activeVideoTrackId, setActiveVideoTrackId] = useState<string | null>(null);
  const [watchVideoError, setWatchVideoError] = useState<string | null>(null);
  const [trackDraft, setTrackDraft] = useState<VideoTrackDraft>({
    agentId: '',
    taskId: '',
    trackName: 'Video',
    namespace: ''
  });
  const [trackActionMessage, setTrackActionMessage] = useState<string | null>(null);
  const [trackActionError, setTrackActionError] = useState<string | null>(null);
  const [creatingTrack, setCreatingTrack] = useState(false);
  const [deletingTrackId, setDeletingTrackId] = useState<string | null>(null);
  const isZh = language === 'zh';
  const videoCopy = shellCopy[language].agentsVideo;
  const inputClassName =
    'w-full rounded-2xl border border-[color:var(--border-soft)] bg-[color:var(--surface-strong)] px-4 py-3 text-sm text-[color:var(--text-main)] outline-none transition placeholder:text-[color:var(--text-muted)] focus:border-[color:var(--border-strong)]';
  const statusLabel = {
    online: isZh ? '在线' : 'online',
    busy: isZh ? '忙碌' : 'busy',
    offline: isZh ? '离线' : 'offline'
  };

  useEffect(() => {
    if (selectedAgentId && !agents.some((agent) => agent.id === selectedAgentId)) {
      setSelectedAgentId('');
    }
  }, [agents, selectedAgentId]);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedAgentId('');
        setVideoDialogOpen(false);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  const selectedAgent =
    agents.find((agent) => agent.id === selectedAgentId) ?? null;
  const activeVideoTrack =
    videoTracks.find((track) => track.trackId === activeVideoTrackId) ?? null;

  const handleWatchTrack = async (trackId: string) => {
    setWatchingTrackId(trackId);
    setWatchVideoError(null);
    setVideoDialogOpen(true);
    setActiveVideoTrackId(trackId);
    setActivePlayerConfig(null);
    setActivePlayerBootstrap(null);

    try {
      const payload = await onWatchTrack(trackId);
      setActivePlayerConfig(payload.player);
      setActivePlayerBootstrap(payload.bootstrap ?? null);
      if (payload.track?.trackId) {
        setActiveVideoTrackId(payload.track.trackId);
      }
    } catch (error) {
      setWatchVideoError(error instanceof Error ? error.message : videoCopy.error);
    } finally {
      setWatchingTrackId(null);
    }
  };

  const handleCreateTrack = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCreatingTrack(true);
    setTrackActionMessage(null);
    setTrackActionError(null);

    try {
      await onCreateTrack(trackDraft);
      setTrackDraft({
        agentId: '',
        taskId: '',
        trackName: 'Video',
        namespace: ''
      });
      setTrackActionMessage(videoCopy.addSuccess);
    } catch (error) {
      setTrackActionError(error instanceof Error ? error.message : videoCopy.actionFailed);
    } finally {
      setCreatingTrack(false);
    }
  };

  const handleDeleteTrack = async (track: VideoTrackModel) => {
    if (track.source === 'direct') {
      return;
    }

    setDeletingTrackId(track.trackId);
    setTrackActionMessage(null);
    setTrackActionError(null);

    try {
      await onDeleteTrack(track.trackId);
      setTrackActionMessage(videoCopy.deleteSuccess);
      if (activeVideoTrackId === track.trackId) {
        setVideoDialogOpen(false);
        setActiveVideoTrackId(null);
      }
    } catch (error) {
      setTrackActionError(error instanceof Error ? error.message : videoCopy.actionFailed);
    } finally {
      setDeletingTrackId(null);
    }
  };

  const detailDialog =
    selectedAgent && typeof document !== 'undefined'
      ? createPortal(
          <div
            className="fixed inset-0 z-[260] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm"
            role="presentation"
            onClick={() => setSelectedAgentId('')}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-label={`${selectedAgent.name} ${isZh ? '详情' : 'details'}`}
              className="glass-panel max-h-[85vh] w-full max-w-4xl overflow-y-auto p-6 md:p-7"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="relative pr-24">
                <button
                  type="button"
                  onClick={() => setSelectedAgentId('')}
                  className="theme-top-button absolute right-0 top-0 px-4 py-2"
                >
                  {isZh ? '关闭' : 'Close'}
                </button>

                <div>
                  <p className="panel-eyebrow">{isZh ? '智能体详情' : 'Agent Detail'}</p>
                  <h3 className="theme-title mt-2 text-2xl font-semibold">{selectedAgent.name}</h3>
                  <div className="mt-3">
                    <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${statusTone[selectedAgent.status]}`}>
                      {statusLabel[selectedAgent.status]}
                    </span>
                  </div>
                  <p className="theme-copy mt-2 max-w-3xl text-sm leading-6">{selectedAgent.summary}</p>
                </div>
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '角色' : 'Role'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.role}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '区域' : 'Region'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.region}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '吞吐量' : 'Throughput'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.throughput}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '运行中任务' : 'Running Tasks'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.taskCount}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '运行时长' : 'Uptime'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.uptime}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '最后心跳' : 'Last Heartbeat'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.lastHeartbeat}</dd>
                </div>
              </div>

              <div className="mt-6 grid gap-4 lg:grid-cols-2">
                <div>
                  <h4 className="theme-title text-sm font-semibold uppercase tracking-[0.18em]">{isZh ? '能力标签' : 'Capabilities'}</h4>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedAgent.capabilities.map((capability) => (
                      <span
                        key={capability}
                        className="theme-chip rounded-full px-3 py-1 text-xs font-medium"
                      >
                        {capability}
                      </span>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="theme-title text-sm font-semibold uppercase tracking-[0.18em]">{isZh ? '告警与备注' : 'Alerts & Notes'}</h4>
                  <ul className="mt-3 space-y-2">
                    {selectedAgent.alerts.map((alert) => (
                      <li key={alert} className="theme-subtle-card theme-copy px-4 py-3 text-sm leading-6">
                        {alert}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>,
          document.body
        )
      : null;

  const videoDialog =
    videoDialogOpen && activeVideoTrack && typeof document !== 'undefined'
      ? createPortal(
          <div
            className="fixed inset-0 z-[265] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm"
            role="presentation"
            onClick={() => setVideoDialogOpen(false)}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-label={`${activeVideoTrack.trackName} video player`}
              className="glass-panel max-h-[88vh] w-full max-w-6xl overflow-y-auto p-6 md:p-7"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                  <p className="panel-eyebrow">{videoCopy.modalEyebrow}</p>
                  <h3 className="theme-title mt-2 text-2xl font-semibold">
                    {activeVideoTrack.trackName}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setVideoDialogOpen(false)}
                  className="theme-top-button px-4 py-2"
                >
                  {videoCopy.close}
                </button>
              </div>

              {watchVideoError ? (
                <div className="theme-subtle-card theme-copy rounded-3xl px-5 py-5 text-sm">
                  {watchVideoError}
                </div>
              ) : activePlayerConfig ? (
                <MOQTrackPlayer
                  language={language}
                  bootstrap={activePlayerBootstrap}
                  player={activePlayerConfig}
                  track={activeVideoTrack}
                />
              ) : (
                <div className="theme-subtle-card theme-copy rounded-3xl px-5 py-10 text-center text-sm">
                  {videoCopy.watching}
                </div>
              )}
            </div>
          </div>,
          document.body
        )
      : null;

  const watchStateLabel = (state: VideoTrackModel['watchState']) => {
    switch (state) {
      case 'requested':
        return videoCopy.requested;
      case 'pending':
        return videoCopy.pending;
      case 'subscribed':
        return videoCopy.subscribed;
      case 'error':
        return videoCopy.error;
      default:
        return videoCopy.ready;
    }
  };

  const trackSourceLabel = (source?: VideoTrackModel['source']) => {
    switch (source) {
      case 'direct':
        return videoCopy.sourceDirect;
      case 'manual':
        return videoCopy.sourceManual;
      default:
        return videoCopy.sourceMoq;
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard
        id="agents-section"
        eyebrow={isZh ? '智能体' : 'Agents'}
        title={isZh ? '智能体名册' : 'Fleet Roster'}
        description={
          isZh
            ? '点击任意智能体卡片即可打开专属详情窗口，查看其资料、健康状态、能力标签与任务负载。'
            : 'Click an agent card to open a dedicated detail window with its profile, health, capabilities, and task load.'
        }
      >
        <div className="grid gap-4 xl:grid-cols-2">
          {agents.map((agent) => (
            <article
              key={agent.id}
              className={[
                'theme-card-muted overflow-hidden p-5 transition',
                selectedAgent?.id === agent.id
                  ? 'theme-nav-active ring-1 ring-cyan-300/25'
                  : 'hover:border-cyan-300/20 hover:bg-white/[0.04]'
              ].join(' ')}
            >
              <button
                type="button"
                onClick={() => setSelectedAgentId(agent.id)}
                className="w-full text-left"
                aria-haspopup="dialog"
                aria-expanded={selectedAgent?.id === agent.id}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="theme-title text-lg font-semibold">{agent.name}</h3>
                    <p className="theme-soft mt-1 text-sm">{agent.role}</p>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${statusTone[agent.status]}`}>
                    {statusLabel[agent.status]}
                  </span>
                </div>
                <dl className="theme-copy mt-5 grid gap-3 text-sm sm:grid-cols-2">
                  <div className="theme-subtle-card p-4">
                    <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '区域' : 'Region'}</dt>
                    <dd className="theme-title mt-2 font-medium">{agent.region}</dd>
                  </div>
                  <div className="theme-subtle-card p-4">
                    <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '吞吐量' : 'Throughput'}</dt>
                    <dd className="theme-title mt-2 font-medium">{agent.throughput}</dd>
                  </div>
                </dl>
                <p className="theme-soft mt-4 text-sm leading-6">{agent.summary}</p>
              </button>
            </article>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        eyebrow={videoCopy.eyebrow}
        title={videoCopy.title}
        description={videoCopy.description}
      >
        <form onSubmit={handleCreateTrack} className="theme-card-muted mb-4 p-5">
          <div className="mb-4">
            <p className="panel-eyebrow">{videoCopy.manageTitle}</p>
            <p className="theme-copy mt-2 text-sm leading-6">{videoCopy.manageDescription}</p>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="block">
              <span className="theme-muted mb-2 block text-xs uppercase tracking-[0.18em]">
                {videoCopy.agentIdLabel}
              </span>
              <input
                value={trackDraft.agentId}
                onChange={(event) =>
                  setTrackDraft((current) => ({ ...current, agentId: event.target.value }))
                }
                className={inputClassName}
                required
              />
            </label>
            <label className="block">
              <span className="theme-muted mb-2 block text-xs uppercase tracking-[0.18em]">
                {videoCopy.taskIdLabel}
              </span>
              <input
                value={trackDraft.taskId}
                onChange={(event) =>
                  setTrackDraft((current) => ({ ...current, taskId: event.target.value }))
                }
                className={inputClassName}
                required
              />
            </label>
            <label className="block">
              <span className="theme-muted mb-2 block text-xs uppercase tracking-[0.18em]">
                {videoCopy.trackNameLabel}
              </span>
              <input
                value={trackDraft.trackName}
                onChange={(event) =>
                  setTrackDraft((current) => ({ ...current, trackName: event.target.value }))
                }
                className={inputClassName}
                required
              />
            </label>
            <label className="block">
              <span className="theme-muted mb-2 block text-xs uppercase tracking-[0.18em]">
                {videoCopy.namespaceLabel}
              </span>
              <input
                value={trackDraft.namespace ?? ''}
                onChange={(event) =>
                  setTrackDraft((current) => ({ ...current, namespace: event.target.value }))
                }
                className={inputClassName}
                placeholder={videoCopy.namespacePlaceholder}
              />
            </label>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <div className="theme-copy text-sm">
              {trackActionError ? trackActionError : trackActionMessage}
            </div>
            <button
              type="submit"
              className={['theme-top-button px-4 py-2', creatingTrack ? 'cursor-wait opacity-70' : ''].join(' ')}
              disabled={creatingTrack}
            >
              {creatingTrack ? videoCopy.adding : videoCopy.add}
            </button>
          </div>
        </form>

        {videoTracksLoading ? (
          <div className="theme-card-muted px-5 py-8 text-sm">{videoCopy.loading}</div>
        ) : videoTracksError ? (
          <div className="theme-card-muted px-5 py-8 text-sm">{videoTracksError}</div>
        ) : videoTracks.length === 0 ? (
          <div className="theme-card-muted px-5 py-8 text-sm">{videoCopy.empty}</div>
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {videoTracks.map((track) => (
              <article key={track.trackId} className="theme-card-muted overflow-hidden p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="theme-title text-lg font-semibold">{track.trackName}</h3>
                    <p className="theme-soft mt-1 text-sm">
                      {track.agentId} · {videoCopy.task} {track.taskId}
                    </p>
                  </div>
                  <span className="theme-chip px-3 py-1 text-xs font-medium uppercase tracking-[0.16em]">
                    {watchStateLabel(track.watchState)}
                  </span>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className="theme-subtle-card p-4">
                    <p className="theme-muted text-xs uppercase tracking-[0.18em]">{videoCopy.namespace}</p>
                    <p className="theme-title mt-2 break-all text-sm font-medium">{track.namespace}</p>
                  </div>
                  <div className="theme-subtle-card p-4">
                    <p className="theme-muted text-xs uppercase tracking-[0.18em]">{videoCopy.seen}</p>
                    <p className="theme-title mt-2 text-sm font-medium">{track.seenCount}</p>
                  </div>
                  <div className="theme-subtle-card p-4">
                    <p className="theme-muted text-xs uppercase tracking-[0.18em]">{videoCopy.source}</p>
                    <p className="theme-title mt-2 text-sm font-medium">{trackSourceLabel(track.source)}</p>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
                  <p className="theme-soft text-sm">
                    {videoCopy.lastSeen}: {new Date(track.lastSeen).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')}
                  </p>
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={() => void handleWatchTrack(track.trackId)}
                      className={['theme-top-button px-4 py-2', watchingTrackId === track.trackId ? 'cursor-wait opacity-70' : ''].join(' ')}
                      disabled={watchingTrackId === track.trackId}
                    >
                      {watchingTrackId === track.trackId ? videoCopy.watching : videoCopy.watch}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteTrack(track)}
                      className={['theme-top-button px-4 py-2', deletingTrackId === track.trackId ? 'cursor-wait opacity-70' : ''].join(' ')}
                      disabled={track.source === 'direct' || deletingTrackId === track.trackId}
                      title={track.source === 'direct' ? videoCopy.deleteBlocked : undefined}
                    >
                      {track.source === 'direct'
                        ? videoCopy.deleteBlocked
                        : deletingTrackId === track.trackId
                          ? videoCopy.deleting
                          : videoCopy.delete}
                    </button>
                  </div>
                </div>

                {track.lastError ? (
                  <p className="theme-copy mt-3 text-sm leading-6">{track.lastError}</p>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </SectionCard>

      {detailDialog}
      {videoDialog}
    </div>
  );
};
