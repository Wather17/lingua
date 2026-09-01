from __future__ import annotations

from pathlib import Path
import os

import typer

from .clippings import group_books, parse_file
from .config import Config, load_config, save_config
from .openrouter import OpenRouterClient, OpenRouterError
from .output import default_named_path, export_anki
from .state import StateStore
from .workflows import evaluate_models, load_and_choose, prepare as prepare_workflow, select_model as select_model_workflow


app = typer.Typer(no_args_is_help=True, help="Kindle Clippings → Anki com tradução contextual.")
WORKSPACE_OPTION = typer.Option(Path(".lingua"), "--workspace", "-w", help="Diretório de estado do projeto.")


def _fail(message: str) -> None:
    typer.secho(f"Erro: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def _client(config: Config) -> OpenRouterClient:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        _fail("defina a variável OPENROUTER_API_KEY")
    return OpenRouterClient(key, config.base_url, config.data_collection)


def _choose(options: list[tuple[str, str, str, int, int]]) -> str:
    typer.echo("Livros encontrados:")
    for index, (key, title, author, total, new) in enumerate(options, start=1):
        byline = f" — {author}" if author else ""
        typer.echo(f"  {index}. {title}{byline} ({new} novos de {total}) [{key}]")
    selected = typer.prompt("Escolha o número", type=int)
    if selected < 1 or selected > len(options):
        _fail("seleção inválida")
    return options[selected - 1][0]


@app.command("init")
def init_command(workspace: Path = WORKSPACE_OPTION, force: bool = typer.Option(False, help="Regrava a configuração.")) -> None:
    """Inicializa a configuração e o banco local."""
    path = workspace / "config.toml"
    if path.exists() and not force:
        _fail(f"{path} já existe; use --force para regravar")
    save_config(workspace, Config())
    StateStore(workspace)
    typer.echo(f"Projeto inicializado em {workspace}")


@app.command("doctor")
def doctor(
    clippings: Path | None = typer.Argument(None, exists=True, dir_okay=False),
    workspace: Path = WORKSPACE_OPTION,
    check_api: bool = typer.Option(True, "--check-api/--no-check-api"),
) -> None:
    """Verifica configuração, arquivo e acesso ao OpenRouter."""
    try:
        config = load_config(workspace)
        StateStore(workspace)
        typer.echo(f"✓ configuração: modelo {config.model}")
        if clippings:
            result = parse_file(clippings)
            typer.echo(f"✓ clippings: {len(result.clippings)} destaques em {len(group_books(result.clippings))} livros")
            if result.skipped:
                typer.echo("  ignorados: " + ", ".join(f"{reason}={count}" for reason, count in result.skipped.items()))
        if check_api:
            with _client(config) as client:
                client.check_connection()
            typer.echo("✓ OpenRouter: chave e conexão válidas")
    except (ValueError, OSError, OpenRouterError) as error:
        _fail(str(error))


@app.command("books")
def books(
    clippings: Path = typer.Argument(..., exists=True, dir_okay=False),
    workspace: Path = WORKSPACE_OPTION,
) -> None:
    """Lista os livros e a quantidade de destaques novos."""
    try:
        result = parse_file(clippings)
        store = StateStore(workspace)
        for key, items in sorted(group_books(result.clippings).items(), key=lambda pair: pair[1][0].title.casefold()):
            statuses = store.statuses([item.fingerprint for item in items])
            new = sum(statuses.get(item.fingerprint) not in {"exported", "rejected"} for item in items)
            author = f" — {items[0].author}" if items[0].author else ""
            typer.echo(f"{key}  {items[0].title}{author}  {new} novos / {len(items)} total")
        if result.skipped:
            typer.echo("Ignorados: " + ", ".join(f"{key}={value}" for key, value in result.skipped.items()))
    except (ValueError, OSError) as error:
        _fail(str(error))


@app.command("prepare")
def prepare_command(
    clippings: Path = typer.Argument(..., exists=True, dir_okay=False),
    book: str | None = typer.Option(None, help="ID ou título exato do livro."),
    output: Path | None = typer.Option(None, "--output", "-o"),
    workspace: Path = WORKSPACE_OPTION,
) -> None:
    """Traduz destaques novos e cria um rascunho revisável."""
    try:
        config = load_config(workspace)
        store = StateStore(workspace)
        _, selected = load_and_choose(clippings, store, book, _choose)
        destination = output or default_named_path(Path("drafts"), selected[0].title, ".tsv")
        with _client(config) as client:
            path, usage = prepare_workflow(selected, store, client, config, destination, typer.echo)
        cost = sum(item.cost for item in usage)
        tokens = sum(item.prompt_tokens + item.completion_tokens for item in usage)
        typer.echo(f"Rascunho criado: {path} ({tokens} tokens; custo reportado US$ {cost:.6f})")
    except (ValueError, OSError, RuntimeError, OpenRouterError) as error:
        _fail(str(error))


@app.command("export")
def export_command(
    draft: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Path | None = typer.Option(None, "--output", "-o"),
    workspace: Path = WORKSPACE_OPTION,
) -> None:
    """Valida o rascunho e gera o TSV importável pelo Anki."""
    try:
        config = load_config(workspace)
        store = StateStore(workspace)
        destination = output or Path("exports") / f"{draft.stem}-anki.tsv"
        exported, rejected = export_anki(draft, destination, config, store)
        typer.echo(f"Exportado: {destination} ({exported} cartões; {rejected} rejeitados)")
    except (ValueError, OSError) as error:
        _fail(str(error))


@app.command("evaluate")
def evaluate_command(
    clippings: Path = typer.Argument(..., exists=True, dir_okay=False),
    book: str | None = typer.Option(None, help="ID ou título exato do livro."),
    sample: int = typer.Option(12, min=1, max=50, help="Número de destaques na amostra."),
    output: Path | None = typer.Option(None, "--output", "-o"),
    workspace: Path = WORKSPACE_OPTION,
) -> None:
    """Gera uma comparação cega dos modelos configurados."""
    try:
        config = load_config(workspace)
        store = StateStore(workspace)
        _, selected = load_and_choose(clippings, store, book, _choose)
        destination = output or default_named_path(Path("evaluations"), selected[0].title, ".tsv")
        with _client(config) as client:
            report = evaluate_models(selected, client, config, destination, sample, typer.echo)
        typer.echo(f"Avaliação criada: {report}")
        typer.echo("Preencha as notas de 1 a 5 e execute: lingua select-model " + str(report))
    except (ValueError, OSError, OpenRouterError) as error:
        _fail(str(error))


@app.command("select-model")
def select_model_command(
    report: Path = typer.Argument(..., exists=True, dir_okay=False),
    workspace: Path = WORKSPACE_OPTION,
) -> None:
    """Escolhe o vencedor de uma avaliação preenchida."""
    try:
        config = load_config(workspace)
        model, averages = select_model_workflow(report, workspace, config)
        typer.echo("Médias: " + ", ".join(f"{key}={value:.2f}" for key, value in sorted(averages.items())))
        typer.echo(f"Modelo selecionado: {model}")
    except (ValueError, OSError, KeyError, ZeroDivisionError) as error:
        _fail(str(error))


if __name__ == "__main__":
    app()

