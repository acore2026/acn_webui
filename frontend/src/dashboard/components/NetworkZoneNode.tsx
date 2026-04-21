import { Node, NodeProps } from '@xyflow/react';

type NetworkZoneNodeData = {
  label: string;
};

export type NetworkZoneNodeModel = Node<NetworkZoneNodeData, 'networkZone'>;

export const NetworkZoneNode = ({ data }: NodeProps<NetworkZoneNodeModel>) => (
  <div className="theme-network-zone">
    <div className="theme-network-zone-label">{data.label}</div>
  </div>
);
