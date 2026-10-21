from __future__ import annotations

import json
import time
from typing import Sequence

import httpx

from .models import Clipping, TranslationResponse, TranslationUsage


PROMPT_VERSION = "2026-10-21-v2"
SYSTEM_PROMPT = """Você cria microaulas para um brasileiro que está aprendendo inglês americano.
Para cada frase:
1. Preserve o texto recebido no campo de entrada; não o reescreva fora do campo de correção.
2. Gere corrected_english corrigindo somente ortografia, pontuação e problemas gramaticais claros. Preserve o significado e as palavras originais sempre que possível. Se não houver correção necessária, repita exatamente a frase recebida.
3. Traduza corrected_english naturalmente para pt-BR, preservando tom, sentido e ambiguidades relevantes.
4. Liste no máximo três palavras, phrasal verbs ou expressões realmente úteis, no formato "termo — explicação curta em português".
5. Escreva uma observação gramatical curta apenas quando ela ensinar algo útil; caso contrário, use string vazia.
Não resuma, não censure, não acrescente fatos e não use Markdown. Mantenha exatamente os IDs recebidos."""


TRANSLATION_SCHEMA = {
    "name": "kindle_translations",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "translations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "corrected_english": {"type": "string"},
                        "portuguese": {"type": "string"},
                        "vocabulary": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 3,
                        },
                        "grammar": {"type": "string"},
                    },
                    "required": ["id", "corrected_english", "portuguese", "vocabulary", "grammar"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["translations"],
        "additionalProperties": False,
    },
}


class OpenRouterError(RuntimeError):
    pass


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        data_collection: str = "deny",
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.data_collection = data_collection
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-Title": "Lingua Kindle",
            },
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "OpenRouterClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def check_connection(self) -> None:
        try:
            # /models is público e não comprova que a chave é válida. /key é o
            # endpoint autenticado de inspeção da chave atual.
            response = self.client.get("/key")
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise OpenRouterError(f"falha ao conectar ao OpenRouter: {error}") from error

    def translate(self, clippings: Sequence[Clipping], model: str) -> tuple[list, TranslationUsage]:
        if not clippings:
            return [], TranslationUsage(model=model)
        items = [
            {
                "id": item.fingerprint,
                "book": item.title,
                "author": item.author,
                "location": item.location,
                "english": item.text,
            }
            for item in clippings
        ]
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_schema", "json_schema": TRANSLATION_SCHEMA},
            "provider": {
                "data_collection": self.data_collection,
                "require_parameters": True,
            },
            "temperature": 0.2,
        }
        started = time.monotonic()
        response = self._post_with_retry(payload)
        latency = time.monotonic() - started
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            parsed = TranslationResponse.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise OpenRouterError(f"resposta estruturada inválida do modelo {model}") from error
        expected = {item.fingerprint for item in clippings}
        received = {item.id for item in parsed.translations}
        if expected != received or len(received) != len(parsed.translations):
            raise OpenRouterError(
                f"o modelo {model} devolveu IDs ausentes, extras ou duplicados"
            )
        usage = data.get("usage", {})
        return parsed.translations, TranslationUsage(
            model=data.get("model", model),
            prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage.get("completion_tokens", 0) or 0),
            cost=float(usage.get("cost", 0.0) or 0.0),
            latency_seconds=latency,
        )

    def _post_with_retry(self, payload: dict) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.client.post("/chat/completions", json=payload)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "erro transitório", request=response.request, response=response
                    )
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as error:
                last_error = error
                retryable = not isinstance(error, httpx.HTTPStatusError) or (
                    error.response.status_code == 429 or error.response.status_code >= 500
                )
                if not retryable:
                    break
                if attempt < 2:
                    time.sleep(0.5 * (2**attempt))
        detail = ""
        if isinstance(last_error, httpx.HTTPStatusError):
            detail = f" HTTP {last_error.response.status_code}: {last_error.response.text[:300]}"
        raise OpenRouterError(f"requisição ao OpenRouter falhou após novas tentativas.{detail}") from last_error
