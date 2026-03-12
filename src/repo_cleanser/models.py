from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum


class FileCategory(StrEnum):
    CANONICAL = "canonical"
    SUPPORTING = "supporting"
    DUPLICATE = "duplicate"
    STALE = "stale"
    HISTORICAL = "historical"
    TEMPORARY = "temporary"
    GENERATED = "generated"
    UNCLEAR_AUTHORITY = "unclear-authority"


class FindingSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReportFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


@dataclass(slots=True)
class FileAssessment:
    path: str
    category: FileCategory
    reasons: list[str] = field(default_factory=list)
    size_bytes: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "category": self.category.value,
            "reasons": self.reasons,
            "size_bytes": self.size_bytes,
        }


@dataclass(slots=True)
class Finding:
    kind: str
    severity: FindingSeverity
    summary: str
    recommendation: str
    paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "severity": self.severity.value,
            "summary": self.summary,
            "recommendation": self.recommendation,
            "paths": self.paths,
        }


@dataclass(slots=True)
class ModuleCandidate:
    path: str
    kind: str
    entrypoints: list[str] = field(default_factory=list)
    registration_paths: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "entrypoints": self.entrypoints,
            "registration_paths": self.registration_paths,
            "signals": self.signals,
        }


@dataclass(slots=True)
class ModuleBoundarySummary:
    candidate_modules: list[ModuleCandidate] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    modularity_risks: list[str] = field(default_factory=list)
    safe_detach_risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_modules": [candidate.to_dict() for candidate in self.candidate_modules],
            "strengths": self.strengths,
            "modularity_risks": self.modularity_risks,
            "safe_detach_risks": self.safe_detach_risks,
        }


@dataclass(slots=True)
class ValidationScopeCandidate:
    path: str
    kind: str
    reasons: list[str] = field(default_factory=list)
    advisory_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "kind": self.kind,
            "reasons": self.reasons,
            "advisory_notes": self.advisory_notes,
        }


@dataclass(slots=True)
class ValidationReadinessSummary:
    advisory_isolated_modules: list[str] = field(default_factory=list)
    broad_validation_areas: list[str] = field(default_factory=list)
    broad_validation_triggers: list[str] = field(default_factory=list)
    narrow_validation_candidates: list[ValidationScopeCandidate] = field(default_factory=list)
    structural_strengths: list[str] = field(default_factory=list)
    readiness_strengths: list[str] = field(default_factory=list)
    shared_core_coupling_risks: list[str] = field(default_factory=list)
    validation_blockers: list[str] = field(default_factory=list)
    manual_review_recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "advisory_isolated_modules": self.advisory_isolated_modules,
            "broad_validation_areas": self.broad_validation_areas,
            "broad_validation_triggers": self.broad_validation_triggers,
            "narrow_validation_candidates": [
                candidate.to_dict() for candidate in self.narrow_validation_candidates
            ],
            "structural_strengths": self.structural_strengths,
            "readiness_strengths": self.readiness_strengths,
            "shared_core_coupling_risks": self.shared_core_coupling_risks,
            "validation_blockers": self.validation_blockers,
            "manual_review_recommendations": self.manual_review_recommendations,
        }


@dataclass(slots=True)
class ConfiguredMirror:
    source: str
    publish: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "publish": self.publish,
        }


@dataclass(slots=True)
class ConfiguredSuppression:
    finding: str
    path_pattern: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "finding": self.finding,
            "path_pattern": self.path_pattern,
            "reason": self.reason,
        }


@dataclass(slots=True)
class RepoConfigSummary:
    path: str | None = None
    ignored_paths: list[str] = field(default_factory=list)
    generated_paths: list[str] = field(default_factory=list)
    mirrored_docs: list[ConfiguredMirror] = field(default_factory=list)
    advisory_suppressions: list[ConfiguredSuppression] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "ignored_paths": self.ignored_paths,
            "generated_paths": self.generated_paths,
            "mirrored_docs": [mirror.to_dict() for mirror in self.mirrored_docs],
            "advisory_suppressions": [
                suppression.to_dict() for suppression in self.advisory_suppressions
            ],
        }


@dataclass(slots=True)
class SuppressedFinding:
    kind: str
    summary: str
    reason: str
    paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "summary": self.summary,
            "reason": self.reason,
            "paths": self.paths,
        }


@dataclass(slots=True)
class RepoReport:
    root: str
    scanned_files: int
    skipped_directories: list[str]
    canonical_doc_chain: list[str]
    config_summary: RepoConfigSummary
    module_boundary: ModuleBoundarySummary
    validation_readiness: ValidationReadinessSummary
    assessments: list[FileAssessment]
    findings: list[Finding]
    suppressed_findings: list[SuppressedFinding]
    recommended_actions: list[str]
    repository_risks: list[str]

    def category_counts(self) -> dict[str, int]:
        counts = Counter(assessment.category.value for assessment in self.assessments)
        return dict(sorted(counts.items()))

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "scanned_files": self.scanned_files,
            "skipped_directories": self.skipped_directories,
            "canonical_doc_chain": self.canonical_doc_chain,
            "config_summary": self.config_summary.to_dict(),
            "module_boundary": self.module_boundary.to_dict(),
            "validation_readiness": self.validation_readiness.to_dict(),
            "category_counts": self.category_counts(),
            "assessments": [assessment.to_dict() for assessment in self.assessments],
            "findings": [finding.to_dict() for finding in self.findings],
            "suppressed_findings": [
                finding.to_dict() for finding in self.suppressed_findings
            ],
            "recommended_actions": self.recommended_actions,
            "repository_risks": self.repository_risks,
        }
