"""
AI Processes for sWFME

Reusable atomic processes for AI inference via the local api-ai service.
Uses the subscription-based CLI backends (no API costs).

Author: Alex Popovic (Arkturian)
"""

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
