"""Generic, reusable AtomarProcess building blocks.

These are domain-free steps every workflow can compose:
    WaitForEvent       — suspend until matching external event OR timeout
    HumanApprovalGate  — suspend until approver decides via API
    EmitAudit          — append annotation to the workflow's audit_target
"""

from swfme.core.atomars.wait_for_event import WaitForEvent
from swfme.core.atomars.human_approval_gate import HumanApprovalGate
from swfme.core.atomars.emit_audit import EmitAudit

__all__ = ["WaitForEvent", "HumanApprovalGate", "EmitAudit"]
