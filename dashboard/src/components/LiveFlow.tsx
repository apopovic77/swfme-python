import { useEffect, useState } from 'react';
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
import dagre from 'dagre';
import { apiClient, API_BASE_URL } from '../services/api';
import { useWebSocket } from '../hooks/useWebSocket';
import type { ProcessEvent, Workflow, WorkflowGraphResponse } from '../types';

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
  inputs?: string[];
  outputs?: string[];
  inputsMap?: Record<string, string>;
  outputsMap?: Record<string, string>;
  value?: any;
  onValueChange?: (val: any) => void;
  ioPreview?: {
    inputs?: Record<string, any>;
    outputs?: Record<string, any>;
  };
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
  const inputEntries = Object.entries(data.inputsMap ?? {});
  const outputEntries = Object.entries(data.outputsMap ?? {});

  const nodeTitle = `${data.name}\nInputs: ${data.inputs?.join(', ') || '–'}\nOutputs: ${data.outputs?.join(', ') || '–'}`;

  return (
    <div className={`process-node status-${data.status}`} title={nodeTitle}>
      <div className="io-column">
        {inputEntries.map(([key], idx) => (
          <Handle
            key={`in-${key}`}
            id={`in-${key}`}
            type="target"
            position={Position.Left}
            className="handle"
            style={{
              top: `${((idx + 1) * 100) / (inputEntries.length + 1)}%`,
              cursor: 'default',
              pointerEvents: 'all',
            }}
            title={`in ${key}: ${data.inputsMap?.[key] ?? ''}`}
          />
        ))}
      </div>
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
        {(inputEntries.length > 0 || outputEntries.length > 0) && (
          <div className="node-io node-io-ports">
            {inputEntries.map(([key, type]) => (
              <span key={`pin-${key}`} className="pill tiny neutral" title={`in ${key}: ${type}`}>
                in {key}:{type}
              </span>
            ))}
            {outputEntries.map(([key, type]) => (
              <span key={`pout-${key}`} className="pill tiny neutral" title={`out ${key}: ${type}`}>
                out {key}:{type}
              </span>
            ))}
          </div>
        )}
        {data.ioPreview?.outputs && Object.keys(data.ioPreview.outputs).length > 0 && (
          <div className="node-io-preview">
            {Object.entries(data.ioPreview.outputs).map(([key, val]) => (
              <span
                key={key}
                className="pill tiny neutral"
                title={typeof val === 'string' ? val : JSON.stringify(val)}
              >
                {key}: {previewToString(val)}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="io-column">
        {outputEntries.map(([key], idx) => (
          <Handle
            key={`out-${key}`}
            id={`out-${key}`}
            type="source"
            position={Position.Right}
            className="handle"
            style={{
              top: `${((idx + 1) * 100) / (outputEntries.length + 1)}%`,
              cursor: 'default',
              pointerEvents: 'all',
            }}
            title={`out ${key}: ${data.outputsMap?.[key] ?? ''}`}
          />
        ))}
      </div>
    </div>
  );
};

const DataNodeCard = ({ data }: NodeProps<ProcessNodeData>) => {
  return (
    <div className="process-node data-node">
      <Handle type="source" position={Position.Right} className="handle" />
      <div className="node-body">
        <div className="node-title">{data.name}</div>
        <div className="node-meta">
          <span className="pill tiny neutral">value</span>
        </div>
        <input
          className="data-input"
          value={data.value ?? ''}
          onChange={(e) => data.onValueChange?.(e.target.value)}
        />
        {data.outputs && (
          <div className="node-io">
            {data.outputs.map((o) => (
              <span key={o} className="pill tiny neutral">
                {o}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const nodeTypes = { processNode: ProcessNodeCard, dataNode: DataNodeCard };

type FlowNode = Node<ProcessNodeData>;
type FlowEdge = Edge;

type LiveFlowVariant = 'canvas' | 'feed';

interface LiveFlowProps {
  variant?: LiveFlowVariant;
  activeWorkflowName?: string | null;
  onRun?: () => void;
  isRunning?: boolean;
  activeWorkflow?: Workflow | null;
  inputValues?: Record<string, any>;
  onInputChange?: (key: string, value: any) => void;
}

export function LiveFlow({
  variant = 'canvas',
  activeWorkflowName,
  onRun,
  isRunning,
  activeWorkflow,
  inputValues = {},
  onInputChange,
}: LiveFlowProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<ProcessNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>([]);
  const [eventLog, setEventLog] = useState<ProcessEvent[]>([]);
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [wsUrl, setWsUrl] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [runAnchor, setRunAnchor] = useState<number | null>(null);
  const [graph, setGraph] = useState<WorkflowGraphResponse | null>(null);

  useEffect(() => {
    const wsBase = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
    setWsUrl(`${wsBase}/ws/monitor/all`);
  }, []);

  useEffect(() => {
    void loadGraph();
  }, [activeWorkflowName]);

  useWebSocket(wsUrl, {
    onEvent: (event) => handleEvent(event),
    onConnect: () => setConnectionState('connected'),
    onDisconnect: () => setConnectionState('disconnected'),
  });

  useEffect(() => {
    setNodes((prev) => {
      let changed = false;
      const next = prev.map((node) => {
        if (node.type === 'dataNode') {
          const key = (node.data as ProcessNodeData).name;
          const val = inputValues?.[key];
          const currentVal = (node.data as ProcessNodeData).value;
          const nextVal = val ?? currentVal;
          if (nextVal !== currentVal) {
            changed = true;
            return {
              ...node,
              data: {
                ...(node.data as ProcessNodeData),
                value: nextVal,
                outputs: [`${nextVal ?? ''}`],
              },
            };
          }
        }
        return node;
      });
      return changed ? next : prev;
    });
  }, [inputValues, setNodes]);

  const loadGraph = async () => {
    if (!activeWorkflowName) return;
    try {
      const data = await apiClient.getWorkflowGraph(activeWorkflowName);
      setGraph(data);
      const baseNodes = graphToNodes(data);
      const baseEdges = graphToEdges(data);
      const withInputs = attachInputNodes(baseNodes, baseEdges, activeWorkflow, inputValues, onInputChange);
      setNodes(withInputs.nodes);
      setEdges(withInputs.edges);
      setEventLog([]);
      setRunAnchor(null);
      void loadHistory(data);
    } catch (error) {
      console.error('Failed to load graph', error);
    }
  };

  const loadHistory = async (graphData?: WorkflowGraphResponse) => {
    try {
      setLoadingHistory(true);
      const history = await apiClient.getEvents();
      const ordered = [...history.events].sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );

      const latestRootStart = findLatestRootStart(ordered);
    const timeFiltered = latestRootStart
      ? ordered.filter((event) => new Date(event.timestamp).getTime() >= latestRootStart)
      : ordered;

      if (latestRootStart) {
        setRunAnchor(latestRootStart);
      }
      const allowedNames = new Set((graphData ?? graph)?.nodes.map((n) => n.name) ?? []);
      timeFiltered
        .filter((event) => allowedNames.size === 0 || allowedNames.has(event.process_name))
        .forEach((event) => handleEvent(event, true));
    } catch (error) {
      console.error('Failed to load event history', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleEvent = (event: ProcessEvent, fromHistory = false) => {
    const allowedNames = new Set(graph?.nodes.map((n) => n.name) ?? []);
    if (allowedNames.size > 0 && !allowedNames.has(event.process_name)) {
      return;
    }

    if (event.type === 'process.started' && (event.group_index ?? 0) === 0) {
      const anchor = new Date(event.timestamp).getTime();
      if (!runAnchor || anchor > runAnchor) {
        setRunAnchor(anchor);
        setNodes((prev) => prev);
        setEventLog([]);
      }
    }

    setEventLog((prev) => [event, ...prev].slice(0, 40));

    setNodes((prevNodes) => {
      if (!prevNodes.some((n) => n.id === event.process_name)) {
        return prevNodes;
      }
      return prevNodes.map((node) =>
        node.id === event.process_name
          ? {
              ...node,
              data: {
                ...(node.data as ProcessNodeData),
                status: statusFromEvent(event.type),
                startedAt: (node.data as ProcessNodeData).startedAt ?? event.timestamp,
                finishedAt:
                  statusFromEvent(event.type) === 'running'
                    ? (node.data as ProcessNodeData).finishedAt
                    : event.timestamp,
                error: event.error ?? (node.data as ProcessNodeData).error,
                ioPreview: event.io_snapshot
                  ? {
                      inputs: event.io_snapshot.inputs,
                      outputs: event.io_snapshot.outputs,
                    }
                  : (node.data as ProcessNodeData).ioPreview,
              },
            }
          : node
      );
    });

    if (!fromHistory) {
      setConnectionState((state) => (state === 'connecting' ? 'connected' : state));
    }
  };

  return (
    <div className="live-flow">
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
          className="rf-wrapper"
          style={{ width: '100%', height: '100%' }}
        >
          <MiniMap
            nodeColor={(node) => nodeStatusColor((node.data as ProcessNodeData).status)}
            maskColor="rgba(13, 18, 26, 0.6)"
          />
          <Controls />
          <Background gap={22} color="var(--grid-color)" />
        </ReactFlow>

        {onRun && (
          <div className="canvas-controls">
            <div className="flow-selection">
              <span className="muted">Active</span>{' '}
              <strong>{activeWorkflowName ?? 'None selected'}</strong>
            </div>
            <span className={`pill ${connectionState === 'connected' ? 'ok' : 'warn'}`}>
              {connectionState}
            </span>
            <button
              className="primary"
              onClick={onRun}
              disabled={!activeWorkflowName || isRunning}
            >
              {isRunning ? 'Running…' : 'Run'}
            </button>
          </div>
        )}
      </div>

      {variant === 'feed' && (
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
      )}
    </div>
  );
}

function nodeStatusColor(status: ProcessStatus) {
  if (status === 'completed') return 'var(--success)';
  if (status === 'running') return 'var(--info)';
  if (status === 'failed') return 'var(--warn)';
  return 'var(--muted-foreground)';
}

function findLatestRootStart(events: ProcessEvent[]): number | null {
  const rootStarts = events
    .filter((event) => event.type === 'process.started' && (event.group_index ?? 0) === 0)
    .map((event) => new Date(event.timestamp).getTime());

  if (!rootStarts.length) return null;
  return Math.max(...rootStarts);
}

function graphToNodes(graph: WorkflowGraphResponse): FlowNode[] {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'LR', ranksep: 120, nodesep: 60 });
  g.setDefaultEdgeLabel(() => ({}));

  const width = 220;
  const height = 140;

  graph.nodes.forEach((node) => {
    g.setNode(node.name, { width, height, group_index: node.group_index });
  });
  graph.edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  return graph.nodes.map((node) => {
    const pos = g.node(node.name);
    return {
      id: node.name,
      type: 'processNode',
      position: { x: pos.x, y: pos.y },
      data: {
        name: node.name,
        className: node.class_name,
        status: 'pending',
        executionMode: node.execution_flag,
        inputs: Object.entries(node.inputs).map(([key, val]) => `${key}:${val}`),
        outputs: Object.entries(node.outputs).map(([key, val]) => `${key}:${val}`),
        inputsMap: node.inputs,
        outputsMap: node.outputs,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });
}

function graphToEdges(graph: WorkflowGraphResponse): FlowEdge[] {
  return graph.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: `out-${edge.source_param}`,
    targetHandle: `in-${edge.target_param}`,
    label: `${edge.source_param} → ${edge.target_param} (${edge.param_type})`,
    labelStyle: { fontSize: 11, fill: 'var(--text-subtle)' },
    animated: true,
    data: {
      paramType: edge.param_type,
    },
  }));
}

function previewToString(val: any): string {
  if (val === null || val === undefined) return 'null';
  if (typeof val === 'string' || typeof val === 'number' || typeof val === 'boolean') {
    return String(val);
  }
  if (typeof val === 'object') {
    if ('type' in val && 'len' in val) {
      return `${val.type}[${val.len}]`;
    }
    if (Array.isArray(val)) return `list[len=${val.length}]`;
    return JSON.stringify(val).slice(0, 80);
  }
  return String(val).slice(0, 80);
}

function attachInputNodes(
  baseNodes: FlowNode[],
  baseEdges: FlowEdge[],
  workflow?: Workflow | null,
  inputValues?: Record<string, any>,
  onInputChange?: (key: string, value: any) => void
) {
  if (!workflow) return { nodes: baseNodes, edges: baseEdges };

  const nodes = [...baseNodes];
  const edges = [...baseEdges];

  const minX = Math.min(...nodes.map((n) => n.position.x));
  let offsetY = Math.min(...nodes.map((n) => n.position.y));

  Object.entries(workflow.input_parameters || {}).forEach(([name, param]) => {
    const value = inputValues?.[name] ?? defaultForParam(param as any, name);
    const targetNode = nodes.find((n) => (n.data as ProcessNodeData).inputsMap?.[name]);
    const yPos = targetNode ? targetNode.position.y : offsetY;
    offsetY += 80;

    const dataNode: FlowNode = {
      id: `input-${name}`,
      type: 'dataNode',
      position: { x: minX - 220, y: yPos },
      data: {
        name,
        className: 'Input',
        status: 'completed',
        value,
        outputs: [`${value ?? ''}`],
        onValueChange: (val: any) => onInputChange?.(name, val),
      } as ProcessNodeData,
      sourcePosition: Position.Right,
    };

    nodes.push(dataNode);

    if (targetNode) {
      edges.push({
        id: `input-${name}->${targetNode.id}`,
        source: dataNode.id,
        target: targetNode.id,
        targetHandle: `in-${name}`,
        animated: true,
        label: `${name} (${(param as any).type})`,
        labelStyle: { fontSize: 11, fill: 'var(--text-subtle)' },
      });
    }
  });

  return { nodes, edges };
}

function defaultForParam(param: any, key: string) {
  if (!param) return '';
  const t = param.type;
  if (t === 'str' || t === 'string') return key === 'filename' ? 'example.csv' : `${key}-sample`;
  if (t === 'int') return 1;
  if (t === 'float') return 1.0;
  if (t === 'bool' || t === 'boolean') return true;
  return '';
}
