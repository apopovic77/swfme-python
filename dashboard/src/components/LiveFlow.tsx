import { useEffect, useMemo, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  useEdgesState,
  useNodesState,
} from 'reactflow';
import type { Edge, Node, NodeProps } from 'reactflow';
import { apiClient, API_BASE_URL } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import type { ProcessEvent } from '../types';

type ProcessStatus = 'pending' | 'running' | 'completed' | 'failed';

interface ProcessNodeData {
  name: string;
  className: string;
  status: ProcessStatus;
  startedAt?: string;
  finishedAt?: string;
  executionMode?: string;
  groupIndex?: number;
  groupSize?: number;
  error?: string;
}

const statusFromEvent = (eventType: string): ProcessStatus => {
  if (eventType === 'process.completed') return 'completed';
  if (eventType === 'process.failed') return 'failed';
  if (eventType === 'process.started') return 'running';
  return 'pending';
};

const statusLabel: Record<ProcessStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
};

const ProcessNodeCard = ({ data }: NodeProps<ProcessNodeData>) => {
  return (
    <div className={`process-node status-${data.status}`}>
      <Handle type="target" position={Position.Left} className="handle" />
      <div className="node-body">
        <div className="node-title">{data.name}</div>
        <div className="node-class">{data.className}</div>
        <div className="node-meta">
          <span className="pill tiny">{statusLabel[data.status]}</span>
          {data.executionMode && <span className="pill tiny neutral">{data.executionMode}</span>}
          {data.error && <span className="pill tiny warn">error</span>}
        </div>
        <div className="node-meta subtle">
          {data.startedAt && <span>↳ {new Date(data.startedAt).toLocaleTimeString()}</span>}
          {data.finishedAt && <span>• {new Date(data.finishedAt).toLocaleTimeString()}</span>}
        </div>
      </div>
      <Handle type="source" position={Position.Right} className="handle" />
    </div>
  );
};

const nodeTypes = { processNode: ProcessNodeCard };

type FlowNode = Node<ProcessNodeData>;
type FlowEdge = Edge;

type LiveFlowVariant = 'canvas' | 'feed';

interface LiveFlowProps {
  variant?: LiveFlowVariant;
  activeWorkflowName?: string | null;
  onRun?: () => void;
  isRunning?: boolean;
}

