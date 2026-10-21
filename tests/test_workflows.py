import csv
import json

import pytest

from lingua.clippings import parse_json_file, parse_text
from lingua.config import Config, load_config
from lingua.models import TranslationItem, TranslationUsage
from lingua.state import StateStore
from lingua.workflows import prepare, select_model


class FakeClient:
    def __init__(self):
        self.calls = 0

    def translate(self, clippings, model):
        self.calls += 1
        return (
            [
                TranslationItem(
                    id=item.fingerprint,
                    corrected_english=item.text,
                    portuguese=f"PT: {item.text}",
                    vocabulary=[],
                    grammar="",
                )
                for item in clippings
            ],
            TranslationUsage(model=model, cost=0.001),
        )


class FailingClient(FakeClient):
    def translate(self, clippings, model):
        self.calls += 1
        raise RuntimeError("temporary failure")


def test_prepare_resumes_cached_translation(tmp_path) -> None:
    clipping = parse_text("Book (A)\n- Your Highlight at location 1\n\nHello.\n==========").clippings[0]
    store = StateStore(tmp_path / ".lingua")
    client = FakeClient()
    output = tmp_path / "draft.tsv"
    prepare([clipping], store, client, Config(), output)
    prepare([clipping], store, client, Config(), output)
    assert client.calls == 1


def test_prepare_enforces_global_daily_limit_before_api(tmp_path) -> None:
    first_path = tmp_path / "first.json"
    first_path.write_text(
        json.dumps({"entries": [{"text": f"Sentence {index}."} for index in range(5)]}),
        encoding="utf-8",
    )
    second_path = tmp_path / "second.json"
    second_path.write_text(
        json.dumps({"entries": [{"text": "A sixth sentence."}]}),
        encoding="utf-8",
    )
    first = parse_json_file(first_path).clippings
    second = parse_json_file(second_path).clippings
    store = StateStore(tmp_path / ".lingua")
    client = FakeClient()
    prepare(first, store, client, Config(daily_limit=5), tmp_path / "first.tsv")
    with pytest.raises(ValueError, match="limite diário"):
        prepare(second, store, client, Config(daily_limit=5), tmp_path / "second.tsv")
    assert client.calls == 1


def test_prepare_releases_reserved_quota_when_api_fails(tmp_path) -> None:
    clipping = parse_text("Book (A)\n- Your Highlight at location 1\n\nHello.\n==========").clippings[0]
    store = StateStore(tmp_path / ".lingua")
    client = FailingClient()
    with pytest.raises(RuntimeError, match="temporary failure"):
        prepare([clipping], store, client, Config(daily_limit=5), tmp_path / "draft.tsv")
    assert store.rows([clipping.fingerprint])[0]["quota_date"] is None


def test_select_model_uses_score_then_cost(tmp_path) -> None:
    report = tmp_path / "evaluation.tsv"
    fields = [
        "A Translation Score", "A Teaching Score",
        "B Translation Score", "B Teaching Score",
    ]
    with report.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerow({field: "5" for field in fields})
    report.with_suffix(".mapping.json").write_text(
        json.dumps({"candidates": {"A": {"model": "expensive", "cost": 2}, "B": {"model": "cheap", "cost": 1}}}),
        encoding="utf-8",
    )
    model, averages = select_model(report, tmp_path / ".lingua", Config())
    assert model == "cheap"
    assert averages == {"A": 5.0, "B": 5.0}
    assert load_config(tmp_path / ".lingua").model == "cheap"

