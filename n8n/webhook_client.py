"""Send synthetic notification payloads to the local n8n test Webhook."""

import json
import os
import re
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

HEADER_NAME = "X-Two-Pick-Secret"
TEST_EMAIL = re.compile(r"^[^@\s]+@example\.test$", re.IGNORECASE)
FORBIDDEN_FIELDS = {
    "password", "jwt", "secret_key", "private_conditions",
    "partner_email", "preferences", "avoidances", "max_budget",
}


class WebhookError(Exception):
    """A request failed without exposing credentials or request data."""


class WebhookTimeoutError(WebhookError):
    pass


class WebhookConnectionError(WebhookError):
    pass


class WebhookResponseError(WebhookError):
    pass


@dataclass(frozen=True)
class WebhookConfig:
    url: str
    secret: str | None
    timeout_seconds: float = 5.0

    def __post_init__(self):
        parsed = urlsplit(self.url)
        if (parsed.scheme not in ("http", "https")
                or parsed.hostname not in ("localhost", "127.0.0.1")
                or parsed.path != "/webhook-test/two-pick-test"
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Only the local n8n test Webhook URL is allowed")
        if not 0 < self.timeout_seconds <= 30:
            raise ValueError("Timeout must be between 0 and 30 seconds")

    @classmethod
    def from_environment(cls):
        url = os.getenv("TWO_PICK_N8N_WEBHOOK_URL")
        secret = os.getenv("TWO_PICK_N8N_WEBHOOK_SECRET")
        if not url or not secret:
            raise ValueError("n8n test URL and secret environment variables are required")
        return cls(url=url, secret=secret)


@dataclass(frozen=True)
class WebhookResult:
    status_code: int
    success: bool
    message: str
    errors: tuple[str, ...]


def _parse_response(status_code: int, body: bytes) -> WebhookResult:
    if status_code == 403:
        # n8n rejects Header Auth before the workflow's Code node runs.
        return WebhookResult(403, False, "Header Auth rejected", ())
    if status_code not in (200, 400):
        raise WebhookResponseError(f"Unexpected n8n HTTP status: {status_code}")
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError) as error:
        raise WebhookResponseError("n8n response is not JSON") from error
    if (not isinstance(data, dict)
            or data.get("status_code") != status_code
            or data.get("success") is not (status_code == 200)
            or not isinstance(data.get("message"), str)
            or not isinstance(data.get("errors"), list)
            or any(not isinstance(item, str) for item in data["errors"])):
        raise WebhookResponseError("n8n response contract mismatch")
    return WebhookResult(status_code, data["success"], data["message"],
                         tuple(data["errors"]))


def send_test_webhook(payload: dict, config: WebhookConfig, opener=None) -> WebhookResult:
    """POST one test request. Never logs keys, payload, or raw response bodies."""
    if not isinstance(payload, dict) or not TEST_EMAIL.fullmatch(
            str(payload.get("recipient_email", ""))):
        raise ValueError("Only synthetic example.test recipients are allowed")
    if FORBIDDEN_FIELDS.intersection(payload):
        raise ValueError("Sensitive fields are not allowed in the test payload")
    headers = {"Content-Type": "application/json"}
    if config.secret is not None:
        headers[HEADER_NAME] = config.secret
    request = Request(config.url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers=headers, method="POST")
    opener = opener or urlopen
    try:
        with opener(request, timeout=config.timeout_seconds) as response:
            return _parse_response(response.status, response.read(65537))
    except HTTPError as error:
        return _parse_response(error.code, error.read(65537))
    except (TimeoutError, socket.timeout) as error:
        raise WebhookTimeoutError("n8n request timed out") from error
    except URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise WebhookTimeoutError("n8n request timed out") from error
        raise WebhookConnectionError("Cannot connect to local n8n") from error
