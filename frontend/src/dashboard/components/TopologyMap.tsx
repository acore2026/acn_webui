import { useMemo } from 'react';
import {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  MiniMap,
  ReactFlow
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { TopologyAgentModel, TopologyLinkModel } from '../types';
import { AgentFlowNode, AgentNode } from './AgentNode';

interface TopologyMapProps {
  agents: TopologyAgentModel[];
  links: TopologyLinkModel[];
}

const nodeTypes = {
  agent: AgentNode
};

export const TopologyMap = ({ agents, links }: TopologyMapProps) => {
  const nodes = useMemo<AgentFlowNode[]>(
    () =>
      agents.map((agent) => ({
        id: agent.id,
        type: 'agent',
        position: agent.position,
        data: { ...agent } as AgentFlowNode['data']
      })),
    [agents]
  );

  const edges = useMemo<Edge[]>(
    () =>
      links.map((link) => ({
        id: link.id,
        source: link.source,
        target: link.target,
        type: 'smoothstep',
        animated: link.active,
        label: link.latency,
        labelStyle: {
          fill: '#cbd5f5',
          fontWeight: 600,
          fontSize: 12
        },
        labelBgPadding: [8, 4],
        labelBgBorderRadius: 999,
        labelBgStyle: {
          fill: 'rgba(15, 23, 42, 0.94)',
          stroke: link.active ? 'rgba(34, 211, 238, 0.3)' : 'rgba(248, 113, 113, 0.22)'
        },
        style: {
          strokeWidth: link.active ? 2.4 : 2,
          stroke: link.active ? '#22d3ee' : '#f87171'
        }
      })),
    [links]
  );

  return (
    <section className="glass-panel flex h-full min-h-[480px] flex-col overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[color:var(--border-soft)] px-6 py-5">
        <div>
          <p className="panel-eyebrow">Topology Map</p>
          <h2 className="theme-title mt-2 text-2xl font-semibold">React Flow Agent Mesh</h2>
          <p className="theme-soft mt-1 text-sm">
            Live routes show animated streams, while edge labels expose current node-to-node latency.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-medium">
          <span className="theme-badge-cyan rounded-full border px-3 py-1">
            {links.filter((link) => link.active).length} active streams
          </span>
          <span className="theme-chip px-3 py-1">
            {agents.length} agents visualized
          </span>
        </div>
      </header>

      <div className="rf-theme flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.45}
          maxZoom={1.35}
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{ type: 'smoothstep' }}
        >
          <MiniMap
            pannable
            zoomable
            nodeStrokeColor={(node) => {
              const status = (node.data as unknown as TopologyAgentModel | undefined)?.status;

              if (status === 'busy') {
                return '#fbbf24';
              }

              if (status === 'offline') {
                return '#fb7185';
              }

              return '#34d399';
            }}
            nodeColor={(node) => {
              const status = (node.data as unknown as TopologyAgentModel | undefined)?.status;

              if (status === 'busy') {
                return 'rgba(251,191,36,0.25)';
              }

              if (status === 'offline') {
                return 'rgba(244,63,94,0.2)';
              }

              return 'rgba(45,212,191,0.25)';
            }}
            maskColor="rgba(2, 6, 23, 0.75)"
            className="theme-rf-panel !rounded-2xl !border"
          />
          <Controls className="theme-rf-panel !overflow-hidden !rounded-2xl !border !shadow-panel" />
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
