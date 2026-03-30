import React from 'react';
import './ControlPanel.css';

const ControlPanel = ({ onDispatchTask, onEmergencyLand, onAbortAll, onRefresh }) => {
  return (
    <div className="center-panel control-panel">
      <div className="panel-header">
        <span className="panel-title">CONTROL CENTER</span>
      </div>
      
      <div className="control-grid">
        <button className="control-btn primary" onClick={onDispatchTask}>
          <span className="btn-icon">➤</span>
          <span className="btn-text">DISPATCH TASK</span>
        </button>
        <button className="control-btn warning" onClick={onEmergencyLand}>
          <span className="btn-icon">🚁</span>
          <span className="btn-text">EMERGENCY LAND</span>
        </button>
        <button className="control-btn danger" onClick={onAbortAll}>
          <span className="btn-icon">⏹</span>
          <span className="btn-text">ABORT ALL</span>
        </button>
        <button className="control-btn secondary" onClick={onRefresh}>
          <span className="btn-icon">↻</span>
          <span className="btn-text">REFRESH</span>
        </button>
      </div>
    </div>
  );
};

export default ControlPanel;
