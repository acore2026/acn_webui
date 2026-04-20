import { Handle, Node, NodeProps, Position } from '@xyflow/react';
import { TopologyAgentModel } from '../types';
import { BotIcon } from './icons';

type AgentNodeData = Record<string, unknown> & TopologyAgentModel;

export type AgentFlowNode = Node<AgentNodeData, 'agent'>;

const statusStyles = {
  online: {
    dot: 'bg-emerald-400',
    pill: 'theme-badge-emerald'
  },
  busy: {
    dot: 'bg-amber-400',
    pill: 'theme-badge-amber'
  },
  offline: {
    dot: 'bg-rose-400',
    pill: 'theme-badge-rose'
  }
};

export const AgentNode = ({ data, selected }: NodeProps<AgentFlowNode>) => {
  const status = statusStyles[data.status];

  return (
    <div
      className={[
        'theme-node-card min-w-[220px] rounded-3xl border px-4 py-4 shadow-panel backdrop-blur',
        selected ? 'border-cyan-300/50 ring-1 ring-cyan-300/40' : ''
      ].join(' ')}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-3 !w-3 !border-2 !border-slate-950 !bg-cyan-300"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-3 !w-3 !border-2 !border-slate-950 !bg-cyan-300"
      />

      <div className="flex items-start justify-between gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-400/20 to-blue-500/20 text-cyan-200">
          <BotIcon className="h-6 w-6" />
        </div>
        <span className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.2em] ${status.pill}`}>
          <span className={`h-2 w-2 rounded-full ${status.dot}`} />
          {data.status}
        </span>
      </div>

      <div className="mt-4">
        <h4 className="theme-title text-base font-semibold">{data.name}</h4>
        <p className="theme-soft mt-1 text-sm">{data.role}</p>
      </div>

      <dl className="theme-soft mt-4 grid grid-cols-2 gap-3 text-xs">
        <div className="theme-subtle-card p-3">
          <dt className="theme-muted uppercase tracking-[0.18em]">Region</dt>
          <dd className="theme-copy mt-1 text-sm font-medium">{data.region}</dd>
        </div>
        <div className="theme-subtle-card p-3">
          <dt className="theme-muted uppercase tracking-[0.18em]">Throughput</dt>
          <dd className="theme-copy mt-1 text-sm font-medium">{data.throughput}</dd>
        </div>
      </dl>
    </div>
  );
};
