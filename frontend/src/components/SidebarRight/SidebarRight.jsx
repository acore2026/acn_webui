import React, { useEffect, useRef, useState } from 'react';
import './SidebarRight.css';

// Canvas-based simulated video feed (fallback when no real stream)
const SimulatedVideoCard = ({ index, agentName }) => {
  const canvasRef = useRef(null);
  const [fps, setFps] = useState(30);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    let frame = 0;
    let animationId;

    const draw = () => {
      frame++;
      
      // Clear canvas
      ctx.fillStyle = index === 0 ? '#1a1a2e' : '#16213e';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      
      // Draw grid
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.2)';
      ctx.lineWidth = 1;
      const gridSize = 40;
      for (let x = 0; x <= canvas.width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let y = 0; y <= canvas.height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }
      
      // Draw animated elements
      if (index === 0) {
        // Drone 1 - Radar-like animation
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const radius = 80 + Math.sin(frame * 0.02) * 20;
        
        ctx.save();
        ctx.translate(centerX, centerY);
        ctx.rotate(frame * 0.02);
        ctx.fillStyle = 'rgba(0, 255, 136, 0.3)';
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.arc(0, 0, radius, -0.3, 0.3);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
        
        // Target dots
        ctx.fillStyle = '#00ff88';
        for (let i = 0; i < 3; i++) {
          const tx = 150 + i * 120 + Math.sin(frame * 0.01 + i) * 30;
          const ty = 100 + i * 60 + Math.cos(frame * 0.015 + i) * 20;
          ctx.beginPath();
          ctx.arc(tx, ty, 4, 0, Math.PI * 2);
          ctx.fill();
        }
      } else {
        // Drone 2 - Thermal-like animation
        for (let i = 0; i < 5; i++) {
          const x = 100 + i * 100 + Math.sin(frame * 0.008 + i) * 40;
          const y = 100 + Math.cos(frame * 0.012 + i) * 30;
          const heat = Math.sin(frame * 0.02 + i * 2) * 0.5 + 0.5;
          
          const gradient = ctx.createRadialGradient(x, y, 0, x, y, 60);
          gradient.addColorStop(0, `rgba(255, ${Math.floor(100 + heat * 100)}, 0, ${heat * 0.6})`);
          gradient.addColorStop(1, 'rgba(255, 100, 0, 0)');
          
          ctx.fillStyle = gradient;
          ctx.beginPath();
          ctx.arc(x, y, 60, 0, Math.PI * 2);
          ctx.fill();
        }
        
        // Scan line
        const scanY = (frame * 2) % canvas.height;
        ctx.fillStyle = 'rgba(255, 51, 102, 0.3)';
        ctx.fillRect(0, scanY, canvas.width, 2);
      }
      
      animationId = requestAnimationFrame(draw);
    };
    
    draw();
    
    // Update FPS periodically
    const fpsInterval = setInterval(() => {
      setFps(Math.floor(Math.random() * 5) + 28);
    }, 2000);
    
    return () => {
      cancelAnimationFrame(animationId);
      clearInterval(fpsInterval);
    };
  }, [index]);

  return (
    <div className="video-card">
      <div className="video-container">
        <canvas 
          ref={canvasRef}
          width={640}
          height={360}
          className="video-element"
        />
        <div className="video-overlay">
          <div className="video-stats">FPS: {fps} | 1080P</div>
          <div className="video-stats">Bitrate: 4.5Mbps</div>
        </div>
      </div>
      <div className="video-info">
        <span className="video-agent-name">{agentName}</span>
        <span className="video-status simulated">● SIMULATED</span>
      </div>
    </div>
  );
};

