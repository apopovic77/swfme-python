"""
Process Base Classes for sWFME

Core process abstraction with Template Method pattern.
Inspired by the original sWFME C# implementation (2010).

Author: Alex Popovic (Arkturian)
Year: 2025 (Modernized from 2010 C# version)
"""

import uuid
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from enum import Enum

from swfme.core.parameters import ParameterSet, InputParameter, OutputParameter


class ProcessStatus(Enum):
    """Process execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessExecutionFlags(Enum):
    """
    Execution flags for child processes in orchestrated workflows.

    SEQUENTIAL: Execute one after another
    PARALLEL: Execute concurrently
    """
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class ProcessExecutionContext:
    """
    Execution context for processes.

    Determines HOW a process is executed:
    - Local vs Distributed
    - Sync vs Async
    - Scalable vs Non-scalable
    """

    def __init__(
        self,
        local_executable: bool = True,
        scalable: bool = False,
        balanceable: bool = False,
        complexity: float = 0.5
    ):
        self.local_executable = local_executable
        self.scalable = scalable
        self.balanceable = balanceable
        self.complexity = complexity  # 0.0 - 1.0


class Process(ABC):
    """
    Abstract base class for all processes.

    Implements the Template Method pattern:
    - execute() defines the workflow
    - execute_impl() is implemented by subclasses

    Features:
    - Type-safe input/output parameters
    - Lifecycle management (pending → running → completed/failed)
    - Event emission for monitoring
    - Execution metrics tracking
    - Context-independent execution

    Example:
        >>> class AddNumbers(AtomarProcess):
        ...     def define_parameters(self):
        ...         self.input.add(InputParameter("a", int))
        ...         self.input.add(InputParameter("b", int))
        ...         self.output.add(OutputParameter("sum", int))
        ...
        ...     async def execute_impl(self):
        ...         a = self.input["a"].value
        ...         b = self.input["b"].value
        ...         self.output["sum"].value = a + b
        ...
        >>> process = AddNumbers()
        >>> process.input["a"].value = 5
        >>> process.input["b"].value = 3
        >>> await process.execute()
        >>> print(process.output["sum"].value)  # 8
    """

    def __init__(self, name: Optional[str] = None):
        # Identity
        self.id = str(uuid.uuid4())
        self.name = name or self.__class__.__name__

        # Status
        self.status = ProcessStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.execution_time_ms: Optional[float] = None
        self.error: Optional[str] = None
        self.error_stacktrace: Optional[str] = None

        # Parameters
        self.input = ParameterSet()
        self.output = ParameterSet()

        # Context
        self.context = ProcessExecutionContext()

        # Event handlers
        self._event_handlers: Dict[str, List] = {}

        # Define parameters (subclass implementation)
        self.define_parameters()

    @abstractmethod
    def define_parameters(self):
        """
        Define input and output parameters for this process.

        This method is called during initialization and should add
        parameters to self.input and self.output.

        Example:
            def define_parameters(self):
                self.input.add(InputParameter("filename", str))
                self.output.add(OutputParameter("content", str))
        """
        pass

    async def execute(self) -> bool:
        """
        Execute this process (Template Method).

        This method orchestrates the execution lifecycle:
        1. Validate inputs
        2. Mark as running
        3. Execute implementation
        4. Validate outputs
        5. Mark as completed/failed

        Returns:
            bool: True if execution succeeded, False otherwise
        """
        try:
            # Pre-execution
            self.status = ProcessStatus.RUNNING
            self.started_at = datetime.utcnow()

            await self._emit_event("started")

            # Validate inputs
            self.input.validate_all()

            # Lock inputs during execution
            self.input.lock_all()

            # Execute implementation
            await self.execute_impl()

            # Validate outputs
            self.output.validate_all()

            # Post-execution
            self.status = ProcessStatus.COMPLETED
            self.completed_at = datetime.utcnow()
            self.execution_time_ms = (
                (self.completed_at - self.started_at).total_seconds() * 1000
            )

            await self._emit_event("completed")

            return True

        except Exception as e:
            # Error handling
            self.status = ProcessStatus.FAILED
            self.completed_at = datetime.utcnow()
            self.error = str(e)

            # Capture stacktrace
            import traceback
            self.error_stacktrace = traceback.format_exc()

            await self._emit_event("failed", error=str(e))

            return False

        finally:
            # Unlock inputs
            self.input.unlock_all()

    @abstractmethod
    async def execute_impl(self):
        """
        Actual process implementation.

        This method must be implemented by subclasses.
        It should read from self.input and write to self.output.

        Raises:
            Exception: Any error during execution
        """
        pass

    async def _emit_event(self, event_type: str, **kwargs):
        """Emit process event for monitoring"""
        # Import here to avoid circular dependency
        from swfme.monitoring.event_bus import event_bus

        event = {
            "type": f"process.{event_type}",
            "process_id": self.id,
            "process_name": self.name,
            "process_class": self.__class__.__name__,
            "timestamp": datetime.utcnow().isoformat(),
            "status": self.status.value,
            **kwargs
        }

        await event_bus.emit(event)

        # Call local event handlers
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                await handler(event)

    def on(self, event_type: str, handler):
        """Register event handler for this process"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def to_dict(self) -> dict:
        """Convert process to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "class": self.__class__.__name__,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
            "input": self.input.to_dict(),
            "output": self.output.to_dict(),
            "context": {
                "local_executable": self.context.local_executable,
                "scalable": self.context.scalable,
                "balanceable": self.context.balanceable,
                "complexity": self.context.complexity
            }
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id[:8]} status={self.status.value}>"


class AtomarProcess(Process):
    """
    Atomic process - cannot be decomposed into smaller processes.

    An atomic process represents a single, indivisible unit of work.
    It has inputs, performs some computation, and produces outputs.

    This is the leaf node in a process hierarchy.

    Example:
        >>> class CalculateSum(AtomarProcess):
        ...     def define_parameters(self):
        ...         self.input.add(InputParameter("numbers", list))
        ...         self.output.add(OutputParameter("sum", int))
        ...
        ...     async def execute_impl(self):
        ...         numbers = self.input["numbers"].value
        ...         total = sum(numbers)
        ...         self.output["sum"].value = total
    """

    def __init__(self, name: Optional[str] = None):
        super().__init__(name)


class OrchestratedProcess(Process):
    """
    Orchestrated process - composed of multiple child processes.

    An orchestrated process defines a workflow by composing
    child processes with execution flags (sequential/parallel).

    Features:
    - Declarative workflow definition
    - Sequential and parallel execution
    - Automatic execution order resolution
    - Parameter derivation (data flow between processes)

    Example:
        >>> class DataPipeline(OrchestratedProcess):
        ...     def define_parameters(self):
        ...         self.input.add(InputParameter("filename", str))
        ...         self.output.add(OutputParameter("result", dict))
        ...
        ...     def orchestrate(self):
        ...         # Sequential steps
        ...         load = ProcessLoadFile()
        ...         load.input["filename"] = self.input["filename"]
        ...         self.add_child(load, ProcessExecutionFlags.SEQUENTIAL)
        ...
        ...         # Parallel processing
        ...         analyze1 = ProcessAnalyzeData()
        ...         analyze1.input["data"] = load.output["data"]
        ...         self.add_child(analyze1, ProcessExecutionFlags.PARALLEL)
        ...
        ...         analyze2 = ProcessValidateData()
        ...         analyze2.input["data"] = load.output["data"]
        ...         self.add_child(analyze2, ProcessExecutionFlags.PARALLEL)
        ...
        ...         # Final step (after parallel)
        ...         save = ProcessSaveResults()
        ...         save.input["analysis"] = analyze1.output["result"]
        ...         save.input["validation"] = analyze2.output["result"]
        ...         self.add_child(save, ProcessExecutionFlags.SEQUENTIAL)
        ...
        ...         # Parameter derivation
        ...         self.output["result"] = save.output["result"]
    """

    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
        self.children: List[Tuple[Process, ProcessExecutionFlags]] = []
        self._orchestration_defined = False
        self._param_connections: List[Tuple] = []

    def add_child(self, process: Process, execution_flag: ProcessExecutionFlags):
        """
        Add a child process to this orchestrated process.

        Args:
            process: Child process instance
            execution_flag: Sequential or Parallel execution
        """
        self.children.append((process, execution_flag))

    def _connect_param(self, source, target):
        """
        Connect parameters for data flow.

        Helper method to define parameter connections.
        Values will be copied from source to target during execution.

        Args:
            source: Source parameter
            target: Target parameter
        """
        self._param_connections.append((source, target))

    @abstractmethod
    def orchestrate(self):
        """
        Define the orchestration of child processes.

        This method should:
        1. Create child process instances
        2. Set up parameter connections
        3. Add children with execution flags
        4. Set up output parameter derivation

        Example:
            def orchestrate(self):
                step1 = ProcessStep1()
                step1.input["data"] = self.input["data"]
                self.add_child(step1, ProcessExecutionFlags.SEQUENTIAL)

                step2 = ProcessStep2()
                step2.input["result"] = step1.output["result"]
                self.add_child(step2, ProcessExecutionFlags.SEQUENTIAL)

                self.output["final_result"] = step2.output["result"]
        """
        pass

    async def execute_impl(self):
        """
        Execute all child processes according to execution flags.

        This method:
        1. Calls orchestrate() to define the workflow
        2. Resolves parameter connections before each process
        3. Groups processes by sequential/parallel execution
        4. Executes groups in order
        5. Resolves output parameter connections
        6. Handles failures
        """
        # Define orchestration if not already done
        if not self._orchestration_defined:
            self.orchestrate()
            self._orchestration_defined = True

        # Get parameter connections if defined
        param_connections = getattr(self, '_param_connections', [])

        # Group processes by execution mode
        sequential_groups = self._group_processes()

        # Execute groups
        for group_idx, group in enumerate(sequential_groups):
            await self._emit_event(
                "group_started",
                group_index=group_idx,
                group_size=len(group),
                execution_mode="parallel" if len(group) > 1 else "sequential"
            )

            # Resolve parameter connections BEFORE executing this group
            for source, target in param_connections:
                # Only resolve if source has a value
                if source.value is not None:
                    target.value = source.value

            if len(group) == 1:
                # Sequential execution
                process = group[0]
                success = await process.execute()

                if not success:
                    raise Exception(
                        f"Process '{process.name}' failed: {process.error}"
                    )
            else:
                # Parallel execution
                tasks = [p.execute() for p in group]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Check for failures
                for process, result in zip(group, results):
                    if isinstance(result, Exception):
                        raise Exception(
                            f"Process '{process.name}' failed: {str(result)}"
                        )
                    elif not result:
                        raise Exception(
                            f"Process '{process.name}' failed: {process.error}"
                        )

            await self._emit_event(
                "group_completed",
                group_index=group_idx
            )

        # Resolve output parameter connections AFTER all execution
        for source, target in param_connections:
            if source.value is not None:
                target.value = source.value

    def _group_processes(self) -> List[List[Process]]:
        """
        Group processes by execution mode.

        Returns:
            List of process groups, where each group is executed sequentially,
            and processes within a group are executed in parallel.

        Example:
            Input: [
                (proc1, SEQUENTIAL),
                (proc2, SEQUENTIAL),
                (proc3, PARALLEL),
                (proc4, PARALLEL),
                (proc5, SEQUENTIAL)
            ]

            Output: [
                [proc1],
                [proc2],
                [proc3, proc4],  # Parallel group
                [proc5]
            ]
        """
        groups = []
        current_parallel_group = []

        for process, flag in self.children:
            if flag == ProcessExecutionFlags.SEQUENTIAL:
                # Flush current parallel group
                if current_parallel_group:
                    groups.append(current_parallel_group)
                    current_parallel_group = []

                # Add as single-process group
                groups.append([process])
            else:  # PARALLEL
                current_parallel_group.append(process)

        # Flush remaining parallel group
        if current_parallel_group:
            groups.append(current_parallel_group)

        return groups

    def get_child(self, name: str) -> Optional[Process]:
        """Get child process by name"""
        for process, _ in self.children:
            if process.name == name:
                return process
        return None

    def to_dict(self) -> dict:
        """Convert orchestrated process to dictionary"""
        base = super().to_dict()
        base["children"] = [
            {
                "process": p.to_dict(),
                "execution_flag": flag.value
            }
            for p, flag in self.children
        ]
        return base
