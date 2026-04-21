import { Handle, Node, NodeProps, Position } from '@xyflow/react';
import { MessageFlowNodeModel } from '../types';
import { BotIcon, ControlIcon, NetworkIcon, SdkIcon } from './icons';

type SystemFlowNodeData = Record<string, unknown> & MessageFlowNodeModel;

export type SystemFlowNodeModelData = Node<SystemFlowNodeData, 'systemFlow'>;

const iconMap = {
  'ACN Agent': BotIcon,
  AgentGW: NetworkIcon,
  IDM: ControlIcon,
  'ACN SDK': SdkIcon
};

const statusStyles = {
  online: {
    dot: 'bg-emerald-400',
    pill: 'theme-badge-emerald'
  },
  offline: {
    dot: 'bg-rose-400',
    pill: 'theme-badge-rose'
  }
};

const hiddenHandleClass =
  '!h-2 !w-2 !border-0 !bg-transparent !opacity-0';

export const SystemFlowNode = ({ data, selected }: NodeProps<SystemFlowNodeModelData>) => {
  const Icon = iconMap[data.name as keyof typeof iconMap] ?? NetworkIcon;
  const status = statusStyles[data.status];

  return (
    <div
      className={[
        'theme-node-card min-w-[220px] rounded-3xl border px-5 py-5 shadow-panel backdrop-blur',
        selected ? 'border-cyan-300/50 ring-1 ring-cyan-300/40' : ''
      ].join(' ')}
    >
      <Handle
        id="left-in"
        type="target"
        position={Position.Left}
        className={hiddenHandleClass}
        style={{ top: '38%' }}
      />
      <Handle
        id="left-mid-in"
        type="target"
        position={Position.Left}
        className={hiddenHandleClass}
        style={{ top: '50%' }}
      />
      <Handle
        id="right-in"
        type="target"
        position={Position.Right}
        className={hiddenHandleClass}
        style={{ top: '38%' }}
      />
      <Handle
        id="right-mid-in"
        type="target"
        position={Position.Right}
        className={hiddenHandleClass}
        style={{ top: '50%' }}
      />
      <Handle
        id="top-in"
        type="target"
        position={Position.Top}
        className={hiddenHandleClass}
        style={{ left: '38%' }}
      />
      <Handle
        id="bottom-in"
        type="target"
        position={Position.Bottom}
        className={hiddenHandleClass}
        style={{ left: '62%' }}
      />
      <Handle
        id="left-out"
        type="source"
        position={Position.Left}
        className={hiddenHandleClass}
        style={{ top: '62%' }}
      />
      <Handle
        id="left-mid-out"
        type="source"
        position={Position.Left}
        className={hiddenHandleClass}
        style={{ top: '50%' }}
      />
      <Handle
        id="right-out"
        type="source"
        position={Position.Right}
        className={hiddenHandleClass}
        style={{ top: '62%' }}
      />
      <Handle
        id="right-mid-out"
        type="source"
        position={Position.Right}
        className={hiddenHandleClass}
        style={{ top: '50%' }}
      />
      <Handle
        id="top-out"
        type="source"
        position={Position.Top}
        className={hiddenHandleClass}
        style={{ left: '62%' }}
      />
      <Handle
        id="bottom-out"
        type="source"
        position={Position.Bottom}
        className={hiddenHandleClass}
        style={{ left: '38%' }}
      />

      <div className="flex items-start justify-between gap-3">
        <div className="theme-accent-icon flex h-12 w-12 items-center justify-center rounded-2xl">
          <Icon className="h-6 w-6" />
        </div>
        <span className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.2em] ${status.pill}`}>
          <span className={`h-2 w-2 rounded-full ${status.dot}`} />
          {data.status}
        </span>
      </div>

      <div className="mt-4">
        <h4 className="theme-title text-lg font-semibold">{data.name}</h4>
        <p className="theme-soft mt-1 text-sm">
          {data.name === 'ACN Agent' && 'Execution runtime and agent-side requests'}
          {data.name === 'AgentGW' && 'ARF and ACF coordination hub'}
          {data.name === 'IDM' && 'Identity verification service'}
          {data.name === 'ACN SDK' && 'Client-side request origin and response consumer'}
        </p>
      </div>
    </div>
  );
};
