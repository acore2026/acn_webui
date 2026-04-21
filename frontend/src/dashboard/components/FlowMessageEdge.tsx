import { BaseEdge, EdgeLabelRenderer, EdgeProps, getBezierPath } from '@xyflow/react';

type FlowMessageEdgeData = {
  routeLabel: string;
  messageLabel?: string;
  countLabel: string;
  active?: boolean;
  bubbleOffsetY?: number;
  bubbleOffsetX?: number;
  curvature?: number;
  bubbleAnchor?: 'source' | 'target' | 'mid';
  bubbleTail?: 'left' | 'right' | 'top' | 'bottom';
};

const resolveBaseBubbleOffset = (tail?: FlowMessageEdgeData['bubbleTail']) => {
  switch (tail) {
    case 'left':
      return { x: 156, y: 0 };
    case 'right':
      return { x: -156, y: 0 };
    case 'top':
      return { x: 0, y: 108 };
    case 'bottom':
      return { x: 0, y: -108 };
    default:
      return { x: 0, y: -22 };
  }
};

export const FlowMessageEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
  data,
}: EdgeProps) => {
  const edgeData = (data ?? {}) as FlowMessageEdgeData;
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: edgeData.curvature ?? 0.35,
  });

  const anchorX =
    edgeData.bubbleAnchor === 'source'
      ? sourceX
      : edgeData.bubbleAnchor === 'target'
        ? targetX
        : labelX;
  const anchorY =
    edgeData.bubbleAnchor === 'source'
      ? sourceY
      : edgeData.bubbleAnchor === 'target'
        ? targetY
        : labelY;
  const baseOffset = resolveBaseBubbleOffset(edgeData.bubbleTail);

  return (
    <>
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style} />
      {edgeData.routeLabel ? (
        <EdgeLabelRenderer>
          <div
            className={[
              'theme-rf-edge-bubble nodrag nopan',
              edgeData.bubbleTail
                ? `theme-rf-edge-bubble--tail-${edgeData.bubbleTail}`
                : '',
            ].join(' ')}
            style={{
              transform: `translate(-50%, -50%) translate(${anchorX + baseOffset.x + (edgeData.bubbleOffsetX ?? 0)}px, ${anchorY + baseOffset.y + (edgeData.bubbleOffsetY ?? 0)}px)`,
            }}
          >
            {edgeData.messageLabel ? (
              <div className="theme-rf-edge-bubble-message">{edgeData.messageLabel}</div>
            ) : null}
            <div className="theme-rf-edge-bubble-route">{edgeData.routeLabel}</div>
            <div className="theme-rf-edge-bubble-count">{edgeData.countLabel}</div>
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
};
