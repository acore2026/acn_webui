import { useEffect, useMemo, useState } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  EdgeTypes,
  Node,
  NodeProps,
  ReactFlow,
  ReactFlowInstance
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { LanguageMode } from '../i18n';
import { MessageFlowEdgeModel, MessageFlowNodeModel } from '../types';
import { FlowMessageEdge } from './FlowMessageEdge';
import { NetworkZoneNode, NetworkZoneNodeModel } from './NetworkZoneNode';
import { SystemFlowNode, SystemFlowNodeModelData } from './SystemFlowNode';

type FlowStageKind = 'identity' | 'joining' | 'task' | 'waiting';

type FlowStageNodeModel = Node<
  {
    title: string;
    kind: FlowStageKind;
    label: string;
  },
  'flowStage'
>;

type TopologyFlowNode = SystemFlowNodeModelData | NetworkZoneNodeModel | FlowStageNodeModel;

interface TopologyMapProps {
  nodes: MessageFlowNodeModel[];
  edges: MessageFlowEdgeModel[];
  language: LanguageMode;
}

const nodeTypes = {
  systemFlow: SystemFlowNode,
  networkZone: NetworkZoneNode,
  flowStage: ({ data }: NodeProps<FlowStageNodeModel>) => (
    <div className={`theme-flow-stage-node theme-flow-stage-node--${data.kind}`}>
      <span>{data.label}</span>
      <strong>{data.title}</strong>
    </div>
  )
};

const edgeTypes: EdgeTypes = {
  flowMessage: FlowMessageEdge
};
const NETWORK_ZONE_NODE_ID = '__network-zone__';
const AGENT_GW_ZONE_NODE_ID = '__agent-gw-zone__';

const triangleLayout: Record<string, { x: number; y: number }> = {
  'ACN Agent': { x: -500, y: 450 },
  IDM: { x: 260, y: 0 },
  ARF: { x: 1100, y: 230 },
  ACF: { x: 960, y: 480 },
  Relay: { x: 1240, y: 480 },
  AgentGW: { x: 1100, y: 350 },
  'ACN SDK': { x: 260, y: 900 }
};

const gatewayNodes = new Set(['ARF', 'ACF', 'Relay', 'AgentGW']);
const BUBBLE_LANE_OFFSETS = [0, -64, 64, -128, 128, -192, 192];
const gatewayCurvatures: Record<string, number> = {
  ARF: 0.15,
  ACF: 0.18,
  Relay: 0.21,
  AgentGW: 0.18
};

const resolveFlowStage = (edges: MessageFlowEdgeModel[], isZh: boolean): { title: string; kind: FlowStageKind } => {
  const stageMatches = [
    {
      title: isZh ? '执行任务' : 'Executing Task',
      kind: 'task' as const,
      test: (text: string) =>
        /\btask\b/.test(text) ||
        text.includes('taskexecution') ||
        text.includes('task execution') ||
        text.includes('执行任务') ||
        text.includes('任务执行')
    },
    {
      title: isZh ? '正在入网' : 'Joining Network',
      kind: 'joining' as const,
      test: (text: string) =>
        text.includes('setup') ||
        text.includes('moq connection') ||
        text.includes('moq') ||
        text.includes('入网')
    },
    {
      title: isZh ? '申请数字身份' : 'Applying Digital Identity',
      kind: 'identity' as const,
      test: (text: string) =>
        text.includes('/idm/v1/identity-applications') ||
        text.includes('identity-applications') ||
        text.includes('identity application') ||
        text.includes('agent-card') ||
        text.includes('agent-cards') ||
        text.includes('vc-verification') ||
        text.includes('vc-verifications') ||
        text.includes('vc-vertification') ||
        text.includes('vc-vertifications') ||
        text.includes('数字身份')
    }
  ];

  const candidates = [...edges]
    .filter((edge) => edge.active || edge.lastTimestamp)
    .sort((a, b) => {
      if (a.active !== b.active) {
        return a.active ? -1 : 1;
      }
      return String(b.lastTimestamp ?? '').localeCompare(String(a.lastTimestamp ?? ''));
    });

  for (const edge of candidates) {
    const edgeText = `${edge.source} ${edge.target} ${edge.lastMessage}`.toLowerCase();
    const stage = stageMatches.find((item) => item.test(edgeText));
    if (stage) {
      return {
        title: stage.title,
        kind: stage.kind
      };
    }
  }

  return {
    title: isZh ? '等待消息流' : 'Waiting For Message Flow',
    kind: 'waiting'
  };
};

