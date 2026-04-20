import React from 'react';
import './MessageLog.css';

const MessageLog = ({ messages, onClear }) => {
  return (
    <div className="center-panel message-panel">
      <div className="panel-header">
        <span className="panel-title">MESSAGE FLOW</span>
        <button className="clear-btn" onClick={onClear}>CLEAR</button>
      </div>
      
      <div className="message-log">
        {[...messages].reverse().map((msg, idx) => (
          <div key={messages.length - idx} className="message-item">
            <span className="message-time">[{msg.time}]</span>
            <span className="message-content">
              <span style={{ color: 'var(--accent-cyan)' }}>{msg.from}</span>
              <span className="message-arrow">→</span>
              <span style={{ color: 'var(--accent-blue)' }}>{msg.to}</span>: 
              {' '}{msg.content}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default MessageLog;
