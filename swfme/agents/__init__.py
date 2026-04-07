"""
Agent-in-the-Loop System for sWFME

Provides reusable abstractions for integrating persistent AI agents
into sWFME workflows via queue-based communication.

Author: Alex Popovic (Arkturian)
"""

from swfme.agents.session import AgentSession
from swfme.agents.intervention import ProcessAgentIntervention

__all__ = ["AgentSession", "ProcessAgentIntervention"]
