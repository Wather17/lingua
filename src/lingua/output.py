from __future__ import annotations

import csv
from datetime import datetime
import html
import json
from pathlib import Path
import re
import unicodedata

from .config import Config
from .state import StateStore


DRAFT_COLUMNS = [
    "Include",
    "English",
    "TypedEnglish",
    "Portuguese",
    "Vocabulary",
    "Grammar",
    "Book",
    "Author",
    "Location",
    "Source",
    "CardID",
    "Model",
]
LEGACY_DRAFT_COLUMNS = [
    "Include",
    "English",
    "Portuguese",
    "Vocabulary",
    "Grammar",
    "Book",
    "Author",
    "Location",
    "CardID",
    "Model",
]
ANKI_COLUMNS = ["CardID", "English", "Portuguese", "Vocabulary", "Grammar", "Source", "Audio", "Tags"]


def html_text(value: str) -> str:
    return _escaped_breaks(value)


def vocabulary_html(value: str) -> str:
    entries = [entry.strip() for entry in re.split(r"(?:\r?\n|<br\s*/?>)", value, flags=re.IGNORECASE) if entry.strip()]
    return "<br>".join(html.escape(entry) for entry in entries)


def write_draft(rows: list, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DRAFT_COLUMNS, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "Include": "yes",
                    "English": _single_line(row["corrected_english"] or row["english"]),
                    "TypedEnglish": _single_line(row["english"]),
                    "Portuguese": _single_line(row["portuguese"] or ""),
                    "Vocabulary": _single_line(row["vocabulary"] or ""),
                    "Grammar": _single_line(row["grammar"] or ""),
                    "Book": _single_line(row["title"]),
                    "Author": _single_line(row["author"]),
                    "Location": _single_line(row["location"]),
                    "Source": _single_line(row["source"] or ""),
                    "CardID": row["fingerprint"],
                    "Model": row["model"] or "",
                }
            )
    temporary.replace(output)
    return output


def export_anki(draft: Path, output: Path, config: Config, store: StateStore) -> tuple[int, int]:
    with draft.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != DRAFT_COLUMNS and reader.fieldnames != LEGACY_DRAFT_COLUMNS:
            raise ValueError("as colunas do rascunho foram alteradas ou estão fora de ordem")
        rows = list(reader)
    legacy = reader.fieldnames == LEGACY_DRAFT_COLUMNS
    exported: list[str] = []
    rejected: list[str] = []
    cards: list[dict[str, str]] = []
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        include = row["Include"].strip().casefold()
        card_id = row["CardID"].strip()
        if not re.fullmatch(r"[0-9a-f]{64}", card_id):
            raise ValueError(f"CardID inválido na linha {line_number}")
        if card_id in seen:
            raise ValueError(f"CardID duplicado na linha {line_number}")
        seen.add(card_id)
        if include in {"no", "não", "nao", "false", "0"}:
            rejected.append(card_id)
            continue
        if include not in {"yes", "sim", "true", "1"}:
            raise ValueError(f"Include deve ser yes/no na linha {line_number}")
        if not row["English"].strip() or not row["Portuguese"].strip():
            raise ValueError(f"English e Portuguese são obrigatórios na linha {line_number}")
        source = "" if legacy else row["Source"].strip()
        if row["Book"].strip():
            tags = f"lingua kindle book::{slugify(row['Book'])}"
        elif source:
            tags = f"lingua manual source::{slugify(source)}"
        else:
            tags = "lingua manual"
        source_parts = [source, row["Book"], row["Author"], row["Location"]]
        cards.append(
            {
                "CardID": card_id,
                "English": html_text(row["English"]),
                "Portuguese": html_text(row["Portuguese"]),
                "Vocabulary": vocabulary_html(row["Vocabulary"]),
                "Grammar": html_text(row["Grammar"]) if row["Grammar"].strip() else "",
                "Source": "<br>".join(html.escape(part.strip()) for part in source_parts if part.strip()),
                "Audio": "",
                "Tags": tags,
            }
        )
        exported.append(card_id)
    known = store.statuses(list(seen))
    unknown = sorted(seen - known.keys())
    if unknown:
        raise ValueError(f"o rascunho contém {len(unknown)} CardID desconhecido(s)")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write("#separator:Tab\n")
        handle.write("#html:true\n")
        handle.write(f"#notetype:{config.notetype}\n")
        handle.write(f"#deck:{config.deck}\n")
        handle.write("#columns:" + "\t".join(ANKI_COLUMNS) + "\n")
        handle.write("#tags column:8\n")
        writer = csv.DictWriter(handle, fieldnames=ANKI_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writerows(cards)
    temporary.replace(output)
    store.mark_many(exported, "exported")
    store.mark_many(rejected, "rejected")
    return len(exported), len(rejected)


def default_named_path(directory: Path, book: str, suffix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return directory / f"{slugify(book)}-{stamp}{suffix}"


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug[:60] or "book"


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _single_line(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>").replace("\t", " ").strip()


def _escaped_breaks(value: str) -> str:
    parts = re.split(r"(?:\r?\n|<br\s*/?>)", value.strip(), flags=re.IGNORECASE)
    return "<br>".join(html.escape(part) for part in parts)
