from __future__ import annotations

import fnmatch
import os
import re
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from repo_cleanser.models import (
    ConfiguredMirror,
    ConfiguredSuppression,
    FileAssessment,
    FileCategory,
    Finding,
    FindingSeverity,
    ModuleBoundarySummary,
    ModuleCandidate,
    RepoConfigSummary,
    RepoReport,
    SuppressedFinding,
    ValidationReadinessSummary,
    ValidationScopeCandidate,
)

CANONICAL_DOC_CHAIN: list[str] = [
    "README.md",
    "AGENTS.md",
    "docs/architecture.md",
    "docs/validation.md",
    "docs/project-tree.md",
]
CONFIG_FILE_NAME = "repo-cleanser.toml"

CANONICAL_ROOT_FILES = {
    ".gitignore",
    "cargo.toml",
    "dockerfile",
    "go.mod",
    "makefile",
    "package.json",
    "pyproject.toml",
    "repo-cleanser.toml",
    "requirements.txt",
}

CANONICAL_DOC_FAMILIES = {
    "readme": "README.md",
    "agents": "AGENTS.md",
    "architecture": "docs/architecture.md",
    "validation": "docs/validation.md",
    "project-tree": "docs/project-tree.md",
}

TEXT_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".rst",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

MARKDOWN_SUFFIXES = {".md", ".rst", ".txt"}
CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
}
TEXT_SUFFIXES |= CODE_SUFFIXES

GENERATED_DIR_NAMES = {
    ".cache",
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".turbo",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "out",
    "target",
    "venv",
}

GENERATED_EXTENSIONS = {".class", ".dll", ".exe", ".o", ".obj", ".pyc", ".pyo", ".so"}
TEMPORARY_TOKENS = {"draft", "scratch", "temp", "tmp", "wip"}
STALE_TOKENS = {"backup", "bak", "copy", "deprecated", "final", "obsolete", "old"}
HISTORICAL_TOKENS = {"archive", "archived", "changelog", "history", "historical"}
MIGRATION_TOKENS = {"legacy", "migrated", "new", "next"} | STALE_TOKENS | TEMPORARY_TOKENS
MAX_TEXT_BYTES = 250_000
SIMILARITY_THRESHOLD = 0.82
VARIANT_SIMILARITY_THRESHOLD = 0.55
CANONICAL_CHAIN_LOWER = {path.lower() for path in CANONICAL_DOC_CHAIN}
MODULE_CONTAINER_NAMES = {
    "areas",
    "domain",
    "domains",
    "feature",
    "features",
    "function",
    "functions",
    "module",
    "modules",
    "plugin",
    "plugins",
    "service",
    "services",
}
ROOT_MODULE_PARENTS = {".", "api", "app", "backend", "client", "frontend", "server", "src"}
EDGE_FUNCTION_CONTAINER_PATHS = {"functions", "supabase/functions"}
SHARED_DIR_NAMES = {
    "_shared",
    "__tests__",
    "assets",
    "common",
    "components",
    "config",
    "configs",
    "core",
    "hooks",
    "infra",
    "infrastructure",
    "lib",
    "libs",
    "shared",
    "styles",
    "test",
    "tests",
    "types",
    "utils",
}
MODULE_ENTRYPOINT_STEMS = {
    "__init__",
    "app",
    "handler",
    "handlers",
    "index",
    "main",
    "route",
    "routes",
}
MODULE_GROUPING_TOKENS = {
    "api",
    "component",
    "components",
    "controller",
    "controllers",
    "handler",
    "handlers",
    "model",
    "models",
    "route",
    "routes",
    "screen",
    "screens",
    "service",
    "services",
    "store",
    "ui",
}
REGISTRY_STEMS = {"app", "bootstrap", "index", "main", "registry", "router", "routes", "server"}
TEST_DIR_NAMES = {"__tests__", "spec", "specs", "test", "tests"}
MANIFEST_FILE_NAMES = {
    "manifest.json",
    "module.json",
    "package.json",
    "plugin.json",
    "pyproject.toml",
    "requirements.txt",
}
VALIDATION_FILE_NAMES = {
    "eslint.config.js",
    "eslint.config.mjs",
    "jest.config.js",
    "jest.config.ts",
    "mypy.ini",
    "pyrightconfig.json",
    "pytest.ini",
    "ruff.toml",
    "tox.ini",
    "tsconfig.json",
    "vitest.config.js",
    "vitest.config.ts",
}
SHARED_CORE_TOKENS = SHARED_DIR_NAMES | {
    "adapter",
    "adapters",
    "base",
    "contract",
    "contracts",
    "interface",
    "interfaces",
    "schema",
    "schemas",
}


@dataclass(slots=True)
class ModuleCandidateRecord:
    path: str
    kind: str
    entrypoints: list[str]
    registration_paths: list[str]
    external_reference_paths: list[str]
    local_test_paths: list[str]
    local_validation_paths: list[str]
    local_manifest_paths: list[str]
    shared_core_reference_paths: list[str]
    cross_boundary_internal_reference_paths: list[str]
    signals: list[str]


@dataclass(slots=True)
class FileRecord:
    absolute_path: Path
    relative_path: str
    size_bytes: int
    text: str | None

    @property
    def name(self) -> str:
        return Path(self.relative_path).name

    @property
    def suffix(self) -> str:
        return Path(self.relative_path).suffix.lower()

    @property
    def lowered_path(self) -> str:
        return self.relative_path.lower()


def _load_repo_config(root: Path) -> RepoConfigSummary:
    config_path = root / CONFIG_FILE_NAME
    if not config_path.exists():
        return RepoConfigSummary()

    try:
        raw_config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read '{CONFIG_FILE_NAME}': {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid '{CONFIG_FILE_NAME}': {exc}") from exc

    ignored_paths = _load_config_path_list(
        raw_config.get("ignored_paths"),
        field_name="ignored_paths",
    )
    generated_paths = _load_config_path_list(
        raw_config.get("generated_paths"),
        field_name="generated_paths",
    )
    mirrored_docs = _load_mirrored_docs_config(raw_config.get("mirrored_docs"))
    advisory_suppressions = _load_advisory_suppressions_config(
        raw_config.get("advisory_suppressions")
    )

    return RepoConfigSummary(
        path=CONFIG_FILE_NAME,
        ignored_paths=ignored_paths,
        generated_paths=generated_paths,
        mirrored_docs=mirrored_docs,
        advisory_suppressions=advisory_suppressions,
    )


def analyze_repository(root: Path) -> RepoReport:
    if not root.exists():
        raise ValueError(f"Repository path does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Repository path must be a directory: {root}")

    config_summary = _load_repo_config(root)
    records, skipped_directories = _scan_files(root, config_summary)
    module_boundary, module_findings, module_candidates = _analyze_module_boundaries(records)
    validation_readiness, readiness_findings = _analyze_validation_readiness(
        records,
        module_boundary,
        module_candidates,
    )
    duplicate_paths, duplicate_findings, mirror_suppressed_duplicates = _detect_duplicate_docs(
        records,
        config_summary,
    )
    unclear_paths, unclear_findings, mirror_suppressed_unclear = _detect_unclear_authority(
        records,
        config_summary,
    )
    (
        duplicate_unclear_findings,
        suppressed_findings,
        suppressed_duplicate_paths,
        suppressed_unclear_paths,
    ) = _apply_advisory_suppressions(
        duplicate_findings + unclear_findings,
        config_summary,
    )
    duplicate_paths -= suppressed_duplicate_paths
    unclear_paths = {
        path: reasons
        for path, reasons in unclear_paths.items()
        if path not in suppressed_unclear_paths
    }

    migration_findings = _detect_partial_migrations(records)
    assessments = _classify_files(records, duplicate_paths, unclear_paths)
    orphan_findings = _detect_orphan_candidates(records, assessments)
    active_other_findings, more_suppressed_findings, _, _ = _apply_advisory_suppressions(
        readiness_findings
        + module_findings
        + migration_findings
        + orphan_findings,
        config_summary,
    )
    findings = sorted(
        duplicate_unclear_findings + active_other_findings,
        key=_finding_sort_key,
    )
    all_suppressed_findings = sorted(
        mirror_suppressed_duplicates
        + mirror_suppressed_unclear
        + suppressed_findings
        + more_suppressed_findings,
        key=lambda finding: (finding.kind, finding.summary),
    )
    recommended_actions = _build_recommended_actions(findings)
    repository_risks = _build_repository_risks(findings)

    return RepoReport(
        root=str(root.resolve()),
        scanned_files=len(records),
        skipped_directories=skipped_directories,
        canonical_doc_chain=CANONICAL_DOC_CHAIN.copy(),
        config_summary=config_summary,
        module_boundary=module_boundary,
        validation_readiness=validation_readiness,
        assessments=assessments,
        findings=findings,
        suppressed_findings=all_suppressed_findings,
        recommended_actions=recommended_actions,
        repository_risks=repository_risks,
    )


def _scan_files(
    root: Path,
    config_summary: RepoConfigSummary,
) -> tuple[list[FileRecord], list[str]]:
    records: list[FileRecord] = []
    skipped_directories: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)
        relative_dir = current_dir.relative_to(root)
        kept_dirnames: list[str] = []

        for dirname in dirnames:
            candidate_dir = str((relative_dir / dirname).as_posix())
            if _path_matches_any(candidate_dir, config_summary.ignored_paths):
                skipped_directories.append(candidate_dir if candidate_dir != "." else dirname)
                continue
            if _path_matches_any(candidate_dir, config_summary.generated_paths):
                skipped_directories.append(candidate_dir if candidate_dir != "." else dirname)
                continue
            if dirname.lower() in GENERATED_DIR_NAMES:
                skipped = str((relative_dir / dirname).as_posix())
                skipped_directories.append(skipped if skipped != "." else dirname)
                continue
            kept_dirnames.append(dirname)

        dirnames[:] = kept_dirnames

        for filename in filenames:
            absolute_path = current_dir / filename
            try:
                stat = absolute_path.stat()
            except OSError:
                continue

            relative_path = absolute_path.relative_to(root).as_posix()
            if _path_matches_any(relative_path, config_summary.ignored_paths):
                continue
            if _path_matches_any(relative_path, config_summary.generated_paths):
                continue
            text = _read_text_if_supported(absolute_path, stat.st_size)
            records.append(
                FileRecord(
                    absolute_path=absolute_path,
                    relative_path=relative_path,
                    size_bytes=stat.st_size,
                    text=text,
                )
            )

    records.sort(key=lambda record: record.lowered_path)
    skipped_directories.sort()
    return records, skipped_directories