const resolveHandles = (
  source: string,
  target: string
): Pick<Edge, 'sourceHandle' | 'targetHandle'> => {
  if (target === 'Relay') {
    if (source === 'ACN SDK') {
      return { sourceHandle: 'right-mid-out', targetHandle: 'bottom-mid-in' };
    }

    if (source === 'ACN Agent') {
      return { sourceHandle: 'right-bottom-out', targetHandle: 'left-mid-in' };
    }

    if (source === 'IDM') {
      return { sourceHandle: 'bottom-out', targetHandle: 'left-mid-in' };
    }

    return { sourceHandle: 'right-out', targetHandle: 'left-mid-in' };
  }

  if (source === 'Relay') {
    if (target === 'IDM') {
      return { sourceHandle: 'left-top-out', targetHandle: 'right-in' };
    }

    if (target === 'ACN SDK') {
      return { sourceHandle: 'left-bottom-out', targetHandle: 'right-in' };
    }

    return { sourceHandle: 'left-mid-out', targetHandle: 'right-mid-in' };
  }

  if (source === 'ACN Agent' && gatewayNodes.has(target)) {
    return {
      sourceHandle: 'right-mid-out',
      targetHandle: 'left-mid-in'
    };
  }

  if (gatewayNodes.has(source) && target === 'ACN Agent') {
    return {
      sourceHandle: 'left-mid-out',
      targetHandle: 'right-mid-in'
    };
  }

  if (gatewayNodes.has(source) && target === 'IDM') {
    if (source === 'ARF') {
      return {
        sourceHandle: 'top-out',
        targetHandle: 'right-in'
      };
    }

    return {
      sourceHandle: 'left-mid-out',
      targetHandle: 'right-in'
    };
  }

  if (source === 'IDM' && gatewayNodes.has(target)) {
    return {
      sourceHandle: 'right-out',
      targetHandle: 'left-mid-in'
    };
  }

  if (source === 'ACN Agent' && target === 'IDM') {
    return { sourceHandle: 'top-out', targetHandle: 'left-in' };
  }

  if (source === 'IDM' && target === 'ACN Agent') {
    return { sourceHandle: 'left-out', targetHandle: 'right-in' };
  }

  if (gatewayNodes.has(source) && target === 'ACN SDK') {
    return {
      sourceHandle: 'left-mid-out',
      targetHandle: 'right-in'
    };
  }

  if (source === 'ACN SDK' && target === 'ACF') {
    return { sourceHandle: 'top-out', targetHandle: 'left-mid-in' };
  }

  if (source === 'ACN SDK' && gatewayNodes.has(target)) {
    return { sourceHandle: 'right-out', targetHandle: 'left-mid-in' };
  }

  if (source === 'ACN Agent' && target === 'ACN SDK') {
    return { sourceHandle: 'bottom-out', targetHandle: 'left-in' };
  }

  if (source === 'ACN SDK' && target === 'ACN Agent') {
    return { sourceHandle: 'left-out', targetHandle: 'bottom-in' };
  }

  if (source === 'IDM' && target === 'ACN SDK') {
    return { sourceHandle: 'bottom-out', targetHandle: 'top-in' };
  }

  if (source === 'ACN SDK' && target === 'IDM') {
    return { sourceHandle: 'top-out', targetHandle: 'bottom-in' };
  }

  return { sourceHandle: 'right-out', targetHandle: 'left-in' };
};

const resolveEdgePresentation = (source: string, target: string) => {
  if (target === 'Relay') {
    return {
      bubbleAnchor: 'mid',
      curvature: source === 'ACN SDK' ? 0.5 : source === 'IDM' ? 0.1 : 0.14
    };
  }

  if (source === 'Relay') {
    return {
      bubbleAnchor: 'mid',
      curvature: target === 'IDM' ? 0.1 : 0.14
    };
  }

  if (source === 'ACN Agent') {
    if (target === 'IDM') {
      return {
        bubbleAnchor: 'mid',
        curvature: 0.4
      };
    }

    if (gatewayNodes.has(target)) {
      return {
        bubbleAnchor: 'mid',
        curvature: gatewayCurvatures[target] ?? 0.18
      };
    }

    return {
      bubbleAnchor: 'mid',
      curvature: 0.18
    };
  }

  if (gatewayNodes.has(source)) {
    if (source === 'ARF' && target === 'IDM') {
      return {
        bubbleAnchor: 'mid',
        curvature: 0.36
      };
    }

    return {
      bubbleAnchor: 'mid',
      curvature: gatewayCurvatures[source] ?? 0.18
    };
  }

  if (source === 'IDM') {
    return {
      bubbleAnchor: 'mid',
      curvature: target === 'ACN SDK' ? 0.03 : gatewayCurvatures[target] ?? 0.18,
    };
  }

  if (source === 'ACN SDK') {
    if (target === 'ACN Agent') {
      return {
        bubbleAnchor: 'mid',
        curvature: 0.5
      };
    }

    return {
      bubbleAnchor: 'mid',
      curvature: target === 'IDM' ? 0.06 : gatewayCurvatures[target] ?? 0.18,
    };
  }

  return { bubbleAnchor: 'mid', curvature: 0.3 };
};

