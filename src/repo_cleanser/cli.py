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
    try:
        report = analyze_repository(repo_path)
        rendered = render_report(report, format=format, include_supporting=include_supporting)

        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            typer.echo(f"Wrote {format.value} report to {_safe_cli_text(str(output))}")
            return

        typer.echo(rendered)
    except ValueError as exc:
        typer.echo(f"Repo Cleanser error: {_safe_cli_text(str(exc))}", err=True)
        raise typer.Exit(code=1) from exc
    except (OSError, UnicodeError) as exc:
        typer.echo(
            f"Repo Cleanser error: unable to write report: {_safe_cli_text(str(exc))}",
            err=True,
        )
        raise typer.Exit(code=1) from exc


def main() -> None:
    app()


def _safe_cli_text(value: str) -> str:
    safe_fragments: list[str] = []
    for char in value:
        if char == "\n":
            safe_fragments.append("\\n")
        elif char == "\r":
            safe_fragments.append("\\r")
        elif char == "\t":
            safe_fragments.append("\\t")
        elif ord(char) < 32 or ord(char) == 127:
            safe_fragments.append(f"\\x{ord(char):02x}")
        else:
            safe_fragments.append(char)

    return "".join(safe_fragments).encode("utf-8", "backslashreplace").decode("utf-8")


if __name__ == "__main__":
    main()
