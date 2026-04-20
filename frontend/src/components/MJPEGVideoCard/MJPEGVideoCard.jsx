import React, { useState, useEffect } from 'react';
import './MJPEGVideoCard.css';

/**
 * MJPEG Video Card Component
 * Displays MJPEG stream using simple <img> tag
 * Compatible with all browsers, no WebCodecs required
 */
const MJPEGVideoCard = ({ 
  streamUrl, 
  title = 'MJPEG Stream',
  width = 640, 
  height = 360 
}) => {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (streamUrl) {
      setIsConnected(true);
      setError(null);
    }
  }, [streamUrl]);

  const handleError = () => {
    setIsConnected(false);
    setError('Stream disconnected');
    
    // Auto-retry
    if (retryCount < 5) {
      setTimeout(() => {
        setRetryCount(prev => prev + 1);
        setIsConnected(true);
      }, 3000);
    }
  };

  const handleLoad = () => {
    setIsConnected(true);
    setError(null);
    setRetryCount(0);
  };

  return (
    <div className="mjpeg-video-card">
      <div className="video-container">
        {streamUrl ? (
          <img
            src={streamUrl}
            alt={title}
            width={width}
            height={height}
            className="mjpeg-stream"
            onError={handleError}
            onLoad={handleLoad}
          />
        ) : (
          <div className="placeholder">
            <div className="placeholder-content">
              <span className="placeholder-icon">📹</span>
              <span className="placeholder-text">Waiting for stream...</span>
            </div>
          </div>
        )}
        
        {/* Status overlay */}
        <div className="status-overlay">
          <div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '● LIVE' : '○ OFFLINE'}
          </div>
          {error && <div className="error-message">{error}</div>}
        </div>
      </div>
      
      <div className="video-info">
        <span className="video-title">{title}</span>
        <span className="video-format">MJPEG</span>
      </div>
    </div>
  );
};

export default MJPEGVideoCard;
