import csv
from pathlib import Path

import pytest

from lingua.clippings import parse_file
from lingua.config import Config
from lingua.models import TranslationItem
from lingua.output import DRAFT_COLUMNS, export_anki, write_draft
from lingua.state import StateStore


FIXTURE = Path(__file__).parent / "fixtures" / "clippings_mixed.txt"


def translated_store(tmp_path):
    clipping = parse_file(FIXTURE).clippings[0]
    store = StateStore(tmp_path / ".lingua")
    store.discover([clipping])
    store.save_translations(
        [
            TranslationItem(
                id=clipping.fingerprint,
                corrected_english="Care about your craft.",
                portuguese="Importe-se com seu ofício.",
                vocabulary=["craft — ofício", "care about — importar-se com"],
                grammar="Imperativo sem sujeito explícito.",
            )
        ],
        "test/model",
        "v1",
    )
    return clipping, store


def test_draft_and_anki_export(tmp_path) -> None:
    clipping, store = translated_store(tmp_path)
    draft = write_draft(store.rows([clipping.fingerprint]), tmp_path / "draft.tsv")
    output = tmp_path / "anki.tsv"
    exported, rejected = export_anki(draft, output, Config(), store)
    assert (exported, rejected) == (1, 0)
    text = output.read_text(encoding="utf-8")
    assert text.startswith("#separator:Tab\n#html:true\n")
    assert "#tags column:8" in text
    assert "Care about your craft." in text
    assert "book::the-pragmatic-programmer" in text
    assert "craft — ofício<br>care about — importar-se com" in text
    assert store.statuses([clipping.fingerprint])[clipping.fingerprint] == "exported"


def test_rejected_draft_row_is_recorded(tmp_path) -> None:
    clipping, store = translated_store(tmp_path)
    draft = write_draft(store.rows([clipping.fingerprint]), tmp_path / "draft.tsv")
    with draft.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    rows[0]["Include"] = "no"
    with draft.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DRAFT_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    assert export_anki(draft, tmp_path / "anki.tsv", Config(), store) == (0, 1)
    assert store.statuses([clipping.fingerprint])[clipping.fingerprint] == "rejected"


def test_invalid_draft_does_not_change_state(tmp_path) -> None:
    clipping, store = translated_store(tmp_path)
    draft = write_draft(store.rows([clipping.fingerprint]), tmp_path / "draft.tsv")
    content = draft.read_text(encoding="utf-8").replace("Importe-se com seu ofício.", "")
    draft.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="obrigatórios"):
        export_anki(draft, tmp_path / "anki.tsv", Config(), store)
    assert store.statuses([clipping.fingerprint])[clipping.fingerprint] == "drafted"


def test_unknown_card_id_is_rejected(tmp_path) -> None:
    clipping, store = translated_store(tmp_path)
    draft = write_draft(store.rows([clipping.fingerprint]), tmp_path / "draft.tsv")
    draft.write_text(draft.read_text(encoding="utf-8").replace(clipping.fingerprint, "0" * 64), encoding="utf-8")
    with pytest.raises(ValueError, match="desconhecido"):
        export_anki(draft, tmp_path / "anki.tsv", Config(), store)
    assert not (tmp_path / "anki.tsv").exists()