export function LiveFlow({ variant = 'canvas', activeWorkflowName, onRun, isRunning }: LiveFlowProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<ProcessNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>([]);
  const [eventLog, setEventLog] = useState<ProcessEvent[]>([]);
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [wsUrl, setWsUrl] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [runAnchor, setRunAnchor] = useState<number | null>(null);

  useEffect(() => {
    const wsBase = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
    setWsUrl(`${wsBase}/ws/monitor/all`);
  }, []);

  useEffect(() => {
    void loadHistory();
  }, []);

  useWebSocket(wsUrl, {
    onEvent: (event) => handleEvent(event),
    onConnect: () => setConnectionState('connected'),
    onDisconnect: () => setConnectionState('disconnected'),
  });

  const loadHistory = async () => {
    try {
      setLoadingHistory(true);
      const history = await apiClient.getEvents();
      const ordered = [...history.events].sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );

      const latestRootStart = findLatestRootStart(ordered);
      const filtered = latestRootStart
        ? ordered.filter((event) => new Date(event.timestamp).getTime() >= latestRootStart)
        : ordered;

      if (latestRootStart) {
        setRunAnchor(latestRootStart);
      }

      filtered.forEach((event) => handleEvent(event, true));
    } catch (error) {
      console.error('Failed to load event history', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleEvent = (event: ProcessEvent, fromHistory = false) => {
    if (event.type === 'process.started' && (event.group_index ?? 0) === 0) {
      const anchor = new Date(event.timestamp).getTime();
      if (!runAnchor || anchor > runAnchor) {
        setRunAnchor(anchor);
        setNodes([]);
        setEdges([]);
        setEventLog([]);
      }
    }

    setEventLog((prev) => [event, ...prev].slice(0, 40));

    setNodes((prevNodes) => {
      const nextNodes = layoutNodes(upsertNodeFromEvent(event, prevNodes));
      setEdges((prevEdges) => syncEdgesFromEvent(event, nextNodes, prevEdges));
      return nextNodes;
    });

    if (!fromHistory) {
      setConnectionState((state) => (state === 'connecting' ? 'connected' : state));
    }
  };

  const statusCounts = useMemo(
    () => ({
      running: nodes.filter((n) => n.data.status === 'running').length,
      completed: nodes.filter((n) => n.data.status === 'completed').length,
      failed: nodes.filter((n) => n.data.status === 'failed').length,
    }),
    [nodes]
  );

  if (variant === 'feed') {
    return (
      <div className="event-feed event-feed--panel">
        <div className="feed-header">
          <span className={`pill tiny ${connectionState === 'connected' ? 'ok' : 'warn'}`}>
            {connectionState}
          </span>
          {loadingHistory ? <span className="muted">Loading history…</span> : <span className="muted">Listening</span>}
        </div>
        <div className="feed-list feed-list--panel">
          {eventLog.map((event) => (
            <div key={`${event.process_id}-${event.timestamp}-${event.type}`} className="feed-item">
              <span className={`pill tiny ${statusFromEvent(event.type) === 'failed' ? 'warn' : 'neutral'}`}>
                {event.type.replace('process.', '')}
              </span>
              <div className="feed-body">
                <strong>{event.process_name}</strong>
                <span className="muted">{event.process_class}</span>
              </div>
              <span className="timestamp">{new Date(event.timestamp).toLocaleTimeString()}</span>
            </div>
          ))}
          {eventLog.length === 0 && <div className="muted">Waiting for events…</div>}
        </div>
      </div>
    );
  }

  return (
    <div className="live-flow">
      <div className="flow-header">
        <div>
          <p className="eyebrow">Live flow</p>
          <h2>React Flow canvas</h2>
          <p className="muted">Real-time topology built from monitor events.</p>
        </div>
        <div className="flow-state">
          <div className="flow-selection">
            <span className="muted">Active</span>{' '}
            <strong>{activeWorkflowName ?? 'None selected'}</strong>
          </div>
          <span className={`pill ${connectionState === 'connected' ? 'ok' : 'warn'}`}>
            {connectionState}
          </span>
          {loadingHistory ? <span className="muted">Loading history…</span> : <span className="muted">Listening</span>}
          {onRun && (
            <button
              className="primary"
              onClick={onRun}
              disabled={!activeWorkflowName || isRunning}
            >
              {isRunning ? 'Running…' : 'Run'}
            </button>
          )}
        </div>
      </div>

      <div className="flow-insights">
        <div className="chip">
          <span className="dot running" />
          Running {statusCounts.running}
        </div>
        <div className="chip">
          <span className="dot completed" />
          Completed {statusCounts.completed}
        </div>
        <div className="chip">
          <span className="dot failed" />
          Failed {statusCounts.failed}
        </div>
        <div className="chip">{nodes.length} nodes</div>
      </div>

      <div className="flow-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{
            type: 'default',
            markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--edge-color)' },
            style: { stroke: 'var(--edge-color)', strokeWidth: 1.4 },
          }}
        >
          <MiniMap
            nodeColor={(node) => nodeStatusColor((node.data as ProcessNodeData).status)}
            maskColor="rgba(13, 18, 26, 0.6)"
          />
          <Controls />
          <Background gap={22} color="var(--grid-color)" />
        </ReactFlow>
      </div>
    </div>
  );
}

function nodeStatusColor(status: ProcessStatus) {
  if (status === 'completed') return 'var(--success)';
  if (status === 'running') return 'var(--info)';
  if (status === 'failed') return 'var(--warn)';
  return 'var(--muted-foreground)';
}

