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

const MOQVideoCard = ({ trackId, frameInfo }) => {
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
      
      // Clear canvas with MOQ themed background
      ctx.fillStyle = '#0a0a1a';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      
      // Draw MOQ network visualization
      ctx.strokeStyle = 'rgba(0, 212, 255, 0.3)';
      ctx.lineWidth = 1;
      
      // Animated grid
      const gridSize = 30;
      const offset = (frame * 0.5) % gridSize;
      for (let x = offset; x <= canvas.width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
      }
      for (let y = offset; y <= canvas.height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
      }
      
      // Draw "receiving" indicator
      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;
      const pulseRadius = 30 + Math.sin(frame * 0.1) * 10;
      
      // Outer pulse
      ctx.fillStyle = `rgba(0, 255, 136, ${0.3 + Math.sin(frame * 0.1) * 0.2})`;
      ctx.beginPath();
      ctx.arc(centerX, centerY, pulseRadius + 20, 0, Math.PI * 2);
      ctx.fill();
      
      // Inner circle
      ctx.fillStyle = '#00ff88';
      ctx.beginPath();
      ctx.arc(centerX, centerY, 15, 0, Math.PI * 2);
      ctx.fill();
      
      // Draw packet indicators
      if (frameInfo) {
        const packetCount = frameInfo.object_id % 10;
        for (let i = 0; i < packetCount; i++) {
          const angle = (frame * 0.02 + i * 0.6) % (Math.PI * 2);
          const radius = 60 + i * 8;
          const x = centerX + Math.cos(angle) * radius;
          const y = centerY + Math.sin(angle) * radius;
          
          ctx.fillStyle = `rgba(0, 212, 255, ${0.5 + Math.sin(frame * 0.1 + i) * 0.3})`;
          ctx.beginPath();
          ctx.arc(x, y, 3, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      
      animationId = requestAnimationFrame(draw);
    };
    
    draw();
    
    return () => {
      cancelAnimationFrame(animationId);
    };
  }, [frameInfo]);

  return (
    <div className="video-card moq-card">
      <div className="video-container">
        <canvas 
          ref={canvasRef}
          width={640}
          height={360}
          className="video-element"
        />
        <div className="video-overlay">
          <div className="video-stats">MOQ Protocol</div>
          <div className="video-stats">
            {frameInfo ? `Obj: ${frameInfo.object_id} | ${frameInfo.payload_size} bytes` : 'Waiting...'}
          </div>
        </div>
      </div>
      <div className="video-info">
        <span className="video-agent-name">{trackId}</span>
        <span className="video-status moq">● MOQ</span>
      </div>
    </div>
  );
};

const SidebarRight = ({ videoStreams = [], moqFrames = {} }) => {
  // Use real streams if available, otherwise show simulated feeds
  const hasRealStreams = videoStreams && videoStreams.length > 0;
  const hasMoqStreams = Object.keys(moqFrames).length > 0;

  // Default simulated videos (fallback)
  const simulatedVideos = [
    { agentName: 'Drone Alpha - Front Cam', type: 'camera' },
    { agentName: 'Drone Beta - Thermal Cam', type: 'thermal' }
  ];

  return (
    <aside className="sidebar-right">
      <div className="panel-header">
        <span className="panel-title">LIVE FEEDS</span>
        <span className="panel-count">
          {hasMoqStreams ? Object.keys(moqFrames).length : 
           hasRealStreams ? videoStreams.length : simulatedVideos.length}
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
          // Show simulated video feeds
          simulatedVideos.map((video, index) => (
            <SimulatedVideoCard
              key={index}
              index={index}
              agentName={video.agentName}
            />
          ))
        )}
      </div>

      {hasMoqStreams && (
        <div className="video-notice">
          <span className="notice-text">🔗 Receiving MOQ video streams from relay
          </span>
        </div>
      )}
      
      {!hasMoqStreams && !hasRealStreams && (
        <div className="video-notice">
          <span className="notice-text">ኁ61 Simulated feeds. Connect agents to see real video.</span>
        </div>
      )}
    </aside>
  );
};

export default SidebarRight;