const resolveBubbleLaneGroup = (source: string, target: string) => {
  if (source === 'Relay' || target === 'Relay') {
    return 'relay-direct';
  }

  if (gatewayNodes.has(source) || gatewayNodes.has(target)) {
    if (source === 'ACN Agent' || target === 'ACN Agent') {
      return 'gateway-agent';
    }
    if (source === 'IDM' || target === 'IDM') {
      return 'gateway-idm';
    }
    if (source === 'ACN SDK' || target === 'ACN SDK') {
      return 'gateway-sdk';
    }
    return 'gateway-internal';
  }

  if ([source, target].includes('ACN Agent')) {
    return 'agent-external';
  }

  if ([source, target].includes('IDM')) {
    return 'idm-external';
  }

  return 'default';
};

const resolveBubblePlacementOverride = (edge: MessageFlowEdgeModel) => {
  const messageText = `${edge.lastMessage} ${edge.source} ${edge.target}`.toLowerCase();
  const isArfIdmEdge =
    (edge.source === 'ARF' && edge.target === 'IDM') ||
    (edge.source === 'IDM' && edge.target === 'ARF');
  const isVcVerification =
    messageText.includes('vc-verification') ||
    messageText.includes('vc-verifications') ||
    messageText.includes('vc-vertification') ||
    messageText.includes('vc-vertifications');

  if (!isVcVerification) {
    return isArfIdmEdge ? { bubbleOffsetY: -24 } : {};
  }

  return {
    bubbleAnchor: 'mid' as const,
    bubbleLaneOffset: 0,
    bubbleOffsetX: 130,
    bubbleOffsetY: isArfIdmEdge ? -110 : -86
  };
};

