"""
Agent Session Management for sWFME

Manages persistent AI agent sessions via the cloud-api queue system.
An AgentSession represents a long-running AI agent (e.g., Claude in tmux)
that can receive tasks and return responses.

Author: Alex Popovic (Arkturian)
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

import httpx


@dataclass
class AgentMessage:
    """A message sent to or received from an agent."""
    id: int
    text: str
    user_id: str
    status: str  # pending, processing, done, failed, timeout
    response: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class AgentSessionConfig:
    """Configuration for an agent session."""
    name: str
    cloud_api_url: str = "https://cloud.arkserver.arkturian.com"
    model: str = "sonnet"
    pretty: bool = True
    prompt_post_id: Optional[int] = None
    timeout: int = 300
    poll_interval: float = 2.0


class AgentSession:
    """
    Manages communication with a persistent AI agent via queue.

    The agent runs in a tmux session on the cloud-api server.
    Communication happens through a SQLite-backed message queue:
    1. Send message to queue (POST /api/queue/{session}/message)
    2. Agent picks up message, processes it
    3. Poll for response (GET /api/queue/{session}/message/{id})

    This class is stateless regarding the agent itself — the agent's
    state lives in the tmux session. This class only manages the
    queue communication.

    Example:
        session = AgentSession(AgentSessionConfig(
            name="email-agent",
            cloud_api_url="https://cloud.arkserver.arkturian.com"
        ))

        # Ensure agent is running
        await session.ensure_running()

        # Send task and wait for response
        response = await session.send_and_wait(
            "Analysiere diese Email: ...",
            user_id="email-pipeline"
        )
    """

    def __init__(self, config: AgentSessionConfig):
        self.config = config
        self.logger = logging.getLogger(f"swfme.agent.{config.name}")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def _api_base(self) -> str:
        return f"{self.config.cloud_api_url}/api"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def ensure_running(self) -> bool:
        """
        Ensure the agent session exists and is running.

        Returns:
            True if session is running, False if creation failed.
        """
        client = await self._get_client()

        # Check if session exists
        try:
            resp = await client.get(f"{self._api_base}/sessions/{self.config.name}")
            if resp.status_code == 200:
                self.logger.info(f"Agent session '{self.config.name}' is running")
                return True
        except httpx.HTTPError:
            pass

        # Create session
        self.logger.info(f"Creating agent session '{self.config.name}'")
        try:
            payload: Dict[str, Any] = {
                "name": self.config.name,
                "pretty": self.config.pretty,
                "model": self.config.model,
            }
            if self.config.prompt_post_id:
                payload["prompt_post_id"] = self.config.prompt_post_id

            resp = await client.post(
                f"{self._api_base}/sessions",
                json=payload
            )
            if resp.status_code in (200, 201):
                self.logger.info(f"Agent session '{self.config.name}' created")
                return True

            self.logger.error(
                f"Failed to create session: {resp.status_code} {resp.text}"
            )
            return False

        except httpx.HTTPError as e:
            self.logger.error(f"Failed to create session: {e}")
            return False

    async def send(self, message: str, user_id: str = "workflow") -> AgentMessage:
        """
        Send a message to the agent queue.

        Args:
            message: The task/question for the agent
            user_id: Identifier of the sender

        Returns:
            AgentMessage with id and pending status
        """
        client = await self._get_client()

        resp = await client.post(
            f"{self._api_base}/queue/{self.config.name}/message",
            json={"text": message, "user_id": user_id}
        )
        resp.raise_for_status()
        data = resp.json()

        return AgentMessage(
            id=data["id"],
            text=message,
            user_id=user_id,
            status=data.get("status", "pending"),
            created_at=datetime.utcnow()
        )

    async def get_response(self, message_id: int) -> AgentMessage:
        """
        Get the current state of a queued message.

        Args:
            message_id: The message ID returned by send()

        Returns:
            AgentMessage with current status and response (if done)
        """
        client = await self._get_client()

        resp = await client.get(
            f"{self._api_base}/queue/{self.config.name}/message/{message_id}"
        )
        resp.raise_for_status()
        data = resp.json()

        return AgentMessage(
            id=message_id,
            text=data.get("text", ""),
            user_id=data.get("user_id", ""),
            status=data.get("status", "unknown"),
            response=data.get("response"),
            completed_at=datetime.utcnow() if data.get("status") == "done" else None
        )

    async def wait_for_response(
        self,
        message_id: int,
        timeout: Optional[int] = None,
        poll_interval: Optional[float] = None
    ) -> AgentMessage:
        """
        Poll until the agent responds or timeout is reached.

        Args:
            message_id: The message ID to wait for
            timeout: Max seconds to wait (default: config.timeout)
            poll_interval: Seconds between polls (default: config.poll_interval)

        Returns:
            AgentMessage with response

        Raises:
            TimeoutError: If agent doesn't respond within timeout
        """
        timeout = timeout or self.config.timeout
        poll_interval = poll_interval or self.config.poll_interval
        elapsed = 0.0

        while elapsed < timeout:
            msg = await self.get_response(message_id)

            if msg.status == "done":
                self.logger.info(
                    f"Agent responded to message {message_id} "
                    f"after {elapsed:.1f}s"
                )
                return msg

            if msg.status in ("failed", "timeout"):
                raise RuntimeError(
                    f"Agent failed on message {message_id}: {msg.status}"
                )

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(
            f"Agent '{self.config.name}' did not respond to message "
            f"{message_id} within {timeout}s"
        )

    async def send_and_wait(
        self,
        message: str,
        user_id: str = "workflow",
        timeout: Optional[int] = None
    ) -> str:
        """
        Send a message and wait for the response. Convenience method.

        Args:
            message: The task/question for the agent
            user_id: Identifier of the sender
            timeout: Max seconds to wait

        Returns:
            The agent's response text

        Raises:
            TimeoutError: If agent doesn't respond within timeout
            RuntimeError: If agent fails to process the message
        """
        msg = await self.send(message, user_id)
        result = await self.wait_for_response(msg.id, timeout=timeout)
        return result.response or ""

    async def restart(self) -> bool:
        """
        Restart the agent session (kill + recreate).

        Useful for resetting context or recovering from errors.
        """
        client = await self._get_client()

        # Delete existing session
        try:
            await client.delete(f"{self._api_base}/sessions/{self.config.name}")
            self.logger.info(f"Deleted session '{self.config.name}'")
        except httpx.HTTPError:
            pass

        await asyncio.sleep(3)

        # Recreate
        return await self.ensure_running()
