import React from 'react';
import './StatusGrid.css';

const StatusCard = ({ agent }) => {
  const workStatus = agent.work_status || 'idle';
  const taskInfo = agent.current_task || 'No active task';

  return (
    <div className={`status-card ${workStatus}`}>
      <div className="status-card-header">
        <span className="status-card-agent">{agent.agent_name}</span>
        <span className={`status-card-state ${workStatus}`}>{workStatus}</span>
      </div>
      <div className="status-card-task">{taskInfo}</div>
      
      {agent.logs && agent.logs.length > 0 && (
        <div className="status-logs">
          <div className="logs-header">Operation Logs:</div>
          <div className="logs-content">
            {agent.logs.map((log, idx) => (
              <div key={idx} className={`log-item ${log.level}`}>
                <span className="log-time">[{log.time}]</span>
                <span className="log-message">{log.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

const StatusGrid = ({ agents }) => {
  const SERVICE_AGENTS = ['IDM-SERVICE', 'ARF-SERVICE', 'ACF-SERVICE'];
  
  const onlineAgents = agents.filter(a => 
    a.agent_status !== 'offline' && !SERVICE_AGENTS.includes(a.agent_id)
  );

  return (
    <div className="center-panel status-panel">
      <div className="panel-header">
        <span className="panel-title">AGENT WORK STATUS</span>
        <div className="status-legend">
          <span className="legend-item"><span className="status-dot idle"></span>IDLE</span>
          <span className="legend-item"><span className="status-dot working"></span>WORKING</span>
          <span className="legend-item"><span className="status-dot tracking"></span>TRACKING</span>
          <span className="legend-item"><span className="status-dot expelling"></span>EXPELLING</span>
        </div>
      </div>
      
      <div className="status-grid">
        {onlineAgents.map(agent => (
          <StatusCard key={agent.agent_id} agent={agent} />
        ))}
      </div>
    </div>
  );
};

export default StatusGrid;
