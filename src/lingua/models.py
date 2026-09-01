from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

from pydantic import BaseModel, Field


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


@dataclass(frozen=True, slots=True)
class Clipping:
    title: str
    author: str
    location: str
    text: str
    metadata: str

    @property
    def book_key(self) -> str:
        raw = f"{normalize_space(self.title).casefold()}\0{normalize_space(self.author).casefold()}"
        return sha256(raw.encode("utf-8")).hexdigest()[:12]

    @property
    def fingerprint(self) -> str:
        raw = "\0".join(
            (
                normalize_space(self.title).casefold(),
                normalize_space(self.author).casefold(),
                normalize_space(self.location).casefold(),
                normalize_space(self.text),
            )
        )
        return sha256(raw.encode("utf-8")).hexdigest()


class TranslationItem(BaseModel):
    id: str
    portuguese: str = Field(min_length=1)
    vocabulary: list[str] = Field(default_factory=list, max_length=3)
    grammar: str = ""


class TranslationResponse(BaseModel):
    translations: list[TranslationItem]


@dataclass(frozen=True, slots=True)
class TranslationUsage:
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    latency_seconds: float = 0.0

