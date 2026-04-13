import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * Hook for managing WebRTC video stream connections
 * 
 * Usage:
 * const { 
 *   videoRef, 
 *   isConnected, 
 *   isConnecting, 
 *   error, 
 *   connect,
 *   disconnect 
 * } = useVideoStream(streamId);
 */
const useVideoStream = (streamId, websocket) => {
  const videoRef = useRef(null);
  const peerConnectionRef = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ fps: 0, bitrate: 0 });

  // WebRTC configuration
  const pcConfig = {
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' }
    ]
  };

  const connect = useCallback(async () => {
    if (!streamId || !videoRef.current) return;

    try {
      setIsConnecting(true);
      setError(null);

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

      // Handle connection state changes
      pc.onconnectionstatechange = () => {
        console.log(`[WebRTC] Connection state: ${pc.connectionState}`);
        if (pc.connectionState === 'connected') {
          setIsConnected(true);
          setIsConnecting(false);
          startStatsMonitoring(pc);
        } else if (pc.connectionState === 'disconnected' || 
                   pc.connectionState === 'failed') {
          setIsConnected(false);
          setIsConnecting(false);
        }
      };

      // Handle ICE candidates
      pc.onicecandidate = (event) => {
        if (event.candidate && websocket) {
          websocket.send(JSON.stringify({
            type: 'WEBRTC_ICE_CANDIDATE',
            payload: {
              stream_id: streamId,
              candidate: event.candidate,
              is_agent: false  // This is from the viewer (browser)
            }
          }));
        }
      };

      // Create offer (as viewer, we're the one initiating)
      const offer = await pc.createOffer({
        offerToReceiveAudio: true,
        offerToReceiveVideo: true
      });
      await pc.setLocalDescription(offer);

      // Send offer to server
      const response = await fetch('/api/video/webrtc/offer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stream_id: streamId,
          offer: pc.localDescription
        })
      });

      if (!response.ok) {
        throw new Error('Failed to send offer');
      }

      // In a real implementation, the server would return an answer
      // For now, we simulate waiting for an answer via WebSocket
      console.log(`[WebRTC] Waiting for answer for stream ${streamId}`);

    } catch (err) {
      console.error('[WebRTC] Connection error:', err);
      setError(err.message);
      setIsConnecting(false);
    }
  }, [streamId, websocket]);

  const disconnect = useCallback(() => {
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsConnected(false);
    setIsConnecting(false);
  }, []);

  // Monitor stats
  const startStatsMonitoring = (pc) => {
    const interval = setInterval(async () => {
      try {
        const stats = await pc.getStats();
        let videoBitrate = 0;
        let fps = 0;

        stats.forEach((report) => {
          if (report.type === 'inbound-rtp' && report.mediaType === 'video') {
            fps = report.framesPerSecond || 0;
            if (report.bytesReceived) {
              videoBitrate = Math.round((report.bytesReceived * 8) / 1000); // kbps
            }
          }
        });

        setStats({ fps, bitrate: videoBitrate });
      } catch (e) {
        console.error('Error getting stats:', e);
      }
    }, 1000);

    return () => clearInterval(interval);
  };

  // Handle WebRTC messages from server
  useEffect(() => {
    if (!websocket) return;

    const handleMessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'WEBRTC_ANSWER' && data.payload?.stream_id === streamId) {
          // Received answer from server
          const answer = data.payload.answer;
          if (peerConnectionRef.current) {
            peerConnectionRef.current.setRemoteDescription(new RTCSessionDescription(answer));
          }
        }

        if (data.type === 'WEBRTC_ICE_CANDIDATE' && data.payload?.stream_id === streamId) {
          // Received ICE candidate from agent
          const candidate = data.payload.candidate;
          if (peerConnectionRef.current && !data.payload.from_agent) {
            peerConnectionRef.current.addIceCandidate(new RTCIceCandidate(candidate));
          }
        }
      } catch (e) {
        console.error('Error handling WebSocket message:', e);
      }
    };

    websocket.addEventListener('message', handleMessage);
    return () => websocket.removeEventListener('message', handleMessage);
  }, [websocket, streamId]);

  // Auto-connect when streamId changes
  useEffect(() => {
    if (streamId) {
      connect();
    }
    return () => disconnect();
  }, [streamId, connect, disconnect]);

  return {
    videoRef,
    isConnected,
    isConnecting,
    error,
    stats,
    connect,
    disconnect
  };
};

export default useVideoStream;
