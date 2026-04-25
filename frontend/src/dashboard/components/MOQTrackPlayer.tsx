import { ReactNode, useEffect, useRef, useState } from 'react';
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

interface PlayerMetadata {
  codec?: string;
  fps?: number;
  generated_at?: string;
  height?: number;
  mime_type?: string;
  mse_codec?: string;
  width?: number;
}

const FRAME_JSON = 1;
const FRAME_INIT = 2;
const FRAME_FRAGMENT = 3;
const FRAME_END = 4;
const LIVE_EDGE_DELAY_SECONDS = 1.2;
const MIN_BUFFER_AHEAD_SECONDS = 0.5;
const MAX_APPEND_QUEUE_SEGMENTS = 8;
const MEDIA_RECOVERY_INTERVAL_MS = 1500;

const hexToUint8Array = (hex: string) => {
  const pairs = hex.match(/.{1,2}/g) ?? [];
  return Uint8Array.from(pairs.map((pair) => parseInt(pair, 16)));
};

const inferAvc1CodecFromInitSegment = (bytes: Uint8Array) => {
  for (let index = 0; index <= bytes.length - 8; index += 1) {
    if (
      bytes[index] === 0x61 &&
      bytes[index + 1] === 0x76 &&
      bytes[index + 2] === 0x63 &&
      bytes[index + 3] === 0x43
    ) {
      const profile = bytes[index + 5].toString(16).padStart(2, '0').toUpperCase();
      const compatibility = bytes[index + 6].toString(16).padStart(2, '0').toUpperCase();
      const level = bytes[index + 7].toString(16).padStart(2, '0').toUpperCase();
      return `avc1.${profile}${compatibility}${level}`;
    }
  }
  return 'avc1.64001F';
};

