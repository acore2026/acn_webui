import { useEffect, useMemo, useState } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  EdgeTypes,
  MarkerType,
  ReactFlow,
  ReactFlowInstance
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { LanguageMode } from '../i18n';
import { MessageFlowEdgeModel, MessageFlowNodeModel } from '../types';
import { FlowMessageEdge } from './FlowMessageEdge';
import { NetworkZoneNode, NetworkZoneNodeModel } from './NetworkZoneNode';
import { SystemFlowNode, SystemFlowNodeModelData } from './SystemFlowNode';

type TopologyFlowNode = SystemFlowNodeModelData | NetworkZoneNodeModel;

interface TopologyMapProps {
  nodes: MessageFlowNodeModel[];
  edges: MessageFlowEdgeModel[];
  language: LanguageMode;
}

const nodeTypes = {
  systemFlow: SystemFlowNode,
  networkZone: NetworkZoneNode
};

const edgeTypes: EdgeTypes = {
  flowMessage: FlowMessageEdge
};
const NETWORK_ZONE_NODE_ID = '__network-zone__';
const AGENT_GW_ZONE_NODE_ID = '__agent-gw-zone__';

const triangleLayout: Record<string, { x: number; y: number }> = {
  'ACN Agent': { x: -280, y: 300 },
  IDM: { x: 260, y: 80 },
  ARF: { x: 820, y: 120 },
  ACF: { x: 820, y: 300 },
  Relay: { x: 820, y: 480 },
  AgentGW: { x: 820, y: 300 },
  'ACN SDK': { x: 260, y: 610 }
};

const gatewayNodes = new Set(['ARF', 'ACF', 'Relay', 'AgentGW']);
const gatewayBundleOffsets: Record<string, number> = {
  ARF: -35,
  ACF: 0,
  Relay: 35,
  AgentGW: 0
};
const gatewayCurvatures: Record<string, number> = {
  ARF: 0.15,
  ACF: 0.18,
  Relay: 0.21,
  AgentGW: 0.18
};

const resolveGatewayLaneHandle = (name: string, side: 'left' | 'right') => {
  const prefix = side === 'left' ? 'left' : 'right';

  if (name === 'ARF') {
    return `${prefix}-top-out`;
  }

  if (name === 'Relay') {
    return `${prefix}-bottom-out`;
  }

  return `${prefix}-mid-out`;
};

