import React, { useState, useEffect, useCallback } from 'react';
import TopBar from './components/TopBar/TopBar';
import SidebarLeft from './components/SidebarLeft/SidebarLeft';
import SidebarRight from './components/SidebarRight/SidebarRight';
import StatusGrid from './components/StatusGrid/StatusGrid';
import MessageLog from './components/MessageLog/MessageLog';
import ControlPanel from './components/ControlPanel/ControlPanel';
import TaskModal from './components/TaskModal/TaskModal';
import useWebSocket from './hooks/useWebSocket';
import { mockAgents, mockMessages } from './utils/mockData';

const App = () => {
  const [agents, setAgents] = useState(mockAgents);
  const [messages, setMessages] = useState(mockMessages);
  const [isModalOpen, setIsModalOpen] = useState(false);
  
  // WebSocket connection
  const { sendMessage, lastMessage, connected } = useWebSocket('ws://localhost:9050/ws');

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage);
        
        switch (data.type) {
          case 'AGENT_LIST':
            if (data.payload?.agents?.length > 0) {
              setAgents(data.payload.agents);
            }
            break;
          case 'TASK_DISPATCHED':
            addMessage('CONTROL', data.payload.agent_id, `Task dispatched: ${data.payload.task_type}`);
            break;
          case 'EMERGENCY_LAND':
            addMessage('CONTROL', 'ALL DRONES', 'EMERGENCY LANDING COMMAND ISSUED');
            triggerShake();
            break;
          case 'ABORT_ALL':
            addMessage('CONTROL', 'ALL AGENTS', 'ABORT ALL TASKS COMMAND ISSUED');
            // Reset all agents to idle
            setAgents(prev => prev.map(a => ({...a, work_status: 'idle', current_task: null})));
            break;
          default:
            break;
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    }
  }, [lastMessage]);

  // Add message helper
  const addMessage = useCallback((from, to, content) => {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', { hour12: false });
    
    setMessages(prev => {
      const newMessages = [...prev, { from, to, content, time: timeStr }];
      // Keep only last 100 messages
      if (newMessages.length > 100) {
        return newMessages.slice(-100);
      }
      return newMessages;
    });
  }, []);

  // Trigger shake animation
  const triggerShake = () => {
    document.body.classList.add('shake-animation');
    setTimeout(() => {
      document.body.classList.remove('shake-animation');
    }, 500);
  };

  // Control handlers
  const handleDispatchTask = () => {
    setIsModalOpen(true);
  };

  const handleTaskSubmit = (taskData) => {
    sendMessage({
      type: 'DISPATCH_TASK',
      payload: {
        ...taskData,
        timestamp: new Date().toISOString()
      }
    });
    
    const agent = agents.find(a => a.agent_id === taskData.agentId);
    addMessage('CONTROL', agent?.agent_name || taskData.agentId, 
      `Task dispatched: ${taskData.taskType}${taskData.description ? ' - ' + taskData.description : ''}`);
  };

  const handleEmergencyLand = () => {
    if (window.confirm('Are you sure you want to initiate emergency landing for all drones?')) {
      sendMessage({
        type: 'EMERGENCY_LAND',
        payload: { timestamp: new Date().toISOString() }
      });
    }
  };

  const handleAbortAll = () => {
    if (window.confirm('Are you sure you want to abort all tasks?')) {
      sendMessage({
        type: 'ABORT_ALL',
        payload: { timestamp: new Date().toISOString() }
      });
    }
  };

  const handleRefresh = () => {
    // Reload mock data
    setAgents(mockAgents);
    addMessage('CONTROL', 'SYSTEM', 'Agent list refreshed (stub data)');
  };

  const handleClearMessages = () => {
    setMessages([]);
  };

  return (
    <div className="app">
      <TopBar />
      
      <main className="main-container">
        <SidebarLeft agents={agents} />
        
        <section className="center-content">
          <StatusGrid agents={agents} />
          <MessageLog messages={messages} onClear={handleClearMessages} />
          <ControlPanel 
            onDispatchTask={handleDispatchTask}
            onEmergencyLand={handleEmergencyLand}
            onAbortAll={handleAbortAll}
            onRefresh={handleRefresh}
          />
        </section>
        
        <SidebarRight />
      </main>
      
      <TaskModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        agents={agents}
        onSubmit={handleTaskSubmit}
      />
    </div>
  );
};

export default App;
