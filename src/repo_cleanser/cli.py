from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from repo_cleanser.analyzer import analyze_repository
from repo_cleanser.models import ReportFormat
from repo_cleanser.reporting import render_report

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help=(
        "Scan a repository for documentation drift and risky cleanup "
        "signals without modifying files."
    ),
)


@app.callback()
def callback() -> None:
    """Repo Cleanser command group."""


@app.command()
def scan(
    repo_path: Annotated[
        Path,
        typer.Argument(
            ...,
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Local repository path to analyze.",
        ),
    ],
    format: Annotated[
        ReportFormat,
        typer.Option(
            "--format",
            case_sensitive=False,
            help="Output format.",
        ),
    ] = ReportFormat.TEXT,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            resolve_path=True,
            help="Write the report to a file instead of stdout.",
        ),
    ] = None,
    include_supporting: Annotated[
        bool,
        typer.Option(
            "--include-supporting",
            help="Include supporting files in the highlights section.",
        ),
    ] = False,
) -> None:
    report = analyze_repository(repo_path)
    rendered = render_report(report, format=format, include_supporting=include_supporting)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        typer.echo(f"Wrote {format.value} report to {output}")
        return

    typer.echo(rendered)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
