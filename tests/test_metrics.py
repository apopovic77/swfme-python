"""
Unit tests for Metrics Collector
"""

import pytest
import asyncio
from datetime import datetime
from swfme.monitoring.metrics import MetricsCollector, ProcessMetrics, AggregatedMetrics
from swfme.monitoring.event_bus import EventBus


class TestProcessMetrics:
    """Test ProcessMetrics data class"""

    def test_metrics_creation(self):
        """Test creating process metrics"""
        metrics = ProcessMetrics(
            process_id="test-123",
            process_name="TestProcess",
            process_class="TestClass",
            status="completed",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            execution_time_ms=100.0
        )

        assert metrics.process_id == "test-123"
        assert metrics.process_name == "TestProcess"
        assert metrics.status == "completed"
        assert metrics.execution_time_ms == 100.0

    def test_metrics_to_dict(self):
        """Test metrics serialization"""
        now = datetime.utcnow()
        metrics = ProcessMetrics(
            process_id="test-123",
            process_name="TestProcess",
            process_class="TestClass",
            status="completed",
            started_at=now,
            completed_at=now
        )

        data = metrics.to_dict()

        assert data["process_id"] == "test-123"
        assert data["status"] == "completed"
        assert "started_at" in data

    def test_is_completed(self):
        """Test is_completed property"""
        completed = ProcessMetrics(
            process_id="1",
            process_name="Test",
            process_class="Test",
            status="completed"
        )

        failed = ProcessMetrics(
            process_id="2",
            process_name="Test",
            process_class="Test",
            status="failed"
        )

        assert completed.is_completed is True
        assert failed.is_completed is False

    def test_is_failed(self):
        """Test is_failed property"""
        failed = ProcessMetrics(
            process_id="1",
            process_name="Test",
            process_class="Test",
            status="failed"
        )

        completed = ProcessMetrics(
            process_id="2",
            process_name="Test",
            process_class="Test",
            status="completed"
        )

        assert failed.is_failed is True
        assert completed.is_failed is False


class TestAggregatedMetrics:
    """Test AggregatedMetrics data class"""

    def test_success_rate_calculation(self):
        """Test success rate calculation"""
        agg = AggregatedMetrics(
            process_class="TestClass",
            total_executions=10,
            successful_executions=8,
            failed_executions=2
        )

        assert agg.success_rate == 0.8  # 80%

    def test_success_rate_no_executions(self):
        """Test success rate with no executions"""
        agg = AggregatedMetrics(
            process_class="TestClass"
        )

        assert agg.success_rate == 0.0

    def test_aggregated_to_dict(self):
        """Test aggregated metrics serialization"""
        agg = AggregatedMetrics(
            process_class="TestClass",
            total_executions=5,
            successful_executions=5,
            avg_execution_time_ms=100.0
        )

        data = agg.to_dict()

        assert data["process_class"] == "TestClass"
        assert data["success_rate"] == 1.0
        assert data["avg_execution_time_ms"] == 100.0