const resolveHandles = (
  source: string,
  target: string
): Pick<Edge, 'sourceHandle' | 'targetHandle'> => {
  if (source === 'ACN Agent' && gatewayNodes.has(target)) {
    return {
      sourceHandle: resolveGatewayLaneHandle(target, 'right'),
      targetHandle: 'left-mid-in'
    };
  }

  if (gatewayNodes.has(source) && target === 'ACN Agent') {
    return {
      sourceHandle: 'bottom-out',
      targetHandle: 'bottom-in'
    };
  }

  if (gatewayNodes.has(source) && target === 'IDM') {
    return {
      sourceHandle: 'top-out',
      targetHandle: 'right-in'
    };
  }

  if (source === 'IDM' && gatewayNodes.has(target)) {
    return {
      sourceHandle: resolveGatewayLaneHandle(target, 'right'),
      targetHandle: 'top-in'
    };
  }

  if (source === 'ACN Agent' && target === 'IDM') {
    return { sourceHandle: 'right-out', targetHandle: 'left-in' };
  }

  if (source === 'IDM' && target === 'ACN Agent') {
    return { sourceHandle: 'left-out', targetHandle: 'right-in' };
  }

  if (gatewayNodes.has(source) && target === 'ACN SDK') {
    return {
      sourceHandle: resolveGatewayLaneHandle(source, 'left'),
      targetHandle: 'right-in'
    };
  }

  if (source === 'ACN SDK' && gatewayNodes.has(target)) {
    return { sourceHandle: 'right-out', targetHandle: 'left-in' };
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
  if (source === 'ACN Agent') {
    if (target === 'IDM') {
      return {
        bubbleAnchor: 'source',
        bubbleTail: 'bottom',
        bubbleOffsetX: -50,
        bubbleOffsetY: -40,
        curvature: 0.18
      };
    }

    if (gatewayNodes.has(target)) {
      return {
        bubbleAnchor: 'source',
        bubbleTail: 'bottom',
        bubbleOffsetX: -50,
        bubbleOffsetY: -40,
        curvature: gatewayCurvatures[target] ?? 0.18,
        bundleOffset: gatewayBundleOffsets[target] ?? 0
      };
    }

    const verticalOffsets: Record<string, number> = {
      'ACN SDK': 72
    };

    return {
      bubbleAnchor: 'source',
      bubbleTail: 'right',
      bubbleOffsetY: verticalOffsets[target] ?? 0,
      curvature: 0.18
    };
  }

  if (gatewayNodes.has(source)) {
    const verticalOffsets: Record<string, number> = {
      IDM: -72,
      'ACN Agent': 0,
      'ACN SDK': 72
    };

    return {
      bubbleAnchor: 'source',
      bubbleTail: 'left',
      bubbleOffsetY: verticalOffsets[target] ?? 0,
      curvature: gatewayCurvatures[source] ?? 0.18,
      bundleOffset: gatewayBundleOffsets[source] ?? 0
    };
  }

  if (source === 'IDM') {
    const horizontalOffsets: Record<string, number> = {
      'ACN Agent': -124,
      'ACN SDK': 0,
      ARF: 124,
      ACF: 124,
      Relay: 124,
      AgentGW: 124
    };

    return {
      bubbleAnchor: 'source',
      bubbleTail: 'bottom',
      bubbleOffsetX: horizontalOffsets[target] ?? 0,
      curvature: target === 'ACN SDK' ? 0.03 : gatewayCurvatures[target] ?? 0.18,
      bundleOffset: gatewayBundleOffsets[target] ?? 0
    };
  }

  if (source === 'ACN SDK') {
    const horizontalOffsets: Record<string, number> = {
      'ACN Agent': -124,
      IDM: 0,
      ARF: 124,
      ACF: 124,
      Relay: 124,
      AgentGW: 124
    };

    return {
      bubbleAnchor: 'source',
      bubbleTail: 'top',
      bubbleOffsetX: horizontalOffsets[target] ?? 0,
      curvature: target === 'IDM' ? 0.06 : gatewayCurvatures[target] ?? 0.18,
      bundleOffset: gatewayBundleOffsets[target] ?? 0
    };
  }

  return { bubbleAnchor: 'mid', bubbleOffsetY: -24, curvature: 0.3 };
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
        position: { x: -350, y: 30 },
        draggable: false,
        selectable: false,
        focusable: false,
        data: {
          label: isZh ? '网络区域' : 'In-Network Zone'
        },
        style: {
          width: 1500,
          height: 760
        }
      };
      const agentGatewayZoneNode: NetworkZoneNodeModel = {
        id: AGENT_GW_ZONE_NODE_ID,
        type: 'networkZone',
        position: { x: 780, y: 62 },
        draggable: false,
        selectable: false,
        focusable: false,
        data: {
          label: 'AgentGW',
          variant: 'gateway'
        },
        style: {
          width: 300,
          height: 630
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

      return [zoneNode, agentGatewayZoneNode, ...systemNodes];
    },
    [activeNodeRoles, displayNodes, isZh]
  );

  const flowEdges = useMemo<Edge[]>(
    () =>
      displayEdges.map((edge) => ({
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
          ...resolveEdgePresentation(edge.source, edge.target)
        },
        zIndex: edge.active ? 20 : 5,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: edge.active ? 22 : 18,
          height: edge.active ? 22 : 18,
          color: edge.active ? '#06b6d4' : '#ef4444'
        },
        style: {
          strokeWidth: edge.active ? 3.6 : 2.2,
          strokeLinecap: 'round',
          stroke: edge.active ? '#06b6d4' : '#ef4444',
          opacity: edge.active ? 0.98 : 0.4,
          filter: edge.active
            ? 'drop-shadow(0 0 8px rgba(34, 211, 238, 0.2))'
            : 'drop-shadow(0 0 2px rgba(15, 23, 42, 0.08))'
        }
      })),
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
          <h2 className="theme-title mt-2 text-2xl font-semibold">{isZh ? 'React Flow 消息路径' : 'React Flow Message Paths'}</h2>
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
