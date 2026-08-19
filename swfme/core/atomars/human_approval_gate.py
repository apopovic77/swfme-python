"""HumanApprovalGate — suspend until an approver decides.

The approver is the `approver` input parameter of THIS step, wired by the
workflow author in `orchestrate()`. It is NOT taken from the decorator's
`pre_approvals` dict — that dict is read in exactly one place
(`swfme_api/submission.py:needs_human_review`), where its mere presence
forces a manual review of the *submitted source*. It pauses nothing at
runtime. A workflow that declares `pre_approvals` but places no gate in
`orchestrate()` runs straight through without a single approval; that
misreading cost a full workflow design in August 2026.

The engine:
  1. persists pending_decision in workflow_runs
  2. notifies the approver(s) via IACP (handled by swfme-api on suspend)
  3. waits for POST /api/runs/{id}/approve or /reject
  4. resumes with decision + reviewer_note injected

WARNING — a rejection does NOT stop anything by itself. `resume_run`
injects the decision as this step's outputs and continues the run
unconditionally; there is no engine-side termination on 'rejected'
(verified 2026-08-16 in swfme_api WorkflowRunner.resume_run — the
word 'rejected' does not appear in the runner at all). An earlier version of this
docstring claimed the run would terminate as 'cancelled'. It does not.

Consequence: a workflow whose later steps do not READ `decision` treats
"no" exactly like "yes". Guard every step that has an effect. Prefer a
required input on the effecting step that raises unless the value is
"approved" — `skip_when` fails OPEN (process.py:784: a predicate that
throws yields should_skip=False, so the step RUNS).
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
