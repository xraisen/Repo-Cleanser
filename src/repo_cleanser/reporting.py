from __future__ import annotations

import json

from repo_cleanser.models import FileCategory, RepoReport, ReportFormat

MAX_HIGHLIGHTS = 20


def render_report(
    report: RepoReport,
    *,
    format: ReportFormat,
    include_supporting: bool = False,
) -> str:
    if format is ReportFormat.JSON:
        return json.dumps(report.to_dict(), indent=2)
    return render_text_report(report, include_supporting=include_supporting)


def render_text_report(report: RepoReport, *, include_supporting: bool = False) -> str:
    counts = report.category_counts()
    config_summary = report.config_summary
    module_boundary = report.module_boundary
    validation_readiness = report.validation_readiness
    lines: list[str] = [
        "Repo Cleanser Report",
        f"Root: {report.root}",
        f"Scanned files: {report.scanned_files}",
        f"Skipped scan directories: {', '.join(report.skipped_directories) or 'none'}",
        "",
        "Config:",
    ]

    if config_summary.path is None:
        lines.extend(
            [
                "- No repo-cleanser.toml config loaded.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"- Loaded config: {config_summary.path}",
                "- Ignored paths: "
                + (", ".join(config_summary.ignored_paths) or "none"),
                "- Known generated paths: "
                + (", ".join(config_summary.generated_paths) or "none"),
                "- Known mirrored docs: "
                + (
                    ", ".join(
                        f"{mirror.source} -> {mirror.publish}"
                        for mirror in config_summary.mirrored_docs
                    )
                    or "none"
                ),
                "- Advisory suppressions: "
                + (
                    ", ".join(
                        f"{suppression.finding} @ {suppression.path_pattern}"
                        for suppression in config_summary.advisory_suppressions
                    )
                    or "none"
                ),
                "",
            ]
        )

    lines.extend(
        [
        "Suggested canonical doc chain:",
        *[f"- {path}" for path in report.canonical_doc_chain],
        "",
        "Category counts:",
        *[f"- {category}: {count}" for category, count in counts.items()],
        "",
        f"Candidate modules analyzed: {len(module_boundary.candidate_modules)}",
        f"Advisory isolated modules: {len(validation_readiness.advisory_isolated_modules)}",
        "",
        "Modularity strengths:",
        "",
        ]
    )

    if module_boundary.strengths:
        lines.extend(f"- {strength}" for strength in module_boundary.strengths)
    else:
        lines.append("- No strong modularity signals detected by this heuristic layer.")

    lines.extend(["", "Modularity risks:"])
    if module_boundary.modularity_risks:
        lines.extend(f"- {risk}" for risk in module_boundary.modularity_risks)
    else:
        lines.append("- No clear module-boundary risks detected by this heuristic layer.")

    lines.extend(["", "Safe-detach risks:"])
    if module_boundary.safe_detach_risks:
        lines.extend(f"- {risk}" for risk in module_boundary.safe_detach_risks)
    else:
        lines.append("- No clear safe-detach risks detected by this heuristic layer.")

    lines.extend(["", "Structural strengths:"])
    if validation_readiness.structural_strengths:
        lines.extend(f"- {strength}" for strength in validation_readiness.structural_strengths)
    else:
        lines.append("- No strong structural readiness signals detected by this heuristic layer.")

    lines.extend(["", "Affected-only readiness strengths:"])
    if validation_readiness.readiness_strengths:
        lines.extend(f"- {strength}" for strength in validation_readiness.readiness_strengths)
    else:
        lines.append(
            "- No strong affected-only readiness signals detected by this heuristic layer."
        )

    lines.extend(["", "Shared/Core coupling risks:"])
    if validation_readiness.shared_core_coupling_risks:
        lines.extend(f"- {risk}" for risk in validation_readiness.shared_core_coupling_risks)
    else:
        lines.append("- No major shared/core coupling risks detected by this heuristic layer.")

    lines.extend(["", "Possible blockers to affected-only validation:"])
    if validation_readiness.validation_blockers:
        lines.extend(f"- {blocker}" for blocker in validation_readiness.validation_blockers)
    else:
        lines.append("- No clear readiness blockers detected by this heuristic layer.")

    lines.extend(["", "Broad validation triggers:"])
    if validation_readiness.broad_validation_triggers:
        lines.extend(f"- {trigger}" for trigger in validation_readiness.broad_validation_triggers)
    else:
        lines.append("- No clear broad-validation triggers detected by this heuristic layer.")

    lines.extend(["", "Possible narrow validation candidates:"])
    if validation_readiness.narrow_validation_candidates:
        for candidate in validation_readiness.narrow_validation_candidates:
            lines.append(f"- {candidate.path} ({candidate.kind})")
            if candidate.reasons:
                lines.append(
                    f"  Signals raising readiness: {'; '.join(candidate.reasons)}"
                )
            if candidate.advisory_notes:
                lines.append(
                    f"  Still advisory because: {'; '.join(candidate.advisory_notes)}"
                )
    else:
        lines.append(
            "- No module-like areas currently rise above the heuristic bar for "
            "advisory narrow validation candidacy."
        )

    lines.extend(["", "Manual-review recommendations:"])
    if validation_readiness.manual_review_recommendations:
        lines.extend(
            f"- {recommendation}"
            for recommendation in validation_readiness.manual_review_recommendations
        )
    else:
        lines.append("- No extra manual-review recommendations beyond the current findings.")

    if validation_readiness.broad_validation_areas:
        lines.extend(["", "Broad validation areas:"])
        lines.extend(f"- {area}" for area in validation_readiness.broad_validation_areas)

    lines.extend(["", "Repository risks:"])

    if report.repository_risks:
        lines.extend(f"- {risk}" for risk in report.repository_risks)
    else:
        lines.append("- No high-risk cleanup signals detected.")

    lines.extend(["", "Recommended actions:"])
    lines.extend(f"- {action}" for action in report.recommended_actions)

    lines.extend(["", "Findings:"])
    if report.findings:
        for finding in report.findings:
            lines.append(f"- [{finding.severity.value}] {finding.kind}: {finding.summary}")
            lines.append(f"  Recommendation: {finding.recommendation}")
            lines.append(f"  Paths: {', '.join(finding.paths)}")
    else:
        lines.append("- No notable duplicate, stale, or migration risk findings.")

    lines.extend(["", "Suppressed findings:"])
    if report.suppressed_findings:
        for suppressed_finding in report.suppressed_findings:
            lines.append(f"- {suppressed_finding.kind}: {suppressed_finding.summary}")
            lines.append(f"  Reason: {suppressed_finding.reason}")
            lines.append(f"  Paths: {', '.join(suppressed_finding.paths)}")
    else:
        lines.append("- No config-driven suppressions were applied.")

    lines.extend(["", "Classified file highlights:"])
    highlights = [
        assessment
        for assessment in report.assessments
        if include_supporting or assessment.category is not FileCategory.SUPPORTING
    ]
    highlights = highlights[:MAX_HIGHLIGHTS]

    if highlights:
        for assessment in highlights:
            reason = assessment.reasons[0] if assessment.reasons else "No reason captured."
            lines.append(f"- [{assessment.category.value}] {assessment.path}: {reason}")
    else:
        lines.append("- No highlighted files.")

    return "\n".join(_safe_text(line) for line in lines)


def _safe_text(value: str) -> str:
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
