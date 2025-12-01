"""
Unit tests for Process execution
"""

import pytest
import asyncio
from swfme.core.process import (
    Process,
    AtomarProcess,
    OrchestratedProcess,
    ProcessStatus,
    ProcessExecutionFlags
)
from swfme.core.parameters import InputParameter, OutputParameter


# ═══════════════════════════════════════════════════════════════════════════
# TEST PROCESSES
# ═══════════════════════════════════════════════════════════════════════════

class SimpleAddProcess(AtomarProcess):
    """Simple process that adds two numbers"""

    def define_parameters(self):
        self.input.add(InputParameter("a", int))
        self.input.add(InputParameter("b", int))
        self.output.add(OutputParameter("sum", int))

    async def execute_impl(self):
        a = self.input["a"].value
        b = self.input["b"].value
        self.output["sum"].value = a + b


class FailingProcess(AtomarProcess):
    """Process that always fails"""

    def define_parameters(self):
        self.input.add(InputParameter("dummy", int, required=False))
        self.output.add(OutputParameter("result", int))

    async def execute_impl(self):
        raise Exception("Intentional failure for testing")


class SlowProcess(AtomarProcess):
    """Process that takes time to execute"""

    def define_parameters(self):
        self.input.add(InputParameter("delay", float))
        self.output.add(OutputParameter("result", str))

    async def execute_impl(self):
        delay = self.input["delay"].value
        await asyncio.sleep(delay)
        self.output["result"].value = f"Completed after {delay}s"


class MultiplyProcess(AtomarProcess):
    """Multiply a number"""

    def define_parameters(self):
        self.input.add(InputParameter("number", int))
        self.input.add(InputParameter("factor", int))
        self.output.add(OutputParameter("result", int))

    async def execute_impl(self):
        number = self.input["number"].value
        factor = self.input["factor"].value
        self.output["result"].value = number * factor


class SimpleOrchestration(OrchestratedProcess):
    """Simple orchestrated process"""

    def define_parameters(self):
        self.input.add(InputParameter("a", int))
        self.input.add(InputParameter("b", int))
        self.output.add(OutputParameter("final_result", int))

    def orchestrate(self):
        # Step 1: Add
        add = SimpleAddProcess(name="Add")
        self._connect_param(self.input["a"], add.input["a"])
        self._connect_param(self.input["b"], add.input["b"])
        self.add_child(add, ProcessExecutionFlags.SEQUENTIAL)

        # Step 2: Multiply by 2
        multiply = MultiplyProcess(name="Multiply")
        self._connect_param(add.output["sum"], multiply.input["number"])
        multiply.input["factor"].value = 2
        self.add_child(multiply, ProcessExecutionFlags.SEQUENTIAL)

        # Output
        self._connect_param(multiply.output["result"], self.output["final_result"])


class ParallelOrchestration(OrchestratedProcess):
    """Orchestration with parallel execution"""

    def define_parameters(self):
        self.input.add(InputParameter("a", int))
        self.input.add(InputParameter("b", int))
        self.output.add(OutputParameter("sum", int))
        self.output.add(OutputParameter("product", int))

    def orchestrate(self):
        # Parallel: Add AND Multiply
        add = SimpleAddProcess(name="Add")
        self._connect_param(self.input["a"], add.input["a"])
        self._connect_param(self.input["b"], add.input["b"])
        self.add_child(add, ProcessExecutionFlags.PARALLEL)

        multiply = MultiplyProcess(name="Multiply")
        self._connect_param(self.input["a"], multiply.input["number"])
        self._connect_param(self.input["b"], multiply.input["factor"])
        self.add_child(multiply, ProcessExecutionFlags.PARALLEL)

        # Outputs
        self._connect_param(add.output["sum"], self.output["sum"])
        self._connect_param(multiply.output["result"], self.output["product"])


# ═══════════════════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestAtomicProcess:
    """Test atomic process execution"""

    @pytest.mark.asyncio
    async def test_simple_execution(self):
        """Test successful process execution"""
        process = SimpleAddProcess()
        process.input["a"].value = 5
        process.input["b"].value = 3

        success = await process.execute()

        assert success is True
        assert process.status == ProcessStatus.COMPLETED
        assert process.output["sum"].value == 8
        assert process.execution_time_ms is not None
        assert process.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_failed_execution(self):
        """Test process execution failure"""
        process = FailingProcess()

        success = await process.execute()

        assert success is False
        assert process.status == ProcessStatus.FAILED
        assert process.error == "Intentional failure for testing"
        assert process.error_stacktrace is not None

    @pytest.mark.asyncio
    async def test_missing_input_validation(self):
        """Test that missing required inputs are detected"""
        process = SimpleAddProcess()
        # Don't set inputs

        success = await process.execute()

        assert success is False
        assert process.status == ProcessStatus.FAILED
        assert "not set" in process.error

    @pytest.mark.asyncio
    async def test_execution_metrics(self):
        """Test that execution metrics are collected"""
        process = SlowProcess()
        process.input["delay"].value = 0.1  # 100ms

        await process.execute()

        assert process.execution_time_ms >= 100  # At least 100ms
        assert process.started_at is not None
        assert process.completed_at is not None

    @pytest.mark.asyncio
    async def test_process_id_generation(self):
        """Test that each process gets a unique ID"""
        process1 = SimpleAddProcess()
        process2 = SimpleAddProcess()

        assert process1.id != process2.id
        assert len(process1.id) > 0


