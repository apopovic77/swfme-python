"""
Process Base Classes for sWFME

Core process abstraction with Template Method pattern.
Inspired by the original sWFME C# implementation (2010).

Author: Alex Popovic (Arkturian)
Year: 2025 (Modernized from 2010 C# version)
"""

import uuid
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from enum import Enum

from swfme.core.parameters import ParameterSet, InputParameter, OutputParameter
from swfme.core.logging import ProcessLogger, process_log_config, ProcessLogLevel


class ProcessStatus(Enum):
    """Process execution status.

    Forward path: PENDING → RUNNING → COMPLETED / FAILED / CANCELLED
    Saga path:    FAILED → COMPENSATING → COMPENSATED / COMPENSATION_FAILED
    Escalation:   COMPENSATION_FAILED → ESCALATED (operator notification sent)
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"
    ESCALATED = "escalated"
    WAITING = "waiting"
    EXPIRED = "expired"


class ProcessExecutionFlags(Enum):
    """
    Execution flags for child processes in orchestrated workflows.

    SEQUENTIAL: Execute one after another
    PARALLEL: Execute concurrently
    """
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class WorkflowSuspend(Exception):
    """Raised by an AtomarProcess to suspend the surrounding workflow.

    Two suspension kinds:
      wait_for          — suspend until a matching external event arrives
                          (resumed by swfme-api's Webhook-Worker) or until
                          timeout_at passes (resumed by ExpirySweeper with
                          triggered_by='timeout').
      pending_decision  — suspend until a human/agent approver calls
                          POST /api/runs/{id}/approve or /reject.

    The engine catches this in OrchestratedProcess.execute_impl, persists the
    suspension state and the resume-position, and returns control. On resume,
    the suspended step's outputs are injected from the resume payload and
    execution continues with the NEXT step — execute_impl of the suspended
    step is NOT re-run.
    """

    def __init__(self, wait_for: Optional[dict] = None,
                 pending_decision: Optional[dict] = None):
        if not wait_for and not pending_decision:
            raise ValueError("WorkflowSuspend needs wait_for or pending_decision")
        self.wait_for = wait_for
        self.pending_decision = pending_decision
        super().__init__("workflow suspended")


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

    def __init__(self, name: Optional[str] = None, depth: int = 0):
        # Identity
        self.id = str(uuid.uuid4())
        self.name = name or self.__class__.__name__

        # Execution depth (for nested orchestrated processes)
        self._depth = depth

        # Logging
        self.logger = logging.getLogger(f"swfme.{self.__class__.__name__}")
        self._process_logger = ProcessLogger(
            process_name=self.name,
            process_class=self.__class__.__name__,
            depth=depth
        )

        # Status
        self.status = ProcessStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.execution_time_ms: Optional[float] = None
        self.error: Optional[str] = None
        self.error_stacktrace: Optional[str] = None

        # Saga-Compensation state
        self.compensated_at: Optional[datetime] = None
        self.compensation_attempts: int = 0
        self.compensation_error: Optional[str] = None

        # Cross-run relations (for sub-workflows + async compensation child-runs)
        self.parent_run_id: Optional[str] = None
        self.parent_relation: Optional[str] = None  # 'compensation' | 'sub_workflow' | None

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

            # Log start with inputs
            self._process_logger.log_start(dict(self.input.items()) if self.input else None)

            await self._emit_event(
                "started",
                io_snapshot=self._build_io_snapshot(include_outputs=False)
            )

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

            # Log completion with outputs
            self._process_logger.log_complete(
                dict(self.output.items()) if self.output else None,
                self.execution_time_ms
            )

            await self._emit_event(
                "completed",
                io_snapshot=self._build_io_snapshot()
            )

            return True

        except WorkflowSuspend:
            # Not a failure — the workflow wants to sleep. Propagate to the
            # runner which persists wait_for/pending_decision + returns.
            self.status = ProcessStatus.WAITING
            await self._emit_event("waiting")
            raise

        except Exception as e:
            # Error handling
            self.status = ProcessStatus.FAILED
            self.completed_at = datetime.utcnow()
            self.error = str(e)
            self.execution_time_ms = (
                (self.completed_at - self.started_at).total_seconds() * 1000
                if self.started_at else None
            )

            # Log failure
            self._process_logger.log_failed(str(e), self.execution_time_ms)

            # Capture stacktrace
            import traceback
            self.error_stacktrace = traceback.format_exc()

            await self._emit_event(
                "failed",
                error=str(e),
                io_snapshot=self._build_io_snapshot(include_outputs=True)
            )

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

    async def compensate(self) -> bool:
        """
        Compensate this process (Saga-Pattern rollback).

        Template Method that orchestrates compensation lifecycle:
        1. Mark as COMPENSATING + emit event
        2. Call compensate_impl() (subclass-provided)
        3. Mark as COMPENSATED or COMPENSATION_FAILED + emit event

        Only processes that previously reached COMPLETED can be compensated —
        otherwise there is nothing to roll back. A FAILED process gets compensated
        by its parent OrchestratedProcess as part of the saga sweep (parent walks
        back through completed children in reverse order).

        Returns:
            bool: True if compensation succeeded, False otherwise
        """
        if self.status not in (ProcessStatus.COMPLETED, ProcessStatus.FAILED):
            self.logger.warning(
                "compensate() called on '%s' but status is %s — skipping",
                self.name, self.status.value,
            )
            return True  # nothing to compensate

        try:
            self.status = ProcessStatus.COMPENSATING
            self.compensation_attempts += 1

            await self._emit_event(
                "compensating",
                attempt=self.compensation_attempts,
                io_snapshot=self._build_io_snapshot(include_outputs=True),
            )

            await self.compensate_impl()

            self.status = ProcessStatus.COMPENSATED
            self.compensated_at = datetime.utcnow()

            await self._emit_event(
                "compensated",
                io_snapshot=self._build_io_snapshot(include_outputs=True),
            )

            self.logger.info("Compensation succeeded for '%s'", self.name)
            return True

        except Exception as e:
            self.status = ProcessStatus.COMPENSATION_FAILED
            self.compensation_error = str(e)

            import traceback
            self.error_stacktrace = traceback.format_exc()

            await self._emit_event(
                "compensation_failed",
                error=str(e),
                io_snapshot=self._build_io_snapshot(include_outputs=True),
            )

            self.logger.error(
                "Compensation FAILED for '%s' on attempt %d: %s",
                self.name, self.compensation_attempts, e,
            )
            return False

    async def compensate_impl(self):
        """
        Subclass-provided compensation logic — the saga-rollback for this process.

        Default: no-op. Override in subclasses that have side-effects worth
        rolling back. Symmetric to execute_impl(): same access to self.input
        and self.output. Should be idempotent (may be retried).

        Example:
            class DeleteArtrackRefs(AtomarProcess):
                async def execute_impl(self):
                    await artrack_api.delete_refs(self.input["asset_id"].value)
                    self.output["deleted_count"].value = ...

                async def compensate_impl(self):
                    # restore the refs we deleted
                    await artrack_api.restore_refs(self.input["asset_id"].value)
        """
        pass

    @property
    def has_compensation(self) -> bool:
        """True if this process has overridden compensate_impl().

        Used by OrchestratedProcess to decide which children to roll back
        during a saga sweep. Walks the MRO to detect override vs inherited
        default.
        """
        for klass in type(self).__mro__:
            if "compensate_impl" in klass.__dict__:
                # Found the most-derived definition
                return klass is not Process
        return False

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

    def _build_io_snapshot(self, include_outputs: bool = True) -> Dict[str, Dict[str, Any]]:
        """Build a lightweight, JSON-serializable preview of inputs/outputs."""
        return {
            "inputs": self._param_preview(self.input),
            "outputs": self._param_preview(self.output) if include_outputs else {}
        }

    def _param_preview(self, params) -> Dict[str, Any]:
        preview = {}
        for name, param in params.items():
            preview[name] = {
                "type": param.param_type.__name__ if isinstance(param.param_type, type) else str(param.param_type),
                "required": param.required,
                "value": self._preview_value(param.value),
            }
        return preview

    def _preview_value(self, val, depth: int = 0):
        """Safe, short preview for event payloads."""
        max_str = 120
        max_items = 3

        if depth > 2:
            return "…"

        if isinstance(val, (str, int, float, bool)) or val is None:
            if isinstance(val, str) and len(val) > max_str:
                return val[:max_str] + "…"
            return val

        if isinstance(val, list):
            return {
                "type": "list",
                "len": len(val),
                "preview": [self._preview_value(v, depth + 1) for v in val[:max_items]]
            }

        if isinstance(val, dict):
            items = list(val.items())[:max_items]
            return {
                "type": "dict",
                "len": len(val),
                "preview": {k: self._preview_value(v, depth + 1) for k, v in items}
            }

        return str(val)[:max_str] + ("…" if len(str(val)) > max_str else "")

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
            "compensated_at": self.compensated_at.isoformat() if self.compensated_at else None,
            "compensation_attempts": self.compensation_attempts,
            "compensation_error": self.compensation_error,
            "has_compensation": self.has_compensation,
            "parent_run_id": self.parent_run_id,
            "parent_relation": self.parent_relation,
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

    def __init__(self, name: Optional[str] = None, depth: int = 0):
        super().__init__(name, depth)

    def define_parameters(self) -> None:
        """Define parameters - override in subclass if needed."""
        pass


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

    def __init__(self, name: Optional[str] = None, depth: int = 0):
        super().__init__(name, depth)
        self._children: List[Tuple[Process, ProcessExecutionFlags]] = []
        self._orchestration_defined = False
        self._param_connections: List[Tuple] = []
        # Resume-support: set by the runner before execute() when waking a
        # suspended run. _resume_from_step's outputs get injected from
        # _resume_outputs, execution continues with the step AFTER it.
        # _restored_outputs holds the persisted outputs of steps that
        # completed BEFORE the suspension (keyed by step name) — restored
        # into the pass-through steps so param-connections keep working.
        self._resume_from_step: Optional[str] = None
        self._resume_outputs: Optional[Dict[str, Any]] = None
        self._restored_outputs: Optional[Dict[str, Dict[str, Any]]] = None

    @property
    def children(self) -> List[Tuple[Process, ProcessExecutionFlags]]:
        """Get child processes."""
        return self._children

    def define_parameters(self) -> None:
        """Define parameters - override in subclass if needed."""
        pass

    def add_child(self, process: Process, execution_flag: ProcessExecutionFlags,
                  skip_when=None):
        """
        Add a child process to this orchestrated process.

        Args:
            process: Child process instance
            execution_flag: Sequential or Parallel execution
            skip_when: optional callable(orchestrator) -> bool. Evaluated just
                before the step runs; if it returns True the step is skipped
                (status='skipped', no execute_impl, treated as completed
                pass-through). Lets a workflow branch conditionally on prior
                step outputs without a DSL — e.g. skip the Send-step when the
                classifier said 'out_of_scope'.
        """
        # Update child's depth for proper log indentation
        process._depth = self._depth + 1
        process._process_logger._depth = self._depth + 1
        process._skip_when = skip_when

        self._children.append((process, execution_flag))

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

    async def after_children_executed(self) -> None:
        """
        Hook called after all child processes have been executed.

        Override this method to perform post-execution logic,
        such as aggregating results from child processes or
        creating additional processes based on child outputs.

        This method is called after all children have completed
        but before the orchestrated process itself is marked as complete.

        Example:
            async def after_children_executed(self):
                # Aggregate results from child processes
                total = 0
                for child, _flag in self._children:
                    total += child.output["value"].value
                self.output["total"].value = total
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
        6. Handles failures — triggers saga-compensation sweep on completed children

        Saga semantics: if any child fails, all previously-completed children with
        `has_compensation == True` are compensated in REVERSE execution order
        before the failure is re-raised to the caller. This means callers always
        see "either all forward, or all compensated" — never partial-forward-state.
        """
        # Define orchestration if not already done
        if not self._orchestration_defined:
            self.orchestrate()
            self._orchestration_defined = True

        # Get parameter connections if defined
        param_connections = getattr(self, '_param_connections', [])

        # Group processes by execution mode
        sequential_groups = self._group_processes()

        # Track children completed successfully so we know what to compensate on failure.
        completed_children: List[Process] = []

        # Resume-mode: skip already-executed steps up to and including the
        # suspended one. Its outputs come from the resume payload.
        resume_skip_active = self._resume_from_step is not None
        resume_found = False

        try:
            # Execute groups
            for group_idx, group in enumerate(sequential_groups):
                if resume_skip_active and not resume_found:
                    skip_group = False
                    for process in group:
                        if process.name == self._resume_from_step:
                            # Inject resume outputs into the suspended step
                            for k, v in (self._resume_outputs or {}).items():
                                if k in process.output:
                                    process.output[k].value = v
                            process.status = ProcessStatus.COMPLETED
                            completed_children.append(process)
                            resume_found = True
                            skip_group = True
                        else:
                            # Steps before the resume-point already ran in the
                            # original execution — restore their persisted
                            # outputs so param-connections downstream work.
                            restored = (self._restored_outputs or {}).get(
                                process.name, {}
                            )
                            for k, v in restored.items():
                                if k in process.output:
                                    process.output[k].value = v
                            process.status = ProcessStatus.COMPLETED
                            completed_children.append(process)
                            skip_group = True
                    if skip_group:
                        # Still resolve param connections so downstream steps
                        # see the injected outputs.
                        for source, target in param_connections:
                            if source.value is not None:
                                target.value = source.value
                        continue
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

                # Conditional skip: evaluate skip_when against the live
                # orchestrator (so it can read prior step outputs). Skipped
                # steps count as completed pass-throughs.
                runnable = []
                for process in group:
                    skip_fn = getattr(process, "_skip_when", None)
                    if skip_fn is not None:
                        try:
                            should_skip = bool(skip_fn(self))
                        except Exception:
                            should_skip = False
                        if should_skip:
                            process.status = ProcessStatus.COMPLETED
                            completed_children.append(process)
                            await process._emit_event("skipped")
                            continue
                    runnable.append(process)
                if not runnable:
                    await self._emit_event("group_completed", group_index=group_idx)
                    continue
                group = runnable

                if len(group) == 1:
                    # Sequential execution
                    process = group[0]
                    success = await process.execute()

                    if not success:
                        raise Exception(
                            f"Process '{process.name}' failed: {process.error}"
                        )

                    completed_children.append(process)
                else:
                    # Parallel execution
                    tasks = [p.execute() for p in group]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Mark children that completed before checking failures —
                    # parallel siblings may have all run, but only successful
                    # ones go on the compensation list.
                    for process, result in zip(group, results):
                        if isinstance(result, bool) and result:
                            completed_children.append(process)

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

            # Call hook for post-execution logic
            await self.after_children_executed()

        except WorkflowSuspend as suspend:
            # Annotate which step suspended so the runner can persist the
            # resume-position. NO saga sweep — suspension is not failure.
            for group in sequential_groups:
                for process in group:
                    if process.status == ProcessStatus.WAITING:
                        suspend.suspended_step = process.name
                        break
            # Snapshot all completed steps' outputs so the runner can persist
            # them — on resume they are restored into the pass-through steps.
            # Without this, outputs from steps between two suspension points
            # would be lost (fresh instance on each resume).
            suspend.completed_outputs = {
                child.name: {
                    k: p.value for k, p in child.output.items()
                    if p.value is not None
                }
                for child in completed_children
            }
            raise

        except Exception as forward_error:
            # Saga sweep: compensate completed children in REVERSE order.
            # Children without compensate_impl() override are skipped (no-op).
            await self._saga_compensate(completed_children, forward_error)
            raise

    async def _saga_compensate(
        self,
        completed_children: List[Process],
        forward_error: Exception,
    ):
        """Compensate already-completed children in reverse execution order.

        Failures during compensation are recorded but do NOT abort the sweep —
        we try every child. The compensation summary is emitted as a single
        event for monitoring. Async-compensation (long-running rollbacks) is
        handled by spawning a child-run with `parent_relation='compensation'`
        — see swfme_api documentation for the pattern.
        """
        if not completed_children:
            return

        candidates = [c for c in reversed(completed_children) if c.has_compensation]
        if not candidates:
            self.logger.info(
                "Saga sweep skipped for '%s' — no completed children declare compensation",
                self.name,
            )
            return

        await self._emit_event(
            "saga_compensation_started",
            forward_error=str(forward_error),
            compensation_targets=[c.name for c in candidates],
        )

        compensated = []
        failed = []
        for child in candidates:
            ok = await child.compensate()
            if ok:
                compensated.append(child.name)
            else:
                failed.append({
                    "name": child.name,
                    "error": child.compensation_error,
                })

        await self._emit_event(
            "saga_compensation_completed",
            compensated=compensated,
            compensation_failed=failed,
            forward_error=str(forward_error),
        )

        if failed:
            self.logger.error(
                "Saga sweep for '%s': %d/%d children compensated, %d failed",
                self.name, len(compensated), len(candidates), len(failed),
            )

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

        for process, flag in self._children:
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
        for process, _ in self._children:
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
            for p, flag in self._children
        ]
        return base

# Convenience constants for easy import
SEQUENTIAL = ProcessExecutionFlags.SEQUENTIAL
PARALLEL = ProcessExecutionFlags.PARALLEL
