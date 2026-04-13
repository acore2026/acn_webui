import React, { useState, useEffect } from 'react';
import './TopBar.css';

const TopBar = ({ onToggleDebug, debugEnabled }) => {
  const [currentTime, setCurrentTime] = useState('00:00:00');
  
  // Mock metrics data
  const metrics = {
    latency: '12ms',
    bandwidth: '847 Mbps',
    activeAgents: 6
  };

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString('en-US', { hour12: false }));
    };
    
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="top-bar">
      <div className="logo">
        <span className="logo-icon">◈</span>
        <span className="logo-text">ACN AGENT MONITOR</span>
      </div>
      
      <div className="metrics">
        <div className="metric-item">
          <span className="metric-label">NETWORK LATENCY</span>
          <span className="metric-value">{metrics.latency}</span>
        </div>
        <div className="metric-item">
          <span className="metric-label">TOTAL BANDWIDTH</span>
          <span className="metric-value">{metrics.bandwidth}</span>
        </div>
        <div className="metric-item">
          <span className="metric-label">ACTIVE AGENTS</span>
          <span className="metric-value">{metrics.activeAgents}</span>
        </div>
        <div className="metric-item">
          <span className="metric-label">SYSTEM STATUS</span>
          <span className="metric-value status-online">ONLINE</span>
        </div>
      </div>
      
      <div className="time-display">{currentTime}</div>
      
      <button 
        className={`settings-btn ${debugEnabled ? 'active' : ''}`}
        onClick={onToggleDebug}
        title="Toggle Debug Panel"
      >
        <span className="settings-icon">⚙</span>
        <span className="settings-label">{debugEnabled ? 'DEBUG ON' : 'DEBUG OFF'}</span>
      </button>
    </header>
  );
};

export default TopBar;
