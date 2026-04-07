"""
Data Processes for sWFME

Reusable atomic processes for HTTP requests, content storage,
and data operations.

Author: Alex Popovic (Arkturian)
"""

from typing import Optional, Dict, Any

import httpx

from swfme.core.process import AtomarProcess
from swfme.core.parameters import InputParameter, OutputParameter


class ProcessHTTPRequest(AtomarProcess):
    """
    Generic HTTP request process.

    Inputs:
        url (str): Request URL
        method (str, optional): HTTP method (default: "GET")
        headers (dict, optional): Request headers
        body (dict, optional): JSON body for POST/PUT
        timeout (int, optional): Timeout in seconds (default: 30)

    Outputs:
        status_code (int): HTTP response status
        response_data (dict): Parsed JSON response
        response_text (str): Raw response text
    """

    def define_parameters(self):
        self.input.add(InputParameter("url", str, required=True))
        self.input.add(InputParameter(
            "method", str, required=False, default="GET"
        ))
        self.input.add(InputParameter(
            "headers", dict, required=False, default={}
        ))
        self.input.add(InputParameter(
            "body", dict, required=False
        ))
        self.input.add(InputParameter(
            "timeout", int, required=False, default=30
        ))

        self.output.add(OutputParameter("status_code", int, required=True))
        self.output.add(OutputParameter("response_data", dict, required=False))
        self.output.add(OutputParameter("response_text", str, required=False))

    async def execute_impl(self):
        url = self.input["url"].value
        method = self.input["method"].value.upper()
        headers = self.input["headers"].value or {}
        body = self.input["body"].value
        timeout = self.input["timeout"].value

        async with httpx.AsyncClient(timeout=float(timeout)) as client:
            resp = await client.request(
                method, url, headers=headers, json=body
            )

            self.output["status_code"].value = resp.status_code
            self.output["response_text"].value = resp.text

            try:
                self.output["response_data"].value = resp.json()
            except Exception:
                self.output["response_data"].value = {"raw": resp.text}


class ProcessStoreContent(AtomarProcess):
    """
    Store content via the Content API.

    Inputs:
        title (str): Content title
        content (str): Content body (markdown)
        metadata (dict, optional): Metadata JSON
        content_api_url (str, optional): Content API base URL

    Outputs:
        post_id (int): Created post ID
        success (bool): Whether storage succeeded
    """

    def define_parameters(self):
        self.input.add(InputParameter("title", str, required=True))
        self.input.add(InputParameter("content", str, required=True))
        self.input.add(InputParameter(
            "metadata", dict, required=False, default={}
        ))
        self.input.add(InputParameter(
            "content_api_url", str, required=False,
            default="https://content-api.arkturian.com"
        ))

        self.output.add(OutputParameter("post_id", int, required=True))
        self.output.add(OutputParameter("success", bool, required=True))

    async def execute_impl(self):
        title = self.input["title"].value
        content = self.input["content"].value
        metadata = self.input["metadata"].value
        api_url = self.input["content_api_url"].value

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{api_url}/api/v1/posts/",
                json={
                    "title": title,
                    "content": content,
                    "content_type": "md",
                    "status": "published",
                    "metadata_json": metadata
                }
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                self.output["post_id"].value = data.get("id", 0)
                self.output["success"].value = True
            else:
                self.logger.error(f"Content store failed: {resp.status_code}")
                self.output["post_id"].value = 0
                self.output["success"].value = False


class ProcessFetchContent(AtomarProcess):
    """
    Fetch content from the Content API.

    Inputs:
        post_id (int): Post ID to fetch
        content_api_url (str, optional): Content API base URL

    Outputs:
        title (str): Post title
        content (str): Post content
        metadata (dict): Post metadata
    """

    def define_parameters(self):
        self.input.add(InputParameter("post_id", int, required=True))
        self.input.add(InputParameter(
            "content_api_url", str, required=False,
            default="https://content-api.arkturian.com"
        ))

        self.output.add(OutputParameter("title", str, required=True))
        self.output.add(OutputParameter("content", str, required=True))
        self.output.add(OutputParameter("metadata", dict, required=False))

    async def execute_impl(self):
        post_id = self.input["post_id"].value
        api_url = self.input["content_api_url"].value

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{api_url}/api/v1/posts/{post_id}")
            resp.raise_for_status()
            data = resp.json()

            self.output["title"].value = data.get("title", "")
            self.output["content"].value = data.get("content", "")
            self.output["metadata"].value = data.get("metadata_json", {})