def _read_text_if_supported(path: Path, size_bytes: int) -> str | None:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if size_bytes > MAX_TEXT_BYTES:
        return None
    if (
        suffix not in TEXT_SUFFIXES
        and name not in CANONICAL_ROOT_FILES
        and not name.endswith(".md")
    ):
        return None

    try:
        raw = path.read_bytes()
    except OSError:
        return None

    if b"\x00" in raw:
        return None

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="ignore")


def _analyze_module_boundaries(
    records: list[FileRecord],
) -> tuple[ModuleBoundarySummary, list[Finding], list[ModuleCandidateRecord]]:
    code_records = [
        record
        for record in records
        if record.suffix in CODE_SUFFIXES and not _is_generated(record)
    ]
    text_records = [record for record in records if record.text is not None]
    module_candidates = _collect_module_candidates(code_records, text_records)

    if not module_candidates:
        return ModuleBoundarySummary(), [], []

    strengths: list[str] = []
    modularity_risks: list[str] = []
    safe_detach_risks: list[str] = []
    findings: list[Finding] = []

    candidates_with_entrypoints = [
        candidate for candidate in module_candidates if candidate.entrypoints
    ]
    candidates_with_registration = [
        candidate for candidate in module_candidates if candidate.registration_paths
    ]
    edge_functions = [
        candidate for candidate in module_candidates if candidate.kind == "edge-function"
    ]

    if len(candidates_with_entrypoints) >= 2:
        strengths.append(
            "Heuristic strength: multiple module-like folders expose local "
            "entrypoints, which suggests clearer boundaries."
        )
    if len(candidates_with_registration) >= 2:
        strengths.append(
            "Heuristic strength: multiple module-like folders appear to be "
            "wired through explicit bootstrap or registry files."
        )
    if len(edge_functions) >= 2 and all(candidate.entrypoints for candidate in edge_functions):
        strengths.append(
            "Heuristic strength: edge-function folders appear isolated with "
            "their own entrypoints."
        )

    for candidate in module_candidates:
        if not candidate.entrypoints:
            modularity_risks.append(
                f"Possible module boundary issue: '{candidate.path}' looks "
                "module-like but no clear entrypoint was found."
            )
            findings.append(
                Finding(
                    kind="module-boundary",
                    severity=FindingSeverity.LOW,
                    summary=(
                        f"'{candidate.path}' looks like a module boundary, but "
                        "no clear local entrypoint was found."
                    ),
                    recommendation=(
                        "Heuristic only. Manual review recommended before any "
                        "restructure. Check whether the module should expose a "
                        "clear index, route, handler, or manifest."
                    ),
                    paths=[candidate.path, *candidate.external_reference_paths[:3]],
                )
            )

        if candidate.kind != "edge-function" and not candidate.registration_paths:
            modularity_risks.append(
                f"Possible module boundary issue: '{candidate.path}' appears "
                "module-like but no explicit registration or bootstrap signal "
                "was found."
            )
            findings.append(
                Finding(
                    kind="module-boundary",
                    severity=FindingSeverity.LOW,
                    summary=(
                        f"'{candidate.path}' appears module-like, but no "
                        "explicit registration or bootstrap signal was found."
                    ),
                    recommendation=(
                        "Heuristic only. Manual review recommended. Verify "
                        "whether the module is intentionally dormant, wired "
                        "implicitly, or simply not connected yet."
                    ),
                    paths=[candidate.path],
                )
            )

        if _has_migration_marker(candidate.path) and candidate.external_reference_paths:
            safe_detach_risks.append(
                f"Possible safe-detach risk: '{candidate.path}' looks legacy "
                "or versioned but still appears referenced outside its folder."
            )
            findings.append(
                Finding(
                    kind="safe-detach-risk",
                    severity=FindingSeverity.MEDIUM,
                    summary=(
                        f"'{candidate.path}' looks legacy or versioned but "
                        "still appears referenced outside its folder."
                    ),
                    recommendation=(
                        "Heuristic only. Manual review recommended before any "
                        "detach or cleanup. Verify current registration and "
                        "runtime dependencies first."
                    ),
                    paths=[candidate.path, *candidate.external_reference_paths[:3]],
                )
            )

    scattered_registry_paths = _detect_scattered_internal_registration(
        module_candidates,
        text_records,
    )
    if scattered_registry_paths:
        modularity_risks.append(
            "Possible module boundary issue: central bootstrap files appear "
            "to reach into scattered module internals directly."
        )
        findings.append(
            Finding(
                kind="module-boundary",
                severity=FindingSeverity.MEDIUM,
                summary=(
                    "Central bootstrap files appear to import or reference "
                    "module internals directly across multiple modules."
                ),
                recommendation=(
                    "Heuristic only. Manual review recommended. Check whether "
                    "those modules should be wired through module root "
                    "entrypoints instead of internal files."
                ),
                paths=scattered_registry_paths,
            )
        )

    duplicated_candidates = _detect_duplicated_module_responsibility(module_candidates)
    for duplicate_group in duplicated_candidates:
        joined_paths = ", ".join(duplicate_group)
        modularity_risks.append(
            f"Possible module boundary issue: similar module responsibility "
            f"appears in multiple folders ({joined_paths})."
        )
        findings.append(
            Finding(
                kind="module-boundary",
                severity=FindingSeverity.LOW,
                summary=(
                    "Similar module responsibility appears across multiple "
                    "folders."
                ),
                recommendation=(
                    "Heuristic only. Manual review recommended. Verify "
                    "whether these folders intentionally split a domain or "
                    "represent duplicated ownership."
                ),
                paths=duplicate_group,
            )
        )

    summary = ModuleBoundarySummary(
        candidate_modules=[
            ModuleCandidate(
                path=candidate.path,
                kind=candidate.kind,
                entrypoints=candidate.entrypoints,
                registration_paths=candidate.registration_paths,
                signals=candidate.signals,
            )
            for candidate in module_candidates
        ],
        strengths=_dedupe_strings(strengths),
        modularity_risks=_dedupe_strings(modularity_risks),
        safe_detach_risks=_dedupe_strings(safe_detach_risks),
    )
    return summary, findings, module_candidates


def _collect_module_candidates(
    code_records: list[FileRecord],
    text_records: list[FileRecord],
) -> list[ModuleCandidateRecord]:
    direct_code_by_dir: dict[str, list[FileRecord]] = defaultdict(list)
    child_dirs_by_parent: dict[str, set[str]] = defaultdict(set)

    for record in code_records:
        parent = _parent_path(record.relative_path)
        direct_code_by_dir[parent].append(record)

        parts = Path(record.relative_path).parts[:-1]
        for index in range(len(parts)):
            dir_path = Path(*parts[: index + 1]).as_posix()
            parent_path = Path(*parts[:index]).as_posix() if index > 0 else "."
            child_dirs_by_parent[parent_path].add(dir_path)

    candidate_paths: set[str] = set()
    for parent_path, child_dirs in child_dirs_by_parent.items():
        eligible_children = sorted(
            child_dir
            for child_dir in child_dirs
            if _is_eligible_module_directory(child_dir)
        )
        if not eligible_children:
            continue
        if _is_module_container(
            parent_path,
            eligible_children,
            direct_code_by_dir,
            child_dirs_by_parent,
        ):
            candidate_paths.update(eligible_children)

    candidates = [
        _build_module_candidate(
            candidate_path,
            code_records,
            text_records,
            child_dirs_by_parent,
        )
        for candidate_path in sorted(candidate_paths)
    ]
    return sorted(candidates, key=lambda candidate: candidate.path)


