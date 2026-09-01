import csv
import json

from lingua.clippings import parse_text
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
                    portuguese=f"PT: {item.text}",
                    vocabulary=[],
                    grammar="",
                )
                for item in clippings
            ],
            TranslationUsage(model=model, cost=0.001),
        )


def test_prepare_resumes_cached_translation(tmp_path) -> None:
    clipping = parse_text("Book (A)\n- Your Highlight at location 1\n\nHello.\n==========").clippings[0]
    store = StateStore(tmp_path / ".lingua")
    client = FakeClient()
    output = tmp_path / "draft.tsv"
    prepare([clipping], store, client, Config(), output)
    prepare([clipping], store, client, Config(), output)
    assert client.calls == 1


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

