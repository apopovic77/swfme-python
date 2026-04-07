"""
Agent-in-the-Loop Intervention Process for sWFME

A reusable AtomarProcess that delegates work to a persistent AI agent
via the queue system. Drop this into any OrchestratedProcess wherever
you need intelligent analysis, decision-making, or creative work.

Author: Alex Popovic (Arkturian)
"""

import json
import logging
from typing import Optional

from swfme.core.process import AtomarProcess
from swfme.core.parameters import InputParameter, OutputParameter
from swfme.agents.session import AgentSession, AgentSessionConfig


class ProcessAgentIntervention(AtomarProcess):
    """
    Delegates a task to a persistent AI agent and waits for the response.

    This is the "Agent-in-the-Loop" pattern — similar to Human-in-the-Loop,
    but with a persistent AI agent that has context, MCP tools, and memory.

    The agent runs in a tmux session via cloud-api. Communication goes
    through a message queue. The agent is NOT a stateless API call —
    it accumulates context over time and can make informed decisions.

    Inputs:
        message (str): The task/question for the agent
        agent_session (str): Name of the agent session (e.g., "email-agent")
        cloud_api_url (str, optional): Cloud API URL
        user_id (str, optional): Sender identifier
        timeout (int, optional): Max wait time in seconds
        parse_json (bool, optional): Try to parse response as JSON

    Outputs:
        response (str): Raw response from the agent
        response_data (dict): Parsed JSON response (if parse_json=True)
        message_id (int): Queue message ID for reference

    Example:
        intervention = ProcessAgentIntervention(name="AnalyseEmail")
        intervention.input["message"].value = "Analysiere: Von: kunde@firma.at ..."
        intervention.input["agent_session"].value = "email-agent"
        await intervention.execute()
        analysis = intervention.output["response"].value
    """

    def __init__(
        self,
        name: Optional[str] = None,
        depth: int = 0,
        session: Optional[AgentSession] = None
    ):
        self._injected_session = session
        super().__init__(name=name or "AgentIntervention", depth=depth)

    def define_parameters(self):
        # Inputs
        self.input.add(InputParameter(
            "message", str, required=True,
            description="Task or question for the agent"
        ))
        self.input.add(InputParameter(
            "agent_session", str, required=True,
            description="Agent session name (e.g., 'email-agent')"
        ))
        self.input.add(InputParameter(
            "cloud_api_url", str, required=False,
            default="https://cloud.arkserver.arkturian.com",
            description="Cloud API base URL"
        ))
        self.input.add(InputParameter(
            "user_id", str, required=False,
            default="workflow",
            description="Sender identifier"
        ))
        self.input.add(InputParameter(
            "timeout", int, required=False,
            default=300,
            description="Max wait time in seconds"
        ))
        self.input.add(InputParameter(
            "parse_json", bool, required=False,
            default=True,
            description="Try to parse agent response as JSON"
        ))

        # Outputs
        self.output.add(OutputParameter(
            "response", str, required=True,
            description="Raw response from the agent"
        ))
        self.output.add(OutputParameter(
            "response_data", dict, required=False,
            description="Parsed JSON response (if parse_json=True)"
        ))
        self.output.add(OutputParameter(
            "message_id", int, required=True,
            description="Queue message ID"
        ))

    async def execute_impl(self):
        message = self.input["message"].value
        session_name = self.input["agent_session"].value
        cloud_api_url = self.input["cloud_api_url"].value
        user_id = self.input["user_id"].value
        timeout = self.input["timeout"].value
        parse_json = self.input["parse_json"].value

        # Use injected session or create one
        if self._injected_session:
            session = self._injected_session
        else:
            config = AgentSessionConfig(
                name=session_name,
                cloud_api_url=cloud_api_url,
                timeout=timeout
            )
            session = AgentSession(config)

        try:
            # Ensure agent is running
            running = await session.ensure_running()
            if not running:
                raise RuntimeError(
                    f"Agent session '{session_name}' could not be started"
                )

            # Send message and wait for response
            msg = await session.send(message, user_id=user_id)
            self.output["message_id"].value = msg.id

            self.logger.info(
                f"Sent to agent '{session_name}' (msg #{msg.id}), "
                f"waiting up to {timeout}s..."
            )

            result = await session.wait_for_response(msg.id, timeout=timeout)
            response_text = result.response or ""

            self.output["response"].value = response_text

            # Try to parse JSON if requested
            if parse_json and response_text:
                try:
                    # Agent might wrap response in markdown code blocks
                    clean = response_text.strip()
                    if clean.startswith("```json"):
                        clean = clean[7:]
                    if clean.startswith("```"):
                        clean = clean[3:]
                    if clean.endswith("```"):
                        clean = clean[:-3]
                    clean = clean.strip()

                    self.output["response_data"].value = json.loads(clean)
                except (json.JSONDecodeError, ValueError):
                    self.output["response_data"].value = {
                        "raw": response_text
                    }
            else:
                self.output["response_data"].value = {"raw": response_text}

        finally:
            # Only close if we created the session ourselves
            if not self._injected_session:
                await session.close()
