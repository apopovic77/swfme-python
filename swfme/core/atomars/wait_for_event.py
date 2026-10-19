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
        self.input.add(InputParameter(
            "timeout_minutes", int, required=False, default=0,
            description="Optional, takes precedence over timeout_hours when > 0. "
                        "For short human-reach timeouts (ReachHuman, #5508). The "
                        "expiry sweeper runs every 60 s, so resolution is ~1 min.",
        ))
        self.output.add(OutputParameter("event_payload", dict, required=False))
        self.output.add(OutputParameter("triggered_by", str, required=False))

    async def execute_impl(self):
        minuten = self.input["timeout_minutes"].value
        if isinstance(minuten, int) and not isinstance(minuten, bool) and minuten > 0:
            dauer = timedelta(minutes=minuten)
        else:
            dauer = timedelta(hours=self.input["timeout_hours"].value or 720)
        timeout_at = datetime.utcnow() + dauer
        raise WorkflowSuspend(wait_for={
            "filter": self.input["event_filter"].value,
            "timeout_at": timeout_at.isoformat() + "Z",
        })
