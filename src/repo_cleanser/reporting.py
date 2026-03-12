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
    module_boundary = report.module_boundary
    validation_readiness = report.validation_readiness
    lines: list[str] = [
        "Repo Cleanser Report",
        f"Root: {report.root}",
        f"Scanned files: {report.scanned_files}",
        f"Skipped generated directories: {', '.join(report.skipped_directories) or 'none'}",
        "",
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
                lines.append(f"  Reasons: {'; '.join(candidate.reasons)}")
            if candidate.advisory_notes:
                lines.append(f"  Advisory: {'; '.join(candidate.advisory_notes)}")
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

    return "\n".join(lines)
