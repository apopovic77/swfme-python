"""In-memory PersistenceBackend — default, no external dependencies.

State is lost on process restart. Use for tests, local development, or
embedded sidecars where workflow-state durability is not required.
swfme-api uses PostgresBackend for crash-recovery + audit.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from swfme.persistence.base import PersistenceBackend, IdempotencyConflict


class InMemoryBackend(PersistenceBackend):
    """All state in Python dicts. Thread-safe via single asyncio lock."""

    def __init__(self):
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._steps: Dict[str, List[Dict[str, Any]]] = {}  # run_id → [step, ...]
        self._outbox: Dict[str, Dict[str, Any]] = {}
        self._dead_letter: Dict[str, Dict[str, Any]] = {}
        # Composite-key index for idempotency lookup
        self._idem_index: Dict[tuple, str] = {}  # (tenant, wf, caller, key) → run_id
        self._lock = asyncio.Lock()

    # ─── Run lifecycle ──────────────────────────────────────────────

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
        async with self._lock:
            idem_tuple = (tenant_id, workflow_name, caller_agent, idempotency_key)
            if idem_tuple in self._idem_index:
                existing_id = self._idem_index[idem_tuple]
                raise IdempotencyConflict(self._runs[existing_id])

            self._runs[run_id] = {
                "run_id": run_id,
                "workflow_name": workflow_name,
                "workflow_version": workflow_version,
                "tenant_id": tenant_id,
                "caller_agent": caller_agent,
                "parameters": parameters,
                "idempotency_key": idempotency_key,
                "parent_run_id": parent_run_id,
                "parent_relation": parent_relation,
                "status": "pending",
                "created_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "execution_time_ms": None,
                "error": None,
                "outputs": None,
            }
            self._idem_index[idem_tuple] = run_id

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
        async with self._lock:
            run = self._runs.get(run_id)
            if not run:
                return
            run["status"] = status
            if started_at is not None:
                run["started_at"] = started_at
            if completed_at is not None:
                run["completed_at"] = completed_at
            if execution_time_ms is not None:
                run["execution_time_ms"] = execution_time_ms
            if error is not None:
                run["error"] = error
            if outputs is not None:
                run["outputs"] = outputs

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self._runs.get(run_id)

    async def find_run_by_idempotency(
        self,
        tenant_id: str,
        workflow_name: str,
        caller_agent: Optional[str],
        idempotency_key: str,
    ) -> Optional[Dict[str, Any]]:
        idem_tuple = (tenant_id, workflow_name, caller_agent, idempotency_key)
        run_id = self._idem_index.get(idem_tuple)
        return self._runs.get(run_id) if run_id else None

    async def list_runs(
        self,
        tenant_id: Optional[str] = None,
        workflow_name: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        results = list(self._runs.values())
        if tenant_id is not None:
            results = [r for r in results if r["tenant_id"] == tenant_id]
        if workflow_name is not None:
            results = [r for r in results if r["workflow_name"] == workflow_name]
        if status is not None:
            results = [r for r in results if r["status"] == status]
        if since is not None:
            results = [r for r in results if r["created_at"] >= since]
        results.sort(key=lambda r: r["created_at"], reverse=True)
        return results[offset : offset + limit]

    async def get_runs_by_status(self, status: str) -> List[Dict[str, Any]]:
        return [r for r in self._runs.values() if r["status"] == status]

    # ─── Step audit ─────────────────────────────────────────────────

    async def save_step(
        self,
        run_id: str,
        step_id: str,
        step_name: str,
        step_class: str,
        inputs: Dict[str, Any],
        compensation_for: Optional[str] = None,
    ) -> None:
        async with self._lock:
            step = {
                "run_id": run_id,
                "step_id": step_id,
                "step_name": step_name,
                "step_class": step_class,
                "inputs": inputs,
                "status": "pending",
                "outputs": None,
                "error": None,
                "retry_count": 0,
                "started_at": datetime.utcnow(),
                "completed_at": None,
                "compensation_for": compensation_for,
            }
            self._steps.setdefault(run_id, []).append(step)

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
        async with self._lock:
            for step in self._steps.get(run_id, []):
                if step["step_id"] == step_id:
                    step["status"] = status
                    if outputs is not None:
                        step["outputs"] = outputs
                    if error is not None:
                        step["error"] = error
                    if completed_at is not None:
                        step["completed_at"] = completed_at
                    if retry_count is not None:
                        step["retry_count"] = retry_count
                    return

    async def list_steps(self, run_id: str) -> List[Dict[str, Any]]:
        return list(self._steps.get(run_id, []))

    # ─── Outbox ─────────────────────────────────────────────────────

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
        async with self._lock:
            self._outbox[outbox_id] = {
                "outbox_id": outbox_id,
                "run_id": run_id,
                "step_id": step_id,
                "target_service": target_service,
                "target_endpoint": target_endpoint,
                "payload": payload,
                "idempotency_key": idempotency_key,
                "status": "pending",
                "attempts": 0,
                "next_retry_at": datetime.utcnow(),
                "last_error": None,
                "created_at": datetime.utcnow(),
                "acked_at": None,
            }

    async def get_pending_outbox(
        self,
        limit: int = 100,
        before: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        before = before or datetime.utcnow()
        pending = [
            e for e in self._outbox.values()
            if e["status"] == "pending" and e["next_retry_at"] <= before
        ]
        pending.sort(key=lambda e: e["next_retry_at"])
        return pending[:limit]

    async def mark_outbox_acked(self, outbox_id: str) -> None:
        async with self._lock:
            entry = self._outbox.get(outbox_id)
            if entry:
                entry["status"] = "acked"
                entry["acked_at"] = datetime.utcnow()

    async def mark_outbox_failed(
        self,
        outbox_id: str,
        error: str,
        next_retry_at: Optional[datetime] = None,
    ) -> None:
        async with self._lock:
            entry = self._outbox.get(outbox_id)
            if entry:
                entry["attempts"] += 1
                entry["last_error"] = error
                if next_retry_at is not None:
                    entry["next_retry_at"] = next_retry_at

    # ─── Dead-letter ────────────────────────────────────────────────

    async def move_to_dead_letter(
        self,
        outbox_id: str,
        run_id: str,
        workflow_name: str,
        failure_reason: str,
        attempts: int,
        escalated_to: Optional[str] = None,
    ) -> None:
        async with self._lock:
            self._dead_letter[outbox_id] = {
                "outbox_id": outbox_id,
                "run_id": run_id,
                "workflow_name": workflow_name,
                "failure_reason": failure_reason,
                "attempts": attempts,
                "escalated_at": datetime.utcnow(),
                "escalation_notified_to": escalated_to,
                "resolved_at": None,
                "resolution": None,
            }
            if outbox_id in self._outbox:
                self._outbox[outbox_id]["status"] = "failed"

    async def list_dead_letter(
        self,
        unresolved_only: bool = True,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results = list(self._dead_letter.values())
        if unresolved_only:
            results = [r for r in results if r["resolved_at"] is None]
        results.sort(key=lambda r: r["escalated_at"], reverse=True)
        return results[:limit]

    async def resolve_dead_letter(
        self,
        outbox_id: str,
        resolution: str,
    ) -> None:
        async with self._lock:
            entry = self._dead_letter.get(outbox_id)
            if entry:
                entry["resolved_at"] = datetime.utcnow()
                entry["resolution"] = resolution

    # ─── Phase 1: Wait-State + Decisions ────────────────────────────

    async def update_run_suspension(
        self, run_id, wait_for=None, pending_decision=None,
        suspended_step=None, expires_at=None, completed_outputs=None,
    ):
        async with self._lock:
            run = self._runs.get(run_id)
            if run:
                run["status"] = "waiting"
                run["wait_for"] = wait_for
                run["pending_decision"] = pending_decision
                run["suspended_step"] = suspended_step
                run["expires_at"] = expires_at
                run["completed_outputs"] = completed_outputs

    async def clear_run_suspension(self, run_id):
        async with self._lock:
            run = self._runs.get(run_id)
            if run:
                run["status"] = "running"
                run["wait_for"] = None
                run["pending_decision"] = None
                run["expires_at"] = None

    async def find_waiting_runs_matching(self, event_name, payload):
        import fnmatch
        matched = []
        for run in self._runs.values():
            if run.get("status") != "waiting" or not run.get("wait_for"):
                continue
            flt = (run["wait_for"] or {}).get("filter", {})
            want_event = flt.get("event")
            if want_event and want_event != event_name:
                continue
            ok = True
            for key, expected in flt.items():
                if key == "event":
                    continue
                if key.endswith("_match"):
                    actual = payload.get(key[:-6], "")
                    if not fnmatch.fnmatch(str(actual), str(expected)):
                        ok = False
                        break
                elif key.endswith("_contains"):
                    actual = payload.get(key[:-9], "")
                    if str(expected) not in str(actual):
                        ok = False
                        break
                else:
                    if str(payload.get(key, "")) != str(expected):
                        ok = False
                        break
            if ok:
                matched.append(run)
        return matched

    async def find_expired_waiting_runs(self):
        from datetime import datetime as _dt
        now = _dt.utcnow().isoformat() + "Z"
        return [
            r for r in self._runs.values()
            if r.get("status") == "waiting"
            and r.get("expires_at")
            and str(r["expires_at"]) <= now
        ]

    async def save_decision(self, run_id, step_name, approver, decision, note):
        if not hasattr(self, "_decisions"):
            self._decisions = []
        from datetime import datetime as _dt
        self._decisions.append({
            "run_id": run_id, "step_name": step_name, "approver": approver,
            "decision": decision, "note": note,
            "decided_at": _dt.utcnow(),
        })
