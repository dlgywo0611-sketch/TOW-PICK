"""Mock transport checks for the local-only n8n test client."""

import io
import json
import secrets
import socket
import unittest
from urllib.error import HTTPError, URLError

from n8n.test_webhook import build_synthetic_payload
from n8n.webhook_client import (
    HEADER_NAME, WebhookConfig, WebhookConnectionError,
    WebhookResponseError, WebhookTimeoutError, send_test_webhook,
)


class FakeResponse:
    def __init__(self, status, data):
        self.status = status
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return self.data


class N8nWebhookClientTests(unittest.TestCase):
    def setUp(self):
        self.secret = secrets.token_urlsafe(24)
        self.config = WebhookConfig(
            "http://localhost:5678/webhook-test/two-pick-test", self.secret)
        self.payload = build_synthetic_payload()

    @staticmethod
    def body(status, success):
        return json.dumps({"success": success, "status_code": status,
                           "message": "Validation result", "errors": []}).encode()

    def test_isolated_payload_has_only_contract_fields_and_fake_recipient(self):
        self.assertEqual(set(self.payload), {
            "job_id", "schedule_id", "notification_type", "occurrence_date",
            "send_at", "recipient_email", "dedupe_key", "message",
        })
        self.assertEqual(self.payload["recipient_email"], "n8n-smoke@example.test")

    def test_success_uses_post_json_header_auth_and_timeout(self):
        def opener(request, timeout):
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(timeout, 5)
            headers = {key.lower(): value for key, value in request.header_items()}
            self.assertEqual(headers[HEADER_NAME.lower()], self.secret)
            self.assertEqual(headers["content-type"], "application/json")
            self.assertEqual(json.loads(request.data), self.payload)
            return FakeResponse(200, self.body(200, True))
        result = send_test_webhook(self.payload, self.config, opener)
        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)

    def test_input_error_returns_400_without_raw_body(self):
        def opener(request, timeout):
            raise HTTPError(request.full_url, 400, "Bad Request", {},
                            io.BytesIO(self.body(400, False)))
        result = send_test_webhook(self.payload, self.config, opener)
        self.assertEqual((result.status_code, result.success), (400, False))

    def test_missing_and_wrong_header_auth_are_403(self):
        for secret in (None, secrets.token_urlsafe(24)):
            with self.subTest(secret_present=secret is not None):
                def opener(request, timeout):
                    headers = {key.lower(): value for key, value in request.header_items()}
                    self.assertEqual(headers.get(HEADER_NAME.lower()), secret)
                    raise HTTPError(request.full_url, 403, "Forbidden", {},
                                    io.BytesIO(b"Forbidden"))
                result = send_test_webhook(
                    self.payload, WebhookConfig(self.config.url, secret), opener)
                self.assertEqual((result.status_code, result.success), (403, False))

    def test_connection_failure_and_timeout_are_distinct(self):
        def unavailable(_request, timeout):
            raise URLError("connection refused")
        with self.assertRaises(WebhookConnectionError):
            send_test_webhook(self.payload, self.config, unavailable)
        def timed_out(_request, timeout):
            raise URLError(socket.timeout())
        with self.assertRaises(WebhookTimeoutError):
            send_test_webhook(self.payload, self.config, timed_out)

    def test_unexpected_or_invalid_response_is_rejected(self):
        with self.assertRaises(WebhookResponseError):
            send_test_webhook(self.payload, self.config,
                              lambda _request, timeout: FakeResponse(200, b"not json"))
        with self.assertRaises(WebhookResponseError):
            send_test_webhook(self.payload, self.config,
                              lambda _request, timeout: FakeResponse(500, b"error"))
        with self.assertRaises(WebhookResponseError):
            send_test_webhook(self.payload, self.config,
                              lambda _request, timeout: FakeResponse(200,
                                  self.body(400, False)))

    def test_real_email_sensitive_fields_and_nonlocal_url_are_blocked(self):
        with self.assertRaises(ValueError):
            send_test_webhook({**self.payload, "recipient_email": "person@invalid.example"},
                              self.config)
        with self.assertRaises(ValueError):
            send_test_webhook({**self.payload, "private_conditions": "secret"},
                              self.config)
        with self.assertRaises(ValueError):
            WebhookConfig("https://example.com/webhook-test/two-pick-test", self.secret)
        with self.assertRaises(ValueError):
            WebhookConfig("http://localhost:5678/webhook/two-pick-test", self.secret)


if __name__ == "__main__":
    unittest.main()
