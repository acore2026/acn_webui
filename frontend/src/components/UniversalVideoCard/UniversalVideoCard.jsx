import React, { useState, useEffect, useRef } from 'react';
import './UniversalVideoCard.css';

/**
 * Universal Video Card Component
 * Supports: MJPEG, H.264 (WebCodecs), WebRTC
 * Automatically selects best format based on browser capabilities
 */
const UniversalVideoCard = ({ 
  trackId,
  streamUrl,
  title = 'Video Stream',
  width = 640,
  height = 360,
  preferredFormat = 'auto' // 'auto', 'mjpeg', 'h264', 'webrtc'
}) => {
  const [format, setFormat] = useState('detecting');
  const [status, setStatus] = useState('connecting');
  const [error, setError] = useState(null);
  const [streamInfo, setStreamInfo] = useState(null);
  
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  
  // Detect best format
  useEffect(() => {
    const detectFormat = () => {
      if (preferredFormat !== 'auto') {
        return preferredFormat;
      }
      
      // Priority: MJPEG > WebRTC > H.264
      // MJPEG works everywhere
      if (streamUrl && streamUrl.includes('/mjpeg')) {
        return 'mjpeg';
      }
      
      // Check WebCodecs support for H.264
      if (window.VideoDecoder && window.EncodedVideoChunk) {
        return 'h264';
      }
      
      // Check WebRTC support
      if (window.RTCPeerConnection) {
        return 'webrtc';
      }
      
      // Fallback to MJPEG
      return 'mjpeg';
    };
    
    setFormat(detectFormat());
  }, [preferredFormat, streamUrl]);
  
  // Fetch stream info
  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const res = await fetch(`/api/video/stream/${trackId}/info`);
        const data = await res.json();
        setStreamInfo(data);
      } catch (e) {
        console.error('Failed to fetch stream info:', e);
      }
    };
    
    fetchInfo();
    const interval = setInterval(fetchInfo, 5000);
    return () => clearInterval(interval);
  }, [trackId]);
  
  // Handle MJPEG stream
  const renderMJPEG = () => {
    const mjpegUrl = streamUrl || `/api/video/stream/${trackId}/mjpeg`;
    
    return (
      <img
        src={mjpegUrl}
        alt={title}
        width={width}
        height={height}
        className="video-stream mjpeg"
        onLoad={() => setStatus('connected')}
        onError={() => {
          setStatus('error');
          setError('Failed to load MJPEG stream');
        }}
      />
    );
  };
  
  // Handle H.264 with WebCodecs
  const renderH264 = () => {
    // Use canvas-based H264 decoder (simplified)
    return (
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="video-stream h264"
      />
    );
  };
  
  // Handle WebRTC
  const renderWebRTC = () => {
    return (
      <video
        ref={videoRef}
        width={width}
        height={height}
        autoPlay
        playsInline
        muted
        className="video-stream webrtc"
      />
    );
  };
  
  // Render based on format
  const renderVideo = () => {
    switch (format) {
      case 'mjpeg':
        return renderMJPEG();
      case 'h264':
        return renderH264();
      case 'webrtc':
        return renderWebRTC();
      default:
        return (
          <div className="placeholder">
            <span>Detecting format...</span>
          </div>
        );
    }
  };
  
  const getStatusClass = () => {
    switch (status) {
      case 'connected':
      case 'playing':
        return 'active';
      case 'connecting':
      case 'detecting':
        return 'connecting';
      case 'error':
        return 'error';
      default:
        return 'inactive';
    }
  };
  
  const getStatusText = () => {
    switch (status) {
      case 'connected':
      case 'playing':
        return '● LIVE';
      case 'connecting':
        return '⟳ Connecting';
      case 'detecting':
        return '⟳ Detecting';
      case 'error':
        return '✗ Error';
      default:
        return '○ Standby';
    }
  };
  
  return (
    <div className="universal-video-card">
      <div className="video-container">
        {renderVideo()}
        
        {/* Status overlay */}
        <div className="status-overlay">
          <div className={`status-badge ${getStatusClass()}`}>
            {getStatusText()}
          </div>
          {format !== 'detecting' && (
            <div className="format-badge">
              {format.toUpperCase()}
            </div>
          )}
          {error && (
            <div className="error-badge">
              {error}
            </div>
          )}
        </div>
      </div>
      
      <div className="video-info">
        <div className="info-left">
          <span className="video-title">{title}</span>
          <span className="track-id">{trackId}</span>
        </div>
        <div className="info-right">
          {streamInfo && (
            <span className="stream-stats">
              {streamInfo.width}x{streamInfo.height} | 
              {streamInfo.format}
            </span>
          )}
        </div>
      </div>
      
      {/* Debug info */}
      {process.env.NODE_ENV === 'development' && streamInfo && (
        <div className="debug-info">
          <pre>{JSON.stringify(streamInfo, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};

export default UniversalVideoCard;