class TestOrchestratedProcess:
    """Test orchestrated process execution"""

    @pytest.mark.asyncio
    async def test_sequential_orchestration(self):
        """Test sequential process execution"""
        workflow = SimpleOrchestration()
        workflow.input["a"].value = 10
        workflow.input["b"].value = 5

        success = await workflow.execute()

        assert success is True
        # (10 + 5) * 2 = 30
        assert workflow.output["final_result"].value == 30

    @pytest.mark.asyncio
    async def test_parallel_orchestration(self):
        """Test parallel process execution"""
        workflow = ParallelOrchestration()
        workflow.input["a"].value = 6
        workflow.input["b"].value = 4

        success = await workflow.execute()

        assert success is True
        assert workflow.output["sum"].value == 10  # 6 + 4
        assert workflow.output["product"].value == 24  # 6 * 4

    @pytest.mark.asyncio
    async def test_parallel_execution_speed(self):
        """Test that parallel execution is actually parallel"""

        class ParallelSleepWorkflow(OrchestratedProcess):
            def define_parameters(self):
                self.output.add(OutputParameter("result", str))

            def orchestrate(self):
                # Run two 0.2s processes in parallel
                slow1 = SlowProcess(name="Slow1")
                slow1.input["delay"].value = 0.2
                self.add_child(slow1, ProcessExecutionFlags.PARALLEL)

                slow2 = SlowProcess(name="Slow2")
                slow2.input["delay"].value = 0.2
                self.add_child(slow2, ProcessExecutionFlags.PARALLEL)

                self._connect_param(slow1.output["result"], self.output["result"])

        workflow = ParallelSleepWorkflow()
        success = await workflow.execute()

        assert success is True
        # Should be ~200ms, not 400ms (if sequential)
        assert workflow.execution_time_ms < 350  # Some overhead allowed

    @pytest.mark.asyncio
    async def test_child_failure_propagation(self):
        """Test that child process failures propagate"""

        class FailingWorkflow(OrchestratedProcess):
            def define_parameters(self):
                self.output.add(OutputParameter("result", int))

            def orchestrate(self):
                failing = FailingProcess()
                self.add_child(failing, ProcessExecutionFlags.SEQUENTIAL)

        workflow = FailingWorkflow()
        success = await workflow.execute()

        assert success is False
        assert workflow.status == ProcessStatus.FAILED
        assert "Intentional failure" in workflow.error


class TestProcessLifecycle:
    """Test process lifecycle management"""

    @pytest.mark.asyncio
    async def test_process_status_transitions(self):
        """Test status transitions during execution"""
        process = SimpleAddProcess()
        process.input["a"].value = 1
        process.input["b"].value = 1

        # Initial status
        assert process.status == ProcessStatus.PENDING

        # Execute
        await process.execute()

        # Final status
        assert process.status == ProcessStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_process_to_dict(self):
        """Test process serialization"""
        process = SimpleAddProcess(name="TestProcess")
        process.input["a"].value = 5
        process.input["b"].value = 3

        await process.execute()

        data = process.to_dict()

        assert data["name"] == "TestProcess"
        assert data["class"] == "SimpleAddProcess"
        assert data["status"] == "completed"
        assert data["execution_time_ms"] > 0
        assert "input" in data
        assert "output" in data


class TestParameterConnections:
    """Test parameter connection mechanism"""

    def test_connect_param_helper(self):
        """Test _connect_param helper method"""
        workflow = SimpleOrchestration()
        workflow.input["a"].value = 10
        workflow.input["b"].value = 5

        # Orchestration creates connections
        workflow.orchestrate()

        # Check connections exist
        assert hasattr(workflow, '_param_connections')
        assert len(workflow._param_connections) > 0

    @pytest.mark.asyncio
    async def test_parameter_flow(self):
        """Test that values flow correctly through connected parameters"""
        workflow = SimpleOrchestration()
        workflow.input["a"].value = 7
        workflow.input["b"].value = 3

        await workflow.execute()

        # Check that values flowed correctly
        add_child = workflow.get_child("Add")
        assert add_child.output["sum"].value == 10  # 7 + 3

        multiply_child = workflow.get_child("Multiply")
        assert multiply_child.output["result"].value == 20  # 10 * 2
