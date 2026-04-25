import { useEffect, useMemo, useRef, useState } from 'react';
import { shellCopy, LanguageMode } from '../i18n';
import { VideoPlayerBootstrap, VideoPlayerConfig, VideoTrackModel } from '../types';

interface MOQTrackPlayerProps {
  bootstrap?: VideoPlayerBootstrap | null;
  language: LanguageMode;
  player: VideoPlayerConfig;
  track: VideoTrackModel;
}

interface StreamInfoPayload {
  status?: string;
  has_frame?: boolean;
  width?: number | null;
  height?: number | null;
  metadata?: Record<string, unknown> | null;
  fragment_count?: number;
  jpeg_sequence?: number;
}

export const MOQTrackPlayer = ({
  language,
  player,
  track
}: MOQTrackPlayerProps) => {
  const copy = shellCopy[language].agentsVideo;
  const [streamInfo, setStreamInfo] = useState<StreamInfoPayload | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [streamNonce, setStreamNonce] = useState(() => Date.now());
  const [snapshotNonce, setSnapshotNonce] = useState(() => Date.now());
  const [renderedFps, setRenderedFps] = useState<number>(0);
  const previousSequenceRef = useRef(0);
  const previousSequenceAtRef = useRef(0);
  const mjpegUrl = player.mjpegUrl ?? `/api/video/stream/${encodeURIComponent(track.trackId)}/mjpeg`;
  const latestFrameUrl = `/api/video/stream/${encodeURIComponent(track.trackId)}/latest?snapshot=${snapshotNonce}`;
  const liveStreamUrl = `${mjpegUrl}${mjpegUrl.includes('?') ? '&' : '?'}stream=${streamNonce}`;

  useEffect(() => {
    setLoaded(false);
    setStreamError(null);
    setStreamNonce(Date.now());
    setSnapshotNonce(Date.now());
    setRenderedFps(0);
    previousSequenceRef.current = 0;
    previousSequenceAtRef.current = 0;
  }, [track.trackId]);

  useEffect(() => {
    let mounted = true;

    const fetchInfo = async () => {
      try {
        const response = await fetch(`/api/video/stream/${encodeURIComponent(track.trackId)}/info`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = (await response.json()) as StreamInfoPayload;
        if (!mounted) {
          return;
        }
        setStreamInfo(payload);
        setStreamError(null);
      } catch (error) {
        if (!mounted) {
          return;
        }
        setStreamError(error instanceof Error ? error.message : copy.playerFailed);
      }
    };

    void fetchInfo();
    const interval = window.setInterval(() => {
      void fetchInfo();
    }, 1000);

    return () => {
      mounted = false;
      window.clearInterval(interval);
    };
  }, [copy.playerFailed, track.trackId]);

  useEffect(() => {
    if (streamInfo?.has_frame && !loaded) {
      setSnapshotNonce(Date.now());
      setStreamNonce(Date.now());
    }
  }, [loaded, streamInfo?.has_frame]);

  useEffect(() => {
    if (!streamInfo?.has_frame || !streamInfo?.jpeg_sequence) {
      setRenderedFps(0);
      return;
    }

    const currentSequence = streamInfo.jpeg_sequence;
    const currentAt = Date.now();
    const previousSequence = previousSequenceRef.current;
    const previousAt = previousSequenceAtRef.current;

    if (!previousAt || currentSequence <= previousSequence) {
      previousSequenceRef.current = currentSequence;
      previousSequenceAtRef.current = currentAt;
      return;
    }

    const elapsedSeconds = (currentAt - previousAt) / 1000;
    const nextValue = elapsedSeconds > 0 ? (currentSequence - previousSequence) / elapsedSeconds : 0;

    previousSequenceRef.current = currentSequence;
    previousSequenceAtRef.current = currentAt;

    setRenderedFps(Number.isFinite(nextValue) ? nextValue : 0);
  }, [streamInfo?.has_frame, streamInfo?.jpeg_sequence]);

  const stats = useMemo(() => {
    const metadata = streamInfo?.metadata ?? track.metadata ?? null;
    return {
      codec: String((metadata?.codec as string) || (metadata?.mse_codec as string) || 'MJPEG'),
      sourceFps:
        typeof metadata?.fps === 'number' && Number.isFinite(metadata.fps) ? metadata.fps : null,
      resolution:
        streamInfo?.width && streamInfo?.height
          ? `${streamInfo.width}x${streamInfo.height}`
          : metadata?.width && metadata?.height
            ? `${String(metadata.width)}x${String(metadata.height)}`
            : '-'
    };
  }, [streamInfo, track.metadata]);

  return (
    <div className="video-monitor-grid">
      <div className="video-monitor-stage">
        <div className="video-monitor-top">
          <div>
            <p className="panel-eyebrow">{copy.modalEyebrow}</p>
            <h4 className="theme-title mt-2 text-xl font-semibold">{track.trackName}</h4>
            <p className="theme-soft mt-2 text-sm leading-6">{copy.modalDescription}</p>
          </div>
          <span className="theme-chip px-3 py-1 text-xs font-medium uppercase tracking-[0.16em]">
            {track.agentId}
          </span>
        </div>

        <div className="video-monitor-screen">
          {!loaded && streamInfo?.has_frame ? (
            <img
              src={latestFrameUrl}
              alt={`${track.trackName} snapshot`}
              className="absolute inset-0 h-full w-full object-contain"
            />
          ) : null}
          <img
            key={liveStreamUrl}
            src={liveStreamUrl}
            alt={track.trackName}
            className={`h-full w-full object-contain transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
            onLoad={() => {
              setLoaded(true);
              setStreamError(null);
            }}
            onError={() => {
              setLoaded(false);
              setStreamError(copy.playerFailed);
            }}
          />
          <div className="video-monitor-overlay">
            <div>{loaded ? copy.subscribed : copy.connecting}</div>
            <div>{streamError ?? (loaded ? copy.ready : copy.waiting)}</div>
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-6">
          <div className="theme-subtle-card px-4 py-3">
            <p className="theme-muted text-xs uppercase tracking-[0.18em]">{copy.fragments}</p>
            <p className="theme-title mt-2 text-xl font-semibold">
              {streamInfo?.fragment_count ?? 0}
            </p>
          </div>
          <div className="theme-subtle-card px-4 py-3">
            <p className="theme-muted text-xs uppercase tracking-[0.18em]">{copy.bytes}</p>
            <p className="theme-title mt-2 text-xl font-semibold">
              {streamInfo?.has_frame ? 'JPEG' : '-'}
            </p>
          </div>
          <div className="theme-subtle-card px-4 py-3">
            <p className="theme-muted text-xs uppercase tracking-[0.18em]">{copy.sourceFps}</p>
            <p className="theme-title mt-2 text-xl font-semibold">
              {stats.sourceFps !== null ? `${stats.sourceFps.toFixed(1)} fps` : '-'}
            </p>
          </div>
          <div className="theme-subtle-card px-4 py-3">
            <p className="theme-muted text-xs uppercase tracking-[0.18em]">{copy.renderedFps}</p>
            <p className="theme-title mt-2 text-xl font-semibold">
              {renderedFps > 0 ? `${renderedFps.toFixed(1)} fps` : '-'}
            </p>
          </div>
          <div className="theme-subtle-card px-4 py-3">
            <p className="theme-muted text-xs uppercase tracking-[0.18em]">{copy.codec}</p>
            <p className="theme-title mt-2 text-sm font-semibold">{stats.codec}</p>
          </div>
          <div className="theme-subtle-card px-4 py-3">
            <p className="theme-muted text-xs uppercase tracking-[0.18em]">{copy.resolution}</p>
            <p className="theme-title mt-2 text-sm font-semibold">{stats.resolution}</p>
          </div>
        </div>
      </div>

      <aside className="theme-card-muted p-5">
        <p className="panel-eyebrow">{language === 'zh' ? '轨道详情' : 'Track Detail'}</p>
        <div className="mt-4 space-y-3 text-sm">
          <div className="theme-subtle-card px-4 py-3">
            <p className="theme-muted text-xs uppercase tracking-[0.18em]">{copy.namespace}</p>
            <p className="theme-title mt-2 break-all text-sm font-medium">{track.namespace}</p>
          </div>
          <div className="theme-subtle-card px-4 py-3">
            <p className="theme-muted text-xs uppercase tracking-[0.18em]">{copy.task}</p>
            <p className="theme-title mt-2 text-sm font-medium">{track.taskId}</p>
          </div>
          <div className="theme-subtle-card px-4 py-3">
            <p className="theme-muted text-xs uppercase tracking-[0.18em]">
              {language === 'zh' ? '播放方式' : 'Playback'}
            </p>
            <p className="theme-title mt-2 text-sm font-medium">MJPEG over HTTP</p>
          </div>
          {streamError ? (
            <div className="theme-subtle-card px-4 py-3">
              <p className="theme-muted text-xs uppercase tracking-[0.18em]">
                {language === 'zh' ? '错误' : 'Error'}
              </p>
              <p className="theme-copy mt-2 text-sm">{streamError}</p>
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
};
