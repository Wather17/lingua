from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re

from .models import Clipping, normalize_space


SEPARATOR = "=========="
HIGHLIGHT_RE = re.compile(r"\b(highlight|destaque|realce|sublinhado)\b", re.IGNORECASE)
NOTE_RE = re.compile(r"\b(note|nota|bookmark|marcador)\b", re.IGNORECASE)
AUTHOR_RE = re.compile(r"^(?P<title>.+?)\s+\((?P<author>[^()]*)\)\s*$")
LOCATION_RE = re.compile(
    r"(?:page|página|pagina|location|posição|posicao|localização|localizacao)\s+[^|]+",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ParseResult:
    clippings: list[Clipping]
    skipped: Counter[str]


def parse_file(path: Path) -> ParseResult:
    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"{path} não está em UTF-8: {error}") from error
    return parse_text(content)


def parse_json_file(path: Path) -> ParseResult:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        raise ValueError(f"{path} não está em UTF-8: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON inválido em {path}: {error.msg} (linha {error.lineno})") from error

    if not isinstance(data, dict) or set(data) != {"entries"}:
        raise ValueError("o JSON deve conter somente a propriedade 'entries'")
    entries = data["entries"]
    if not isinstance(entries, list):
        raise ValueError("'entries' deve ser uma lista")

    clippings: list[Clipping] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"entries[{index}] deve ser um objeto")
        unknown = set(entry) - {"text", "source"}
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"entries[{index}] contém propriedades desconhecidas: {names}")
        text = entry.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"entries[{index}].text deve ser um texto não vazio")
        source = entry.get("source", "")
        if not isinstance(source, str):
            raise ValueError(f"entries[{index}].source deve ser um texto")
        clipping = Clipping(
            title="",
            author="",
            location="",
            text=text,
            metadata="",
            source=source,
            entry_type="manual",
        )
        if clipping.fingerprint in seen:
            continue
        seen.add(clipping.fingerprint)
        clippings.append(clipping)
    return ParseResult(clippings=clippings, skipped=Counter())


def parse_input_file(path: Path) -> ParseResult:
    if path.suffix.casefold() == ".json":
        return parse_json_file(path)
    return parse_file(path)


def parse_text(content: str) -> ParseResult:
    clippings: list[Clipping] = []
    skipped: Counter[str] = Counter()
    for raw_block in content.replace("\r\n", "\n").replace("\r", "\n").split(SEPARATOR):
        block = raw_block.strip("\n \t")
        if not block:
            continue
        lines = block.split("\n")
        if len(lines) < 2:
            skipped["bloco incompleto"] += 1
            continue
        heading = lines[0].strip()
        metadata = lines[1].strip()
        if NOTE_RE.search(metadata) and not HIGHLIGHT_RE.search(metadata):
            skipped["não é destaque"] += 1
            continue
        if not HIGHLIGHT_RE.search(metadata):
            skipped["tipo desconhecido"] += 1
            continue
        if len(lines) < 3:
            skipped["bloco incompleto"] += 1
            continue
        text = "\n".join(lines[2:]).strip()
        if not text:
            skipped["destaque vazio"] += 1
            continue
        if not _looks_like_latin_text(text):
            skipped["idioma não suportado"] += 1
            continue
        title, author = _split_heading(heading)
        location_match = LOCATION_RE.search(metadata)
        location = normalize_space(location_match.group(0) if location_match else metadata.lstrip("- "))
        clippings.append(
            Clipping(
                title=title,
                author=author,
                location=location,
                text=text,
                metadata=metadata,
            )
        )
    return ParseResult(clippings=clippings, skipped=skipped)


def _split_heading(heading: str) -> tuple[str, str]:
    match = AUTHOR_RE.match(heading)
    if not match:
        return normalize_space(heading), ""
    return normalize_space(match.group("title")), normalize_space(match.group("author"))


def _looks_like_latin_text(text: str) -> bool:
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return False
    latin = sum("LATIN" in __import__("unicodedata").name(character, "") for character in letters)
    return latin / len(letters) >= 0.8


def group_books(clippings: list[Clipping]) -> dict[str, list[Clipping]]:
    books: dict[str, list[Clipping]] = {}
    for clipping in clippings:
        books.setdefault(clipping.book_key, []).append(clipping)
    return books
