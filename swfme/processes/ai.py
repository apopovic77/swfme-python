"""
AI Processes for sWFME

Reusable atomic processes for AI inference via the local api-ai service.
Uses the subscription-based CLI backends (no API costs).

Author: Alex Popovic (Arkturian)
"""

import asyncio
import shutil
from typing import Optional

import httpx

from swfme.core.process import AtomarProcess
from swfme.core.parameters import InputParameter, OutputParameter


class ProcessAIAnalyse(AtomarProcess):
    """
    Send a prompt to an AI model via the local api-ai service.

    Supports Claude, Gemini, and ChatGPT backends.
    Runs through subscription CLIs — no API billing.

    Inputs:
        prompt (str): The prompt/question
        system (str, optional): System prompt
        model (str, optional): "claude", "gemini", or "chatgpt" (default: "claude")
        max_tokens (int, optional): Max response tokens (default: 1000)
        temperature (float, optional): Sampling temperature (default: 0.3)
        api_base (str, optional): API base URL

    Outputs:
        response (str): AI response text
        model_used (str): Actual model identifier
        tokens_used (int): Token count
    """

    def define_parameters(self):
        self.input.add(InputParameter(
            "prompt", str, required=True,
            description="Prompt for the AI"
        ))
        self.input.add(InputParameter(
            "system", str, required=False,
            description="System prompt"
        ))
        self.input.add(InputParameter(
            "model", str, required=False, default="claude",
            description="AI backend: claude, gemini, chatgpt"
        ))
        self.input.add(InputParameter(
            "max_tokens", int, required=False, default=1000
        ))
        self.input.add(InputParameter(
            "temperature", float, required=False, default=0.3
        ))
        self.input.add(InputParameter(
            "api_base", str, required=False,
            default="http://127.0.0.1:8000",
            description="api-ai base URL"
        ))

        self.output.add(OutputParameter("response", str, required=True))
        self.output.add(OutputParameter("model_used", str, required=False))
        self.output.add(OutputParameter("tokens_used", int, required=False))

    async def execute_impl(self):
        prompt = self.input["prompt"].value
        system = self.input["system"].value
        model = self.input["model"].value
        max_tokens = self.input["max_tokens"].value
        temperature = self.input["temperature"].value
        api_base = self.input["api_base"].value

        # Map model name to endpoint
        endpoint_map = {
            "claude": "/ai/claude",
            "gemini": "/ai/gemini",
            "chatgpt": "/ai/chatgpt",
        }
        endpoint = endpoint_map.get(model, "/ai/claude")

        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{api_base}{endpoint}",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()

            self.output["response"].value = data.get(
                "response", data.get("message", "")
            )
            self.output["model_used"].value = data.get("model", model)
            self.output["tokens_used"].value = data.get("tokens_used", 0)


class ProcessClaudeCliAnalyse(AtomarProcess):
    """
    Send a prompt to Claude via the local `claude --print` CLI subprocess.

    Stateless: each invocation spawns a fresh `claude --print` process and
    captures its stdout. Uses whatever auth credentials the running user has
    in their `~/.claude.json`. No queue, no session pool, no API key required.

    Useful when:
    - You want to use a Claude subscription (not API key billing)
    - You have claude CLI installed locally on the same host
    - You don't need streaming or session continuity

    Inputs:
        prompt (str): The user prompt
        system (str, optional): System prompt — prepended to user prompt with separator
        model (str, optional): Claude model alias or full id (e.g. "sonnet",
            "opus", "claude-sonnet-4-6"). Default: "claude-sonnet-4-6"
        timeout (int, optional): Subprocess timeout in seconds (default: 120)
        claude_bin (str, optional): Path to claude binary. Auto-detected if empty.

    Outputs:
        response (str): Claude's text response
        model_used (str): The model name passed to claude CLI
        tokens_used (int): Always 0 (subscription mode, no token tracking)
    """

    def define_parameters(self):
        self.input.add(InputParameter(
            "prompt", str, required=True,
            description="Prompt for Claude"
        ))
        self.input.add(InputParameter(
            "system", str, required=False,
            description="System prompt (prepended to user prompt)"
        ))
        self.input.add(InputParameter(
            "model", str, required=False, default="claude-sonnet-4-6",
            description="Claude model alias or full id"
        ))
        self.input.add(InputParameter(
            "timeout", int, required=False, default=120,
            description="Subprocess timeout in seconds"
        ))
        self.input.add(InputParameter(
            "claude_bin", str, required=False, default="",
            description="Path to claude binary (auto-detected if empty)"
        ))

        self.output.add(OutputParameter("response", str, required=True))
        self.output.add(OutputParameter("model_used", str, required=False))
        self.output.add(OutputParameter("tokens_used", int, required=False))

    async def execute_impl(self):
        prompt = self.input["prompt"].value
        system = self.input["system"].value
        model = self.input["model"].value
        timeout = self.input["timeout"].value
        claude_bin = self.input["claude_bin"].value or shutil.which("claude") or "claude"

        # Build the combined prompt — claude --print takes a single positional prompt
        if system:
            full_prompt = f"{system}\n\n---\n\n{prompt}"
        else:
            full_prompt = prompt

        # Run claude --print --model X "<prompt>" via subprocess
        # --dangerously-skip-permissions: no interactive confirmations
        cmd = [
            claude_bin,
            "--print",
            "--model", model,
            "--dangerously-skip-permissions",
            full_prompt,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise RuntimeError(f"claude CLI timed out after {timeout}s")

            if proc.returncode != 0:
                err = stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"claude CLI exited with code {proc.returncode}: {err}")

            response = stdout.decode("utf-8", errors="replace").strip()
        except FileNotFoundError:
            raise RuntimeError(f"claude binary not found at {claude_bin}")

        self.output["response"].value = response
        self.output["model_used"].value = model
        self.output["tokens_used"].value = 0
