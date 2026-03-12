from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from repo_cleanser.cli import app
from repo_cleanser.models import (
    FileAssessment,
    FileCategory,
    Finding,
    FindingSeverity,
    ModuleBoundarySummary,
    RepoConfigSummary,
    RepoReport,
    ReportFormat,
    SuppressedFinding,
    ValidationReadinessSummary,
)
from repo_cleanser.reporting import render_report

runner = CliRunner()


def write_file(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def test_scan_command_renders_text_report(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / "docs" / "architecture.md", "Architecture doc.\n")
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        "export const billing = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "billing" / "billing.test.ts",
        "import { billing } from './index';\n",
    )
    write_file(
        tmp_path / "src" / "app" / "router.ts",
        "import * as billing from '../features/billing';\n",
    )

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0
    assert "Repo Cleanser Report" in result.stdout
    assert "Modularity strengths:" in result.stdout
    assert "Affected-only readiness strengths:" in result.stdout
    assert "Possible blockers to affected-only validation:" in result.stdout
    assert "Broad validation triggers:" in result.stdout
    assert "Possible narrow validation candidates:" in result.stdout
    assert "Signals raising readiness:" in result.stdout
    assert "Still advisory because:" in result.stdout
    assert "Safe-detach risks:" in result.stdout
    assert "Suggested canonical doc chain:" in result.stdout


def test_scan_command_writes_json_report(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / "docs" / "architecture.md", "Architecture doc.\n")
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        "export const billing = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "billing" / "billing.test.ts",
        "import { billing } from './index';\n",
    )
    write_file(
        tmp_path / "src" / "app" / "router.ts",
        "import * as billing from '../features/billing';\n",
    )
    output_path = tmp_path / "report.json"

    result = runner.invoke(
        app,
        ["scan", str(tmp_path), "--format", "json", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["root"] == str(tmp_path.resolve())
    assert "assessments" in payload
    assert "module_boundary" in payload
    assert "validation_readiness" in payload
    assert "config_summary" in payload
    assert "suppressed_findings" in payload
    assert "broad_validation_triggers" in payload["validation_readiness"]
    assert "narrow_validation_candidates" in payload["validation_readiness"]


def test_scan_command_reports_loaded_config_and_suppressed_findings(tmp_path: Path) -> None:
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[advisory_suppressions]]\n"
        'finding = "orphaned-artifacts"\n'
        'path_pattern = "scratch-notes.md"\n'
        'reason = "Intentional local scratch note."\n',
    )
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / "scratch-notes.md", "Temporary cleanup notes.\n")

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0
    assert "Config:" in result.stdout
    assert "Loaded config: repo-cleanser.toml" in result.stdout
    assert "Suppressed findings:" in result.stdout
    assert "orphaned-artifacts" in result.stdout


def test_scan_command_reports_invalid_config_as_controlled_error(tmp_path: Path) -> None:
    (tmp_path / "repo-cleanser.toml").write_bytes(b"\xff\xfe\x00")

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 1
    assert "Repo Cleanser error:" in result.output
    assert "Unable to decode 'repo-cleanser.toml' as UTF-8" in result.output


def test_scan_command_reports_output_write_error_without_traceback(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    output_dir = tmp_path / "report-output"
    output_dir.mkdir()

    result = runner.invoke(app, ["scan", str(tmp_path), "--output", str(output_dir)])

    assert result.exit_code == 1
    assert "Repo Cleanser error: unable to write report:" in result.output
    assert "Permission denied" in result.output or "Is a directory" in result.output


def test_text_report_escapes_control_and_escape_characters() -> None:
    report = RepoReport(
        root="C:/repo/\x1b[31mred",
        scanned_files=1,
        skipped_directories=["dist\nnext"],
        canonical_doc_chain=["README.md"],
        config_summary=RepoConfigSummary(
            path="repo-cleanser.toml",
            ignored_paths=["notes\tarchive"],
        ),
        module_boundary=ModuleBoundarySummary(),
        validation_readiness=ValidationReadinessSummary(),
        assessments=[
            FileAssessment(
                path="scratch\tfile.md",
                category=FileCategory.TEMPORARY,
                reasons=["review\nlater"],
            )
        ],
        findings=[
            Finding(
                kind="orphaned-artifacts",
                severity=FindingSeverity.LOW,
                summary="line1\nline2",
                recommendation="check\tfirst",
                paths=["scratch/\x1b[31mnote.md"],
            )
        ],
        suppressed_findings=[
            SuppressedFinding(
                kind="duplicate-docs",
                summary="publish copy",
                reason="known\nmirror",
                paths=["public/docs/\x1b[31mguide.md"],
            )
        ],
        recommended_actions=["Review \x1b[31msafely"],
        repository_risks=["risk\tflag"],
    )

    rendered = render_report(report, format=ReportFormat.TEXT)

    assert "\x1b" not in rendered
    assert "line1\\nline2" in rendered
    assert "check\\tfirst" in rendered
    assert "dist\\nnext" in rendered
    assert "scratch/\\x1b[31mnote.md" in rendered
    assert "review\\nlater" in rendered
