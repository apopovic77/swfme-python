"""HumanApprovalGate — suspend until an approver decides.

The approver is named per-step in the workflow's pre_approvals decorator
dict (e.g. {"SendCounterMail": "human:Alex"}). The engine:
  1. persists pending_decision in workflow_runs
  2. notifies the approver(s) via IACP (handled by swfme-api on suspend)
  3. waits for POST /api/runs/{id}/approve or /reject
  4. resumes with decision + reviewer_note injected

On 'rejected' the workflow takes the rejected-branch if the orchestration
defines one, otherwise the run terminates as 'cancelled'.
"""

from swfme.core.parameters import InputParameter, OutputParameter
from swfme.core.process import AtomarProcess, WorkflowSuspend


class HumanApprovalGate(AtomarProcess):
    def define_parameters(self):
        self.input.add(InputParameter(
            "approver", str, required=True,
            description="'human:Alex' or 'human:Alex+Markus' (AND) or "
                        "'agent:Business' — who must decide.",
        ))
        self.input.add(InputParameter(
            "review_payload", dict, required=True,
            description="What the reviewer sees: draft text, classification, "
                        "context links. Shown in the Dashboard decision card.",
        ))
        self.output.add(OutputParameter("decision", str, required=False))
        self.output.add(OutputParameter("reviewer_note", str, required=False))

    async def execute_impl(self):
        raise WorkflowSuspend(pending_decision={
            "step_name": self.name,
            "approver": self.input["approver"].value,
            "review_payload": self.input["review_payload"].value,
        })
