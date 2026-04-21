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
import { SignalIcon } from './icons';
import { NetworkZoneNode, NetworkZoneNodeModel } from './NetworkZoneNode';
import { SystemFlowNode, SystemFlowNodeModelData } from './SystemFlowNode';

interface TopologyMapProps {
  nodes: MessageFlowNodeModel[];
  edges: MessageFlowEdgeModel[];
  language: LanguageMode;
  testFlowBusy: boolean;
  testFlowPaused: boolean;
  testFlowMessage: string | null;
  testFlowSpeed: number;
  onTestFlowSpeedChange: (speed: number) => void;
  onToggleTestFlowPause: () => Promise<void>;
  onRunTestFlow: () => Promise<void>;
}

const nodeTypes = {
  systemFlow: SystemFlowNode,
  networkZone: NetworkZoneNode
};

const edgeTypes: EdgeTypes = {
  flowMessage: FlowMessageEdge
};
const NETWORK_ZONE_NODE_ID = '__network-zone__';

const triangleLayout: Record<string, { x: number; y: number }> = {
  'ACN Agent': { x: -280, y: 300 },
  IDM: { x: 260, y: 80 },
  AgentGW: { x: 820, y: 300 },
  'ACN SDK': { x: 260, y: 590 }
};

const resolveHandles = (
  source: string,
  target: string
): Pick<Edge, 'sourceHandle' | 'targetHandle'> => {
  if (source === 'ACN Agent' && target === 'AgentGW') {
    return { sourceHandle: 'right-mid-out', targetHandle: 'left-mid-in' };
  }

  if (source === 'AgentGW' && target === 'ACN Agent') {
    return { sourceHandle: 'bottom-out', targetHandle: 'bottom-in' };
  }

  if (source === 'AgentGW' && target === 'IDM') {
    return { sourceHandle: 'top-out', targetHandle: 'right-in' };
  }

  if (source === 'IDM' && target === 'AgentGW') {
    return { sourceHandle: 'right-out', targetHandle: 'top-in' };
  }

  if (source === 'ACN Agent' && target === 'IDM') {
    return { sourceHandle: 'right-out', targetHandle: 'left-in' };
  }

  if (source === 'IDM' && target === 'ACN Agent') {
    return { sourceHandle: 'left-out', targetHandle: 'right-in' };
  }

  if (source === 'AgentGW' && target === 'ACN SDK') {
    return { sourceHandle: 'left-out', targetHandle: 'right-in' };
  }

  if (source === 'ACN SDK' && target === 'AgentGW') {
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

    if (target === 'AgentGW') {
      return {
        bubbleAnchor: 'source',
        bubbleTail: 'bottom',
        bubbleOffsetX: -50,
        bubbleOffsetY: -40,
        curvature: 0.18
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

  if (source === 'AgentGW') {
    const verticalOffsets: Record<string, number> = {
      IDM: -72,
      'ACN Agent': 0,
      'ACN SDK': 72
    };

    return {
      bubbleAnchor: 'source',
      bubbleTail: 'left',
      bubbleOffsetY: verticalOffsets[target] ?? 0,
      curvature: 0.18
    };
  }

  if (source === 'IDM') {
    const horizontalOffsets: Record<string, number> = {
      'ACN Agent': -124,
      'ACN SDK': 0,
      AgentGW: 124
    };

    return {
      bubbleAnchor: 'source',
      bubbleTail: 'bottom',
      bubbleOffsetX: horizontalOffsets[target] ?? 0,
      curvature: target === 'ACN SDK' ? 0.03 : 0.18
    };
  }

  if (source === 'ACN SDK') {
    const horizontalOffsets: Record<string, number> = {
      'ACN Agent': -124,
      IDM: 0,
      AgentGW: 124
    };

    return {
      bubbleAnchor: 'source',
      bubbleTail: 'top',
      bubbleOffsetX: horizontalOffsets[target] ?? 0,
      curvature: target === 'IDM' ? 0.06 : 0.18
    };
  }

  return { bubbleAnchor: 'mid', bubbleOffsetY: -24, curvature: 0.3 };
};

export const TopologyMap = ({
  nodes,
  edges,
  language,
  testFlowBusy,
  testFlowPaused,
  testFlowMessage,
  testFlowSpeed,
  onTestFlowSpeedChange,
  onToggleTestFlowPause,
  onRunTestFlow
}: TopologyMapProps) => {
  const [flowInstance, setFlowInstance] = useState<ReactFlowInstance | null>(null);
  const [interactive, setInteractive] = useState(true);
  const [displayNodes, setDisplayNodes] = useState<MessageFlowNodeModel[]>(nodes);
  const [displayEdges, setDisplayEdges] = useState<MessageFlowEdgeModel[]>(edges);
  const isZh = language === 'zh';

  useEffect(() => {
    if (!testFlowPaused) {
      setDisplayNodes(nodes);
      setDisplayEdges(edges);
    }
  }, [edges, nodes, testFlowPaused]);

  const flowNodes = useMemo<Array<SystemFlowNodeModelData | NetworkZoneNodeModel>>(
    () => {
      const zoneNode: NetworkZoneNodeModel = {
        id: NETWORK_ZONE_NODE_ID,
        type: 'networkZone',
        position: { x: -360, y: 20 },
        draggable: false,
        selectable: false,
        focusable: false,
        data: {
          label: isZh ? '网络区域' : 'In-Network Zone'
        },
        style: {
          width: 1460,
          height: 500
        }
      };

      const systemNodes: SystemFlowNodeModelData[] = displayNodes.map((node) => ({
        id: node.id,
        type: 'systemFlow' as const,
        position: triangleLayout[node.name] ?? node.position,
        data: { ...node } as SystemFlowNodeModelData['data']
      }));

      return [zoneNode, ...systemNodes];
    },
    [displayNodes, isZh]
  );

  const flowEdges = useMemo<Edge[]>(
    () =>
      displayEdges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: 'flowMessage',
        ...resolveHandles(edge.source, edge.target),
        animated: edge.active && !testFlowPaused,
        data: {
          routeLabel: `${edge.source} → ${edge.target}`,
          messageLabel: edge.lastMessage,
          countLabel: isZh ? `${edge.count} 条消息` : `${edge.count} ${edge.count === 1 ? 'msg' : 'msgs'}`,
          active: edge.active,
          ...resolveEdgePresentation(edge.source, edge.target)
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 22,
          height: 22,
          color: edge.active ? '#0891b2' : '#dc2626'
        },
        style: {
          strokeWidth: edge.active ? 3 : 2.4,
          strokeLinecap: 'round',
          stroke: edge.active ? '#0891b2' : '#dc2626'
        }
      })),
    [displayEdges, isZh, testFlowPaused]
  );

  useEffect(() => {
    if (!flowInstance || flowNodes.length === 0 || testFlowPaused) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      flowInstance.fitView({
        duration: 250,
        padding: 0.2,
      });
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [flowEdges.length, flowInstance, flowNodes.length, testFlowPaused]);

  return (
    <section className="glass-panel overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[color:var(--border-soft)] px-6 py-5">
        <div>
          <p className="panel-eyebrow">{isZh ? '拓扑图' : 'Topology Map'}</p>
          <h2 className="theme-title mt-2 text-2xl font-semibold">{isZh ? 'React Flow 消息路径' : 'React Flow Message Paths'}</h2>
          <p className="theme-soft mt-1 text-sm">
            {isZh
              ? '将最近收到的 pipeline 日志聚合为 ACN Agent、AgentGW、IDM 与 ACN SDK 之间的实时消息路径。'
              : 'Recent pipeline logs are aggregated into live paths between ACN Agent, AgentGW, IDM, and ACN SDK.'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-medium">
          <label className="theme-top-button cursor-default px-4 py-2 text-xs font-semibold">
            <span className="theme-muted">
              {isZh ? '测试速度' : 'Test Speed'}
            </span>
            <select
              value={testFlowSpeed}
              onChange={(event) => onTestFlowSpeedChange(Number(event.target.value))}
              disabled={testFlowBusy}
              className="ml-2 rounded-xl border border-[color:var(--border-soft)] bg-[color:var(--surface-strong)] px-2 py-1 text-xs text-[color:var(--text-main)] outline-none"
            >
              {[0.1, 0.25, 0.5, 0.75, 1, 1.25, 1.5, 2].map((speed) => (
                <option key={speed} value={speed}>
                  {speed.toFixed(speed < 1 ? 2 : speed % 1 === 0 ? 1 : 2)}x
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => {
              void onToggleTestFlowPause();
            }}
            disabled={!testFlowBusy}
            className={[
              'theme-top-button px-4 py-2 text-xs font-semibold',
              !testFlowBusy ? 'cursor-not-allowed opacity-50' : ''
            ].join(' ')}
          >
            {testFlowPaused
              ? (isZh ? '继续测试流' : 'Resume Flow')
              : (isZh ? '暂停测试流' : 'Pause Flow')}
          </button>
          <button
            type="button"
            onClick={() => {
              void onRunTestFlow();
            }}
            disabled={testFlowBusy}
            className={[
              'theme-top-button px-4 py-2 text-xs font-semibold',
              testFlowBusy ? 'cursor-wait opacity-70' : ''
            ].join(' ')}
          >
            <span className="theme-accent-icon flex h-8 w-8 items-center justify-center rounded-2xl">
              <SignalIcon className="h-4 w-4" />
            </span>
            {testFlowBusy ? (isZh ? '注入中...' : 'Injecting...') : (isZh ? '运行测试流' : 'Run Test Flow')}
          </button>
          <span className="theme-badge-cyan rounded-full border px-3 py-1">
            {isZh ? `${edges.filter((edge) => edge.active).length} 条活动路径` : `${edges.filter((edge) => edge.active).length} active routes`}
          </span>
          <span className="theme-chip px-3 py-1">
            {isZh ? `${edges.reduce((total, edge) => total + edge.count, 0)} 条最近消息` : `${edges.reduce((total, edge) => total + edge.count, 0)} recent messages`}
          </span>
        </div>
      </header>

      {testFlowMessage ? (
        <div className="border-b border-[color:var(--border-soft)] px-6 py-3">
          <div className="flex flex-wrap gap-2">
            {testFlowMessage ? (
              <span className="theme-chip inline-flex rounded-full px-3 py-1 text-xs font-medium">
                {testFlowMessage}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="rf-theme theme-topology-canvas w-full">
        <ReactFlow
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          className="h-full w-full"
          fitView
          fitViewOptions={{ padding: 0.24 }}
          onInit={setFlowInstance}
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
