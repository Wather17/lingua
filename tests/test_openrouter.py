import json

import httpx
import pytest

from lingua.clippings import parse_text
from lingua.openrouter import OpenRouterClient, OpenRouterError


CLIPPING = parse_text("Book (A)\n- Your Highlight at location 1\n\nHello world.\n==========").clippings[0]


def test_structured_translation_and_privacy_body() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        content = {
            "translations": [
                {
                    "id": CLIPPING.fingerprint,
                    "corrected_english": "Hello world.",
                    "portuguese": "Olá, mundo.",
                    "vocabulary": ["hello — olá"],
                    "grammar": "",
                }
            ]
        }
        return httpx.Response(
            200,
            json={
                "model": "resolved/model",
                "choices": [{"message": {"content": json.dumps(content)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 8, "cost": 0.001},
            },
        )

    transport = httpx.MockTransport(handler)
    with OpenRouterClient("secret", "https://example.test/v1", transport=transport) as client:
        translations, usage = client.translate([CLIPPING], "test/model")
    assert translations[0].corrected_english == "Hello world."
    assert translations[0].portuguese == "Olá, mundo."
    assert usage.model == "resolved/model"
    assert captured["provider"] == {"data_collection": "deny", "require_parameters": True}
    assert captured["response_format"]["json_schema"]["strict"] is True


def test_rejects_missing_ids() -> None:
    content = {"translations": []}
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})
    )
    with OpenRouterClient("secret", "https://example.test/v1", transport=transport) as client:
        with pytest.raises(OpenRouterError, match="IDs"):
            client.translate([CLIPPING], "test/model")


def test_does_not_retry_authentication_error() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, text="invalid key")

    with OpenRouterClient("bad", "https://example.test/v1", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OpenRouterError, match="401"):
            client.translate([CLIPPING], "test/model")
    assert calls == 1


def test_connection_check_uses_authenticated_key_endpoint() -> None:
    seen_path = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_path
        seen_path = request.url.path
        return httpx.Response(200, json={"data": {"limit_remaining": 1}})

    with OpenRouterClient("secret", "https://example.test/v1", transport=httpx.MockTransport(handler)) as client:
        client.check_connection()
    assert seen_path == "/v1/key"
