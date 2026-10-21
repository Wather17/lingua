from pathlib import Path

from lingua.clippings import parse_file
from lingua.models import TranslationItem
from lingua.state import StateStore


FIXTURE = Path(__file__).parent / "fixtures" / "clippings_mixed.txt"


def test_state_lifecycle(tmp_path) -> None:
    clipping = parse_file(FIXTURE).clippings[0]
    store = StateStore(tmp_path)
    store.discover([clipping])
    assert clipping.fingerprint in store.untranslated([clipping.fingerprint])
    store.save_translations(
        [
            TranslationItem(
                id=clipping.fingerprint,
                corrected_english=clipping.text,
                portuguese="Tradução",
                vocabulary=["craft — ofício"],
                grammar="",
            )
        ],
        "test/model",
        "v1",
    )
    row = store.rows([clipping.fingerprint])[0]
    assert row["status"] == "drafted"
    assert row["portuguese"] == "Tradução"
    assert row["corrected_english"] == clipping.text
    store.mark_many([clipping.fingerprint], "exported")
    assert store.statuses([clipping.fingerprint])[clipping.fingerprint] == "exported"