const getCandidateHosts = (host: string) => {
  const candidates = [host, window.location.hostname];
  if (['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)) {
    candidates.push('127.0.0.1', 'localhost');
  }
  const seen: Record<string, true> = {};
  return candidates.filter((candidate): candidate is string => {
    if (!candidate || seen[candidate]) {
      return false;
    }
    seen[candidate] = true;
    return true;
  });
};

const MjpegTrackPlayer = ({
  language,
  player,
  track
}: Omit<MOQTrackPlayerProps, 'bootstrap'>) => {
  const copy = shellCopy[language].agentsVideo;
  const [streamInfo, setStreamInfo] = useState<StreamInfoPayload | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [streamNonce, setStreamNonce] = useState(() => Date.now());
  const [snapshotNonce, setSnapshotNonce] = useState(() => Date.now());
  const mjpegUrl = player.mjpegUrl ?? `/api/video/stream/${encodeURIComponent(track.trackId)}/mjpeg`;
  const latestFrameUrl = `/api/video/stream/${encodeURIComponent(track.trackId)}/latest?snapshot=${snapshotNonce}`;
  const liveStreamUrl = `${mjpegUrl}${mjpegUrl.includes('?') ? '&' : '?'}stream=${streamNonce}`;

  useEffect(() => {
    setLoaded(false);
    setStreamError(null);
    setStreamNonce(Date.now());
    setSnapshotNonce(Date.now());
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

  return (
    <TrackPlayerLayout
      track={track}
      error={streamError}
      statusLabel={loaded ? copy.subscribed : copy.connecting}
      statusDetail={streamError ?? (loaded ? copy.ready : copy.waiting)}
    >
      <div className="moq-video-surface">
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
      </div>
    </TrackPlayerLayout>
  );
};

const TrackPlayerLayout = ({
  children,
  error,
  statusDetail,
  statusLabel,
  track
}: {
  children: ReactNode;
  error?: string | null;
  statusDetail: string;
  statusLabel: string;
  track: VideoTrackModel;
}) => {
  const previewTrackLabel = `${track.namespace.replace(/^\/+/, '')}/${track.trackName}`;

  return (
    <section className="moq-videos-panel">
      <div className="moq-videos-header">
        <span className="panel-eyebrow">VIDEOS</span>
        <span className="moq-connection-text">{statusLabel}</span>
      </div>

      <div className="moq-video-grid">
        <div className="moq-video-card">
          <div className="moq-video-container">{children}</div>
          <div className="moq-video-info">
            <span className="moq-video-track">Preview Track: {previewTrackLabel}</span>
            <span className="moq-video-status">{error ?? statusDetail}</span>
          </div>
        </div>
      </div>
    </section>
  );
};

export const MOQTrackPlayer = ({
  bootstrap,
  language,
  player,
  track
}: MOQTrackPlayerProps) => {
  const copy = shellCopy[language].agentsVideo;
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const transportRef = useRef<any>(null);
  const mediaSourceRef = useRef<MediaSource | null>(null);
  const sourceBufferRef = useRef<SourceBuffer | null>(null);
  const videoUrlRef = useRef<string | null>(null);
  const appendQueueRef = useRef<Uint8Array[]>([]);
  const pendingSegmentsRef = useRef<Uint8Array[]>([]);
  const metadataRef = useRef<PlayerMetadata | null>(null);
  const initSegmentRef = useRef<Uint8Array | null>(null);
  const playbackGenerationRef = useRef(0);
  const lastMediaRecoveryAtRef = useRef(0);
  const [connectionLabel, setConnectionLabel] = useState<string>(copy.connecting);
  const [connectionDetail, setConnectionDetail] = useState<string>(copy.waiting);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const useMjpegFallback = !player.certHash || !player.path;

  useEffect(() => {
    if (useMjpegFallback) {
      return;
    }

    let cancelled = false;
    const generation = playbackGenerationRef.current + 1;
    playbackGenerationRef.current = generation;

    const updateConnection = (label: string, detail: string, error: string | null = null) => {
      if (cancelled || playbackGenerationRef.current !== generation) {
        return;
      }
      setConnectionLabel(label);
      setConnectionDetail(detail);
      setConnectionError(error);
    };

    const requestPlayback = () => {
      const video = videoRef.current;
      if (!video || (!video.currentSrc && !videoUrlRef.current)) {
        return;
      }
      const promise = video.play();
      if (promise && typeof promise.catch === 'function') {
        promise.catch((error: Error) => {
          updateConnection(copy.error, error.message, error.message);
        });
      }
    };

    const releaseVideoSource = () => {
      const video = videoRef.current;
      if (videoUrlRef.current) {
        URL.revokeObjectURL(videoUrlRef.current);
        videoUrlRef.current = null;
      }
      if (video) {
        video.removeAttribute('src');
        video.load();
      }
    };

    const flushSourceBuffer = () => {
      const sourceBuffer = sourceBufferRef.current;
      const mediaSource = mediaSourceRef.current;
      if (!sourceBuffer || sourceBuffer.updating || appendQueueRef.current.length === 0) {
        return;
      }
      if (!mediaSource || mediaSource.readyState !== 'open') {
        return;
      }

      const next = appendQueueRef.current.shift();
      if (!next) {
        return;
      }

      try {
        sourceBuffer.appendBuffer(next);
      } catch (error) {
        const message = error instanceof Error ? error.message : copy.playerFailed;
        updateConnection(copy.error, message, message);
      }
    };

    const syncPlaybackPosition = () => {
      const video = videoRef.current;
      if (!video?.buffered || video.buffered.length === 0) {
        return;
      }
      const lastRange = video.buffered.length - 1;
      const rangeStart = video.buffered.start(lastRange);
      const rangeEnd = video.buffered.end(lastRange);
      const currentTime = video.currentTime || 0;
      const bufferAhead = rangeEnd - currentTime;

      if (Number.isFinite(bufferAhead)) {
        if (bufferAhead > LIVE_EDGE_DELAY_SECONDS + 0.6) {
          video.playbackRate = 1.04;
        } else if (bufferAhead > LIVE_EDGE_DELAY_SECONDS + 0.3) {
          video.playbackRate = 1.02;
        } else {
          video.playbackRate = 1.0;
        }
      }

      if (bufferAhead >= MIN_BUFFER_AHEAD_SECONDS && currentTime >= rangeStart && currentTime <= rangeEnd) {
        return;
      }
      const liveEdge = Math.max(rangeStart, rangeEnd - LIVE_EDGE_DELAY_SECONDS);
      if (liveEdge > currentTime + 0.15) {
        video.currentTime = liveEdge;
      }
    };

    const ensurePlayer = (nextMetadata: PlayerMetadata) => {
      if (mediaSourceRef.current) {
        return;
      }
      if (!('MediaSource' in window)) {
        throw new Error(copy.browserUnsupported);
      }

      const mimeType = nextMetadata.mime_type || `video/mp4; codecs="${nextMetadata.mse_codec || 'avc1.42E01F'}"`;
      if (!MediaSource.isTypeSupported(mimeType)) {
        throw new Error(`${copy.browserUnsupported} ${mimeType}`);
      }

      const mediaSource = new MediaSource();
      mediaSource.addEventListener(
        'sourceopen',
        () => {
          if (cancelled || playbackGenerationRef.current !== generation) {
            return;
          }
          try {
            const sourceBuffer = mediaSource.addSourceBuffer(mimeType);
            sourceBuffer.mode = 'segments';
            sourceBuffer.addEventListener('error', () => {
              updateConnection(copy.error, 'SourceBuffer error', 'SourceBuffer error');
            });
            sourceBuffer.addEventListener('updateend', () => {
              flushSourceBuffer();
              syncPlaybackPosition();
              requestPlayback();
            });
            sourceBufferRef.current = sourceBuffer;
            updateConnection(copy.ready, mimeType);
            flushSourceBuffer();
          } catch (error) {
            const message = error instanceof Error ? error.message : copy.playerFailed;
            updateConnection(copy.error, message, message);
          }
        },
        { once: true }
      );

      mediaSourceRef.current = mediaSource;
      videoUrlRef.current = URL.createObjectURL(mediaSource);
      if (videoRef.current) {
        videoRef.current.src = videoUrlRef.current;
      }
    };

    const recoverMediaPipeline = (reason: string) => {
      const now = Date.now();
      if (!metadataRef.current || !initSegmentRef.current || now - lastMediaRecoveryAtRef.current < MEDIA_RECOVERY_INTERVAL_MS) {
        return;
      }
      lastMediaRecoveryAtRef.current = now;
      appendQueueRef.current = [];
      pendingSegmentsRef.current = [];
      sourceBufferRef.current = null;
      mediaSourceRef.current = null;
      releaseVideoSource();
      updateConnection(copy.connecting, reason);
      enqueueSegment(initSegmentRef.current);
    };

    const enqueueSegment = (segment: Uint8Array) => {
      if (!metadataRef.current) {
        pendingSegmentsRef.current.push(segment);
        return;
      }

      try {
        ensurePlayer(metadataRef.current);
      } catch (error) {
        const message = error instanceof Error ? error.message : copy.playerFailed;
        updateConnection(copy.error, message, message);
        return;
      }

      if (initSegmentRef.current && segment !== initSegmentRef.current && appendQueueRef.current.length >= MAX_APPEND_QUEUE_SEGMENTS) {
        appendQueueRef.current.splice(0, appendQueueRef.current.length - (MAX_APPEND_QUEUE_SEGMENTS - 1));
      }
      appendQueueRef.current.push(segment);
      flushSourceBuffer();
    };

    const applyMetadata = (nextMetadata: PlayerMetadata) => {
      const merged = metadataRef.current ? { ...metadataRef.current, ...nextMetadata } : nextMetadata;
      metadataRef.current = merged;
      for (const pending of pendingSegmentsRef.current.splice(0)) {
        enqueueSegment(pending);
      }
    };

    const handleControlMessage = (message: { type?: string; metadata?: PlayerMetadata }) => {
      if (message.type === 'metadata' && message.metadata) {
        applyMetadata(message.metadata);
        updateConnection(copy.connecting, copy.waiting);
      }
      if (message.type === 'end') {
        updateConnection(copy.ready, language === 'zh' ? '发布端已结束当前流。' : 'Publisher ended the current stream.');
      }
    };

    const handleFrame = (frameType: number, payload: Uint8Array) => {
      if (cancelled || playbackGenerationRef.current !== generation) {
        return;
      }
      if (frameType === FRAME_JSON) {
        handleControlMessage(JSON.parse(new TextDecoder().decode(payload)));
        return;
      }
      if (frameType === FRAME_INIT) {
        initSegmentRef.current = payload;
        if (!metadataRef.current) {
          const mseCodec = inferAvc1CodecFromInitSegment(payload);
          applyMetadata({
            codec: 'H.264',
            mse_codec: mseCodec,
            mime_type: `video/mp4; codecs="${mseCodec}"`
          });
        }
        enqueueSegment(payload);
        updateConnection(copy.connecting, language === 'zh' ? '已收到初始化片段。' : 'Initialization segment received.');
        return;
      }
      if (frameType === FRAME_FRAGMENT) {
        enqueueSegment(payload);
        updateConnection(copy.subscribed, language === 'zh' ? '正在接收实时片段。' : 'Receiving live fragments.');
        return;
      }
      if (frameType === FRAME_END) {
        handleControlMessage({ type: 'end' });
      }
    };

    const consumeReadableStream = async (readableStream: ReadableStream<Uint8Array>) => {
      const reader = readableStream.getReader();
      let buffer = new Uint8Array(0);
      try {
        while (!cancelled && playbackGenerationRef.current === generation) {
          const { value, done } = await reader.read();
          if (done) {
            return;
          }
          if (!value) {
            continue;
          }

          const merged = new Uint8Array(buffer.length + value.length);
          merged.set(buffer, 0);
          merged.set(value, buffer.length);
          buffer = merged;

          while (buffer.length >= 5) {
            const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
            const frameType = view.getUint8(0);
            const frameLength = view.getUint32(1);
            if (buffer.length < frameLength + 5) {
              break;
            }
            const payload = buffer.slice(5, 5 + frameLength);
            buffer = buffer.slice(5 + frameLength);
            handleFrame(frameType, payload);
          }
        }
      } finally {
        reader.releaseLock();
      }
    };

    const consumeIncomingStreams = async (transport: any) => {
      const reader = transport.incomingUnidirectionalStreams.getReader();
      try {
        while (!cancelled && playbackGenerationRef.current === generation) {
          const { value, done } = await reader.read();
          if (done) {
            return;
          }
          if (value) {
            void consumeReadableStream(value).catch((error: Error) => {
              updateConnection(copy.error, error.message, error.message);
              recoverMediaPipeline(error.message);
            });
          }
        }
      } finally {
        reader.releaseLock();
      }
    };

    const closeActiveTransport = () => {
      const transport = transportRef.current;
      transportRef.current = null;
      if (transport) {
        try {
          transport.close();
        } catch {
          return;
        }
      }
    };

    const attachTransportClosedHandlers = (transport: any) => {
      transport.closed
        .then(() => {
          if (!cancelled && transportRef.current === transport) {
            transportRef.current = null;
            updateConnection(copy.ready, language === 'zh' ? 'WebTransport 会话已关闭。' : 'WebTransport session closed.');
          }
        })
        .catch((error: Error) => {
          if (!cancelled && transportRef.current === transport) {
            transportRef.current = null;
            updateConnection(copy.error, error.message, error.message);
          }
        });
    };

    const connectTransport = async () => {
      if (!window.isSecureContext) {
        throw new Error(
          language === 'zh'
            ? 'WebTransport 需要 HTTPS 页面或 localhost。'
            : 'WebTransport requires HTTPS or localhost.'
        );
      }
      const WebTransportCtor = (window as any).WebTransport;
      if (!WebTransportCtor) {
        throw new Error(copy.browserUnsupported);
      }

      const certificateHashes = [
        {
          algorithm: 'sha-256',
          value: hexToUint8Array(player.certHash)
        }
      ];
      const failures: string[] = [];

      for (const host of getCandidateHosts(player.host)) {
        if (cancelled || playbackGenerationRef.current !== generation) {
          return;
        }
        const url = `https://${host}:${player.port}${player.path}`;
        const transport = new WebTransportCtor(url, { serverCertificateHashes: certificateHashes });
        transportRef.current = transport;
        updateConnection(copy.connecting, url);

        try {
          await transport.ready;
        } catch (error) {
          const message = error instanceof Error ? error.message : copy.playerFailed;
          failures.push(`${url}: ${message}`);
          if (transportRef.current === transport) {
            transportRef.current = null;
          }
          try {
            transport.close();
          } catch {}
          continue;
        }

        if (cancelled || playbackGenerationRef.current !== generation || transportRef.current !== transport) {
          return;
        }

        attachTransportClosedHandlers(transport);
        updateConnection(copy.ready, language === 'zh' ? 'WebTransport 已连接，等待媒体片段。' : 'WebTransport connected. Waiting for media fragments.');
        void consumeIncomingStreams(transport).catch((error: Error) => {
          updateConnection(copy.error, error.message, error.message);
          recoverMediaPipeline(error.message);
        });
        return;
      }

      throw new Error(failures.join(' | ') || copy.playerFailed);
    };

    appendQueueRef.current = [];
    pendingSegmentsRef.current = [];
    metadataRef.current = bootstrap?.metadata ?? track.metadata ?? null;
    initSegmentRef.current = null;
    sourceBufferRef.current = null;
    mediaSourceRef.current = null;
    lastMediaRecoveryAtRef.current = 0;
    updateConnection(copy.connecting, copy.waiting);
    releaseVideoSource();
    closeActiveTransport();

    void connectTransport().catch((error: Error) => {
      updateConnection(copy.error, error.message, error.message);
    });

    const video = videoRef.current;
    const handleVideoWaiting = () => updateConnection(copy.connecting, copy.waiting);
    const handleVideoPlaying = () => updateConnection(copy.subscribed, copy.ready);
    const handleVideoError = () => {
      const detail = video?.error?.message || copy.playerFailed;
      updateConnection(copy.error, detail, detail);
      recoverMediaPipeline(detail);
    };

    video?.addEventListener('waiting', handleVideoWaiting);
    video?.addEventListener('playing', handleVideoPlaying);
    video?.addEventListener('error', handleVideoError);

    return () => {
      cancelled = true;
      closeActiveTransport();
      releaseVideoSource();
      appendQueueRef.current = [];
      pendingSegmentsRef.current = [];
      sourceBufferRef.current = null;
      mediaSourceRef.current = null;
      video?.removeEventListener('waiting', handleVideoWaiting);
      video?.removeEventListener('playing', handleVideoPlaying);
      video?.removeEventListener('error', handleVideoError);
    };
  }, [
    bootstrap?.metadata,
    copy.browserUnsupported,
    copy.connecting,
    copy.error,
    copy.playerFailed,
    copy.ready,
    copy.subscribed,
    copy.waiting,
    language,
    player.certHash,
    player.host,
    player.path,
    player.port,
    track.metadata,
    track.trackId,
    useMjpegFallback
  ]);

  if (useMjpegFallback) {
    return <MjpegTrackPlayer language={language} player={player} track={track} />;
  }

  return (
    <TrackPlayerLayout
      track={track}
      error={connectionError}
      statusLabel={connectionLabel}
      statusDetail={connectionDetail}
    >
      <div className="moq-video-surface">
        <video
          ref={videoRef}
          className="h-full w-full object-contain"
          autoPlay
          muted
          playsInline
          controls
        />
      </div>
    </TrackPlayerLayout>
  );
};