// Real WebRTC video stream card
const RealVideoCard = ({ stream, websocket }) => {
  const videoRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [stats, setStats] = useState({ fps: 0, bitrate: 0 });
  const peerConnectionRef = useRef(null);

  // WebRTC configuration
  const pcConfig = {
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' }
    ]
  };

  useEffect(() => {
    if (!stream || !stream.stream_id) return;

    const connectStream = async () => {
      try {
        setIsConnecting(true);

        // Create peer connection
        const pc = new RTCPeerConnection(pcConfig);
        peerConnectionRef.current = pc;

        // Handle incoming stream
        pc.ontrack = (event) => {
          if (videoRef.current && event.streams[0]) {
            videoRef.current.srcObject = event.streams[0];
            setIsConnected(true);
            setIsConnecting(false);
          }
        };

        pc.onconnectionstatechange = () => {
          console.log(`[WebRTC] ${stream.stream_id} state: ${pc.connectionState}`);
          if (pc.connectionState === 'connected') {
            setIsConnected(true);
            setIsConnecting(false);
          } else if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
            setIsConnected(false);
            setIsConnecting(false);
          }
        };

        // Request stream from server (in real impl, this would be more complex)
        // For now, we'll show connecting state
        console.log(`[VideoStream] Connecting to ${stream.stream_id}`);

      } catch (err) {
        console.error('[WebRTC] Error:', err);
        setIsConnecting(false);
      }
    };

    connectStream();

    return () => {
      if (peerConnectionRef.current) {
        peerConnectionRef.current.close();
      }
    };
  }, [stream]);

  const statusText = isConnected ? '● LIVE' : (isConnecting ? '⟳ CONNECTING' : '○ OFFLINE');
  const statusClass = isConnected ? 'live' : (isConnecting ? 'connecting' : 'offline');

  return (
    <div className="video-card">
      <div className="video-container">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="video-element real-video"
        />
        {!isConnected && (
          <div className="video-placeholder">
            <div className="placeholder-content">
              <span className="placeholder-icon">📹</span>
              <span className="placeholder-text">
                {isConnecting ? 'Connecting...' : 'Waiting for stream'}
              </span>
            </div>
          </div>
        )}
        <div className="video-overlay">
          <div className="video-stats">FPS: {stats.fps || stream.fps} | {stream.resolution}</div>
          <div className="video-stats">Bitrate: {stats.bitrate || stream.bitrate}kbps</div>
        </div>
      </div>
      <div className="video-info">
        <span className="video-agent-name">{stream.agent_name} - {stream.stream_type}</span>
        <span className={`video-status ${statusClass}`}>{statusText}</span>
      </div>
    </div>
  );
};

const base64ToBytes = (base64) => {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
};

const findAnnexBStartCode = (bytes, fromIndex = 0) => {
  for (let i = fromIndex; i < bytes.length - 3; i += 1) {
    if (bytes[i] === 0 && bytes[i + 1] === 0 && bytes[i + 2] === 1) {
      return { index: i, length: 3 };
    }
    if (
      i < bytes.length - 4 &&
      bytes[i] === 0 &&
      bytes[i + 1] === 0 &&
      bytes[i + 2] === 0 &&
      bytes[i + 3] === 1
    ) {
      return { index: i, length: 4 };
    }
  }
  return null;
};

const splitAnnexBH264 = (bytes) => {
  const nalUnits = [];
  let cursor = 0;

  while (cursor < bytes.length) {
    const start = findAnnexBStartCode(bytes, cursor);
    if (!start) break;

    const naluStart = start.index + start.length;
    const next = findAnnexBStartCode(bytes, naluStart);
    const naluEnd = next ? next.index : bytes.length;

    if (naluStart < naluEnd) {
      nalUnits.push(bytes.slice(naluStart, naluEnd));
    }

    cursor = naluEnd;
  }

  return nalUnits;
};

const parseLengthPrefixedH264 = (bytes) => {
  const nalUnits = [];
  let cursor = 0;

  while (cursor + 4 <= bytes.length) {
    const naluLength =
      (bytes[cursor] << 24) |
      (bytes[cursor + 1] << 16) |
      (bytes[cursor + 2] << 8) |
      bytes[cursor + 3];
    const unsignedLength = naluLength >>> 0;
    cursor += 4;

    if (unsignedLength <= 0 || cursor + unsignedLength > bytes.length) {
      return null;
    }

    nalUnits.push(bytes.slice(cursor, cursor + unsignedLength));
    cursor += unsignedLength;
  }

  if (!nalUnits.length) {
    return null;
  }

  return nalUnits;
};

const parseH264Payload = (bytes) => {
  const annexBNalUnits = splitAnnexBH264(bytes);
  if (annexBNalUnits.length) {
    return {
      nalUnits: annexBNalUnits,
      annexBBytes: bytes
    };
  }

  const lengthPrefixedNalUnits = parseLengthPrefixedH264(bytes);
  if (lengthPrefixedNalUnits?.length) {
    const annexBParts = [];
    lengthPrefixedNalUnits.forEach((nal) => {
      annexBParts.push(new Uint8Array([0, 0, 0, 1]));
      annexBParts.push(nal);
    });

    const annexBBytes = new Uint8Array(
      annexBParts.reduce((sum, part) => sum + part.length, 0)
    );
    let offset = 0;
    annexBParts.forEach((part) => {
      annexBBytes.set(part, offset);
      offset += part.length;
    });

    return {
      nalUnits: lengthPrefixedNalUnits,
      annexBBytes
    };
  }

  return null;
};

