import React, { useState, useEffect, useCallback } from 'react';
import TopBar from './components/TopBar/TopBar';
import SidebarLeft from './components/SidebarLeft/SidebarLeft';
import SidebarRight from './components/SidebarRight/SidebarRight';
import StatusGrid from './components/StatusGrid/StatusGrid';
import MessageLog from './components/MessageLog/MessageLog';
import ControlPanel from './components/ControlPanel/ControlPanel';
import TaskModal from './components/TaskModal/TaskModal';
import DebugPanel from './components/DebugPanel/DebugPanel';
import useWebSocket from './hooks/useWebSocket';
import { mockAgents, mockMessages } from './utils/mockData';

const App = () => {
  const [agents, setAgents] = useState(mockAgents);
  const [messages, setMessages] = useState(mockMessages);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [moqVideoStreams, setMoqVideoStreams] = useState([]);
  const [moqFrames, setMoqFrames] = useState({}); // track_id -> latest frame
  const [videoStreams, setVideoStreams] = useState([]);
  const [debugEnabled, setDebugEnabled] = useState(false); // Debug面板开关
  
  // WebSocket connection - 使用相对路径自动适配当前host
  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
  const { sendMessage, lastMessage, connected } = useWebSocket(wsUrl);
  
  // 切换Debug面板
  const toggleDebug = () => {
    setDebugEnabled(prev => !prev);
  };

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (lastMessage) {
      console.log('[WebSocket] Received:', lastMessage);
      try {
        const data = JSON.parse(lastMessage);
        console.log('[WebSocket] Parsed:', data);
        
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
          case 'REFRESH_COMPLETE':
            if (data.payload?.agents) {
              setAgents(data.payload.agents);
            }
            addMessage('CONTROL', 'SYSTEM', 'Environment cleared and agent list refreshed');
            break;
          case 'REFRESH_ERROR':
            addMessage('CONTROL', 'SYSTEM', `Refresh failed: ${data.payload?.error || 'Unknown error'}`);
            break;
          case 'PIPELINE_LOG':
            // Handle pipeline log messages from backend
            if (data.payload) {
              const { source, destination, abstract, content } = data.payload;
              const from = source || 'Unknown';
              const to = destination || 'Unknown';
              const displayContent = abstract || content || 'No content';
              console.log('[PIPELINE_LOG]', from, '->', to, ':', displayContent);
              addMessage(from, to, displayContent);
            }
            break;
          case 'AGENT_STATUS_UPDATE':
            // Handle agent status updates from element logs
            if (data.payload?.agent) {
              const updatedAgent = data.payload.agent;
              setAgents(prevAgents => {
                const existingIndex = prevAgents.findIndex(a => a.agent_id === updatedAgent.agent_id);
                if (existingIndex >= 0) {
                  // Update existing agent
                  const newAgents = [...prevAgents];
                  newAgents[existingIndex] = {
                    ...newAgents[existingIndex],
                    ...updatedAgent,
                    work_status: updatedAgent.work_status,
                    current_task: updatedAgent.current_task,
                    logs: updatedAgent.logs || newAgents[existingIndex].logs
                  };
                  return newAgents;
                } else {
                  // Add new agent
                  return [...prevAgents, updatedAgent];
                }
              });
              
              // Also add to message flow
              const { element_id, log_type, current_task } = data.payload;
              addMessage(element_id, updatedAgent.agent_name || updatedAgent.agent_id, `${log_type}: ${current_task}`);
            }
            break;
          case 'VIDEO_STREAM_LIST':
            // Handle video stream list updates
            if (data.payload?.streams) {
              setVideoStreams(data.payload.streams);
            }
            break;
          case 'VIDEO_STREAM_UPDATE':
            // Handle individual stream updates
            if (data.payload) {
              setVideoStreams(prev => {
                const streamId = data.payload.stream_id;
                const existingIndex = prev.findIndex(s => s.stream_id === streamId);
                if (existingIndex >= 0) {
                  const newStreams = [...prev];
                  newStreams[existingIndex] = data.payload;
                  return newStreams;
                } else {
                  return [...prev, data.payload];
                }
              });
            }
            break;
          case 'VIDEO_FRAME':
            // Handle MOQ video frame
            if (data.payload) {
              const { track_id, group_id, object_id, frame_type, payload_size } = data.payload;
              // Update latest frame for this track
              setMoqFrames(prev => ({
                ...prev,
                [track_id]: {
                  group_id,
                  object_id,
                  frame_type,
                  payload_size,
                  timestamp: new Date()
                }
              }));
              // Add to message flow (optional, can be verbose)
              // addMessage('MOQ', track_id, `Frame ${object_id} (${frame_type}, ${payload_size} bytes)`);
            }
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
    // Send refresh request to backend to call ARF /clear
    sendMessage({
      type: 'REFRESH',
      payload: { timestamp: new Date().toISOString() }
    });
    addMessage('CONTROL', 'SYSTEM', 'Sending clear environment request...');
  };

  const handleClearMessages = () => {
    setMessages([]);
  };

  return (
    <div className="app">
      <TopBar onToggleDebug={toggleDebug} debugEnabled={debugEnabled} />
      
      {/* Debug Panel */}
      {debugEnabled && (
        <DebugPanel backendUrl={`${window.location.protocol}//${window.location.host}`} />
      )}
      
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
        
        <SidebarRight videoStreams={videoStreams} moqFrames={moqFrames} />
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
