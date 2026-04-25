import { Node, NodeProps } from '@xyflow/react';

type NetworkZoneNodeData = {
  label: string;
  variant?: 'network' | 'gateway';
};

export type NetworkZoneNodeModel = Node<NetworkZoneNodeData, 'networkZone'>;

export const NetworkZoneNode = ({ data }: NodeProps<NetworkZoneNodeModel>) => (
  <div
    className={[
      'theme-network-zone',
      data.variant === 'gateway' ? 'theme-gateway-zone' : ''
    ].join(' ')}
  >
    <div className="theme-network-zone-label">{data.label}</div>
  </div>
);
