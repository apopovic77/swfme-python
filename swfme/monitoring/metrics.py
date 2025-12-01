"""
Metrics Collector for sWFME

Collects and aggregates process execution metrics.
Provides insights into performance, success rates, and execution patterns.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict


@dataclass
class ProcessMetrics:
    """Metrics for a single process execution"""

    process_id: str
    process_name: str
    process_class: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[float] = None
    error: Optional[str] = None

    # Input/Output metadata
    input_params: Dict[str, Any] = field(default_factory=dict)
    output_params: Dict[str, Any] = field(default_factory=dict)

    # Child process metrics (for orchestrated processes)
    child_metrics: List["ProcessMetrics"] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = asdict(self)
        # Convert datetime objects
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            data["completed_at"] = self.completed_at.isoformat()
        return data

    @property
    def is_completed(self) -> bool:
        """Check if process completed successfully"""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if process failed"""
        return self.status == "failed"


@dataclass
class AggregatedMetrics:
    """Aggregated metrics for a process type"""

    process_class: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_execution_time_ms: float = 0.0
    min_execution_time_ms: Optional[float] = None
    max_execution_time_ms: Optional[float] = None
    last_execution_at: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 - 1.0)"""
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "process_class": self.process_class,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": self.success_rate,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "min_execution_time_ms": self.min_execution_time_ms,
            "max_execution_time_ms": self.max_execution_time_ms,
            "last_execution_at": self.last_execution_at.isoformat() if self.last_execution_at else None
        }


class MetricsCollector:
    """
    Collects and aggregates process execution metrics.

    Features:
    - Per-execution metrics
    - Aggregated metrics by process class
    - Success rate tracking
    - Performance analytics
    - Automatic event subscription

    Example:
        >>> collector = MetricsCollector()
        >>> # Metrics are collected automatically via event bus
        >>> metrics = collector.get_metrics("process-id-123")
        >>> print(f"Execution time: {metrics.execution_time_ms}ms")
        >>>
        >>> # Get aggregated metrics
        >>> agg = collector.get_aggregated_metrics("DataPipeline")
        >>> print(f"Success rate: {agg.success_rate:.2%}")
    """

    def __init__(self):
        # Per-execution metrics
        self._metrics: Dict[str, ProcessMetrics] = {}

        # Aggregated metrics by process class
        self._aggregated: Dict[str, AggregatedMetrics] = defaultdict(
            lambda: AggregatedMetrics(process_class="")
        )

        # Subscribe to events
        self._subscribe_to_events()

    def _subscribe_to_events(self):
        """Subscribe to process events"""
        from swfme.monitoring.event_bus import event_bus

        event_bus.subscribe("process.started", self._on_process_started)
        event_bus.subscribe("process.completed", self._on_process_completed)
        event_bus.subscribe("process.failed", self._on_process_failed)

    async def _on_process_started(self, event: Dict[str, Any]):
        """Handle process started event"""
        process_id = event.get("process_id")
        process_name = event.get("process_name", "Unknown")
        process_class = event.get("process_class", "Unknown")
        timestamp = event.get("timestamp")

        # Parse timestamp
        started_at = None
        if timestamp:
            try:
                started_at = datetime.fromisoformat(timestamp)
            except:
                started_at = datetime.utcnow()

        # Create metrics entry
        self._metrics[process_id] = ProcessMetrics(
            process_id=process_id,
            process_name=process_name,
            process_class=process_class,
            status="running",
            started_at=started_at
        )

    async def _on_process_completed(self, event: Dict[str, Any]):
        """Handle process completed event"""
        process_id = event.get("process_id")

        if process_id not in self._metrics:
            return

        metric = self._metrics[process_id]
        timestamp = event.get("timestamp")

        # Update metrics
        metric.status = "completed"
        if timestamp:
            try:
                metric.completed_at = datetime.fromisoformat(timestamp)
            except:
                metric.completed_at = datetime.utcnow()

        # Calculate execution time
        if metric.started_at and metric.completed_at:
            metric.execution_time_ms = (
                (metric.completed_at - metric.started_at).total_seconds() * 1000
            )

        # Update aggregated metrics
        self._update_aggregated(metric)

    async def _on_process_failed(self, event: Dict[str, Any]):
        """Handle process failed event"""
        process_id = event.get("process_id")

        if process_id not in self._metrics:
            return

        metric = self._metrics[process_id]
        timestamp = event.get("timestamp")

        # Update metrics
        metric.status = "failed"
        metric.error = event.get("error")

        if timestamp:
            try:
                metric.completed_at = datetime.fromisoformat(timestamp)
            except:
                metric.completed_at = datetime.utcnow()

        # Calculate execution time
        if metric.started_at and metric.completed_at:
            metric.execution_time_ms = (
                (metric.completed_at - metric.started_at).total_seconds() * 1000
            )

        # Update aggregated metrics
        self._update_aggregated(metric)

    def _update_aggregated(self, metric: ProcessMetrics):
        """Update aggregated metrics"""
        process_class = metric.process_class
        agg = self._aggregated[process_class]

        # Set process class if first time
        if not agg.process_class:
            agg.process_class = process_class

        # Update counts
        agg.total_executions += 1
        if metric.is_completed:
            agg.successful_executions += 1
        elif metric.is_failed:
            agg.failed_executions += 1

        # Update execution times
        if metric.execution_time_ms is not None:
            exec_time = metric.execution_time_ms

            # Update average (incremental)
            n = agg.total_executions
            old_avg = agg.avg_execution_time_ms
            agg.avg_execution_time_ms = old_avg + (exec_time - old_avg) / n

            # Update min/max
            if agg.min_execution_time_ms is None or exec_time < agg.min_execution_time_ms:
                agg.min_execution_time_ms = exec_time

            if agg.max_execution_time_ms is None or exec_time > agg.max_execution_time_ms:
                agg.max_execution_time_ms = exec_time

        # Update last execution time
        if metric.completed_at:
            if (agg.last_execution_at is None or
                metric.completed_at > agg.last_execution_at):
                agg.last_execution_at = metric.completed_at

    def get_metrics(self, process_id: str) -> Optional[ProcessMetrics]:
        """Get metrics for a specific process execution"""
        return self._metrics.get(process_id)

    def get_all_metrics(self) -> List[ProcessMetrics]:
        """Get all process metrics"""
        return list(self._metrics.values())

    def get_aggregated_metrics(self, process_class: str) -> Optional[AggregatedMetrics]:
        """Get aggregated metrics for a process class"""
        return self._aggregated.get(process_class)

    def get_all_aggregated(self) -> List[AggregatedMetrics]:
        """Get all aggregated metrics"""
        return list(self._aggregated.values())

    def get_summary(self) -> Dict[str, Any]:
        """Get overall summary statistics"""
        total_processes = len(self._metrics)
        completed = sum(1 for m in self._metrics.values() if m.is_completed)
        failed = sum(1 for m in self._metrics.values() if m.is_failed)

        exec_times = [
            m.execution_time_ms
            for m in self._metrics.values()
            if m.execution_time_ms is not None
        ]

        return {
            "total_processes": total_processes,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / total_processes if total_processes > 0 else 0,
            "avg_execution_time_ms": sum(exec_times) / len(exec_times) if exec_times else 0,
            "process_classes": len(self._aggregated)
        }

    def clear(self):
        """Clear all metrics"""
        self._metrics.clear()
        self._aggregated.clear()

    def __repr__(self) -> str:
        return f"<MetricsCollector processes={len(self._metrics)} classes={len(self._aggregated)}>"


# Global singleton instance
metrics_collector = MetricsCollector()
