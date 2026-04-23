export type LanguageMode = 'en' | 'zh';

export const shellCopy = {
  en: {
    brandEyebrow: 'Command Mesh',
    brandTitle: 'Ops Dashboard',
    nav: {
      overview: { label: 'Overview', detail: 'Mission overview' },
      agents: { label: 'Agents', detail: 'Roster and health' },
      network: { label: 'Network', detail: 'Topology traffic' },
      control: { label: 'Control', detail: 'Operator actions' },
      settings: { label: 'Settings', detail: 'Policy controls' }
    },
    sidebarSnapshot: {
      title: 'Live Snapshot',
      integrity: 'Mesh integrity',
      alarmWindow: 'Alarm window',
      globalSync: 'Global sync',
      integrityValue: '98.7%',
      alarmValue: '03 active',
      syncValue: '09:26 UTC'
    },
    pageMeta: {
      overview: {
        title: 'Operational Overview',
        description: 'A single-screen command view for live latency, active agents, route health, and critical operator messages.'
      },
      agents: {
        title: 'Agent Inventory',
        description: 'Roster-level visibility into the active mesh, including role assignment, field throughput, and on-demand video tracks.'
      },
      network: {
        title: 'Network Diagnostics',
        description: 'Inspect current routes, detect slow paths, and validate which streams are actively flowing.'
      },
      control: {
        title: 'Operator Controls',
        description: 'Run backend control actions such as environment reset and immediate snapshot refresh from a dedicated control surface.'
      },
      settings: {
        title: 'System Settings',
        description: 'Tune the guardrails and operator-facing presentation without leaving the dashboard.'
      }
    },
    shellStatus: {
      missionEyebrow: 'Mission Control Dashboard',
      websocketLive: 'WebSocket live',
      websocketReconnect: 'WebSocket reconnecting',
      apiLoading: 'Loading API snapshot',
      apiConnected: 'API snapshot connected',
      online: 'Online',
      busy: 'Busy',
      offline: 'Offline'
    },
    themeMenu: {
      title: 'Appearance',
      description: 'Choose the theme that feels more comfortable for everyday use.',
      darkLabel: 'Dark mode',
      darkDescription: 'A darker interface that is easier on the eyes.',
      lightLabel: 'Light mode',
      lightDescription: 'A brighter interface for normal daytime use.'
    },
    languageMenu: {
      title: 'Language',
      description: 'Choose the interface language used in the dashboard shell.',
      enLabel: 'English',
      enDescription: 'Show the dashboard in English.',
      zhLabel: '中文',
      zhDescription: '将仪表盘界面切换为中文。'
    },
    demoAction: {
      label: 'Demo Config',
      detail: 'Choose and save local demo stages',
      running: 'Running local demo...',
      ready: 'Ready to run the saved demo config',
      success: 'Local demo injected successfully.',
      failed: 'Local demo failed.',
      quickRunLabel: 'Run Demo',
      quickRunDescription: 'Run the saved demo config now'
    },
    demoConfig: {
      eyebrow: 'Demo Config',
      title: 'Configure Demo Stages',
      description: 'Choose which local demo stages to inject into the dashboard.',
      registerLabel: 'Register',
      registerDescription: 'Inject local identity and capability registration for demo agents.',
      taskLabel: 'Apply Task',
      taskDescription: 'Inject single-agent task execution activity and task records.',
      cooperateLabel: 'Apply Cooperate',
      cooperateDescription: 'Inject collaboration activity between demo agents.',
      deregisterLabel: 'Deregister',
      deregisterDescription: 'Clear existing local demo agents and tasks from the dashboard.',
      close: 'Close',
      run: 'Run Demo',
      running: 'Running...',
      selected: 'selected',
      required: 'Select at least one demo stage.'
    },
    agentsVideo: {
      eyebrow: 'Videos',
      title: 'Remote Video Tracks',
      description: 'Tracks discovered from subscribe-track messages stay here until an operator chooses to watch one.',
      manageTitle: 'Manage track list',
      manageDescription: 'Add a manual track card for operator testing, or delete an existing MOQ/manual card from the dashboard.',
      agentIdLabel: 'Agent ID',
      taskIdLabel: 'Task ID',
      trackNameLabel: 'Track name',
      namespaceLabel: 'Namespace',
      namespacePlaceholder: '/task-id/agent-id',
      add: 'Add track',
      adding: 'Adding...',
      delete: 'Delete',
      deleting: 'Deleting...',
      deleteBlocked: 'Managed by backend',
      source: 'Source',
      sourceMoq: 'MOQ',
      sourceManual: 'Manual',
      sourceDirect: 'Direct',
      addSuccess: 'Track added.',
      deleteSuccess: 'Track deleted.',
      actionFailed: 'Track update failed.',
      loading: 'Loading discovered tracks...',
      empty: 'No video-type tracks have been discovered yet.',
      watch: 'Watch',
      watching: 'Preparing video...',
      ready: 'Ready',
      requested: 'Requested',
      pending: 'Pending',
      subscribed: 'Watching',
      error: 'Error',
      namespace: 'Namespace',
      task: 'Task',
      seen: 'Seen',
      lastSeen: 'Last seen',
      modalEyebrow: 'Live Viewer',
      modalDescription: 'The backend subscribes only after you choose watch, then exposes the stream as MJPEG for direct browser playback.',
      close: 'Close',
      browserUnsupported: 'This browser cannot render the MJPEG stream.',
      connecting: 'Connecting to the MJPEG stream...',
      waiting: 'Waiting for the first video frame.',
      playerFailed: 'Failed to initialize the MJPEG player.',
      fragments: 'Fragments',
      bytes: 'Bytes',
      sourceFps: 'Source FPS',
      renderedFps: 'Rendered FPS',
      codec: 'Codec',
      resolution: 'Resolution'
    }
  },
  zh: {
    brandEyebrow: '指挥网格',
    brandTitle: '运维看板',
    nav: {
      overview: { label: '总览', detail: '任务概览' },
      agents: { label: '智能体', detail: '名册与健康' },
      network: { label: '网络', detail: '拓扑与流量' },
      control: { label: '控制', detail: '运维操作' },
      settings: { label: '设置', detail: '界面与策略' }
    },
    sidebarSnapshot: {
      title: '实时快照',
      integrity: '网格完整性',
      alarmWindow: '告警窗口',
      globalSync: '全局同步',
      integrityValue: '98.7%',
      alarmValue: '03 个活动',
      syncValue: '09:26 UTC'
    },
    pageMeta: {
      overview: {
        title: '运行总览',
        description: '在单一视图中查看实时延迟、在线智能体、链路状态以及关键系统消息。'
      },
      agents: {
        title: '智能体清单',
        description: '查看当前网格中的智能体名册、角色分工、吞吐、健康状态以及按需视频轨道。'
      },
      network: {
        title: '网络诊断',
        description: '检查当前链路、识别高延迟路径，并验证哪些流正在实时传输。'
      },
      control: {
        title: '运维控制台',
        description: '在专用控制面板中执行环境重置、任务派发和快照刷新等操作。'
      },
      settings: {
        title: '系统设置',
        description: '调整主题、布局与界面呈现方式，而无需离开当前仪表盘。'
      }
    },
    shellStatus: {
      missionEyebrow: '任务控制看板',
      websocketLive: 'WebSocket 已连接',
      websocketReconnect: 'WebSocket 重连中',
      apiLoading: '正在加载接口快照',
      apiConnected: '接口快照已连接',
      online: '在线',
      busy: '忙碌',
      offline: '离线'
    },
    themeMenu: {
      title: '外观',
      description: '选择更适合当前使用场景的界面主题。',
      darkLabel: '深色模式',
      darkDescription: '适合低亮环境，减轻长时间查看的视觉压力。',
      lightLabel: '浅色模式',
      lightDescription: '适合白天与明亮环境，整体显示更清晰。'
    },
    languageMenu: {
      title: '语言',
      description: '选择仪表盘界面所使用的语言。',
      enLabel: 'English',
      enDescription: '将仪表盘界面切换为英文。',
      zhLabel: '中文',
      zhDescription: '将仪表盘界面切换为中文。'
    },
    demoAction: {
      label: '演示配置',
      detail: '选择并保存本地演示阶段',
      running: '正在运行本地演示...',
      ready: '可直接运行已保存的演示配置',
      success: '本地演示已成功注入。',
      failed: '本地演示运行失败。',
      quickRunLabel: '运行演示',
      quickRunDescription: '立即运行已保存的演示配置'
    },
    demoConfig: {
      eyebrow: '演示配置',
      title: '配置演示阶段',
      description: '选择要注入到仪表盘中的本地演示阶段。',
      registerLabel: '注册',
      registerDescription: '注入本地身份与能力注册演示事件。',
      taskLabel: '申请任务',
      taskDescription: '注入单智能体任务执行活动与任务记录。',
      cooperateLabel: '申请协作',
      cooperateDescription: '注入多个演示智能体之间的协作活动。',
      deregisterLabel: '注销',
      deregisterDescription: '从仪表盘中清除现有本地演示智能体与任务。',
      close: '关闭',
      run: '运行演示',
      running: '运行中...',
      selected: '已选择',
      required: '请至少选择一个演示阶段。'
    },
    agentsVideo: {
      eyebrow: '视频',
      title: '远程视频轨道',
      description: '从 subscribe-track 消息中发现的视频轨道会先展示在这里，只有在操作员点击观看后后端才会真正订阅。',
      manageTitle: '轨道管理',
      manageDescription: '可手动添加测试轨道卡片，也可从看板删除已有的 MOQ/手动轨道卡片。',
      agentIdLabel: '智能体 ID',
      taskIdLabel: '任务 ID',
      trackNameLabel: '轨道名',
      namespaceLabel: '命名空间',
      namespacePlaceholder: '/task-id/agent-id',
      add: '添加轨道',
      adding: '添加中...',
      delete: '删除',
      deleting: '删除中...',
      deleteBlocked: '由后端管理',
      source: '来源',
      sourceMoq: 'MOQ',
      sourceManual: '手动',
      sourceDirect: '直连',
      addSuccess: '轨道已添加。',
      deleteSuccess: '轨道已删除。',
      actionFailed: '轨道更新失败。',
      loading: '正在加载已发现的视频轨道...',
      empty: '暂未发现任何视频类轨道。',
      watch: '观看',
      watching: '正在准备视频...',
      ready: '就绪',
      requested: '已请求',
      pending: '等待中',
      subscribed: '观看中',
      error: '错误',
      namespace: '命名空间',
      task: '任务',
      seen: '次数',
      lastSeen: '最近发现',
      modalEyebrow: '实时观看',
      modalDescription: '只有在点击观看后，后端才会订阅该轨道，并以 MJPEG 方式直接提供给浏览器播放。',
      close: '关闭',
      browserUnsupported: '当前浏览器无法显示 MJPEG 视频流。',
      connecting: '正在连接 MJPEG 视频流...',
      waiting: '正在等待第一帧视频。',
      playerFailed: 'MJPEG 播放器初始化失败。',
      fragments: '片段',
      bytes: '字节',
      sourceFps: '源帧率',
      renderedFps: '显示帧率',
      codec: '编码',
      resolution: '分辨率'
    }
  }
} as const;