export const TopologyMap = ({
  nodes,
  edges,
  language
}: TopologyMapProps) => {
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance<TopologyFlowNode, Edge> | null>(null);
  const [interactive, setInteractive] = useState(false);
  const [displayNodes, setDisplayNodes] = useState<MessageFlowNodeModel[]>(nodes);
  const [displayEdges, setDisplayEdges] = useState<MessageFlowEdgeModel[]>(edges);
  const isZh = language === 'zh';
  const flowStage = useMemo(
    () => resolveFlowStage(displayEdges, isZh),
    [displayEdges, isZh]
  );

  useEffect(() => {
    setDisplayNodes(nodes);
    setDisplayEdges(edges);
  }, [edges, nodes]);

  const activeNodeRoles = useMemo(() => {
    const roleMap = new Map<string, 'source' | 'target' | 'both'>();

    displayEdges
      .filter((edge) => edge.active)
      .forEach((edge) => {
        const currentSource = roleMap.get(edge.source);
        roleMap.set(
          edge.source,
          currentSource === 'target' || currentSource === 'both' ? 'both' : 'source'
        );

        const currentTarget = roleMap.get(edge.target);
        roleMap.set(
          edge.target,
          currentTarget === 'source' || currentTarget === 'both' ? 'both' : 'target'
        );
      });

    return roleMap;
  }, [displayEdges]);

  const flowNodes = useMemo<TopologyFlowNode[]>(
    () => {
      const zoneNode: NetworkZoneNodeModel = {
        id: NETWORK_ZONE_NODE_ID,
        type: 'networkZone',
        position: { x: -570, y: -70 },
        draggable: false,
        selectable: false,
        focusable: false,
        data: {
          label: isZh ? '网络区域' : 'In-Network Zone'
        },
        style: {
          width: 2120,
          height: 860
        }
      };
      const agentGatewayZoneNode: NetworkZoneNodeModel = {
        id: AGENT_GW_ZONE_NODE_ID,
        type: 'networkZone',
        position: { x: 920, y: 112 },
        draggable: false,
        selectable: false,
        focusable: false,
        data: {
          label: 'AgentGW',
          variant: 'gateway'
        },
        style: {
          width: 540,
          height: 630
        }
      };
      const flowStageNode: FlowStageNodeModel = {
        id: '__flow-stage__',
        type: 'flowStage',
        position: { x: 115, y: -220 },
        draggable: false,
        selectable: false,
        focusable: false,
        data: {
          label: isZh ? '当前阶段' : 'Current Stage',
          title: flowStage.title,
          kind: flowStage.kind
        }
      };

      const systemNodes: SystemFlowNodeModelData[] = displayNodes.map((node) => ({
        id: node.id,
        type: 'systemFlow' as const,
        position: triangleLayout[node.name] ?? node.position,
        data: {
          ...node,
          compact: ['ARF', 'ACF', 'Relay'].includes(node.name),
          highlightRole: activeNodeRoles.get(node.id) ?? null
        } as SystemFlowNodeModelData['data']
      }));

      return [zoneNode, agentGatewayZoneNode, flowStageNode, ...systemNodes];
    },
    [activeNodeRoles, displayNodes, flowStage, isZh]
  );

  const flowEdges = useMemo<Edge[]>(
    () => {
      const laneIndexes = new Map<string, number>();

      return displayEdges.map((edge) => {
        const laneGroup = resolveBubbleLaneGroup(edge.source, edge.target);
        const laneIndex = laneIndexes.get(laneGroup) ?? 0;
        laneIndexes.set(laneGroup, laneIndex + 1);

        return {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          type: 'flowMessage',
          ...resolveHandles(edge.source, edge.target),
          animated: edge.active,
          data: {
            routeLabel: `${edge.source} → ${edge.target}`,
            messageLabel: edge.lastMessage,
            countLabel: isZh ? `${edge.count} 条消息` : `${edge.count} ${edge.count === 1 ? 'msg' : 'msgs'}`,
            active: edge.active,
            bubbleLaneOffset: BUBBLE_LANE_OFFSETS[laneIndex % BUBBLE_LANE_OFFSETS.length],
            ...resolveEdgePresentation(edge.source, edge.target),
            ...resolveBubblePlacementOverride(edge)
          },
          zIndex: edge.active ? 20 : 5,
          style: {
            strokeWidth: edge.active ? 3.6 : 2.2,
            strokeLinecap: 'round',
            stroke: edge.active ? '#06b6d4' : '#ef4444',
            opacity: edge.active ? 0.98 : 0.4,
            filter: edge.active
              ? 'drop-shadow(0 0 8px rgba(34, 211, 238, 0.2))'
              : 'drop-shadow(0 0 2px rgba(15, 23, 42, 0.08))'
          }
        };
      });
    },
    [displayEdges, isZh]
  );

  useEffect(() => {
    if (!flowInstance || flowNodes.length === 0) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      flowInstance.fitView({
        duration: 250,
        padding: 0.2,
      });
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [flowEdges.length, flowInstance, flowNodes.length]);

  return (
    <section className="glass-panel overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[color:var(--border-soft)] px-6 py-5">
        <div>
          <p className="panel-eyebrow">{isZh ? '拓扑图' : 'Topology Map'}</p>
          <h2 className="theme-title mt-2 text-2xl font-semibold">{isZh ? 'ACN 网络拓扑' : 'Topology of ACN Network'}</h2>
          <p className="theme-soft mt-1 text-sm">
            {isZh
              ? '将最近收到的 pipeline 日志聚合为 ACN Agent、ARF、ACF、Relay、IDM 与 ACN SDK 之间的实时消息路径。'
              : 'Recent pipeline logs are aggregated into live paths between ACN Agent, ARF, ACF, Relay, IDM, and ACN SDK.'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-medium">
          <span className="theme-badge-cyan rounded-full border px-3 py-1">
            {isZh ? `${edges.filter((edge) => edge.active).length} 条活动路径` : `${edges.filter((edge) => edge.active).length} active routes`}
          </span>
          <span className="theme-chip px-3 py-1">
            {isZh ? `${edges.reduce((total, edge) => total + edge.count, 0)} 条最近消息` : `${edges.reduce((total, edge) => total + edge.count, 0)} recent messages`}
          </span>
        </div>
      </header>

      <div className="rf-theme theme-topology-canvas w-full">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          className="h-full w-full"
          fitView
          fitViewOptions={{ padding: 0.24 }}
          onInit={(instance) => {
            setFlowInstance(instance);
            window.requestAnimationFrame(() => {
              instance.fitView({
                duration: 0,
                padding: 0.24
              });
            });
          }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={interactive}
          panOnDrag={interactive}
          zoomOnScroll={interactive}
          zoomOnPinch={interactive}
          zoomOnDoubleClick={interactive}
          minZoom={0.45}
          maxZoom={1.35}
          proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: 'flowMessage' }}
        >
          <Controls
            className="theme-rf-panel !overflow-hidden !rounded-2xl !border !shadow-panel"
            onInteractiveChange={setInteractive}
          />
          <Background
            gap={24}
            size={1}
            variant={BackgroundVariant.Dots}
            color="rgba(96, 165, 250, 0.22)"
          />
        </ReactFlow>
      </div>
    </section>
  );
};
