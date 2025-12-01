"""
FastAPI Routes for sWFME

REST API endpoints for workflow execution and monitoring.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from pydantic import BaseModel, Field

from swfme.registry.process_registry import process_registry
from swfme.monitoring.event_bus import event_bus
from swfme.monitoring.metrics import metrics_collector
from swfme.core.process import OrchestratedProcess


# ═══════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════

class WorkflowExecuteRequest(BaseModel):
    """Request to execute a workflow"""
    workflow_name: str = Field(..., description="Registered workflow name")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Input parameters")
    instance_name: Optional[str] = Field(None, description="Optional instance name")


class WorkflowExecuteResponse(BaseModel):
    """Response from workflow execution"""
    success: bool
    process_id: str
    status: str
    execution_time_ms: Optional[float] = None
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ProcessInfo(BaseModel):
    """Process information"""
    name: str
    class_name: str = Field(..., alias="class")
    type: str
    module: str
    doc: Optional[str] = None
    input_parameters: Dict[str, Any]
    output_parameters: Dict[str, Any]

    class Config:
        populate_by_name = True


class MetricsResponse(BaseModel):
    """Metrics response"""
    process_id: str
    process_name: str
    process_class: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time_ms: Optional[float] = None
    error: Optional[str] = None


class AggregatedMetricsResponse(BaseModel):
    """Aggregated metrics response"""
    process_class: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float
    avg_execution_time_ms: float
    min_execution_time_ms: Optional[float] = None
    max_execution_time_ms: Optional[float] = None
    last_execution_at: Optional[str] = None


class GraphNode(BaseModel):
    """Graph node for workflow orchestration"""
    id: str
    name: str
    class_name: str
    type: str
    group_index: int
    execution_flag: str
    inputs: Dict[str, str]
    outputs: Dict[str, str]


class GraphEdge(BaseModel):
    """Graph edge showing parameter connection"""
    id: str
    source: str
    target: str
    source_param: str
    target_param: str
    param_type: str


# ═══════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════

router = APIRouter(prefix="/api", tags=["swfme"])


# ═══════════════════════════════════════════════════════════════════════════
# WORKFLOW ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/workflows", response_model=List[ProcessInfo])
async def list_workflows():
    """
    List all registered workflows.

    Returns:
        List of workflow information including parameters
    """
    processes = process_registry.list_processes()
    return processes


@router.get("/workflows/{name}", response_model=ProcessInfo)
async def get_workflow_info(name: str):
    """
    Get detailed information about a specific workflow.

    Args:
        name: Workflow name

    Returns:
        Workflow information

    Raises:
        HTTPException: If workflow not found
    """
    info = process_registry.get_info(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")
    return info


@router.get("/workflows/{name}/graph", response_model=Dict[str, Any])
async def get_workflow_graph(name: str):
    """
    Build the orchestration graph for an orchestrated workflow (static DAG).

    Returns nodes (processes) and edges (parameter connections) without executing the workflow.
    """
    workflow = process_registry.create(name)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")

    if not isinstance(workflow, OrchestratedProcess):
        raise HTTPException(status_code=400, detail=f"Workflow '{name}' is not orchestrated")

    # Ensure orchestration is defined
    if not getattr(workflow, "_orchestration_defined", False):
        workflow.orchestrate()
        workflow._orchestration_defined = True

    groups = workflow._group_processes()

    # Map parameter object -> metadata (process, param name, direction, type)
    param_map: Dict[int, Dict[str, Any]] = {}
    nodes: List[GraphNode] = []

    for group_index, group in enumerate(groups):
        execution_flag = "parallel" if len(group) > 1 else "sequential"
        for process in group:
            node_inputs = {p.name: _type_name(p.param_type) for p in process.input.values()}
            node_outputs = {p.name: _type_name(p.param_type) for p in process.output.values()}

            # Record parameter metadata
            for p in process.input.values():
                param_map[id(p)] = {
                    "process": process.name,
                    "param": p.name,
                    "direction": "input",
                    "type": _type_name(p.param_type),
                }
            for p in process.output.values():
                param_map[id(p)] = {
                    "process": process.name,
                    "param": p.name,
                    "direction": "output",
                    "type": _type_name(p.param_type),
                }

            nodes.append(GraphNode(
                id=process.name,
                name=process.name,
                class_name=process.__class__.__name__,
                type="atomic" if process.__class__.__name__.startswith("Process") else "process",
                group_index=group_index,
                execution_flag=execution_flag,
                inputs=node_inputs,
                outputs=node_outputs,
            ))

    edges: List[GraphEdge] = []
    for source, target in getattr(workflow, "_param_connections", []):
        source_meta = param_map.get(id(source))
        target_meta = param_map.get(id(target))

        # Skip edges that touch the orchestrator itself (avoid SaveResult -> Pipeline)
        if not source_meta or not target_meta:
            continue

        edges.append(GraphEdge(
            id=f"{source_meta['process']}:{source_meta['param']}->{target_meta['process']}:{target_meta['param']}",
            source=source_meta["process"],
            target=target_meta["process"],
            source_param=source_meta["param"],
            target_param=target_meta["param"],
            param_type=source_meta["type"],
        ))

    return {
        "workflow": workflow.name,
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }


@router.post("/workflows/execute", response_model=WorkflowExecuteResponse)
async def execute_workflow(request: WorkflowExecuteRequest):
    """
    Execute a workflow.

    Args:
        request: Workflow execution request

    Returns:
        Execution result with process ID and outputs

    Raises:
        HTTPException: If workflow not found or execution fails

    Example:
        POST /api/workflows/execute
        {
            "workflow_name": "DataPipeline",
            "parameters": {
                "filename": "data.csv"
            }
        }
    """
    # Create workflow instance
    workflow = process_registry.create(
        request.workflow_name,
        instance_name=request.instance_name
    )

    if not workflow:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{request.workflow_name}' not found"
        )

    # Set input parameters
    try:
        for key, value in request.parameters.items():
            if key in workflow.input:
                workflow.input[key].value = value
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown parameter: {key}"
                )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Parameter error: {str(e)}"
        )

    # Execute workflow
    success = await workflow.execute()

    # Collect outputs
    output = {}
    if success:
        output = {
            k: v.value
            for k, v in workflow.output.items()
            if v.value is not None
        }

    return WorkflowExecuteResponse(
        success=success,
        process_id=workflow.id,
        status=workflow.status.value,
        execution_time_ms=workflow.execution_time_ms,
        output=output if success else None,
        error=workflow.error if not success else None
    )


@router.get("/workflows/{process_id}/status", response_model=MetricsResponse)
async def get_workflow_status(process_id: str):
    """
    Get execution status for a workflow.

    Args:
        process_id: Process ID

    Returns:
        Execution metrics

    Raises:
        HTTPException: If process not found
    """
    metrics = metrics_collector.get_metrics(process_id)

    if not metrics:
        raise HTTPException(
            status_code=404,
            detail=f"Process '{process_id}' not found"
        )

    return MetricsResponse(
        process_id=metrics.process_id,
        process_name=metrics.process_name,
        process_class=metrics.process_class,
        status=metrics.status,
        started_at=metrics.started_at.isoformat() if metrics.started_at else None,
        completed_at=metrics.completed_at.isoformat() if metrics.completed_at else None,
        execution_time_ms=metrics.execution_time_ms,
        error=metrics.error
    )


# ═══════════════════════════════════════════════════════════════════════════
# METRICS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/metrics/summary")
async def get_metrics_summary():
    """
    Get overall metrics summary.

    Returns:
        Summary statistics for all processes
    """
    return metrics_collector.get_summary()


@router.get("/metrics/aggregated", response_model=List[AggregatedMetricsResponse])
async def get_aggregated_metrics(
    process_class: Optional[str] = Query(None, description="Filter by process class")
):
    """
    Get aggregated metrics.

    Args:
        process_class: Optional filter by process class

    Returns:
        List of aggregated metrics per process class
    """
    if process_class:
        agg = metrics_collector.get_aggregated_metrics(process_class)
        if not agg:
            return []
        return [AggregatedMetricsResponse(**agg.to_dict())]
    else:
        agg_list = metrics_collector.get_all_aggregated()
        return [AggregatedMetricsResponse(**agg.to_dict()) for agg in agg_list]


@router.get("/metrics/processes", response_model=List[MetricsResponse])
async def get_all_process_metrics():
    """
    Get metrics for all process executions.

    Returns:
        List of all process metrics
    """
    all_metrics = metrics_collector.get_all_metrics()

    return [
        MetricsResponse(
            process_id=m.process_id,
            process_name=m.process_name,
            process_class=m.process_class,
            status=m.status,
            started_at=m.started_at.isoformat() if m.started_at else None,
            completed_at=m.completed_at.isoformat() if m.completed_at else None,
            execution_time_ms=m.execution_time_ms,
            error=m.error
        )
        for m in all_metrics
    ]


# ═══════════════════════════════════════════════════════════════════════════
# EVENTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/events")
async def get_events(
    process_id: Optional[str] = Query(None, description="Filter by process ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: Optional[int] = Query(100, description="Max events to return")
):
    """
    Get event history.

    Args:
        process_id: Optional filter by process ID
        event_type: Optional filter by event type
        limit: Maximum number of events

    Returns:
        List of events
    """
    events = event_bus.get_events(
        process_id=process_id,
        event_type=event_type,
        limit=limit
    )

    return {"events": events, "count": len(events)}


# ═══════════════════════════════════════════════════════════════════════════
# WEBSOCKET ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, process_id: str):
        """Connect a WebSocket"""
        await websocket.accept()

        if process_id not in self.active_connections:
            self.active_connections[process_id] = []

        self.active_connections[process_id].append(websocket)

    def disconnect(self, websocket: WebSocket, process_id: str):
        """Disconnect a WebSocket"""
        if process_id in self.active_connections:
            if websocket in self.active_connections[process_id]:
                self.active_connections[process_id].remove(websocket)

            # Clean up empty lists
            if not self.active_connections[process_id]:
                del self.active_connections[process_id]

    async def send_event(self, event: Dict[str, Any]):
        """Send event to all subscribers"""
        process_id = event.get("process_id", "")

        # Send to specific process subscribers
        if process_id in self.active_connections:
            for connection in self.active_connections[process_id]:
                try:
                    await connection.send_json(event)
                except:
                    pass

        # Send to "all" subscribers
        if "all" in self.active_connections:
            for connection in self.active_connections["all"]:
                try:
                    await connection.send_json(event)
                except:
                    pass


manager = ConnectionManager()


@router.websocket("/ws/monitor/{process_id}")
async def monitor_process(websocket: WebSocket, process_id: str):
    """
    WebSocket endpoint for real-time process monitoring.

    Connect to this endpoint to receive real-time events for a specific process
    or all processes (use "all" as process_id).

    Args:
        websocket: WebSocket connection
        process_id: Process ID to monitor, or "all" for all processes

    Example:
        ws://localhost:8000/api/ws/monitor/abc-123
        ws://localhost:8000/api/ws/monitor/all
    """
    await manager.connect(websocket, process_id)

    # Subscribe to events
    async def send_event(event: Dict[str, Any]):
        """Send event to this WebSocket"""
        event_process_id = event.get("process_id", "")

        # Send if matches or monitoring all
        if process_id == "all" or event_process_id == process_id:
            try:
                await websocket.send_json(event)
            except:
                pass

    event_bus.subscribe("*", send_event)

    try:
        # Keep connection alive
        while True:
            # Wait for messages (heartbeat)
            data = await websocket.receive_text()

            # Optional: Handle client messages (ping/pong)
            if data == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})

    except WebSocketDisconnect:
        manager.disconnect(websocket, process_id)
        event_bus.unsubscribe("*", send_event)


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "swfme",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "stats": {
            "registered_workflows": len(process_registry),
            "total_executions": metrics_collector.get_summary()["total_processes"],
            "event_stats": event_bus.get_stats()
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _type_name(param_type: Any) -> str:
    """Get a readable type name for a parameter."""
    try:
        return param_type.__name__
    except Exception:
        return str(param_type)
