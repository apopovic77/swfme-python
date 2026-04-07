"""
Communication Processes for sWFME

Reusable atomic processes for email, Telegram, and other messaging.
These are generic building blocks — configure via input parameters.

Author: Alex Popovic (Arkturian)
"""

import logging
from typing import Optional, List, Dict, Any

import httpx

from swfme.core.process import AtomarProcess
from swfme.core.parameters import InputParameter, OutputParameter


class ProcessFetchGmail(AtomarProcess):
    """
    Fetch new emails from Gmail via the Gmail API.

    Uses OAuth2 credentials to poll for unread/new messages.
    Returns a list of parsed email objects.

    Inputs:
        access_token (str): Gmail OAuth2 access token
        max_results (int, optional): Max emails to fetch (default: 10)
        query (str, optional): Gmail search query (default: "is:unread")
        api_base (str, optional): Gmail API base URL

    Outputs:
        emails (list): List of email dicts with id, from, subject, body, date
        count (int): Number of emails fetched
    """

    def define_parameters(self):
        self.input.add(InputParameter(
            "access_token", str, required=True,
            description="Gmail OAuth2 access token"
        ))
        self.input.add(InputParameter(
            "max_results", int, required=False, default=10,
            description="Max emails to fetch"
        ))
        self.input.add(InputParameter(
            "query", str, required=False, default="is:unread",
            description="Gmail search query"
        ))
        self.input.add(InputParameter(
            "api_base", str, required=False,
            default="https://gmail.googleapis.com/gmail/v1",
            description="Gmail API base URL"
        ))

        self.output.add(OutputParameter("emails", list, required=True))
        self.output.add(OutputParameter("count", int, required=True))

    async def execute_impl(self):
        token = self.input["access_token"].value
        max_results = self.input["max_results"].value
        query = self.input["query"].value
        api_base = self.input["api_base"].value

        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            # List messages
            resp = await client.get(
                f"{api_base}/users/me/messages",
                headers=headers,
                params={"q": query, "maxResults": max_results}
            )
            resp.raise_for_status()
            message_list = resp.json().get("messages", [])

            emails = []
            for msg_ref in message_list:
                # Fetch each message
                msg_resp = await client.get(
                    f"{api_base}/users/me/messages/{msg_ref['id']}",
                    headers=headers,
                    params={"format": "full"}
                )
                msg_resp.raise_for_status()
                msg_data = msg_resp.json()

                # Parse headers
                headers_list = msg_data.get("payload", {}).get("headers", [])
                header_dict = {h["name"]: h["value"] for h in headers_list}

                emails.append({
                    "id": msg_data["id"],
                    "thread_id": msg_data.get("threadId"),
                    "from": header_dict.get("From", ""),
                    "to": header_dict.get("To", ""),
                    "subject": header_dict.get("Subject", "(kein Betreff)"),
                    "date": header_dict.get("Date", ""),
                    "snippet": msg_data.get("snippet", ""),
                    "label_ids": msg_data.get("labelIds", []),
                })

            self.output["emails"].value = emails
            self.output["count"].value = len(emails)


class ProcessSendTelegram(AtomarProcess):
    """
    Send a message via Telegram Bot API.

    Inputs:
        bot_token (str): Telegram bot token
        chat_id (str): Target chat/user ID
        message (str): Message text (supports Markdown)
        parse_mode (str, optional): "Markdown" or "HTML" (default: "Markdown")

    Outputs:
        success (bool): Whether the message was sent
        message_id (int): Telegram message ID
    """

    def define_parameters(self):
        self.input.add(InputParameter(
            "bot_token", str, required=True,
            description="Telegram bot token"
        ))
        self.input.add(InputParameter(
            "chat_id", str, required=True,
            description="Target chat ID"
        ))
        self.input.add(InputParameter(
            "message", str, required=True,
            description="Message text"
        ))
        self.input.add(InputParameter(
            "parse_mode", str, required=False, default="Markdown",
            description="Parse mode: Markdown or HTML"
        ))

        self.output.add(OutputParameter("success", bool, required=True))
        self.output.add(OutputParameter("message_id", int, required=False))

    async def execute_impl(self):
        bot_token = self.input["bot_token"].value
        chat_id = self.input["chat_id"].value
        message = self.input["message"].value
        parse_mode = self.input["parse_mode"].value

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": parse_mode
            })

            data = resp.json()
            ok = data.get("ok", False)

            self.output["success"].value = ok
            if ok:
                self.output["message_id"].value = data["result"]["message_id"]
            else:
                self.logger.error(f"Telegram send failed: {data}")


class ProcessSendEmail(AtomarProcess):
    """
    Send an email via the comm-api or SMTP.

    Inputs:
        to (str): Recipient email address
        subject (str): Email subject
        body (str): Email body (plain text or HTML)
        comm_api_url (str, optional): Comm API URL for sending
        html (bool, optional): Whether body is HTML

    Outputs:
        success (bool): Whether the email was sent
        message_id (str): Email message ID
    """

    def define_parameters(self):
        self.input.add(InputParameter("to", str, required=True))
        self.input.add(InputParameter("subject", str, required=True))
        self.input.add(InputParameter("body", str, required=True))
        self.input.add(InputParameter(
            "comm_api_url", str, required=False,
            default="http://127.0.0.1:8055",
            description="Comm API base URL"
        ))
        self.input.add(InputParameter(
            "html", bool, required=False, default=False
        ))

        self.output.add(OutputParameter("success", bool, required=True))
        self.output.add(OutputParameter("message_id", str, required=False))

    async def execute_impl(self):
        to = self.input["to"].value
        subject = self.input["subject"].value
        body = self.input["body"].value
        comm_api_url = self.input["comm_api_url"].value

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{comm_api_url}/api/v1/email/send",
                json={
                    "to": to,
                    "subject": subject,
                    "body": body,
                    "html": self.input["html"].value
                }
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                self.output["success"].value = True
                self.output["message_id"].value = data.get("message_id", "")
            else:
                self.logger.error(f"Email send failed: {resp.status_code}")
                self.output["success"].value = False