def _build_module_candidate(
    candidate_path: str,
    code_records: list[FileRecord],
    text_records: list[FileRecord],
    child_dirs_by_parent: dict[str, set[str]],
) -> ModuleCandidateRecord:
    descendant_records = [
        record for record in code_records if _is_under_path(record.relative_path, candidate_path)
    ]
    local_text_records = [
        record for record in text_records if _is_under_path(record.relative_path, candidate_path)
    ]
    entrypoints = sorted(
        record.relative_path
        for record in descendant_records
        if _is_module_entrypoint(record, candidate_path)
    )
    registration_paths = sorted(
        {
            record.relative_path
            for record in text_records
            if not _is_under_path(record.relative_path, candidate_path)
            and _is_registry_like_record(record)
            and _text_references_module(record.text, candidate_path)
        }
    )
    external_reference_paths = sorted(
        {
            record.relative_path
            for record in text_records
            if not _is_under_path(record.relative_path, candidate_path)
            and _text_references_module(record.text, candidate_path)
        }
    )
    local_test_paths = sorted(
        record.relative_path
        for record in local_text_records
        if _is_local_test_record(record)
    )
    local_validation_paths = sorted(
        record.relative_path
        for record in local_text_records
        if _is_local_validation_record(record)
    )
    local_manifest_paths = sorted(
        record.relative_path
        for record in local_text_records
        if _is_manifest_record(record)
    )

    signals: list[str] = []
    if entrypoints:
        signals.append("clear-entrypoint")
    if registration_paths:
        signals.append("explicit-registration-signal")
    if local_test_paths:
        signals.append("local-tests")
    if local_validation_paths:
        signals.append("local-validation")
    if _has_local_grouping(candidate_path, descendant_records, child_dirs_by_parent):
        signals.append("local-grouping")
    if local_manifest_paths or _has_manifest_file(descendant_records):
        signals.append("local-manifest")

    kind = _module_kind(candidate_path)
    if kind == "edge-function":
        signals.append("isolated-edge-function")

    return ModuleCandidateRecord(
        path=candidate_path,
        kind=kind,
        entrypoints=entrypoints,
        registration_paths=registration_paths,
        external_reference_paths=external_reference_paths,
        local_test_paths=local_test_paths,
        local_validation_paths=local_validation_paths,
        local_manifest_paths=local_manifest_paths,
        shared_core_reference_paths=[],
        cross_boundary_internal_reference_paths=[],
        signals=signals,
    )


