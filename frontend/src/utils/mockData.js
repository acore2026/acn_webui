// Mock Agents for demo
export const mockAgents = [
  { 
    agent_id: 'ACN-AGENT-001', 
    agent_name: 'Drone Alpha', 
    agent_status: 'online', 
    agent_capability: ['surveillance', 'tracking'], 
    priority: 5, 
    work_status: 'working', 
    current_task: 'Patrolling sector 7',
    logs: [
      { time: '10:35:18', level: 'warning', message: 'Detected suspicious person' },
      { time: '10:35:20', level: 'info', message: 'Expulsion task dispatched' },
      { time: '10:36:05', level: 'success', message: 'Expulsion completed' }
    ]
  },
  { 
    agent_id: 'ACN-AGENT-002', 
    agent_name: 'Drone Beta', 
    agent_status: 'working', 
    agent_capability: ['patrol', 'expel', 'thermal'], 
    priority: 4, 
    work_status: 'tracking', 
    current_task: 'Tracking target T-001',
    logs: [
      { time: '10:29:15', level: 'success', message: 'Target T-001 locked' },
      { time: '10:31:45', level: 'warning', message: 'Target moving to crowded area' },
      { time: '10:32:10', level: 'info', message: 'Adjusting altitude' }
    ]
  },
  { 
    agent_id: 'ACN-AGENT-003', 
    agent_name: 'Ground Unit 1', 
    agent_status: 'online', 
    agent_capability: ['inspection', 'security'], 
    priority: 3, 
    work_status: 'idle', 
    current_task: 'Waiting for assignment',
    logs: [
      { time: '10:25:00', level: 'info', message: 'System initialized' },
      { time: '10:25:05', level: 'success', message: 'Connected to ACN gateway' },
      { time: '10:25:30', level: 'info', message: 'Standing by at station A' }
    ]
  },
  { 
    agent_id: 'ACN-AGENT-004', 
    agent_name: 'Drone Gamma', 
    agent_status: 'offline', 
    agent_capability: ['surveillance', 'night_vision'], 
    priority: 2 
  },
  { 
    agent_id: 'ACN-AGENT-005', 
    agent_name: 'Marine Unit A', 
    agent_status: 'online', 
    agent_capability: ['underwater', 'sonar'], 
    priority: 4, 
    work_status: 'working', 
    current_task: 'Underwater perimeter scan',
    logs: [
      { time: '10:21:30', level: 'success', message: 'Sonar system activated' },
      { time: '10:25:20', level: 'info', message: 'No anomalies detected' },
      { time: '10:27:00', level: 'info', message: 'Moving to sector 2' }
    ]
  },
  { 
    agent_id: 'ACN-AGENT-006', 
    agent_name: 'RobotDog', 
    agent_status: 'online', 
    agent_capability: ['patrol', 'obstacle_avoidance', 'terrain_adaptation'], 
    priority: 4, 
    work_status: 'working', 
    current_task: 'Patrolling building perimeter',
    logs: [
      { time: '10:16:30', level: 'success', message: 'Obstacle detected and avoided' },
      { time: '10:20:45', level: 'warning', message: 'Sound detected near gate B' },
      { time: '10:21:10', level: 'info', message: 'Investigating sound source' }
    ]
  },
  { 
    agent_id: 'ACN-AGENT-007', 
    agent_name: 'RobotARM', 
    agent_status: 'online', 
    agent_capability: ['manipulation', 'precision_operation', 'object_grasping'], 
    priority: 3, 
    work_status: 'working', 
    current_task: 'Sorting items in warehouse',
    logs: [
      { time: '10:10:30', level: 'success', message: 'Vision system calibrated' },
      { time: '10:12:15', level: 'info', message: 'Picked up package #2847' },
      { time: '10:13:40', level: 'success', message: 'Placed in Zone C' }
    ]
  },
  { 
    agent_id: 'IDM-SERVICE', 
    agent_name: 'IDM Service', 
    agent_status: 'online', 
    agent_capability: ['identity', 'verification', 'vc_management'], 
    priority: 10, 
    work_status: 'working', 
    current_task: 'Processing identity requests' 
  },
  { 
    agent_id: 'ARF-SERVICE', 
    agent_name: 'ARF Service', 
    agent_status: 'online', 
    agent_capability: ['repository', 'discovery', 'matching'], 
    priority: 10, 
    work_status: 'working', 
    current_task: 'Agent discovery service active' 
  },
  { 
    agent_id: 'ACF-SERVICE', 
    agent_name: 'ACF Service', 
    agent_status: 'online', 
    agent_capability: ['communication', 'routing', 'ws_gateway'], 
    priority: 10, 
    work_status: 'working', 
    current_task: 'WebSocket gateway active' 
  }
];

// Mock Messages
const now = new Date();
const formatTime = (date) => date.toLocaleTimeString('en-US', { hour12: false });

export const mockMessages = [
  { from: 'ACN Agent', to: 'IDM', content: 'Apply for digital identity', time: formatTime(new Date(now - 300000)) },
  { from: 'IDM', to: 'ACN Agent', content: 'Identity verification completed - VC issued', time: formatTime(new Date(now - 280000)) },
  { from: 'ACN Agent', to: 'ARF', content: 'Request agent discovery for patrol task', time: formatTime(new Date(now - 260000)) },
  { from: 'ARF', to: 'ACN Agent', content: 'Discovery result: 3 agents found', time: formatTime(new Date(now - 240000)) },
  { from: 'ACN Agent', to: 'MOQT Relay', content: 'Subscribe to track: surveillance-feed-01', time: formatTime(new Date(now - 220000)) },
  { from: 'MOQT Relay', to: 'ACN Agent', content: 'Track subscription confirmed', time: formatTime(new Date(now - 200000)) },
  { from: 'SYSTEM', to: 'ALL', content: 'Network latency check: 12ms', time: formatTime(new Date(now - 180000)) },
  { from: 'Drone Alpha', to: 'SYSTEM', content: 'Status update: Sector 7 clear', time: formatTime(new Date(now - 160000)) },
  { from: 'Drone Beta', to: 'SYSTEM', content: 'Target T-001 detected at coordinates [34.0522, -118.2437]', time: formatTime(new Date(now - 140000)) },
  { from: 'SYSTEM', to: 'Drone Beta', content: 'Command: Initiate tracking protocol', time: formatTime(new Date(now - 120000)) }
];
