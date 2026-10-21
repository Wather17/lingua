from pathlib import Path

import json

import pytest

from lingua.clippings import group_books, parse_file, parse_input_file, parse_json_file, parse_text


FIXTURE = Path(__file__).parent / "fixtures" / "clippings_mixed.txt"


def test_parses_english_and_portuguese_highlights() -> None:
    result = parse_file(FIXTURE)
    assert len(result.clippings) == 2
    assert len(group_books(result.clippings)) == 2
    assert result.clippings[0].author == "David Thomas, Andrew Hunt"
    assert result.clippings[1].location.startswith("página 23")
    assert result.skipped["não é destaque"] == 2


def test_supports_bom_crlf_and_multiline() -> None:
    content = "\ufeffBook (Author)\r\n- Your Highlight at location 5-6\r\n\r\nFirst line.\r\nSecond line.\r\n=========="
    result = parse_text(content)
    assert result.clippings[0].text == "First line.\nSecond line."
    assert result.clippings[0].location == "location 5-6"


def test_rejects_empty_and_non_latin_highlights() -> None:
    content = "Book\n- Your Highlight at location 1\n\n你好世界\n==========\nBroken"
    result = parse_text(content)
    assert result.clippings == []
    assert result.skipped["idioma não suportado"] == 1
    assert result.skipped["bloco incompleto"] == 1


def test_fingerprint_is_stable_across_whitespace() -> None:
    first = parse_text("Book (A)\n- Your Highlight at location 1\n\nHello   world\n==========").clippings[0]
    second = parse_text("Book (A)\n- Your Highlight at location 1\n\nHello world\n==========").clippings[0]
    assert first.fingerprint == second.fingerprint


def test_internal_bom_does_not_split_the_same_book() -> None:
    content = (
        "Book (A)\n- Your Highlight at location 1\n\nFirst highlight.\n==========\n"
        "\ufeffBook (A)\n- Your Highlight at location 2\n\nSecond highlight.\n=========="
    )
    result = parse_text(content)
    assert len(group_books(result.clippings)) == 1
    assert result.clippings[1].title == "Book"


def test_parses_manual_json_and_preserves_text(tmp_path) -> None:
    path = tmp_path / "entries.json"
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {"text": "I couldnt quite put my finger on it.", "source": "reading"},
                    {"text": "I couldnt quite put my finger on it.", "source": "reading"},
                    {"text": "That was unexpected."},
                ]
            }
        ),
        encoding="utf-8",
    )
    result = parse_input_file(path)
    assert len(result.clippings) == 2
    assert result.clippings[0].text == "I couldnt quite put my finger on it."
    assert result.clippings[0].source == "reading"
    assert result.clippings[0].entry_type == "manual"
    assert result.clippings[1].source == ""


def test_rejects_unknown_manual_json_properties(tmp_path) -> None:
    path = tmp_path / "entries.json"
    path.write_text(json.dumps({"entries": [{"text": "Hello.", "book": "x"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="propriedades desconhecidas"):
        parse_json_file(path)
