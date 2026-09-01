from __future__ import annotations

import csv
from datetime import datetime
import json
from pathlib import Path
import random
from typing import Callable, Sequence

from .clippings import ParseResult, group_books, parse_file
from .config import Config, save_config
from .models import Clipping, TranslationUsage
from .openrouter import OpenRouterClient, PROMPT_VERSION
from .output import default_named_path, write_draft, write_json_atomic
from .state import StateStore


def load_and_choose(
    path: Path,
    store: StateStore,
    book: str | None,
    choose: Callable[[list[tuple[str, str, str, int, int]]], str],
) -> tuple[ParseResult, list[Clipping]]:
    result = parse_file(path)
    books = group_books(result.clippings)
    if not books:
        raise ValueError("nenhum destaque reconhecido no arquivo")
    options: list[tuple[str, str, str, int, int]] = []
    for key, items in books.items():
        statuses = store.statuses([item.fingerprint for item in items])
        new = sum(statuses.get(item.fingerprint) not in {"exported", "rejected"} for item in items)
        options.append((key, items[0].title, items[0].author, len(items), new))
    options.sort(key=lambda item: item[1].casefold())
    if book:
        matches = [item for item in options if item[0] == book or item[1].casefold() == book.casefold()]
        if len(matches) != 1:
            raise ValueError("livro não encontrado ou título ambíguo; use o ID exibido por 'lingua books'")
        selected_key = matches[0][0]
    else:
        selected_key = choose(options)
    return result, books[selected_key]


def prepare(
    clippings: list[Clipping],
    store: StateStore,
    client: OpenRouterClient,
    config: Config,
    output: Path,
    progress: Callable[[str], None] = lambda _: None,
) -> tuple[Path, list[TranslationUsage]]:
    statuses = store.statuses([item.fingerprint for item in clippings])
    active = [
        item for item in clippings if statuses.get(item.fingerprint) not in {"exported", "rejected"}
    ]
    if not active:
        raise ValueError("este livro não possui destaques novos")
    store.discover(active)
    untranslated = store.untranslated([item.fingerprint for item in active])
    pending = [item for item in active if item.fingerprint in untranslated]
    usage: list[TranslationUsage] = []
    completed = 0
    for batch in _batches(pending, config.batch_size):
        progress(f"Traduzindo {completed + 1}-{completed + len(batch)} de {len(pending)}...")
        translations, batch_usage = client.translate(batch, config.model)
        store.save_translations(translations, config.model, PROMPT_VERSION)
        usage.append(batch_usage)
        completed += len(batch)
    rows = store.rows([item.fingerprint for item in active])
    if any(not row["portuguese"] for row in rows):
        raise RuntimeError("há traduções pendentes; execute prepare novamente")
    return write_draft(rows, output), usage


def evaluate_models(
    clippings: list[Clipping],
    client: OpenRouterClient,
    config: Config,
    output: Path,
    sample_size: int,
    progress: Callable[[str], None] = lambda _: None,
) -> Path:
    if len(config.candidates) < 2 or len(config.candidates) > 10:
        raise ValueError("configure entre 2 e 10 modelos candidatos para a avaliação")
    sample_size = min(max(sample_size, 1), len(clippings))
    sample = random.Random(42).sample(clippings, sample_size)
    aliases = [chr(ord("A") + index) for index in range(len(config.candidates))]
    results: dict[str, dict[str, object]] = {}
    usages: dict[str, TranslationUsage] = {}
    for alias, model in zip(aliases, config.candidates, strict=True):
        progress(f"Avaliando candidato {alias}...")
        all_translations = []
        model_usages: list[TranslationUsage] = []
        for batch in _batches(sample, config.batch_size):
            translations, usage = client.translate(batch, model)
            all_translations.extend(translations)
            model_usages.append(usage)
        results[alias] = {item.id: item for item in all_translations}
        usages[alias] = TranslationUsage(
            model=model_usages[-1].model,
            prompt_tokens=sum(item.prompt_tokens for item in model_usages),
            completion_tokens=sum(item.completion_tokens for item in model_usages),
            cost=sum(item.cost for item in model_usages),
            latency_seconds=sum(item.latency_seconds for item in model_usages),
        )
    fields = ["CardID", "English", "Book"]
    for alias in aliases:
        fields.extend(
            [
                f"{alias} Portuguese",
                f"{alias} Vocabulary",
                f"{alias} Grammar",
                f"{alias} Translation Score",
                f"{alias} Teaching Score",
            ]
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for clipping in sample:
            row: dict[str, str] = {
                "CardID": clipping.fingerprint,
                "English": clipping.text.replace("\n", "<br>"),
                "Book": clipping.title,
            }
            for alias in aliases:
                item = results[alias][clipping.fingerprint]
                row[f"{alias} Portuguese"] = item.portuguese
                row[f"{alias} Vocabulary"] = "<br>".join(item.vocabulary)
                row[f"{alias} Grammar"] = item.grammar
                row[f"{alias} Translation Score"] = ""
                row[f"{alias} Teaching Score"] = ""
            writer.writerow(row)
    temporary.replace(output)
    mapping_path = output.with_suffix(".mapping.json")
    write_json_atomic(
        mapping_path,
        {
            "report": output.name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "candidates": {
                alias: {
                    "model": model,
                    "resolved_model": usages[alias].model,
                    "prompt_tokens": usages[alias].prompt_tokens,
                    "completion_tokens": usages[alias].completion_tokens,
                    "cost": usages[alias].cost,
                    "latency_seconds": round(usages[alias].latency_seconds, 3),
                }
                for alias, model in zip(aliases, config.candidates, strict=True)
            },
        },
    )
    return output


def select_model(report: Path, workspace: Path, config: Config) -> tuple[str, dict[str, float]]:
    mapping_path = report.with_suffix(".mapping.json")
    if not mapping_path.exists():
        raise ValueError(f"arquivo de mapeamento não encontrado: {mapping_path}")
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    candidates: dict[str, dict] = mapping["candidates"]
    totals = {alias: 0.0 for alias in candidates}
    counts = {alias: 0 for alias in candidates}
    with report.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for line_number, row in enumerate(reader, start=2):
            for alias in candidates:
                for kind in ("Translation", "Teaching"):
                    field = f"{alias} {kind} Score"
                    try:
                        score = int(row[field])
                    except (KeyError, TypeError, ValueError) as error:
                        raise ValueError(f"preencha {field} com nota de 1 a 5 na linha {line_number}") from error
                    if score < 1 or score > 5:
                        raise ValueError(f"nota fora do intervalo 1-5 em {field}, linha {line_number}")
                    totals[alias] += score
                    counts[alias] += 1
    averages = {alias: totals[alias] / counts[alias] for alias in candidates}
    winner = max(
        candidates,
        key=lambda alias: (averages[alias], -float(candidates[alias].get("cost", 0.0))),
    )
    config.model = candidates[winner]["model"]
    save_config(workspace, config)
    return config.model, averages


def _batches(items: Sequence[Clipping], batch_size: int, max_characters: int = 6_000):
    """Agrupa por quantidade e tamanho para caber também em modelos de contexto curto."""
    batch: list[Clipping] = []
    characters = 0
    for item in items:
        item_size = len(item.text) + len(item.title) + len(item.author) + len(item.location)
        if batch and (len(batch) >= batch_size or characters + item_size > max_characters):
            yield batch
            batch = []
            characters = 0
        batch.append(item)
        characters += item_size
    if batch:
        yield batch
