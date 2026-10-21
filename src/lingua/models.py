from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

from pydantic import BaseModel, Field


def normalize_space(value: str) -> str:
    # Alguns Kindles repetem o BOM no início de blocos posteriores do arquivo.
    # Ele não deve criar títulos, autores ou fingerprints distintos.
    clean = value.replace("\ufeff", "").replace("\u200b", "")
    return re.sub(r"\s+", " ", clean).strip()


@dataclass(frozen=True, slots=True)
class Clipping:
    title: str
    author: str
    location: str
    text: str
    metadata: str
    source: str = ""
    entry_type: str = "kindle"

    @property
    def book_key(self) -> str:
        raw = f"{normalize_space(self.title).casefold()}\0{normalize_space(self.author).casefold()}"
        return sha256(raw.encode("utf-8")).hexdigest()[:12]

    @property
    def fingerprint(self) -> str:
        if self.entry_type == "manual":
            raw = "\0".join(
                (
                    self.entry_type,
                    normalize_space(self.source).casefold(),
                    normalize_space(self.text),
                )
            )
            return sha256(raw.encode("utf-8")).hexdigest()
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
    corrected_english: str = Field(min_length=1)
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
