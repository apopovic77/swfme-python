"""WaitForEvent — generic suspension step.

Suspends the surrounding workflow until an external event matching
event_filter arrives on the swfme Event-Bus, OR until timeout passes.

Design constraint (MVP): place WaitForEvent as early as possible in the
workflow — steps before it re-run as completed pass-throughs on resume,
their outputs are NOT restored (the resumed instance is a fresh object).
The C2-pattern (wait first, then act on the event payload) fits naturally.

The engine resumes by injecting:
    event_payload — the matched event's payload dict (or {} on timeout)
    triggered_by  — "event" | "timeout"
"""

from datetime import datetime, timedelta

from swfme.core.parameters import InputParameter, OutputParameter
from swfme.core.process import AtomarProcess, WorkflowSuspend


class WaitForEvent(AtomarProcess):
    def define_parameters(self):
        self.input.add(InputParameter(
            "event_filter", dict, required=True,
            description="Match-spec: {'event': 'conversation.message_received', "
                        "'thread_id': '...', 'from_match': '*@c2circle.de'}. "
                        "String-equality per key; *_match keys use glob.",
        ))
        self.input.add(InputParameter(
            "timeout_hours", int, required=False, default=720,  # 30 days
            description="After this many hours the workflow resumes with "
                        "triggered_by='timeout' and empty event_payload.",
        ))
        self.output.add(OutputParameter("event_payload", dict, required=False))
        self.output.add(OutputParameter("triggered_by", str, required=False))

    async def execute_impl(self):
        timeout_at = datetime.utcnow() + timedelta(
            hours=self.input["timeout_hours"].value or 720
        )
        raise WorkflowSuspend(wait_for={
            "filter": self.input["event_filter"].value,
            "timeout_at": timeout_at.isoformat() + "Z",
        })
