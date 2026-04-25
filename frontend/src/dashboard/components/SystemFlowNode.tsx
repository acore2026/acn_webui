import { Handle, Node, NodeProps, Position } from '@xyflow/react';
import { MessageFlowNodeModel } from '../types';
import { BotIcon, ControlIcon, NetworkIcon, SdkIcon } from './icons';

type FlowHighlightRole = 'source' | 'target' | 'both' | null;

type SystemFlowNodeData = Record<string, unknown> &
  MessageFlowNodeModel & {
    highlightRole?: FlowHighlightRole;
    activeCount?: number;
    compact?: boolean;
  };

export type SystemFlowNodeModelData = Node<SystemFlowNodeData, 'systemFlow'>;

const iconMap = {
  'ACN Agent': BotIcon,
  AgentGW: NetworkIcon,
  ARF: NetworkIcon,
  ACF: NetworkIcon,
  Relay: NetworkIcon,
  IDM: ControlIcon,
  'ACN SDK': SdkIcon
};

const toneMap = {
  'ACN Agent': 'agent',
  'ACN SDK': 'sdk',
  IDM: 'identity',
  ARF: 'repository',
  ACF: 'control',
  Relay: 'relay',
  AgentGW: 'gateway'
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
  const highlightRole = data.highlightRole ?? null;
  const isHighlighted = highlightRole !== null;
  const compact = Boolean(data.compact);
  const tone = toneMap[data.name as keyof typeof toneMap] ?? 'default';
  const highlightClass =
    highlightRole === 'both'
      ? 'theme-node-card-active-both'
      : highlightRole === 'source'
        ? 'theme-node-card-active-source'
        : highlightRole === 'target'
          ? 'theme-node-card-active-target'
          : '';

  return (
    <div
      className={[
        'theme-node-card flex flex-col rounded-3xl border shadow-panel backdrop-blur',
        `theme-flow-node-${tone}`,
        compact ? 'min-w-[190px] gap-4 p-5' : 'min-w-[280px] gap-4 p-6',
        highlightClass,
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
        id="left-top-out"
        type="source"
        position={Position.Left}
        className={hiddenHandleClass}
        style={{ top: '28%' }}
      />
      <Handle
        id="left-mid-out"
        type="source"
        position={Position.Left}
        className={hiddenHandleClass}
        style={{ top: '50%' }}
      />
      <Handle
        id="left-bottom-out"
        type="source"
        position={Position.Left}
        className={hiddenHandleClass}
        style={{ top: '72%' }}
      />
      <Handle
        id="right-out"
        type="source"
        position={Position.Right}
        className={hiddenHandleClass}
        style={{ top: '62%' }}
      />
      <Handle
        id="right-top-out"
        type="source"
        position={Position.Right}
        className={hiddenHandleClass}
        style={{ top: '28%' }}
      />
      <Handle
        id="right-mid-out"
        type="source"
        position={Position.Right}
        className={hiddenHandleClass}
        style={{ top: '50%' }}
      />
      <Handle
        id="right-bottom-out"
        type="source"
        position={Position.Right}
        className={hiddenHandleClass}
        style={{ top: '72%' }}
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

      <div className="flex items-start justify-between gap-4">
        <div
          className={[
            'theme-accent-icon flex items-center justify-center rounded-2xl transition',
            compact ? 'h-12 w-12' : 'h-16 w-16',
            isHighlighted ? 'scale-[1.04] shadow-[0_0_0_4px_rgba(34,211,238,0.12)]' : ''
          ].join(' ')}
        >
          <Icon className={compact ? 'h-6 w-6' : 'h-8 w-8'} />
        </div>
        <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 font-semibold uppercase tracking-[0.2em] ${compact ? 'text-[10px]' : 'text-xs'} ${status.pill}`}>
          <span className={`${compact ? 'h-1.5 w-1.5' : 'h-2 w-2'} rounded-full ${status.dot}`} />
          {data.status}
        </span>
      </div>

      <div className="flex flex-col gap-1">
        <h4 className={`theme-title font-medium leading-tight ${compact ? 'text-2xl tracking-[0.08em]' : 'text-3xl tracking-[0.02em]'}`}>
          {data.name}
        </h4>
        {isHighlighted ? (
          <span
            className={[
              'mt-2 w-fit rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em]',
              highlightRole === 'both'
                ? 'theme-badge-cyan'
                : highlightRole === 'source'
                  ? 'theme-badge-amber'
                  : 'theme-badge-emerald'
            ].join(' ')}
          >
            {highlightRole === 'both'
              ? 'in/out'
              : highlightRole === 'source'
                ? 'out'
                : 'in'}
          </span>
        ) : null}
      </div>
    </div>
  );
};
