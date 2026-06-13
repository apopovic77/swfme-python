"""EmitAudit — append an audit annotation to the workflow's audit_target.

audit_target comes from the workflow decorator, e.g. "content_post:816".
Best-effort: audit failure never fails the workflow (log + continue).

Supported targets:
    content_post:<id>  — annotation via content-api
    log:<session>      — line via log-api (fallback channel)
"""

import logging
import os

import httpx

from swfme.core.parameters import InputParameter, OutputParameter
from swfme.core.process import AtomarProcess

logger = logging.getLogger("swfme.atomars.emit_audit")

CONTENT_API_BASE = os.getenv("CONTENT_API_BASE", "https://content-api.arkturian.com")
CONTENT_API_KEY = os.getenv("CONTENT_ADMIN_API_KEY")


class EmitAudit(AtomarProcess):
    def define_parameters(self):
        self.input.add(InputParameter("message", str, required=True))
        self.input.add(InputParameter(
            "audit_target", str, required=False,
            description="Override; default comes from workflow decorator "
                        "via runner-injection.",
        ))
        self.output.add(OutputParameter("emitted", bool, required=False))

    async def execute_impl(self):
        target = self.input["audit_target"].value or ""
        message = self.input["message"].value

        if not target:
            logger.info("EmitAudit (no target): %s", message)
            self.output["emitted"].value = False
            return

        try:
            if target.startswith("content_post:"):
                post_id = int(target.split(":", 1)[1])
                async with httpx.AsyncClient(timeout=10) as client:
                    headers = (
                        {"X-API-KEY": CONTENT_API_KEY} if CONTENT_API_KEY else {}
                    )
                    r = await client.post(
                        f"{CONTENT_API_BASE}/api/v1/posts/{post_id}/annotations",
                        json={
                            "body": message,
                            "metadata": {
                                "source": "swfme-audit",
                                "workflow_run_id": self.parent_run_id or self.id,
                                "step": self.name,
                            },
                        },
                        headers=headers,
                    )
                    r.raise_for_status()
                self.output["emitted"].value = True
            else:
                logger.info("EmitAudit (unsupported target %s): %s", target, message)
                self.output["emitted"].value = False
        except Exception as e:
            # Audit must never break the workflow
            logger.warning("EmitAudit failed for %s: %s", target, e)
            self.output["emitted"].value = False