def _analyze_validation_readiness(
    records: list[FileRecord],
    module_boundary: ModuleBoundarySummary,
    module_candidates: list[ModuleCandidateRecord],
) -> tuple[ValidationReadinessSummary, list[Finding]]:
    if not module_candidates:
        return ValidationReadinessSummary(), []

    code_records = [
        record
        for record in records
        if record.suffix in CODE_SUFFIXES and not _is_generated(record)
    ]
    text_records = [record for record in records if record.text is not None]
    shared_core_areas = _collect_shared_core_areas(code_records)
    contract_areas = [
        area
        for area in shared_core_areas
        if _dir_name(area)
        in {
            "contract",
            "contracts",
            "interface",
            "interfaces",
            "schema",
            "schemas",
            "types",
        }
    ]
    shared_core_code_records = [
        record for record in code_records if _shared_core_area(record.relative_path) is not None
    ]

    for candidate in module_candidates:
        module_text_records = [
            record
            for record in text_records
            if _is_under_path(record.relative_path, candidate.path)
        ]
        candidate.shared_core_reference_paths = sorted(
            {
                record.relative_path
                for record in module_text_records
                if _text_references_shared_core_areas(record.text, shared_core_areas)
            }
        )
        candidate.cross_boundary_internal_reference_paths = sorted(
            {
                record.relative_path
                for record in module_text_records
                if _references_other_module_internals(record, candidate.path, module_candidates)
            }
        )

    global_cross_boundary_internal_paths = sorted(
        {
            record.relative_path
            for record in text_records
            if _touches_multiple_module_internals(record, module_candidates)
        }
    )

    modules_with_local_checks = [
        candidate
        for candidate in module_candidates
        if candidate.local_test_paths or candidate.local_validation_paths
    ]
    modules_with_manifests = [
        candidate for candidate in module_candidates if candidate.local_manifest_paths
    ]
    modules_with_shared_refs = [
        candidate for candidate in module_candidates if candidate.shared_core_reference_paths
    ]
    modules_with_contract_refs = [
        candidate
        for candidate in module_candidates
        if contract_areas
        and any(
            _text_references_shared_core_areas(record.text, contract_areas)
            for record in text_records
            if _is_under_path(record.relative_path, candidate.path)
        )
    ]
    edge_functions_with_shared_refs = [
        candidate
        for candidate in module_candidates
        if candidate.kind == "edge-function" and candidate.shared_core_reference_paths
    ]
    advisory_isolated_modules = sorted(
        candidate.path
        for candidate in module_candidates
        if _candidate_looks_advisory_isolated(candidate)
    )

    structural_strengths = module_boundary.strengths.copy()
    readiness_strengths: list[str] = []
    broad_validation_triggers: list[str] = []
    shared_core_coupling_risks: list[str] = []
    validation_blockers: list[str] = []
    manual_review_recommendations: list[str] = []
    findings: list[Finding] = []
    local_check_examples = _format_path_examples(
        [candidate.path for candidate in modules_with_local_checks]
    )
    manifest_examples = _format_path_examples(
        [candidate.path for candidate in modules_with_manifests]
    )
    isolated_examples = _format_path_examples(advisory_isolated_modules)
    shared_core_examples = _format_path_examples(shared_core_areas)
    shared_ref_examples = _format_path_examples(
        [candidate.path for candidate in modules_with_shared_refs]
    )
    contract_examples = _format_path_examples(contract_areas)
    contract_module_examples = _format_path_examples(
        [candidate.path for candidate in modules_with_contract_refs]
    )
    global_cross_boundary_examples = _format_path_examples(
        global_cross_boundary_internal_paths
    )

    if len(modules_with_local_checks) >= 2:
        module_check_count = _counted_phrase(
            len(modules_with_local_checks),
            "module-like area",
            "module-like areas",
        )
        structural_strengths.append(
            "Heuristic structural strength: "
            f"{module_check_count} show local tests or validation files "
            f"({local_check_examples}), "
            "which makes narrower validation boundaries easier to reason about."
        )
    if len(modules_with_manifests) >= 2:
        manifest_count = _counted_phrase(
            len(modules_with_manifests),
            "module-like area",
            "module-like areas",
        )
        structural_strengths.append(
            "Heuristic structural strength: "
            f"{manifest_count} show local manifests or package declarations "
            f"({manifest_examples}), "
            "which gives their boundaries a more explicit shape."
        )

    if len(advisory_isolated_modules) >= 2:
        isolated_count = _counted_phrase(
            len(advisory_isolated_modules),
            "module-like area",
            "module-like areas",
        )
        readiness_strengths.append(
            "Heuristic readiness strength: "
            f"{isolated_count} ({isolated_examples}) combine clear entrypoints, "
            "explicit wiring or isolated layout, local checks, and no detected "
            "shared/core or cross-boundary internal references."
        )
    isolated_edge_functions = [
        candidate.path
        for candidate in module_candidates
        if candidate.kind == "edge-function"
        and candidate.path in advisory_isolated_modules
    ]
    if isolated_edge_functions:
        isolated_edge_examples = _format_path_examples(isolated_edge_functions)
        isolated_edge_count = _counted_phrase(
            len(isolated_edge_functions),
            "edge-function folder",
            "edge-function folders",
        )
        readiness_strengths.append(
            "Heuristic readiness strength: "
            f"{isolated_edge_count} ({isolated_edge_examples}) look structurally closer "
            "to narrower validation because they combine isolated layout, local "
            "entrypoints, and low detected coupling."
        )

    shared_core_ratio = (
        len(shared_core_code_records) / len(code_records)
        if code_records
        else 0.0
    )
    if shared_core_areas and (
        shared_core_ratio >= 0.25
        or len(shared_core_code_records) >= max(4, len(module_candidates))
    ):
        shared_core_area_count = _counted_phrase(
            len(shared_core_areas),
            "shared/core-style area",
            "shared/core-style areas",
        )
        shared_core_coupling_risks.append(
            "Possible shared/core coupling risk: "
            f"{shared_core_area_count} ({shared_core_examples}) account for about "
            f"{shared_core_ratio:.0%} of scanned code files, which lowers confidence "
            "that one-folder validation maps cleanly to real impact."
        )
        validation_blockers.append(
            "Possible blocker to affected-only validation: concentrated "
            f"shared/core-style areas ({shared_core_examples}) "
            "likely widen validation scope and still deserve broad manual review."
        )
        findings.append(
            Finding(
                kind="shared-core-coupling",
                severity=(
                    FindingSeverity.HIGH
                    if shared_core_ratio >= 0.35
                    else FindingSeverity.MEDIUM
                ),
                summary=(
                    "Shared/core-style areas "
                    f"({shared_core_examples}) account for about "
                    f"{shared_core_ratio:.0%} of scanned code files."
                ),
                recommendation=(
                    "Heuristic only. Manual review recommended. Treat changes "
                    "in those shared/core areas as likely broad validation "
                    "triggers until their downstream coupling is better understood."
                ),
                paths=shared_core_areas[:6],
            )
        )
        manual_review_recommendations.append(
            "Review shared/core-style directories such as "
            f"{shared_core_examples} first when deciding "
            "whether narrower validation is realistic."
        )
        if shared_core_areas:
            broad_validation_triggers.append(
                "Likely broad validation trigger: changes inside shared/core-style "
                f"areas ({shared_core_examples}) may widen "
                "validation scope beyond one module-like area because a large "
                "share of scanned code sits there."
            )

    if len(modules_with_shared_refs) >= max(2, (len(module_candidates) + 1) // 2):
        shared_ref_count = _counted_phrase(
            len(modules_with_shared_refs),
            "module-like area",
            "module-like areas",
        )
        shared_core_coupling_risks.append(
            "Possible shared/core coupling risk: "
            f"{shared_ref_count} ({shared_ref_examples}) "
            "appear to reference shared/core code directly."
        )
        validation_blockers.append(
            "Possible blocker to affected-only validation: folder boundaries "
            "look cleaner than the dependency surface because many module-like "
            "areas still route logic through shared/core hubs."
        )
        findings.append(
            Finding(
                kind="shared-core-coupling",
                severity=FindingSeverity.MEDIUM,
                summary=(
                    f"{shared_ref_count} appear to reference shared/core "
                    f"code directly ({shared_ref_examples})."
                ),
                recommendation=(
                    "Heuristic only. Manual review recommended. Reduce "
                    "confidence in affected-only validation when many modules "
                    "depend on shared/core hubs rather than mostly local boundaries."
                ),
                paths=[candidate.path for candidate in modules_with_shared_refs[:6]],
            )
        )
        manual_review_recommendations.append(
            "Inspect whether shared/core areas act as utility hubs or contract "
            "hubs before trusting module-scoped validation, especially for "
            f"{shared_ref_examples}."
        )
        broad_validation_triggers.append(
            "Likely broad validation trigger: shared/core hubs referenced from "
            f"{shared_ref_examples} "
            "may widen validation beyond a single module-like folder."
        )

    if len(modules_with_contract_refs) >= 2:
        contract_ref_count = _counted_phrase(
            len(modules_with_contract_refs),
            "module-like area",
            "module-like areas",
        )
        shared_core_coupling_risks.append(
            "Possible shared/core coupling risk: contract-style areas "
            f"({contract_examples}) appear to be touched by "
            f"{contract_ref_count} ({contract_module_examples})."
        )
        validation_blockers.append(
            "Possible blocker to affected-only validation: shared contracts, "
            "types, or schemas appear central enough that their changes may need "
            "broader validation than one module at a time."
        )
        findings.append(
            Finding(
                kind="shared-core-coupling",
                severity=FindingSeverity.MEDIUM,
                summary=(
                    "Contract-style areas "
                    f"({contract_examples}) appear to be shared by "
                    f"{contract_ref_count}."
                ),
                recommendation=(
                    "Heuristic only. Manual review recommended. Treat changes "
                    "to those contract-style areas as higher-risk until a more "
                    "explicit dependency picture exists."
                ),
                paths=contract_areas[:6],
            )
        )
        if contract_areas:
            broad_validation_triggers.append(
                "Likely broad validation trigger: central contract-style areas "
                f"({contract_examples}) sit on multiple module "
                "paths, so changes there may widen validation scope."
            )

    missing_local_checks = [
        candidate
        for candidate in module_candidates
        if not candidate.local_test_paths and not candidate.local_validation_paths
    ]
    missing_local_check_examples = _format_path_examples(
        [candidate.path for candidate in missing_local_checks]
    )
    if missing_local_checks and len(missing_local_checks) >= max(1, len(module_candidates) // 2):
        missing_local_check_count = _counted_phrase(
            len(missing_local_checks),
            "module-like area",
            "module-like areas",
        )
        validation_blockers.append(
            "Possible blocker to affected-only validation: "
            f"{missing_local_check_count} ({missing_local_check_examples}) "
            "do not show module-local tests or validation files, so there is "
            "less structural evidence for narrow validation boundaries."
        )
        findings.append(
            Finding(
                kind="validation-readiness",
                severity=FindingSeverity.MEDIUM,
                summary=(
                    f"{missing_local_check_count} do not show local tests or "
                    f"validation files ({missing_local_check_examples})."
                ),
                recommendation=(
                    "Heuristic only. Manual review recommended. Add or "
                    "identify module-local checks before trusting module-scoped "
                    "validation decisions."
                ),
                paths=[candidate.path for candidate in missing_local_checks[:6]],
            )
        )
        manual_review_recommendations.append(
            "Prefer module-local tests or validation commands if advisory "
            "affected-scope validation is a future goal, especially for "
            f"{missing_local_check_examples}."
        )

    if global_cross_boundary_internal_paths:
        validation_blockers.append(
            "Possible blocker to affected-only validation: "
            f"{_counted_phrase(len(global_cross_boundary_internal_paths), 'file', 'files')} "
            f"such as {_format_path_examples(global_cross_boundary_internal_paths)} "
            "appear to reference multiple module internals directly, which can "
            "force broader bootstrap-level validation."
        )
        findings.append(
            Finding(
                kind="validation-readiness",
                severity=FindingSeverity.MEDIUM,
                summary=(
                    "Files such as "
                    f"{_format_path_examples(global_cross_boundary_internal_paths)} "
                    "appear to reach into multiple module internals directly."
                ),
                recommendation=(
                    "Heuristic only. Manual review recommended. Prefer module "
                    "root entrypoints over internal cross-boundary imports "
                    "before assuming a narrow validation scope is reliable."
                ),
                paths=global_cross_boundary_internal_paths[:6],
            )
        )
        manual_review_recommendations.append(
            "Check whether central bootstrap files and feature code can depend "
            "on module entrypoints instead of internal module files, especially "
            f"for {_format_path_examples(global_cross_boundary_internal_paths)}."
        )
        broad_validation_triggers.append(
            "Likely broad validation trigger: files such as "
            f"{global_cross_boundary_examples} appear to "
            "reach into multiple module internals directly."
        )

    if edge_functions_with_shared_refs:
        edge_function_paths = [candidate.path for candidate in edge_functions_with_shared_refs]
        edge_function_examples = _format_path_examples(edge_function_paths)
        edge_function_count = _counted_phrase(
            len(edge_functions_with_shared_refs),
            "edge-function folder",
            "edge-function folders",
        )
        validation_blockers.append(
            "Possible blocker to affected-only validation: "
            f"{edge_function_count} ({edge_function_examples}) look isolated by "
            "layout but still depend on shared/core areas."
        )
        findings.append(
            Finding(
                kind="validation-readiness",
                severity=FindingSeverity.MEDIUM,
                summary=(
                    "Edge-function folders "
                    f"({edge_function_examples}) look isolated by "
                    "layout but still appear to depend on shared/core areas."
                ),
                recommendation=(
                    "Heuristic only. Manual review recommended. Treat changes "
                    "to the shared/core areas they consume as broader "
                    "validation triggers."
                ),
                paths=[candidate.path for candidate in edge_functions_with_shared_refs[:6]],
            )
        )
        broad_validation_triggers.append(
            "Likely broad validation trigger: edge-function or service-style "
            f"folders ({edge_function_examples}) still depend "
            "on shared/core internals, so changes in those shared areas may widen "
            "validation beyond one isolated folder."
        )

    narrow_validation_candidates = sorted(
        [
            _build_validation_scope_candidate(
                candidate,
                repo_has_broad_triggers=bool(broad_validation_triggers),
            )
            for candidate in module_candidates
            if _candidate_looks_advisory_isolated(candidate)
        ],
        key=lambda candidate: candidate.path,
    )
    if narrow_validation_candidates:
        manual_review_recommendations.append(
            "Treat possible narrow validation candidates as advisory structure "
            "signals only; manual review is still recommended before narrowing checks."
        )

    summary = ValidationReadinessSummary(
        advisory_isolated_modules=advisory_isolated_modules,
        broad_validation_areas=shared_core_areas if broad_validation_triggers else [],
        broad_validation_triggers=_dedupe_strings(broad_validation_triggers),
        narrow_validation_candidates=narrow_validation_candidates,
        structural_strengths=_dedupe_strings(structural_strengths),
        readiness_strengths=_dedupe_strings(readiness_strengths),
        shared_core_coupling_risks=_dedupe_strings(shared_core_coupling_risks),
        validation_blockers=_dedupe_strings(validation_blockers),
        manual_review_recommendations=_dedupe_strings(manual_review_recommendations),
    )
    return summary, findings


def _is_module_container(
    parent_path: str,
    child_dirs: list[str],
    direct_code_by_dir: dict[str, list[FileRecord]],
    child_dirs_by_parent: dict[str, set[str]],
) -> bool:
    parent_name = _dir_name(parent_path)
    if parent_path in EDGE_FUNCTION_CONTAINER_PATHS or parent_name in MODULE_CONTAINER_NAMES:
        return True
    if parent_path not in ROOT_MODULE_PARENTS or len(child_dirs) < 2:
        return False

    signaled_children = sum(
        1
        for child_dir in child_dirs
        if _child_has_module_signals(child_dir, direct_code_by_dir, child_dirs_by_parent)
    )
    return signaled_children >= 2


def _child_has_module_signals(
    child_dir: str,
    direct_code_by_dir: dict[str, list[FileRecord]],
    child_dirs_by_parent: dict[str, set[str]],
) -> bool:
    direct_records = direct_code_by_dir.get(child_dir, [])
    has_entrypoint = any(_is_module_entrypoint(record, child_dir) for record in direct_records)
    has_grouping_dir = any(
        _dir_name(nested_dir) in MODULE_GROUPING_TOKENS
        for nested_dir in child_dirs_by_parent.get(child_dir, set())
    )
    return has_entrypoint or has_grouping_dir


def _detect_scattered_internal_registration(
    module_candidates: list[ModuleCandidateRecord],
    text_records: list[FileRecord],
) -> list[str]:
    scattered_paths: list[str] = []

    for record in text_records:
        if not _is_registry_like_record(record):
            continue

        touched_modules = {
            candidate.path
            for candidate in module_candidates
            if _text_references_module_internal(record.text, candidate.path)
        }
        if len(touched_modules) >= 3:
            scattered_paths.append(record.relative_path)

    return sorted(scattered_paths)


def _detect_duplicated_module_responsibility(
    module_candidates: list[ModuleCandidateRecord],
) -> list[list[str]]:
    grouped_candidates: dict[str, list[str]] = defaultdict(list)

    for candidate in module_candidates:
        normalized_name = _normalized_module_name(candidate.path)
        if len(normalized_name) >= 3:
            grouped_candidates[normalized_name].append(candidate.path)

    return sorted(
        [
            sorted(paths)
            for paths in grouped_candidates.values()
            if len(paths) > 1
        ]
    )


def _detect_duplicate_docs(
    records: list[FileRecord],
    config_summary: RepoConfigSummary,
) -> tuple[set[str], list[Finding], list[SuppressedFinding]]:
    duplicate_paths: set[str] = set()
    findings: list[Finding] = []
    suppressed_findings: list[SuppressedFinding] = []
    docs = [record for record in records if record.suffix in MARKDOWN_SUFFIXES]
    grouped_docs = _group_docs_by_family(docs)

    for family, group in grouped_docs.items():
        if len(group) < 2:
            continue

        anchor = _pick_anchor(group, family)
        duplicates = [anchor]

        for record in group:
            if record.relative_path == anchor.relative_path:
                continue
            similarity = _similarity(anchor.text, record.text)
            if similarity >= SIMILARITY_THRESHOLD:
                duplicates.append(record)
                continue
            if (
                _has_variant_marker(record.relative_path)
                and similarity >= VARIANT_SIMILARITY_THRESHOLD
            ):
                duplicates.append(record)

        deduped = sorted(
            {record.relative_path: record for record in duplicates}.values(),
            key=lambda item: item.lowered_path,
        )
        if len(deduped) < 2:
            continue

        active_records: list[FileRecord] = []
        for record in deduped:
            counterpart_paths = [
                other.relative_path
                for other in deduped
                if other.relative_path != record.relative_path
            ]
            mirror_match = _find_publish_mirror_counterpart(
                record.relative_path,
                counterpart_paths,
                config_summary.mirrored_docs,
            )
            if mirror_match is None:
                active_records.append(record)
                continue

            mirror, counterpart = mirror_match
            suppressed_findings.append(
                SuppressedFinding(
                    kind="duplicate-docs",
                    summary=(
                        "Configured mirrored documentation suppressed expected "
                        f"duplicate-docs noise for '{record.relative_path}'."
                    ),
                    reason=(
                        "Configured mirrored docs: "
                        f"`{mirror.source}` -> `{mirror.publish}` with source "
                        f"counterpart `{counterpart}`."
                    ),
                    paths=sorted({record.relative_path, counterpart}),
                )
            )

        if len(active_records) < 2:
            continue

        canonical_present = any(
            record.lowered_path in CANONICAL_CHAIN_LOWER for record in active_records
        )
        for record in active_records:
            if record.lowered_path not in CANONICAL_CHAIN_LOWER:
                duplicate_paths.add(record.relative_path)

        severity = FindingSeverity.HIGH if canonical_present else FindingSeverity.MEDIUM
        findings.append(
            Finding(
                kind="duplicate-docs",
                severity=severity,
                summary=(
                    f"Potential duplicate documentation detected for the '{family}' doc family."
                ),
                recommendation=(
                    "Choose one canonical file, merge any missing content, "
                    "then archive or remove the verified duplicate variants."
                ),
                paths=[record.relative_path for record in active_records],
            )
        )

    return duplicate_paths, findings, _dedupe_suppressed_findings(suppressed_findings)


def _detect_unclear_authority(
    records: list[FileRecord],
    config_summary: RepoConfigSummary,
) -> tuple[dict[str, list[str]], list[Finding], list[SuppressedFinding]]:
    unclear_paths: dict[str, list[str]] = {}
    findings: list[Finding] = []
    suppressed_findings: list[SuppressedFinding] = []
    docs = [record for record in records if record.suffix in MARKDOWN_SUFFIXES]
    grouped_docs = _group_docs_by_family(docs)

    for family, group in grouped_docs.items():
        expected_path = CANONICAL_DOC_FAMILIES.get(family)
        if expected_path is None:
            continue

        noncanonical = [record for record in group if record.lowered_path != expected_path.lower()]
        if not noncanonical:
            continue

        active_noncanonical: list[FileRecord] = []
        reasons = [f"Looks like a governance doc outside the canonical location '{expected_path}'."]
        for record in noncanonical:
            counterpart_paths = [
                other.relative_path
                for other in group
                if other.relative_path != record.relative_path
            ]
            mirror_match = _find_publish_mirror_counterpart(
                record.relative_path,
                counterpart_paths,
                config_summary.mirrored_docs,
            )
            if mirror_match is not None:
                mirror, counterpart = mirror_match
                suppressed_findings.append(
                    SuppressedFinding(
                        kind="unclear-authority",
                        summary=(
                            "Configured mirrored documentation suppressed expected "
                            f"unclear-authority noise for '{record.relative_path}'."
                        ),
                        reason=(
                            "Configured mirrored docs: "
                            f"`{mirror.source}` -> `{mirror.publish}` with source "
                            f"counterpart `{counterpart}`."
                        ),
                        paths=sorted({record.relative_path, counterpart}),
                    )
                )
                continue

            active_noncanonical.append(record)
            unclear_paths[record.relative_path] = reasons

        if not active_noncanonical:
            continue

        active_group = [
            record for record in group if record.lowered_path == expected_path.lower()
        ] + active_noncanonical

        if len(active_group) == 1 and active_group[0].lowered_path != expected_path.lower():
            findings.append(
                Finding(
                    kind="unclear-authority",
                    severity=FindingSeverity.MEDIUM,
                    summary=(
                        f"'{active_group[0].relative_path}' appears to act as a "
                        f"'{family}' authority file, but the canonical path is "
                        "missing."
                    ),
                    recommendation=(
                        f"Either move this content to '{expected_path}' or "
                        "declare a different canonical authority explicitly."
                    ),
                    paths=[active_group[0].relative_path],
                )
            )
        elif len(active_group) > 1:
            findings.append(
                Finding(
                    kind="unclear-authority",
                    severity=FindingSeverity.MEDIUM,
                    summary=(
                        f"Multiple files appear to claim authority for '{family}' documentation."
                    ),
                    recommendation=(
                        f"Normalize authority around '{expected_path}' and "
                        "demote or archive the variants."
                    ),
                    paths=[record.relative_path for record in active_group],
                )
            )

    return unclear_paths, findings, _dedupe_suppressed_findings(suppressed_findings)


def _detect_partial_migrations(records: list[FileRecord]) -> list[Finding]:
    findings: list[Finding] = []
    docs = [record for record in records if record.suffix in MARKDOWN_SUFFIXES]
    grouped_docs = _group_docs_by_family(docs)

    for family, group in grouped_docs.items():
        if len(group) < 2:
            continue
        variant_paths = [
            record.relative_path for record in group if _has_migration_marker(record.relative_path)
        ]
        if not variant_paths:
            continue
        severity = (
            FindingSeverity.HIGH if family in CANONICAL_DOC_FAMILIES else FindingSeverity.MEDIUM
        )
        findings.append(
            Finding(
                kind="partial-migration",
                severity=severity,
                summary=(
                    "Versioned or legacy-looking files suggest an incomplete "
                    f"migration around '{family}'."
                ),
                recommendation=(
                    "Finish the migration into a single source of truth "
                    "before deleting any leftover files."
                ),
                paths=sorted(record.relative_path for record in group),
            )
        )

    return findings


def _classify_files(
    records: list[FileRecord],
    duplicate_paths: set[str],
    unclear_paths: dict[str, list[str]],
) -> list[FileAssessment]:
    assessments: list[FileAssessment] = []
    unclear_lookup = {path.lower(): reasons for path, reasons in unclear_paths.items()}

    for record in records:
        reasons: list[str] = []
        lowered_path = record.lowered_path

        if _is_generated(record):
            category = FileCategory.GENERATED
            reasons.append("Matches generated file naming or extension patterns.")
        elif lowered_path in duplicate_paths:
            category = FileCategory.DUPLICATE
            reasons.append("Overlaps with another document in the same family.")
        elif _is_exact_canonical(record):
            category = FileCategory.CANONICAL
            reasons.append("Matches a canonical governance or root configuration path.")
        elif _has_temporary_marker(record.relative_path):
            category = FileCategory.TEMPORARY
            reasons.append("Looks like a temporary, draft, or scratch artifact.")
        elif _has_historical_marker(record.relative_path):
            category = FileCategory.HISTORICAL
            reasons.append("Looks like intentionally archived or historical material.")
        elif _has_stale_marker(record.relative_path):
            category = FileCategory.STALE
            reasons.append("Looks like an old, copied, backup, or deprecated artifact.")
        elif lowered_path in unclear_lookup:
            category = FileCategory.UNCLEAR_AUTHORITY
            reasons.extend(unclear_lookup[lowered_path])
        else:
            category = FileCategory.SUPPORTING
            reasons.append(
                "Supports implementation, tests, or documentation but does "
                "not appear authoritative."
            )

        assessments.append(
            FileAssessment(
                path=record.relative_path,
                category=category,
                reasons=reasons,
                size_bytes=record.size_bytes,
            )
        )

    return assessments


def _detect_orphan_candidates(
    records: list[FileRecord],
    assessments: list[FileAssessment],
) -> list[Finding]:
    text_map = {
        record.relative_path: record.text.lower() for record in records if record.text is not None
    }
    suspicious_paths = {
        assessment.path
        for assessment in assessments
        if assessment.category
        in {
            FileCategory.DUPLICATE,
            FileCategory.STALE,
            FileCategory.TEMPORARY,
            FileCategory.UNCLEAR_AUTHORITY,
        }
    }

    orphan_candidates: list[str] = []
    for path in sorted(suspicious_paths):
        filename = Path(path).name.lower()
        references = [
            other_path
            for other_path, text in text_map.items()
            if other_path != path and filename in text
        ]
        if not references:
            orphan_candidates.append(path)

    if not orphan_candidates:
        return []

    return [
        Finding(
            kind="orphaned-artifacts",
            severity=FindingSeverity.LOW,
            summary=(
                "Some suspicious files look likely orphaned because they are "
                "not referenced elsewhere in repository text."
            ),
            recommendation=(
                "Manual review is required. Verify they are not used "
                "indirectly by tooling or human workflows before any "
                "non-destructive archiving or destructive cleanup."
            ),
            paths=orphan_candidates,
        )
    ]


def _build_recommended_actions(findings: list[Finding]) -> list[str]:
    actions: list[str] = []
    finding_kinds = {finding.kind for finding in findings}

    if "duplicate-docs" in finding_kinds:
        actions.append(
            "Consolidate duplicate documentation into one canonical source of truth per topic."
        )
    if "unclear-authority" in finding_kinds:
        actions.append(
            "Normalize governance docs around README.md -> AGENTS.md -> "
            "docs/architecture.md -> docs/validation.md -> docs/project-tree.md."
        )
    if "partial-migration" in finding_kinds:
        actions.append("Finish or explicitly abandon partial migrations before cleanup.")
    if "module-boundary" in finding_kinds:
        actions.append(
            "Review module-like folders for clearer entrypoints, registration, "
            "and internal boundary discipline."
        )
    if "validation-readiness" in finding_kinds:
        actions.append(
            "Treat affected-only validation as advisory only until module-local "
            "checks and cross-boundary coupling are clearer."
        )
    if "shared-core-coupling" in finding_kinds:
        actions.append(
            "Treat shared/core-style directories as broad validation triggers "
            "until their coupling pressure is better understood."
        )
    if "safe-detach-risk" in finding_kinds:
        actions.append(
            "Treat detach or cleanup of legacy-looking modules as manual-review "
            "work only until registration and references are verified."
        )
    if "orphaned-artifacts" in finding_kinds:
        actions.append(
            "Verify suspicious orphan candidates against scripts, CI, and "
            "manual workflows before removal."
        )
    if not actions:
        actions.append(
            "No high-risk cleanup issues detected; keep the existing "
            "governance chain explicit and current."
        )
    return actions


def _build_repository_risks(findings: list[Finding]) -> list[str]:
    finding_kinds = {finding.kind for finding in findings}
    risks: list[str] = []

    if "duplicate-docs" in finding_kinds:
        risks.append(
            "Duplicate or near-duplicate docs can split authority and drift independently."
        )
    if "unclear-authority" in finding_kinds:
        risks.append("Unclear governance ownership makes documentation updates inconsistent.")
    if "partial-migration" in finding_kinds:
        risks.append(
            "Incomplete migrations increase the chance of deleting a file that is still needed."
        )
    if "module-boundary" in finding_kinds:
        risks.append(
            "Weak module boundaries can make feature ownership and registration "
            "harder to reason about."
        )
    if "validation-readiness" in finding_kinds:
        risks.append(
            "Affected-only validation may be misleading when local checks and "
            "cross-boundary coupling signals are weak."
        )
    if "shared-core-coupling" in finding_kinds:
        risks.append(
            "Shared/core concentration can force broader validation even when "
            "feature folders look clean."
        )
    if "safe-detach-risk" in finding_kinds:
        risks.append(
            "Legacy-looking modules may still be live, so detach safety should "
            "not be inferred from naming alone."
        )
    if "orphaned-artifacts" in finding_kinds:
        risks.append(
            "Files that appear unreferenced may still be used indirectly by humans or tooling."
        )

    return risks


def _group_docs_by_family(records: list[FileRecord]) -> dict[str, list[FileRecord]]:
    grouped: dict[str, list[FileRecord]] = {}
    for record in records:
        family = _document_family(record.relative_path)
        grouped.setdefault(family, []).append(record)
    return grouped


def _document_family(relative_path: str) -> str:
    stem = Path(relative_path).stem.lower()
    tokens = re.findall(r"[a-z0-9]+", stem)
    normalized_tokens = [
        token
        for token in tokens
        if token not in MIGRATION_TOKENS and not re.fullmatch(r"v\d+", token)
    ]
    if normalized_tokens == ["project", "tree"]:
        return "project-tree"
    if normalized_tokens:
        return "-".join(normalized_tokens)
    return stem


def _pick_anchor(group: list[FileRecord], family: str) -> FileRecord:
    expected = CANONICAL_DOC_FAMILIES.get(family)
    if expected is not None:
        for record in group:
            if record.lowered_path == expected.lower():
                return record
    return min(group, key=lambda record: (len(record.relative_path), record.lowered_path))


def _similarity(left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    normalized_left = _normalize_text(left)
    normalized_right = _normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    return SequenceMatcher(a=normalized_left, b=normalized_right).ratio()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _has_variant_marker(relative_path: str) -> bool:
    return _contains_any_token(relative_path, MIGRATION_TOKENS) or _contains_version_token(
        relative_path
    )


def _has_migration_marker(relative_path: str) -> bool:
    return _contains_any_token(relative_path, MIGRATION_TOKENS) or _contains_version_token(
        relative_path
    )


def _has_temporary_marker(relative_path: str) -> bool:
    return _contains_any_token(relative_path, TEMPORARY_TOKENS)


def _has_stale_marker(relative_path: str) -> bool:
    return _contains_any_token(relative_path, STALE_TOKENS)


def _has_historical_marker(relative_path: str) -> bool:
    return _contains_any_token(relative_path, HISTORICAL_TOKENS)


def _contains_any_token(relative_path: str, tokens: set[str]) -> bool:
    parts = re.findall(r"[a-z0-9]+", relative_path.lower())
    return any(token in parts for token in tokens)


def _contains_version_token(relative_path: str) -> bool:
    parts = re.findall(r"[a-z0-9]+", relative_path.lower())
    return any(re.fullmatch(r"v\d+", part) for part in parts)


def _has_local_grouping(
    candidate_path: str,
    descendant_records: list[FileRecord],
    child_dirs_by_parent: dict[str, set[str]],
) -> bool:
    grouping_tokens: set[str] = set()

    for record in descendant_records:
        relative_parts = Path(record.relative_path).parts
        candidate_parts = Path(candidate_path).parts
        for part in relative_parts[len(candidate_parts) : -1]:
            if part.lower() in MODULE_GROUPING_TOKENS:
                grouping_tokens.add(part.lower())

    for nested_dir in child_dirs_by_parent.get(candidate_path, set()):
        nested_name = _dir_name(nested_dir)
        if nested_name in MODULE_GROUPING_TOKENS:
            grouping_tokens.add(nested_name)

    return len(grouping_tokens) >= 2


def _has_manifest_file(descendant_records: list[FileRecord]) -> bool:
    manifest_names = {"manifest.json", "module.json", "package.json", "plugin.json"}
    manifest_stems = {"manifest", "module", "plugin", "registry"}
    return any(
        record.name.lower() in manifest_names or Path(record.name).stem.lower() in manifest_stems
        for record in descendant_records
    )


def _is_local_test_record(record: FileRecord) -> bool:
    path = Path(record.relative_path)
    stem = path.stem.lower()
    suffixes = [suffix.lower() for suffix in path.suffixes]
    path_parts = {part.lower() for part in path.parts}
    return (
        bool(path_parts & TEST_DIR_NAMES)
        or ".test" in suffixes
        or ".spec" in suffixes
        or stem.startswith("test_")
        or stem.endswith("_test")
        or stem.endswith("_spec")
    )


def _is_local_validation_record(record: FileRecord) -> bool:
    name = record.name.lower()
    stem = Path(record.name).stem.lower()
    return name in VALIDATION_FILE_NAMES or "validation" in stem


def _is_manifest_record(record: FileRecord) -> bool:
    return record.name.lower() in MANIFEST_FILE_NAMES


def _collect_shared_core_areas(records: list[FileRecord]) -> list[str]:
    return sorted(
        {
            area
            for record in records
            if (area := _shared_core_area(record.relative_path)) is not None
        }
    )


def _shared_core_area(relative_path: str) -> str | None:
    parts = Path(relative_path).parts[:-1]
    for index, part in enumerate(parts):
        if part.lower() in SHARED_CORE_TOKENS:
            return Path(*parts[: index + 1]).as_posix()
    return None


def _text_references_shared_core_areas(text: str | None, shared_core_areas: list[str]) -> bool:
    if text is None or not shared_core_areas:
        return False

    lowered_text = text.casefold()
    variants: set[str] = set()
    for area in shared_core_areas:
        variants.update(_shared_core_reference_variants(area))

    return any(
        variant and (f"{variant}/" in lowered_text or f"{variant}\\" in lowered_text)
        for variant in variants
    )


def _shared_core_reference_variants(area: str) -> set[str]:
    area_lower = area.casefold()
    variants = {area_lower, area_lower.replace("/", "\\")}

    if area_lower.startswith("src/"):
        trimmed = area_lower[4:]
        variants.add(trimmed)
        variants.add(trimmed.replace("/", "\\"))

    parts = area_lower.split("/")
    for index, part in enumerate(parts):
        if part in SHARED_CORE_TOKENS:
            tail = "/".join(parts[index:])
            variants.add(tail)
            variants.add(tail.replace("/", "\\"))
            variants.add(part)
            break

    return variants


def _references_other_module_internals(
    record: FileRecord,
    owner_module_path: str,
    module_candidates: list[ModuleCandidateRecord],
) -> bool:
    return any(
        candidate.path != owner_module_path
        and _text_references_module_internal(record.text, candidate.path)
        for candidate in module_candidates
    )


def _touches_multiple_module_internals(
    record: FileRecord,
    module_candidates: list[ModuleCandidateRecord],
) -> bool:
    owner_module_path = _owning_module_path(record.relative_path, module_candidates)
    touched_modules = {
        candidate.path
        for candidate in module_candidates
        if _text_references_module_internal(record.text, candidate.path)
        and candidate.path != owner_module_path
    }
    return len(touched_modules) >= 2


def _owning_module_path(
    relative_path: str,
    module_candidates: list[ModuleCandidateRecord],
) -> str | None:
    owning_paths = [
        candidate.path
        for candidate in module_candidates
        if _is_under_path(relative_path, candidate.path)
    ]
    if not owning_paths:
        return None
    return max(owning_paths, key=len)


def _candidate_looks_advisory_isolated(candidate: ModuleCandidateRecord) -> bool:
    return (
        bool(candidate.entrypoints)
        and (bool(candidate.registration_paths) or candidate.kind == "edge-function")
        and (bool(candidate.local_test_paths) or bool(candidate.local_validation_paths))
        and not candidate.shared_core_reference_paths
        and not candidate.cross_boundary_internal_reference_paths
        and not _has_migration_marker(candidate.path)
    )


def _build_validation_scope_candidate(
    candidate: ModuleCandidateRecord,
    *,
    repo_has_broad_triggers: bool,
) -> ValidationScopeCandidate:
    reasons: list[str] = []
    if candidate.entrypoints:
        reasons.append(
            "Entrypoints detected: "
            f"{_format_path_examples(candidate.entrypoints)}."
        )
    if candidate.registration_paths:
        reasons.append(
            "Registration or bootstrap references detected from "
            f"{_format_path_examples(candidate.registration_paths)}."
        )
    elif candidate.kind == "edge-function":
        reasons.append(
            "Edge-function-style container layout detected for "
            f"`{candidate.path}`."
        )
    if candidate.local_test_paths or candidate.local_validation_paths:
        local_check_paths = candidate.local_test_paths + candidate.local_validation_paths
        reasons.append(
            "Local checks detected: "
            f"{_format_path_examples(local_check_paths)}."
        )
    if candidate.local_manifest_paths:
        reasons.append(
            "Local manifest or package declaration detected: "
            f"{_format_path_examples(candidate.local_manifest_paths)}."
        )
    if not candidate.shared_core_reference_paths:
        reasons.append(
            "No shared/core references were detected in scanned files under "
            f"`{candidate.path}`."
        )
    if not candidate.cross_boundary_internal_reference_paths:
        reasons.append(
            "No direct cross-boundary internal references were detected in "
            f"scanned files under `{candidate.path}`."
        )

    advisory_notes = [
        "Heuristic only. Manual review recommended before treating this area "
        f"(`{candidate.path}`) as a narrow validation candidate.",
        "No actual changed-file or dependency impact analysis is being performed.",
    ]
    if not candidate.local_manifest_paths:
        advisory_notes.append(
            "No local manifest or module-level script declaration was detected, "
            "so this boundary is still inferred from layout, entrypoints, and local checks."
        )
    if repo_has_broad_triggers:
        advisory_notes.append(
            "Repo-wide broad validation triggers still exist elsewhere, so "
            "this is not evidence that full-repo validation can be skipped."
        )

    return ValidationScopeCandidate(
        path=candidate.path,
        kind=candidate.kind,
        reasons=reasons,
        advisory_notes=advisory_notes,
    )


def _module_kind(candidate_path: str) -> str:
    parent_path = _parent_path(candidate_path)
    parent_name = _dir_name(parent_path)
    if (
        candidate_path.startswith("supabase/functions/")
        or parent_path in EDGE_FUNCTION_CONTAINER_PATHS
    ):
        return "edge-function"
    if parent_name in {"feature", "features"}:
        return "feature"
    if parent_name in {"domain", "domains"}:
        return "domain"
    if parent_name in {"plugin", "plugins"}:
        return "plugin"
    if parent_name in {"service", "services"}:
        return "service-area"
    return "module-area"


def _normalized_module_name(candidate_path: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", _dir_name(candidate_path))
    normalized_tokens = [
        token
        for token in tokens
        if token not in MIGRATION_TOKENS and not re.fullmatch(r"v\d+", token)
    ]
    return "-".join(normalized_tokens) if normalized_tokens else _dir_name(candidate_path)


def _is_eligible_module_directory(candidate_path: str) -> bool:
    candidate_name = _dir_name(candidate_path)
    return candidate_name not in SHARED_DIR_NAMES and candidate_name != "."


def _is_module_entrypoint(record: FileRecord, candidate_path: str) -> bool:
    record_name = Path(record.relative_path).stem.lower()
    candidate_name = _dir_name(candidate_path).replace("-", "_")
    return record_name in MODULE_ENTRYPOINT_STEMS or record_name == candidate_name


def _is_registry_like_record(record: FileRecord) -> bool:
    stem = Path(record.relative_path).stem.lower()
    path_tokens = set(re.findall(r"[a-z0-9]+", record.relative_path.lower()))
    return stem in REGISTRY_STEMS or bool(path_tokens & REGISTRY_STEMS)


def _text_references_module(text: str | None, candidate_path: str) -> bool:
    if text is None:
        return False

    lowered_text = text.casefold()
    module_name = _dir_name(candidate_path).casefold()
    path_variants = {
        candidate_path.casefold(),
        candidate_path.casefold().replace("/", "\\"),
    }
    if candidate_path.startswith("src/"):
        trimmed_path = candidate_path[4:].casefold()
        path_variants.add(trimmed_path)
        path_variants.add(trimmed_path.replace("/", "\\"))

    if any(path_variant and path_variant in lowered_text for path_variant in path_variants):
        return True

    if len(module_name) < 3:
        return False

    return (
        re.search(rf"(?<![a-z0-9]){re.escape(module_name)}(?![a-z0-9])", lowered_text)
        is not None
    )


def _text_references_module_internal(text: str | None, candidate_path: str) -> bool:
    if text is None:
        return False

    lowered_text = text.casefold()
    module_name = _dir_name(candidate_path).casefold()
    if len(module_name) < 3:
        return False

    return any(
        f"{module_name}/{token}" in lowered_text or f"{module_name}\\{token}" in lowered_text
        for token in MODULE_GROUPING_TOKENS
    )


def _is_under_path(relative_path: str, candidate_path: str) -> bool:
    return relative_path == candidate_path or relative_path.startswith(f"{candidate_path}/")


def _parent_path(relative_path: str) -> str:
    parent = Path(relative_path).parent.as_posix()
    return parent if parent else "."


def _dir_name(relative_path: str) -> str:
    return Path(relative_path).name if relative_path != "." else "."


def _dedupe_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _counted_phrase(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _format_path_examples(paths: list[str], *, limit: int = 3) -> str:
    if not paths:
        return "no examples captured"

    unique_paths = list(dict.fromkeys(paths))
    formatted = ", ".join(f"`{path}`" for path in unique_paths[:limit])
    remaining = len(unique_paths) - limit
    if remaining > 0:
        return f"{formatted} (+{remaining} more)"
    return formatted


def _load_config_path_list(
    raw_value: object,
    *,
    field_name: str,
) -> list[str]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"'{field_name}' must be a list of repo-relative path patterns.")

    normalized_paths: list[str] = []
    for item in raw_value:
        if not isinstance(item, str):
            raise ValueError(f"'{field_name}' entries must be strings.")
        normalized_paths.append(_normalize_config_path(item, field_name=field_name))

    return list(dict.fromkeys(normalized_paths))


def _load_mirrored_docs_config(raw_value: object) -> list[ConfiguredMirror]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError("'mirrored_docs' must be a list of {source, publish} tables.")

    mirrors: list[ConfiguredMirror] = []
    for item in raw_value:
        if not isinstance(item, dict):
            raise ValueError("'mirrored_docs' entries must be tables.")

        source = item.get("source")
        publish = item.get("publish")
        if not isinstance(source, str) or not isinstance(publish, str):
            raise ValueError(
                "'mirrored_docs' entries must include string 'source' and 'publish' paths."
            )

        mirrors.append(
            ConfiguredMirror(
                source=_normalize_config_path(source, field_name="mirrored_docs.source"),
                publish=_normalize_config_path(
                    publish,
                    field_name="mirrored_docs.publish",
                ),
            )
        )

    deduped: dict[tuple[str, str], ConfiguredMirror] = {}
    for mirror in mirrors:
        deduped[(mirror.source, mirror.publish)] = mirror
    return list(deduped.values())


def _load_advisory_suppressions_config(
    raw_value: object,
) -> list[ConfiguredSuppression]:
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(
            "'advisory_suppressions' must be a list of {finding, path_pattern, reason} tables."
        )

    suppressions: list[ConfiguredSuppression] = []
    for item in raw_value:
        if not isinstance(item, dict):
            raise ValueError("'advisory_suppressions' entries must be tables.")

        finding = item.get("finding")
        path_pattern = item.get("path_pattern")
        reason = item.get("reason")
        if not isinstance(finding, str) or not isinstance(path_pattern, str):
            raise ValueError(
                "'advisory_suppressions' entries must include string 'finding' "
                "and 'path_pattern' values."
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "'advisory_suppressions' entries must include a non-empty 'reason'."
            )

        suppressions.append(
            ConfiguredSuppression(
                finding=finding.strip(),
                path_pattern=_normalize_config_path(
                    path_pattern,
                    field_name="advisory_suppressions.path_pattern",
                ),
                reason=reason.strip(),
            )
        )

    deduped: dict[tuple[str, str, str], ConfiguredSuppression] = {}
    for suppression in suppressions:
        key = (
            suppression.finding,
            suppression.path_pattern,
            suppression.reason,
        )
        deduped[key] = suppression
    return list(deduped.values())


def _normalize_config_path(value: str, *, field_name: str) -> str:
    normalized = value.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = re.sub(r"/+", "/", normalized).rstrip("/")

    if not normalized or normalized == ".":
        raise ValueError(f"'{field_name}' entries must not be empty.")
    if Path(normalized).is_absolute() or normalized.startswith("/"):
        raise ValueError(f"'{field_name}' entries must be repo-relative paths.")

    return normalized


def _path_matches_any(relative_path: str, patterns: list[str]) -> bool:
    return any(_path_matches_pattern(relative_path, pattern) for pattern in patterns)


def _path_matches_pattern(relative_path: str, pattern: str) -> bool:
    normalized_path = relative_path.replace("\\", "/").casefold()
    normalized_pattern = pattern.replace("\\", "/").casefold()
    return (
        fnmatch.fnmatch(normalized_path, normalized_pattern)
        or normalized_path == normalized_pattern
        or normalized_path.startswith(f"{normalized_pattern}/")
    )


def _apply_advisory_suppressions(
    findings: list[Finding],
    config_summary: RepoConfigSummary,
) -> tuple[list[Finding], list[SuppressedFinding], set[str], set[str]]:
    if not config_summary.advisory_suppressions:
        return findings, [], set(), set()

    active_findings: list[Finding] = []
    suppressed_findings: list[SuppressedFinding] = []
    suppressed_duplicate_paths: set[str] = set()
    suppressed_unclear_paths: set[str] = set()

    for finding in findings:
        matched_suppression = _match_advisory_suppression(
            finding,
            config_summary.advisory_suppressions,
        )
        if matched_suppression is None:
            active_findings.append(finding)
            continue

        suppressed_findings.append(
            SuppressedFinding(
                kind=finding.kind,
                summary=finding.summary,
                reason=(
                    "Configured advisory suppression "
                    f"({matched_suppression.finding} @ "
                    f"`{matched_suppression.path_pattern}`): "
                    f"{matched_suppression.reason}"
                ),
                paths=finding.paths,
            )
        )
        if finding.kind == "duplicate-docs":
            suppressed_duplicate_paths.update(finding.paths)
        if finding.kind == "unclear-authority":
            suppressed_unclear_paths.update(finding.paths)

    return (
        active_findings,
        _dedupe_suppressed_findings(suppressed_findings),
        suppressed_duplicate_paths,
        suppressed_unclear_paths,
    )


def _match_advisory_suppression(
    finding: Finding,
    suppressions: list[ConfiguredSuppression],
) -> ConfiguredSuppression | None:
    for suppression in suppressions:
        if suppression.finding != finding.kind:
            continue
        if not finding.paths:
            continue
        if all(_path_matches_pattern(path, suppression.path_pattern) for path in finding.paths):
            return suppression
    return None


def _find_publish_mirror_counterpart(
    target_path: str,
    candidate_paths: list[str],
    mirrors: list[ConfiguredMirror],
) -> tuple[ConfiguredMirror, str] | None:
    for mirror in mirrors:
        target_tail = _relative_to_base_path(target_path, mirror.publish)
        if target_tail is None:
            continue

        for candidate_path in candidate_paths:
            if _relative_to_base_path(candidate_path, mirror.source) == target_tail:
                return mirror, candidate_path

    return None


def _relative_to_base_path(relative_path: str, base_path: str) -> str | None:
    normalized_path = relative_path.replace("\\", "/")
    normalized_base = base_path.replace("\\", "/")
    if normalized_path == normalized_base:
        return ""
    if normalized_path.startswith(f"{normalized_base}/"):
        return normalized_path[len(normalized_base) + 1 :]
    return None


def _dedupe_suppressed_findings(
    findings: list[SuppressedFinding],
) -> list[SuppressedFinding]:
    deduped: dict[tuple[str, str, str, tuple[str, ...]], SuppressedFinding] = {}
    for finding in findings:
        key = (
            finding.kind,
            finding.summary,
            finding.reason,
            tuple(finding.paths),
        )
        deduped[key] = finding
    return list(deduped.values())


def _is_generated(record: FileRecord) -> bool:
    if record.suffix in GENERATED_EXTENSIONS:
        return True
    parts = set(re.findall(r"[a-z0-9._-]+", record.relative_path.lower()))
    return any(part in GENERATED_DIR_NAMES for part in parts)


def _is_exact_canonical(record: FileRecord) -> bool:
    lowered_path = record.lowered_path
    if lowered_path in CANONICAL_CHAIN_LOWER:
        return True
    return lowered_path == record.name.lower() and record.name.lower() in CANONICAL_ROOT_FILES


def _finding_sort_key(finding: Finding) -> tuple[int, str, str]:
    severity_order = {
        FindingSeverity.HIGH: 0,
        FindingSeverity.MEDIUM: 1,
        FindingSeverity.LOW: 2,
    }
    return severity_order[finding.severity], finding.kind, finding.summary
