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
        description: 'Roster-level visibility into the active mesh, including role assignment and field throughput.'
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
      label: 'Run Demo',
      detail: 'Inject local registration and interaction demo events',
      running: 'Running local demo...',
      ready: 'Ready to inject a local demo scenario',
      success: 'Local demo injected successfully.',
      failed: 'Local demo failed.'
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
        description: '查看当前网格中的智能体名册、角色分工、吞吐与健康状态。'
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
      label: '运行演示',
      detail: '注入本地注册与交互演示事件',
      running: '正在运行本地演示...',
      ready: '可一键注入本地演示场景',
      success: '本地演示已成功注入。',
      failed: '本地演示运行失败。'
    }
  }
} as const;