class TestMetricsCollector:
    """Test MetricsCollector"""

    def setup_method(self):
        """Setup for each test"""
        # Use the global event bus and metrics collector
        from swfme.monitoring.event_bus import event_bus
        from swfme.monitoring.metrics import metrics_collector

        self.event_bus = event_bus
        self.collector = metrics_collector

        # Clear any previous state
        self.collector.clear()
        self.event_bus.clear_history()

    @pytest.mark.asyncio
    async def test_collect_metrics_from_events(self):
        """Test that metrics are collected from events"""
        # Emit process started event
        await self.event_bus.emit({
            "type": "process.started",
            "process_id": "test-123",
            "process_name": "TestProcess",
            "process_class": "TestClass",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Check metrics created
        metrics = self.collector.get_metrics("test-123")
        assert metrics is not None
        assert metrics.process_id == "test-123"
        assert metrics.status == "running"

    @pytest.mark.asyncio
    async def test_process_completion_updates_metrics(self):
        """Test that completion events update metrics"""
        process_id = "test-123"

        # Started
        await self.event_bus.emit({
            "type": "process.started",
            "process_id": process_id,
            "process_name": "TestProcess",
            "process_class": "TestClass",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Small delay to simulate execution
        await asyncio.sleep(0.01)

        # Completed
        await self.event_bus.emit({
            "type": "process.completed",
            "process_id": process_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Check metrics updated
        metrics = self.collector.get_metrics(process_id)
        assert metrics.status == "completed"
        assert metrics.completed_at is not None
        assert metrics.execution_time_ms is not None
        assert metrics.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_process_failure_updates_metrics(self):
        """Test that failure events update metrics"""
        process_id = "test-123"

        # Started
        await self.event_bus.emit({
            "type": "process.started",
            "process_id": process_id,
            "process_name": "TestProcess",
            "process_class": "TestClass",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Failed
        await self.event_bus.emit({
            "type": "process.failed",
            "process_id": process_id,
            "error": "Test error",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Check metrics updated
        metrics = self.collector.get_metrics(process_id)
        assert metrics.status == "failed"
        assert metrics.error == "Test error"

    @pytest.mark.asyncio
    async def test_aggregated_metrics_accumulation(self):
        """Test that aggregated metrics are accumulated"""
        # Execute multiple processes of same class
        for i in range(5):
            process_id = f"test-{i}"

            await self.event_bus.emit({
                "type": "process.started",
                "process_id": process_id,
                "process_name": f"TestProcess{i}",
                "process_class": "TestClass",
                "timestamp": datetime.utcnow().isoformat()
            })

            await asyncio.sleep(0.01)

            await self.event_bus.emit({
                "type": "process.completed",
                "process_id": process_id,
                "timestamp": datetime.utcnow().isoformat()
            })

        # Check aggregated metrics
        agg = self.collector.get_aggregated_metrics("TestClass")
        assert agg is not None
        assert agg.total_executions == 5
        assert agg.successful_executions == 5
        assert agg.failed_executions == 0
        assert agg.success_rate == 1.0
        assert agg.avg_execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_aggregated_metrics_with_failures(self):
        """Test aggregated metrics with some failures"""
        # 3 successful, 2 failed
        for i in range(5):
            process_id = f"test-{i}"

            await self.event_bus.emit({
                "type": "process.started",
                "process_id": process_id,
                "process_name": f"TestProcess{i}",
                "process_class": "TestClass",
                "timestamp": datetime.utcnow().isoformat()
            })

            await asyncio.sleep(0.01)

            if i < 3:
                # Successful
                await self.event_bus.emit({
                    "type": "process.completed",
                    "process_id": process_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                # Failed
                await self.event_bus.emit({
                    "type": "process.failed",
                    "process_id": process_id,
                    "error": "Test error",
                    "timestamp": datetime.utcnow().isoformat()
                })

        # Check aggregated metrics
        agg = self.collector.get_aggregated_metrics("TestClass")
        assert agg.total_executions == 5
        assert agg.successful_executions == 3
        assert agg.failed_executions == 2
        assert agg.success_rate == 0.6  # 60%

    def test_get_all_metrics(self):
        """Test getting all process metrics"""
        # Manually add some metrics (simulating events)
        self.collector._metrics["test-1"] = ProcessMetrics(
            process_id="test-1",
            process_name="Test1",
            process_class="Class1",
            status="completed"
        )

        self.collector._metrics["test-2"] = ProcessMetrics(
            process_id="test-2",
            process_name="Test2",
            process_class="Class2",
            status="completed"
        )

        all_metrics = self.collector.get_all_metrics()

        assert len(all_metrics) == 2

    def test_get_all_aggregated(self):
        """Test getting all aggregated metrics"""
        # Manually add aggregated metrics
        self.collector._aggregated["Class1"] = AggregatedMetrics(
            process_class="Class1",
            total_executions=5
        )

        self.collector._aggregated["Class2"] = AggregatedMetrics(
            process_class="Class2",
            total_executions=3
        )

        all_agg = self.collector.get_all_aggregated()

        assert len(all_agg) >= 2  # May have more from other tests

    def test_get_summary(self):
        """Test getting summary statistics"""
        # Add some metrics
        self.collector._metrics["test-1"] = ProcessMetrics(
            process_id="test-1",
            process_name="Test1",
            process_class="Class1",
            status="completed",
            execution_time_ms=100.0
        )

        self.collector._metrics["test-2"] = ProcessMetrics(
            process_id="test-2",
            process_name="Test2",
            process_class="Class1",
            status="failed",
            execution_time_ms=50.0
        )

        summary = self.collector.get_summary()

        assert summary["total_processes"] == 2
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert summary["success_rate"] == 0.5
        assert summary["avg_execution_time_ms"] == 75.0  # (100 + 50) / 2

    def test_clear(self):
        """Test clearing all metrics"""
        # Add some metrics
        self.collector._metrics["test-1"] = ProcessMetrics(
            process_id="test-1",
            process_name="Test1",
            process_class="Class1",
            status="completed"
        )

        assert len(self.collector._metrics) > 0

        # Clear
        self.collector.clear()

        assert len(self.collector._metrics) == 0
        assert len(self.collector._aggregated) == 0
