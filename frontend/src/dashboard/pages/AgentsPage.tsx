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
  onDeleteTrack: (trackId: string) => Promise<void>;
  onSubscribeTrack: (
    draft: VideoTrackDraft
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
  onDeleteTrack,
  onSubscribeTrack
}: AgentsPageProps) => {
  const [selectedAgentId, setSelectedAgentId] = useState<string>('');
  const [watchingTrackId, setWatchingTrackId] = useState<string | null>(null);
  const [activePlayerConfig, setActivePlayerConfig] = useState<VideoPlayerConfig | null>(null);
  const [activePlayerBootstrap, setActivePlayerBootstrap] = useState<VideoPlayerBootstrap | null>(null);
  const [activeVideoTrack, setActiveVideoTrack] = useState<VideoTrackModel | null>(null);
  const [watchVideoError, setWatchVideoError] = useState<string | null>(null);
  const [trackDraft, setTrackDraft] = useState<VideoTrackDraft>({
    namespace: '',
    trackName: ''
  });
  const [subscribedTrackOrder, setSubscribedTrackOrder] = useState<string[]>([]);
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
  const trackSummaryEmpty = isZh ? '暂无轨道' : 'No track';

  useEffect(() => {
    if (selectedAgentId && !agents.some((agent) => agent.id === selectedAgentId)) {
      setSelectedAgentId('');
    }
  }, [agents, selectedAgentId]);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSelectedAgentId('');
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, []);

  const selectedAgent =
    agents.find((agent) => agent.id === selectedAgentId) ?? null;
  const activeRenderedTrack =
    videoTracks.find((track) => track.trackId === activeVideoTrack?.trackId) ?? activeVideoTrack;
  const subscribedTrackLookup = new Map(
    videoTracks
      .filter((track) => track.watchState === 'subscribed')
      .map((track) => [track.trackId, track])
  );
  const orderedSubscribedTracks = subscribedTrackOrder
    .map((trackId) => subscribedTrackLookup.get(trackId))
    .filter((track): track is VideoTrackModel => Boolean(track));
  const orderedSubscribedTrackIds = new Set(orderedSubscribedTracks.map((track) => track.trackId));
  const subscribedTracks = [
    ...orderedSubscribedTracks,
    ...videoTracks.filter(
      (track) => track.watchState === 'subscribed' && !orderedSubscribedTrackIds.has(track.trackId)
    )
  ];

  useEffect(() => {
    setSubscribedTrackOrder((current) => {
      const nextSubscribedTrackIds = new Set(
        videoTracks
          .filter((track) => track.watchState === 'subscribed')
          .map((track) => track.trackId)
      );
      const next = current.filter((trackId) => nextSubscribedTrackIds.has(trackId));
      for (const track of videoTracks) {
        if (track.watchState === 'subscribed' && !next.includes(track.trackId)) {
          next.push(track.trackId);
        }
      }

      if (next.length === current.length && next.every((trackId, index) => trackId === current[index])) {
        return current;
      }
      return next;
    });
  }, [videoTracks]);

  const handleSwitchTrack = async (track: VideoTrackModel) => {
    const trackId = track.trackId;
    setWatchingTrackId(trackId);
    setWatchVideoError(null);

    try {
      const payload = await onSubscribeTrack({
        namespace: track.namespace.replace(/^\/+/, ''),
        trackName: track.trackName
      });
      setActivePlayerConfig(payload.player);
      setActivePlayerBootstrap(payload.bootstrap ?? null);
      setActiveVideoTrack(payload.track ?? track);
    } catch (error) {
      setWatchVideoError(error instanceof Error ? error.message : videoCopy.error);
    } finally {
      setWatchingTrackId(null);
    }
  };

  const handleCreateTrack = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const namespace = trackDraft.namespace.trim();
    const trackName = trackDraft.trackName.trim();
    const namespaceParts = namespace.split('/').map((part) => part.trim()).filter(Boolean);
    if (namespaceParts.length === 0 || !trackName) {
      setWatchVideoError(videoCopy.requiredFields);
      return;
    }

    setCreatingTrack(true);
    setWatchVideoError(null);

    try {
      const payload = await onSubscribeTrack({ namespace, trackName });
      setActivePlayerConfig(payload.player);
      setActivePlayerBootstrap(payload.bootstrap ?? null);
      setActiveVideoTrack(payload.track ?? null);
      setTrackDraft({
        namespace,
        trackName
      });
    } catch (error) {
      setWatchVideoError(error instanceof Error ? error.message : videoCopy.actionFailed);
    } finally {
      setCreatingTrack(false);
    }
  };

  const handleRemoveTrack = async (track: VideoTrackModel) => {
    setDeletingTrackId(track.trackId);
    setWatchVideoError(null);

    try {
      await onDeleteTrack(track.trackId);
      if (activeVideoTrack?.trackId === track.trackId) {
        setActiveVideoTrack(null);
        setActivePlayerConfig(null);
        setActivePlayerBootstrap(null);
        setWatchVideoError(null);
      }
    } catch (error) {
      setWatchVideoError(error instanceof Error ? error.message : videoCopy.actionFailed);
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
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '优先级' : 'Priority'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.priority || '--'}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '区域' : 'Region'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.region}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '运行中任务' : 'Running Tasks'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.taskCount}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '上线时间' : 'Launch Time'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.launchTime}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '离线时间' : 'Offline Time'}</dt>
                  <dd className="theme-title mt-2 text-sm font-medium">{selectedAgent.offlineTime}</dd>
                </div>
                <div className="theme-subtle-card p-4">
                  <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '最后消息时间' : 'Last Message Time'}</dt>
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
                  <h4 className="theme-title text-sm font-semibold uppercase tracking-[0.18em]">{isZh ? '任务信息' : 'Tasks'}</h4>
                  <div className="mt-3 space-y-2">
                    {selectedAgent.tasks?.length ? (
                      selectedAgent.tasks.map((task) => (
                        <div key={`${task.taskId}-${task.status}`} className="theme-subtle-card px-4 py-3 text-sm">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="theme-title break-words font-medium">{task.taskId}</p>
                            <span className={task.status === 'processing' ? 'theme-badge-amber rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em]' : 'theme-badge-emerald rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em]'}>
                              {task.status}
                            </span>
                          </div>
                          <p className="theme-soft mt-2 leading-6">{task.description || task.taskName || '-'}</p>
                        </div>
                      ))
                    ) : (
                      <div className="theme-subtle-card theme-copy px-4 py-3 text-sm leading-6">
                        {isZh ? '暂无任务' : 'No tasks'}
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <h4 className="theme-title text-sm font-semibold uppercase tracking-[0.18em]">{isZh ? '发布轨道信息' : 'Published Track Info'}</h4>
                  <div className="mt-3 space-y-2">
                    {selectedAgent.tracks.length ? (
                      selectedAgent.tracks.map((track) => (
                        <div key={track.id} className="theme-subtle-card px-4 py-3 text-sm">
                          <p className="theme-title break-words font-medium">
                            {(track.namespace ? `${track.namespace.replace(/^\/+/, '')}/` : '') + track.name}
                            <span className="theme-soft ml-2 font-normal">
                              {track.taskId ? `(${isZh ? '任务' : 'Task'}: ${track.taskId})` : ''}
                            </span>
                          </p>
                        </div>
                      ))
                    ) : (
                      <div className="theme-subtle-card theme-copy px-4 py-3 text-sm leading-6">
                        {trackSummaryEmpty}
                      </div>
                    )}
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

  return (
    <div className="space-y-6">
      <SectionCard
        id="agents-section"
        eyebrow={isZh ? '智能体' : 'Agents'}
        description={
          isZh
            ? '点击任意智能体卡片即可打开专属详情窗口，查看其资料、健康状态、视频轨道以及上线/离线时间。'
            : 'Click an agent card to open a dedicated detail window with its profile, health, track inventory, and launch/offline timing.'
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
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${statusTone[agent.status]}`}>
                    {statusLabel[agent.status]}
                  </span>
                </div>
                <dl className="theme-copy mt-5 grid gap-3 text-sm sm:grid-cols-2">
                  <div className="theme-subtle-card p-4">
                    <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '能力标签' : 'Capabilities'}</dt>
                    <dd className="mt-3 flex flex-wrap gap-2">
                      {agent.capabilities.length ? (
                        agent.capabilities.map((capability) => (
                          <span key={`${agent.id}-${capability}`} className="theme-chip px-2.5 py-1 text-xs font-medium">
                            {capability}
                          </span>
                        ))
                      ) : (
                        <span className="theme-title font-medium">-</span>
                      )}
                    </dd>
                  </div>
                  <div className="theme-subtle-card p-4">
                    <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '运行中任务' : 'Running Tasks'}</dt>
                    <dd className="theme-title mt-2 font-medium">{agent.taskCount}</dd>
                  </div>
                  <div className="theme-subtle-card p-4 sm:col-span-2">
                    <dt className="theme-muted text-xs uppercase tracking-[0.18em]">{isZh ? '上线时间' : 'Launch Time'}</dt>
                    <dd className="theme-title mt-2 font-medium">{agent.launchTime}</dd>
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
        <form onSubmit={handleCreateTrack} className="theme-card-muted mb-4 p-5" noValidate>
          <div className="mb-4">
            <p className="panel-eyebrow">{videoCopy.manageTitle}</p>
            <p className="theme-copy mt-2 text-sm leading-6">{videoCopy.manageDescription}</p>
          </div>

          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(220px,0.55fr)]">
            <label className="block">
              <span className="theme-muted mb-2 block text-xs uppercase tracking-[0.18em]">
                {videoCopy.namespaceLabel}
              </span>
              <input
                value={trackDraft.namespace}
                onChange={(event) =>
                  setTrackDraft((current) => ({ ...current, namespace: event.target.value }))
                }
                className={inputClassName}
                placeholder={videoCopy.namespacePlaceholder}
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
          </div>

          <div className="mt-4 flex justify-end">
            <button
              type="submit"
              className={['theme-top-button px-4 py-2', creatingTrack ? 'cursor-wait opacity-70' : ''].join(' ')}
              disabled={creatingTrack}
            >
              {creatingTrack ? videoCopy.subscribing : videoCopy.subscribe}
            </button>
          </div>
        </form>

        <div className="theme-card-muted mb-4 p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="panel-eyebrow">{videoCopy.subscribedTracks}</p>
              <p className="theme-copy mt-2 text-sm leading-6">{videoCopy.subscribedDescription}</p>
            </div>
            {videoTracksLoading ? (
              <span className="theme-chip px-3 py-1 text-xs font-medium uppercase tracking-[0.16em]">
                {videoCopy.loading}
              </span>
            ) : null}
          </div>

          {videoTracksError ? (
            <div className="theme-subtle-card theme-copy px-4 py-3 text-sm">{videoTracksError}</div>
          ) : subscribedTracks.length === 0 ? (
            <div className="theme-subtle-card theme-copy px-4 py-3 text-sm">{videoCopy.emptySubscribed}</div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {subscribedTracks.map((track) => {
                const active = activeRenderedTrack?.trackId === track.trackId;
                return (
                  <div
                    key={track.trackId}
                    className={[
                      'inline-flex max-w-full items-center gap-1 rounded-full border px-1.5 py-1',
                      active
                        ? 'border-cyan-300/45 bg-cyan-300/10'
                        : 'border-[color:var(--border-soft)] bg-[color:var(--surface-strong)]'
                    ].join(' ')}
                  >
                    <button
                      type="button"
                      onClick={() => void handleSwitchTrack(track)}
                      className="theme-title max-w-[320px] truncate rounded-full px-3 py-1.5 text-sm font-medium"
                      disabled={watchingTrackId === track.trackId}
                    >
                      {track.namespace.replace(/^\/+/, '')}/{track.trackName}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleRemoveTrack(track)}
                      className="theme-soft rounded-full px-2 py-1 text-sm hover:text-[color:var(--text-main)]"
                      disabled={deletingTrackId === track.trackId}
                      aria-label={`${videoCopy.removeTrack} ${track.trackName}`}
                    >
                      x
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {watchVideoError ? (
          <div className="theme-card-muted theme-copy px-5 py-5 text-sm">{watchVideoError}</div>
        ) : activePlayerConfig && activeRenderedTrack ? (
          <MOQTrackPlayer
            key={activeRenderedTrack.trackId}
            language={language}
            bootstrap={activePlayerBootstrap}
            player={activePlayerConfig}
            track={activeRenderedTrack}
          />
        ) : (
          <div className="theme-card-muted theme-copy px-5 py-12 text-center text-sm">
            {videoCopy.previewPlaceholder}
          </div>
        )}
      </SectionCard>

      {detailDialog}
    </div>
  );
};
