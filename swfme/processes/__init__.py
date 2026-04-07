"""
Reusable Atomic Processes for sWFME

Generic building blocks that can be composed into any workflow.
Each process is self-contained with typed inputs/outputs.

Author: Alex Popovic (Arkturian)
"""

from swfme.processes.communication import (
    ProcessSendTelegram,
    ProcessSendEmail,
    ProcessFetchGmail,
)
from swfme.processes.ai import ProcessAIAnalyse, ProcessClaudeCliAnalyse
from swfme.processes.data import (
    ProcessHTTPRequest,
    ProcessStoreContent,
    ProcessFetchContent,
)

__all__ = [
    "ProcessSendTelegram",
    "ProcessSendEmail",
    "ProcessFetchGmail",
    "ProcessAIAnalyse",
    "ProcessClaudeCliAnalyse",
    "ProcessHTTPRequest",
    "ProcessStoreContent",
    "ProcessFetchContent",
]
