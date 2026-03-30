import React, { useState } from 'react';
import './TaskModal.css';

const TaskModal = ({ isOpen, onClose, agents, onSubmit }) => {
  const [selectedAgent, setSelectedAgent] = useState('');
  const [taskType, setTaskType] = useState('patrol');
  const [description, setDescription] = useState('');

  const SERVICE_AGENTS = ['IDM-SERVICE', 'ARF-SERVICE', 'ACF-SERVICE'];
  
  const availableAgents = agents.filter(a => 
    a.agent_status !== 'offline' && !SERVICE_AGENTS.includes(a.agent_id)
  );

  const handleSubmit = () => {
    if (!selectedAgent) {
      alert('Please select an agent');
      return;
    }
    
    onSubmit({
      agentId: selectedAgent,
      taskType,
      description
    });
    
    // Reset form
    setSelectedAgent('');
    setTaskType('patrol');
    setDescription('');
    onClose();
  };

  const handleClose = () => {
    setSelectedAgent('');
    setTaskType('patrol');
    setDescription('');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">DISPATCH NEW TASK</span>
          <button className="close-btn" onClick={handleClose}>×</button>
        </div>
        
        <div className="modal-body">
          <div className="form-group">
            <label>Select Agent:</label>
            <select 
              value={selectedAgent} 
              onChange={(e) => setSelectedAgent(e.target.value)}
            >
              <option value="">-- Select Agent --</option>
              {availableAgents.map(agent => (
                <option key={agent.agent_id} value={agent.agent_id}>
                  {agent.agent_name} ({agent.agent_id})
                </option>
              ))}
            </select>
          </div>
          
          <div className="form-group">
            <label>Task Type:</label>
            <select 
              value={taskType} 
              onChange={(e) => setTaskType(e.target.value)}
            >
              <option value="patrol">Patrol</option>
              <option value="track">Track Target</option>
              <option value="expel">Expel Intruder</option>
              <option value="inspect">Inspect Area</option>
            </select>
          </div>
          
          <div className="form-group">
            <label>Description:</label>
            <textarea 
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Enter task description..."
            />
          </div>
        </div>
        
        <div className="modal-footer">
          <button className="btn secondary" onClick={handleClose}>CANCEL</button>
          <button className="btn primary" onClick={handleSubmit}>DISPATCH</button>
        </div>
      </div>
    </div>
  );
};

export default TaskModal;
