import { BaseEdge, EdgeLabelRenderer, EdgeProps, Position } from '@xyflow/react';

type FlowMessageEdgeData = {
  routeLabel: string;
  messageLabel?: string;
  countLabel: string;
  active?: boolean;
  bubbleOffsetY?: number;
  bubbleOffsetX?: number;
  curvature?: number;
  bundleOffset?: number;
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

const resolveControlPoint = (
  x: number,
  y: number,
  position: Position,
  distance: number,
  bundleOffset: number
) => {
  switch (position) {
    case Position.Left:
      return { x: x - distance, y: y + bundleOffset };
    case Position.Right:
      return { x: x + distance, y: y + bundleOffset };
    case Position.Top:
      return { x: x + bundleOffset, y: y - distance };
    case Position.Bottom:
      return { x: x + bundleOffset, y: y + distance };
    default:
      return { x, y };
  }
};

const resolveBezierPoint = (
  start: number,
  controlA: number,
  controlB: number,
  end: number,
  t: number
) =>
  (1 - t) ** 3 * start +
  3 * (1 - t) ** 2 * t * controlA +
  3 * (1 - t) * t ** 2 * controlB +
  t ** 3 * end;

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
  const curvature = edgeData.curvature ?? 0.35;
  const bundleOffset = edgeData.bundleOffset ?? 0;
  const axisDistance = Math.max(Math.abs(targetX - sourceX), Math.abs(targetY - sourceY), 120);
  const controlDistance = Math.max(48, axisDistance * curvature);
  const sourceControl = resolveControlPoint(
    sourceX,
    sourceY,
    sourcePosition,
    controlDistance,
    bundleOffset
  );
  const targetControl = resolveControlPoint(
    targetX,
    targetY,
    targetPosition,
    controlDistance,
    bundleOffset
  );
  const edgePath = `M ${sourceX},${sourceY} C ${sourceControl.x},${sourceControl.y} ${targetControl.x},${targetControl.y} ${targetX},${targetY}`;
  const labelX = resolveBezierPoint(sourceX, sourceControl.x, targetControl.x, targetX, 0.5);
  const labelY = resolveBezierPoint(sourceY, sourceControl.y, targetControl.y, targetY, 0.5);

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
      {edgeData.active ? (
        <path
          d={edgePath}
          className="theme-topology-edge-direction"
          style={{
            stroke: typeof style?.stroke === 'string' ? style.stroke : '#06b6d4'
          }}
        />
      ) : null}
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
