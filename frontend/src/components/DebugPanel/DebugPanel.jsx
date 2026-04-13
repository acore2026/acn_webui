import React, { useState, useEffect, useRef } from 'react';
import './DebugPanel.css';

const DebugPanel = ({ backendUrl }) => {
  const [frontendLogs, setFrontendLogs] = useState([]);
  const [backendLogs, setBackendLogs] = useState([]);
  const [activeTab, setActiveTab] = useState('frontend');
  const [isPaused, setIsPaused] = useState(false);
  const frontendLogRef = useRef(null);
  const backendLogRef = useRef(null);
  const originalConsole = useRef(null);

  // 捕获前端console日志
  useEffect(() => {
    // 保存原始console方法
    originalConsole.current = {
      log: console.log,
      warn: console.warn,
      error: console.error,
      info: console.info
    };

    // 添加时间戳
    const getTimestamp = () => {
      return new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 });
    };

    // 重写console方法
    console.log = (...args) => {
      originalConsole.current.log(...args);
      if (!isPaused) {
        const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)).join(' ');
        addFrontendLog('log', message);
      }
    };

    console.warn = (...args) => {
      originalConsole.current.warn(...args);
      if (!isPaused) {
        const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)).join(' ');
        addFrontendLog('warn', message);
      }
    };

    console.error = (...args) => {
      originalConsole.current.error(...args);
      if (!isPaused) {
        const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)).join(' ');
        addFrontendLog('error', message);
      }
    };

    console.info = (...args) => {
      originalConsole.current.info(...args);
      if (!isPaused) {
        const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg)).join(' ');
        addFrontendLog('info', message);
      }
    };

    // 恢复原始console
    return () => {
      if (originalConsole.current) {
        console.log = originalConsole.current.log;
        console.warn = originalConsole.current.warn;
        console.error = originalConsole.current.error;
        console.info = originalConsole.current.info;
      }
    };
  }, [isPaused]);

  const addFrontendLog = (level, message) => {
    setFrontendLogs(prev => {
      const newLogs = [...prev, { time: new Date().toLocaleTimeString('en-US', { hour12: false }), level, message }];
      return newLogs.slice(-200); // 保留最后200条
    });
  };

  // 获取后端日志
  const fetchBackendLogs = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/logs`);
      if (response.ok) {
        const data = await response.json();
        setBackendLogs(data.logs || []);
      }
    } catch (error) {
      console.error('Failed to fetch backend logs:', error);
    }
  };

  // 定期获取后端日志
  useEffect(() => {
    fetchBackendLogs();
    const interval = setInterval(fetchBackendLogs, 3000);
    return () => clearInterval(interval);
  }, [backendUrl]);

  // 自动滚动到底部
  useEffect(() => {
    if (activeTab === 'frontend' && frontendLogRef.current) {
      frontendLogRef.current.scrollTop = frontendLogRef.current.scrollHeight;
    }
    if (activeTab === 'backend' && backendLogRef.current) {
      backendLogRef.current.scrollTop = backendLogRef.current.scrollHeight;
    }
  }, [frontendLogs, backendLogs, activeTab]);

  const clearLogs = () => {
    if (activeTab === 'frontend') {
      setFrontendLogs([]);
    } else {
      setBackendLogs([]);
    }
  };

  const getLevelColor = (level) => {
    switch (level) {
      case 'error': return '#ff4444';
      case 'warn': return '#ffaa00';
      case 'info': return '#00aaff';
      default: return '#00ff88';
    }
  };

  return (
    <div className="debug-panel">
      <div className="debug-header">
        <div className="debug-tabs">
          <button 
            className={`debug-tab ${activeTab === 'frontend' ? 'active' : ''}`}
            onClick={() => setActiveTab('frontend')}
          >
            Frontend Logs ({frontendLogs.length})
          </button>
          <button 
            className={`debug-tab ${activeTab === 'backend' ? 'active' : ''}`}
            onClick={() => setActiveTab('backend')}
          >
            Backend Logs ({backendLogs.length})
          </button>
        </div>
        <div className="debug-controls">
          <button className="debug-btn" onClick={() => setIsPaused(!isPaused)}>
            {isPaused ? '▶ Resume' : '⏸ Pause'}
          </button>
          <button className="debug-btn" onClick={clearLogs}>
            🗑 Clear
          </button>
        </div>
      </div>

      <div className="debug-content">
        {activeTab === 'frontend' ? (
          <div className="log-container" ref={frontendLogRef}>
            {frontendLogs.length === 0 ? (
              <div className="log-empty">No frontend logs yet...</div>
            ) : (
              frontendLogs.map((log, index) => (
                <div key={index} className={`log-line log-${log.level}`}>
                  <span className="log-time">[{log.time}]</span>
                  <span className="log-level" style={{ color: getLevelColor(log.level) }}>
                    [{log.level.toUpperCase()}]
                  </span>
                  <span className="log-message">{log.message}</span>
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="log-container" ref={backendLogRef}>
            {backendLogs.length === 0 ? (
              <div className="log-empty">No backend logs available...</div>
            ) : (
              backendLogs.map((log, index) => (
                <div key={index} className="log-line">
                  <span className="log-time">[{log.time || '???:??:??'}]</span>
                  <span className="log-message">{log.message}</span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DebugPanel;
