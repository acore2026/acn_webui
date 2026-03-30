import React, { useEffect, useRef, useState } from 'react';
import './SidebarRight.css';

const VideoCard = ({ index, agentName, fallbackColor }) => {
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
        <span className="video-status">● LIVE</span>
      </div>
    </div>
  );
};

const SidebarRight = () => {
  const videos = [
    { agentName: 'Drone Alpha - Front Cam' },
    { agentName: 'Drone Beta - Thermal Cam' }
  ];

  return (
    <aside className="sidebar-right">
      <div className="panel-header">
        <span className="panel-title">LIVE FEEDS</span>
        <span className="panel-count">{videos.length}</span>
      </div>
      
      <div className="video-grid">
        {videos.map((video, index) => (
          <VideoCard 
            key={index}
            index={index}
            agentName={video.agentName}
          />
        ))}
      </div>
    </aside>
  );
};

export default SidebarRight;
