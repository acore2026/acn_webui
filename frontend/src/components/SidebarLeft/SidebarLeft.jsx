import React from 'react';
import './SidebarLeft.css';

const SidebarLeft = ({ agents }) => {
  // Filter out service agents
  const SERVICE_AGENTS = ['IDM-SERVICE', 'ARF-SERVICE', 'ACF-SERVICE'];
  
  const displayAgents = agents
    .filter(a => !SERVICE_AGENTS.includes(a.agent_id))
    .sort((a, b) => (b.priority || 0) - (a.priority || 0));

  return (
    <aside className="sidebar-left">
      <div className="panel-header">
        <span className="panel-title">REGISTERED AGENTS</span>
        <span className="panel-count">{displayAgents.length}</span>
      </div>
      
      <div className="agent-list">
        {displayAgents.map(agent => (
          <div key={agent.agent_id} className={`agent-item ${agent.agent_status}`}>
            <div className="agent-header">
              <span className="agent-name">{agent.agent_name}</span>
              <span className={`agent-status ${agent.agent_status}`}>
                {agent.agent_status}
              </span>
            </div>
            <div className="agent-meta">
              <span className="agent-meta-label">ID:</span>
              <span className="agent-meta-value">{agent.agent_id}</span>
            </div>
            <div className="agent-capabilities">
              {(agent.agent_capability || []).map((cap, idx) => (
                <span key={idx} className="capability-tag">{cap}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
};

export default SidebarLeft;