const buildAvcConfig = (sps, pps) => {
  if (!sps || !pps || sps.length < 4 || pps.length < 1) {
    return null;
  }

  const profileIdc = sps[1];
  const profileCompat = sps[2];
  const levelIdc = sps[3];
  const codec = `avc1.${profileIdc.toString(16).padStart(2, '0')}${profileCompat
    .toString(16)
    .padStart(2, '0')}${levelIdc.toString(16).padStart(2, '0')}`;

  const description = new Uint8Array(6 + 2 + sps.length + 1 + 2 + pps.length);
  let offset = 0;
  description[offset++] = 1;
  description[offset++] = profileIdc;
  description[offset++] = profileCompat;
  description[offset++] = levelIdc;
  description[offset++] = 0xff;
  description[offset++] = 0xe1;
  description[offset++] = (sps.length >> 8) & 0xff;
  description[offset++] = sps.length & 0xff;
  description.set(sps, offset);
  offset += sps.length;
  description[offset++] = 1;
  description[offset++] = (pps.length >> 8) & 0xff;
  description[offset++] = pps.length & 0xff;
  description.set(pps, offset);

  return { codec, description };
};

const H264VideoCard = ({ trackId, frameInfo }) => {
  const canvasRef = useRef(null);
  const decoderRef = useRef(null);
  const codecRef = useRef(null);
  const spsRef = useRef(null);
  const ppsRef = useRef(null);
  const [status, setStatus] = useState('connecting');
  const [error, setError] = useState(null);
  const [supported, setSupported] = useState(true);

  const drawFrame = (videoFrame) => {
    const canvas = canvasRef.current;
    if (!canvas) {
      videoFrame.close();
      return;
    }

    const width = videoFrame.displayWidth || videoFrame.codedWidth || 640;
    const height = videoFrame.displayHeight || videoFrame.codedHeight || 360;
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;

    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(videoFrame, 0, 0, canvas.width, canvas.height);
    }
    videoFrame.close();
  };

  const ensureDecoder = (bytes, parsedNalUnits) => {
    if (!supported || typeof window.VideoDecoder !== 'function' || typeof window.EncodedVideoChunk !== 'function') {
      setSupported(false);
      setStatus('unsupported');
      return null;
    }

    const nalUnits = parsedNalUnits || splitAnnexBH264(bytes);
    const sps = nalUnits.find(nal => (nal[0] & 0x1f) === 7) || spsRef.current;
    const pps = nalUnits.find(nal => (nal[0] & 0x1f) === 8) || ppsRef.current;
    if (sps) spsRef.current = sps;
    if (pps) ppsRef.current = pps;

    const config = buildAvcConfig(spsRef.current, ppsRef.current);
    if (!config) {
      setStatus('waiting SPS/PPS');
      return null;
    }

    if (!decoderRef.current || codecRef.current !== config.codec) {
      if (decoderRef.current) {
        try {
          decoderRef.current.close();
        } catch (_) {}
      }

      const decoder = new window.VideoDecoder({
        output: drawFrame,
        error: (err) => {
          console.error('[MOQ H264] Decoder error:', err);
          setError(err?.message || String(err));
          setStatus('decoder error');
        }
      });

      try {
        decoder.configure({
          codec: config.codec,
          description: config.description
        });
      } catch (err) {
        console.error('[MOQ H264] Failed to configure decoder:', err);
        setError(err?.message || String(err));
        setStatus('configure failed');
        try {
          decoder.close();
        } catch (_) {}
        return null;
      }

      decoderRef.current = decoder;
      codecRef.current = config.codec;
      setStatus('configured');
    }

    return decoderRef.current;
  };

  useEffect(() => {
    return () => {
      if (decoderRef.current) {
        try {
          decoderRef.current.close();
        } catch (_) {}
        decoderRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const payload = frameInfo?.payload_base64;
    if (!payload) return;

    try {
      const bytes = base64ToBytes(payload);
      const parsed = parseH264Payload(bytes);
      if (!parsed) {
        setStatus('waiting for H264');
        return;
      }
      const { nalUnits, annexBBytes } = parsed;
      const hasIdr = nalUnits.some(nal => (nal[0] & 0x1f) === 5);
      const decoder = ensureDecoder(bytes, nalUnits);
      if (!decoder) return;

      const chunkType = frameInfo?.frame_type === 'keyframe' || hasIdr ? 'key' : 'delta';
      const timestamp = frameInfo?.timestamp ? Date.parse(frameInfo.timestamp) * 1000 : Date.now() * 1000;
      const chunk = new window.EncodedVideoChunk({
        type: chunkType,
        timestamp,
        data: annexBBytes
      });

      decoder.decode(chunk);
      setStatus(chunkType === 'key' ? 'keyframe' : 'live');
      setError(null);
    } catch (err) {
      console.error('[MOQ H264] Failed to decode frame:', err);
      setError(err?.message || String(err));
      setStatus('decode failed');
    }
  }, [frameInfo?.payload_base64, frameInfo?.frame_type, frameInfo?.timestamp]);

  const displayName = frameInfo?.track_name || trackId.split('_').pop() || 'Video';
  const agentId = trackId.split('_')[0] || 'Unknown';

  return (
    <div className="video-card moq-card">
      <div className="video-container">
        <canvas
          ref={canvasRef}
          width={640}
          height={360}
          className="video-element moq-image"
        />
        <div className="video-overlay">
          <div className="video-stats">MOQ H264</div>
          <div className="video-stats">
            {frameInfo?.namespace ? `NS: ${frameInfo.namespace.split('/').pop()}` : 'Waiting for data...'}
          </div>
          <div className="video-stats">WebCodecs</div>
          {error && <div className="video-stats">{error}</div>}
        </div>
      </div>
      <div className="video-info">
        <span className="video-agent-name">{agentId} - {displayName}</span>
        <span className={`video-status ${status === 'live' || status === 'keyframe' ? 'moq' : 'connecting'}`}>
          {supported ? (status === 'live' || status === 'keyframe' ? '● LIVE H264' : '⟳ Decoding') : '○ WebCodecs unavailable'}
        </span>
      </div>
    </div>
  );
};

const MOQVideoCard = ({ trackId, frameInfo }) => {
  const canvasRef = useRef(null);
  const [fps, setFps] = useState(30);
  const isRenderable = Boolean(frameInfo?.is_renderable && frameInfo?.data_url);
  const codec = frameInfo?.codec || (frameInfo?.mime_type === 'video/h264' ? 'h264' : null);
  const isH264 = codec === 'h264';

  // Extract display info from trackId and frameInfo
  const displayName = frameInfo?.track_name || trackId.split('_').pop() || 'Video';
  const agentId = trackId.split('_')[0] || 'Unknown';
  const status = frameInfo?.status || 'connecting';

  if (isH264) {
    return <H264VideoCard trackId={trackId} frameInfo={frameInfo} />;
  }

  return (
    <div className="video-card moq-card">
      <div className="video-container">
        {isRenderable ? (
          <img
            src={frameInfo.data_url}
            alt={`${agentId} ${displayName}`}
            className="video-element moq-image"
            draggable="false"
          />
        ) : (
          <canvas 
            ref={canvasRef}
            width={640}
            height={360}
            className="video-element"
          />
        )}
        <div className="video-overlay">
          <div className="video-stats">MOQ Protocol</div>
          <div className="video-stats">
            {frameInfo?.namespace ? `NS: ${frameInfo.namespace.split('/').pop()}` : 'Waiting for data...'}
          </div>
          <div className="video-stats">
            {frameInfo?.mime_type ? frameInfo.mime_type : (codec ? `codec:${codec}` : 'unknown')}
          </div>
        </div>
      </div>
      <div className="video-info">
        <span className="video-agent-name">{agentId} - {displayName}</span>
        <span className={`video-status ${status === 'subscribed' ? 'moq' : 'connecting'}`}>
          {isRenderable ? '● LIVE MOQ' : status === 'subscribed' ? '● MOQ' : '⟳ Connecting'}
        </span>
      </div>
    </div>
  );
};

const SidebarRight = ({ videoStreams = [], moqFrames = {} }) => {
  // Use real streams if available
  const hasRealStreams = videoStreams && videoStreams.length > 0;
  const hasMoqStreams = Object.keys(moqFrames).length > 0;

  return (
    <aside className="sidebar-right">
      <div className="panel-header">
        <span className="panel-title">LIVE FEEDS</span>
        <span className="panel-count">
          {hasMoqStreams ? Object.keys(moqFrames).length : 
           hasRealStreams ? videoStreams.length : 0}
        </span>
      </div>

      <div className="video-grid">
        {hasMoqStreams ? (
          // Show MOQ video streams
          Object.entries(moqFrames).map(([trackId, frameInfo]) => (
            <MOQVideoCard
              key={trackId}
              trackId={trackId}
              frameInfo={frameInfo}
            />
          ))
        ) : hasRealStreams ? (
          // Show WebRTC video streams
          videoStreams.map((stream, index) => (
            <RealVideoCard
              key={stream.stream_id || index}
              stream={stream}
            />
          ))
        ) : (
          // Empty state
          <div className="video-empty-state">
            <span className="empty-icon">📹</span>
            <span className="empty-text">No video streams available</span>
            <span className="empty-subtext">Waiting for agent connections...</span>
          </div>
        )}
      </div>

      {hasMoqStreams && (
        <div className="video-notice">
          <span className="notice-text">🔗 Receiving MOQ video streams from relay
          </span>
        </div>
      )}
    </aside>
  );
};

export default SidebarRight;
