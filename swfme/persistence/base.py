"""Persistence-Backend interface — async ABC.

Concrete implementations:
  - InMemoryBackend (default, no dependencies, lost on restart)
  - PostgresBackend (swfme-api, survives crashes, supports recovery + audit)

The Engine and swfme-api both consume this interface and never touch SQL
directly. Outbox / dead-letter / run-recovery are all routed through here.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class PersistenceBackend(ABC):
    """Storage interface for workflow runs, steps, outbox + dead-letter."""

    # ─── Run lifecycle ──────────────────────────────────────────────

    @abstractmethod
    async def save_run(
        self,
        run_id: str,
        workflow_name: str,
        workflow_version: str,
        tenant_id: str,
        caller_agent: Optional[str],
        parameters: Dict[str, Any],
        idempotency_key: str,
        parent_run_id: Optional[str] = None,
        parent_relation: Optional[str] = None,
    ) -> None:
        """Persist a new run in PENDING state.

        Compound unique constraint on
        (tenant_id, workflow_name, caller_agent, idempotency_key) — if a
        duplicate is detected, raise IdempotencyConflict and the caller
        looks up the existing run instead.
        """
        ...

    @abstractmethod
    async def update_run_status(
        self,
        run_id: str,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        execution_time_ms: Optional[int] = None,
        error: Optional[str] = None,
        outputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Transition a run's status with optional timestamp + result fields."""
        ...

    @abstractmethod
    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a run by id — None if not found."""
        ...

    @abstractmethod
    async def find_run_by_idempotency(
        self,
        tenant_id: str,
        workflow_name: str,
        caller_agent: Optional[str],
        idempotency_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Lookup an existing run by the compound idempotency tuple."""
        ...

    @abstractmethod
    async def list_runs(
        self,
        tenant_id: Optional[str] = None,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Paginated run-browser."""
        ...

    @abstractmethod
    async def get_runs_by_status(self, status: str) -> List[Dict[str, Any]]:
        """All runs in the given status — used by recovery-worker on boot."""
        ...

    # ─── Step audit ─────────────────────────────────────────────────

    @abstractmethod
    async def save_step(
        self,
        run_id: str,
        step_id: str,
        step_name: str,
        step_class: str,
        inputs: Dict[str, Any],
        compensation_for: Optional[str] = None,
    ) -> None:
        ...

    @abstractmethod
    async def update_step_status(
        self,
        run_id: str,
        step_id: str,
        status: str,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        retry_count: Optional[int] = None,
    ) -> None:
        ...

    @abstractmethod
    async def list_steps(self, run_id: str) -> List[Dict[str, Any]]:
        ...

    # ─── Outbox (durable child-service calls) ───────────────────────

    @abstractmethod
    async def save_outbox(
        self,
        outbox_id: str,
        run_id: str,
        step_id: str,
        target_service: str,
        target_endpoint: str,
        payload: Dict[str, Any],
        idempotency_key: str,
    ) -> None:
        """Persist a child-service call BEFORE it leaves the wire.

        This is the durability boundary: once `save_outbox` returns, the
        Engine guarantees the call will eventually be delivered (after
        retries, possibly across swfme-api restarts) OR end up in the
        dead-letter queue with operator notification.
        """
        ...

    @abstractmethod
    async def get_pending_outbox(
        self,
        limit: int = 100,
        before: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Outbox entries due for delivery now — used by outbox-worker."""
        ...

    @abstractmethod
    async def mark_outbox_acked(self, outbox_id: str) -> None:
        ...

    @abstractmethod
    async def mark_outbox_failed(
        self,
        outbox_id: str,
        error: str,
        next_retry_at: Optional[datetime] = None,
    ) -> None:
        ...

    # ─── Dead-letter + Escalation ───────────────────────────────────

    @abstractmethod
    async def move_to_dead_letter(
        self,
        outbox_id: str,
        run_id: str,
        workflow_name: str,
        failure_reason: str,
        attempts: int,
        escalated_to: Optional[str] = None,
    ) -> None:
        ...

    @abstractmethod
    async def list_dead_letter(
        self,
        unresolved_only: bool = True,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def resolve_dead_letter(
        self,
        outbox_id: str,
        resolution: str,
    ) -> None:
        """Resolution: 'manual_retry' | 'abandoned' | 'compensated'."""
        ...


class IdempotencyConflict(Exception):
    """Raised by save_run when the idempotency tuple already exists.

    Caller looks up the existing run via find_run_by_idempotency and
    returns its run_id — guarantees same-trigger-twice → same-run-id.
    """

    def __init__(self, existing_run: Dict[str, Any]):
        self.existing_run = existing_run
        super().__init__(
            f"Idempotency conflict — existing run {existing_run.get('run_id')} "
            f"for ({existing_run.get('tenant_id')}, "
            f"{existing_run.get('workflow_name')}, "
            f"{existing_run.get('caller_agent')}, "
            f"{existing_run.get('idempotency_key')})"
        )


# ─── Phase 1 additions: Wait-State + Decisions ──────────────────────
# (appended as free methods on the ABC via monkey-friendly default impls
#  would be wrong — subclasses must implement. Declared here as abstract
#  extension protocol; both InMemoryBackend and PostgresBackend implement.)

class WaitStateMixin:
    """Extension protocol for Phase-1 backends. PersistenceBackend
    subclasses implement these alongside the original ABC methods."""

    async def update_run_suspension(self, run_id, wait_for=None,
                                     pending_decision=None,
                                     suspended_step=None, expires_at=None):
        raise NotImplementedError

    async def clear_run_suspension(self, run_id):
        raise NotImplementedError

    async def find_waiting_runs_matching(self, event_name, payload):
        raise NotImplementedError

    async def find_expired_waiting_runs(self):
        raise NotImplementedError

    async def save_decision(self, run_id, step_name, approver, decision, note):
        raise NotImplementedError