function upsertNodeFromEvent(event: ProcessEvent, nodes: FlowNode[]): FlowNode[] {
  const status = statusFromEvent(event.type);
  const existingIndex = nodes.findIndex((node) => node.id === event.process_id);
  const baseData: ProcessNodeData = {
    name: event.process_name,
    className: event.process_class,
    status,
    startedAt: event.timestamp,
    finishedAt: status === 'running' ? undefined : event.timestamp,
    executionMode: event.execution_mode,
    groupIndex: event.group_index,
    groupSize: event.group_size,
    error: event.error,
  };

  if (existingIndex >= 0) {
    const next = [...nodes];
    const existing = next[existingIndex];
    next[existingIndex] = {
      ...existing,
      data: {
        ...existing.data,
        ...baseData,
        status,
        startedAt: existing.data.startedAt || event.timestamp,
        finishedAt: status === 'running' ? existing.data.finishedAt : event.timestamp,
        error: event.error ?? existing.data.error,
      },
    };
    return next;
  }

  return [
    ...nodes,
    {
      id: event.process_id,
      type: 'processNode',
      position: getPositionForEvent(event, nodes),
      data: baseData,
    },
  ];
}

function syncEdgesFromEvent(event: ProcessEvent, nodes: FlowNode[], edges: FlowEdge[]): FlowEdge[] {
  const groupIndex = event.group_index ?? 0;
  const targetId = event.process_id;

  const sourceNode =
    groupIndex > 0
      ? findLast(nodes, (node) => (node.data as ProcessNodeData).groupIndex === groupIndex - 1)
      : findLast(nodes, (node) => node.id !== targetId);

  if (!sourceNode) return edges;

  const edgeId = `${sourceNode.id}-${targetId}`;
  if (edges.some((edge) => edge.id === edgeId)) return edges;

  const nextEdge: FlowEdge = {
    id: edgeId,
    source: sourceNode.id,
    target: targetId,
    animated: true,
    label: event.execution_mode || (groupIndex > 0 ? 'sequential' : 'flow'),
    labelStyle: { fontSize: 11, fill: 'var(--text-subtle)' },
  };

  return [...edges, nextEdge];
}

function getPositionForEvent(event: ProcessEvent, nodes: FlowNode[]) {
  const groupIndex = event.group_index ?? 0;
  const column = groupIndex;
  const siblings = nodes.filter((node) => (node.data as ProcessNodeData).groupIndex === groupIndex)
    .length;
  const x = 80 + column * 320;
  const y = 80 + siblings * 180;
  return { x, y };
}

function findLast<T>(list: T[], predicate: (item: T) => boolean): T | undefined {
  for (let i = list.length - 1; i >= 0; i -= 1) {
    if (predicate(list[i])) {
      return list[i];
    }
  }
  return undefined;
}

function layoutNodes(nodes: FlowNode[]): FlowNode[] {
  const spacingX = 280;
  const spacingY = 170;

  const groups = new Map<number, FlowNode[]>();
  nodes.forEach((node) => {
    const index = (node.data as ProcessNodeData).groupIndex ?? 0;
    const list = groups.get(index) ?? [];
    list.push(node);
    groups.set(index, list);
  });

  const sortedGroupIndexes = [...groups.keys()].sort((a, b) => a - b);

  const positioned: FlowNode[] = [];
  sortedGroupIndexes.forEach((groupIndex, colIndex) => {
    const groupNodes = groups.get(groupIndex) ?? [];
    groupNodes
      .sort((a, b) => {
        const aTime = (a.data as ProcessNodeData).startedAt ?? '';
        const bTime = (b.data as ProcessNodeData).startedAt ?? '';
        return aTime.localeCompare(bTime);
      })
      .forEach((node, rowIndex) => {
        positioned.push({
          ...node,
          position: {
            x: 80 + colIndex * spacingX,
            y: 80 + rowIndex * spacingY,
          },
        });
      });
  });

  return positioned;
}

function findLatestRootStart(events: ProcessEvent[]): number | null {
  const rootStarts = events
    .filter((event) => event.type === 'process.started' && (event.group_index ?? 0) === 0)
    .map((event) => new Date(event.timestamp).getTime());

  if (!rootStarts.length) return null;
  return Math.max(...rootStarts);
}
