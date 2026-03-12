from __future__ import annotations

import os
from pathlib import Path

import pytest

from repo_cleanser.analyzer import analyze_repository
from repo_cleanser.models import FileCategory


def write_file(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def test_analyzer_reports_modularity_strengths_for_clean_feature_modules(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "README.md", "# Sample Repo\n")
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        "export * from './routes';\n",
    )
    write_file(
        tmp_path / "src" / "features" / "billing" / "routes.ts",
        "export const billingRoutes = [];\n",
    )
    write_file(
        tmp_path / "src" / "features" / "billing" / "billing.test.ts",
        "import { billingRoutes } from './routes';\n",
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "index.ts",
        "export * from './services';\n",
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "services.ts",
        "export const orderServices = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "orders.test.ts",
        "import { orderServices } from './services';\n",
    )
    write_file(
        tmp_path / "src" / "app" / "router.ts",
        "import * as billing from '../features/billing';\n"
        "import * as orders from '../features/orders';\n",
    )

    report = analyze_repository(tmp_path)

    assert report.module_boundary.candidate_modules
    assert report.module_boundary.strengths
    assert not report.module_boundary.modularity_risks
    assert not report.module_boundary.safe_detach_risks
    assert report.validation_readiness.readiness_strengths
    assert report.validation_readiness.advisory_isolated_modules
    assert report.validation_readiness.narrow_validation_candidates
    assert not report.validation_readiness.broad_validation_triggers
    assert not report.validation_readiness.shared_core_coupling_risks
    assert not report.validation_readiness.validation_blockers
    billing_candidate = next(
        candidate
        for candidate in report.validation_readiness.narrow_validation_candidates
        if candidate.path == "src/features/billing"
    )
    assert any("index.ts" in reason for reason in billing_candidate.reasons)
    assert any("router.ts" in reason for reason in billing_candidate.reasons)
    assert any("billing.test.ts" in reason for reason in billing_candidate.reasons)
    assert all(
        candidate.advisory_notes
        for candidate in report.validation_readiness.narrow_validation_candidates
    )
    assert not any(
        finding.kind
        in {
            "module-boundary",
            "safe-detach-risk",
            "shared-core-coupling",
            "validation-readiness",
        }
        for finding in report.findings
    )


def test_analyzer_detects_duplicate_docs_and_partial_migration(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Sample Repo\n")
    write_file(tmp_path / "AGENTS.md", "Follow the repo rules.\n")
    write_file(
        tmp_path / "docs" / "architecture.md",
        "Canonical architecture for the sample repo.\n",
    )
    write_file(
        tmp_path / "docs" / "architecture-v2.md",
        "Canonical architecture for the sample repo.\nWith one extra line.\n",
    )
    write_file(tmp_path / "src" / "main.py", "print('ok')\n")

    report = analyze_repository(tmp_path)
    categories = {assessment.path: assessment.category for assessment in report.assessments}
    finding_kinds = {finding.kind for finding in report.findings}

    assert categories["README.md"] is FileCategory.CANONICAL
    assert categories["docs/architecture-v2.md"] is FileCategory.DUPLICATE
    assert "duplicate-docs" in finding_kinds
    assert "partial-migration" in finding_kinds


def test_analyzer_reports_scattered_module_internals_as_boundary_risk(tmp_path: Path) -> None:
    write_file(
        tmp_path / "src" / "features" / "billing" / "services.ts",
        "export const billingService = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "controllers.ts",
        "export const orderController = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "inventory" / "api.ts",
        "export const inventoryApi = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "users" / "handlers.ts",
        "export const userHandler = {};\n",
    )
    write_file(
        tmp_path / "src" / "main.ts",
        "import { billingService } from './features/billing/services';\n"
        "import { orderController } from './features/orders/controllers';\n"
        "import { inventoryApi } from './features/inventory/api';\n"
        "import { userHandler } from './features/users/handlers';\n",
    )

    report = analyze_repository(tmp_path)

    assert report.module_boundary.modularity_risks
    assert any(finding.kind == "module-boundary" for finding in report.findings)


def test_feature_folders_do_not_override_shared_core_readiness_blockers(tmp_path: Path) -> None:
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        "export * from '../../shared/contracts/billing';\n",
    )
    write_file(
        tmp_path / "src" / "features" / "billing" / "billing.test.ts",
        "import { billingContract } from '../../shared/contracts/billing';\n",
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "index.ts",
        "export * from '../../shared/contracts/orders';\n",
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "orders.test.ts",
        "import { orderContract } from '../../shared/contracts/orders';\n",
    )
    write_file(
        tmp_path / "src" / "shared" / "contracts" / "billing.ts",
        "export const billingContract = {};\n",
    )
    write_file(
        tmp_path / "src" / "shared" / "contracts" / "orders.ts",
        "export const orderContract = {};\n",
    )
    write_file(
        tmp_path / "src" / "app" / "router.ts",
        "import * as billing from '../features/billing';\n"
        "import * as orders from '../features/orders';\n",
    )

    report = analyze_repository(tmp_path)

    assert report.module_boundary.strengths
    assert report.validation_readiness.broad_validation_triggers
    assert not report.validation_readiness.narrow_validation_candidates
    assert report.validation_readiness.shared_core_coupling_risks
    assert report.validation_readiness.validation_blockers
    assert any(
        "shared/core" in trigger or "contract-style" in trigger
        for trigger in report.validation_readiness.broad_validation_triggers
    )
    assert any(
        "src/shared" in risk
        for risk in report.validation_readiness.shared_core_coupling_risks
    )
    assert any(
        finding.kind == "shared-core-coupling" for finding in report.findings
    )


def test_analyzer_reports_unregistered_module_like_folder(tmp_path: Path) -> None:
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        "export const billing = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "reports" / "index.ts",
        "export const reports = {};\n",
    )
    write_file(
        tmp_path / "src" / "app" / "router.ts",
        "import * as billing from '../features/billing';\n",
    )

    report = analyze_repository(tmp_path)

    assert any("reports" in risk for risk in report.module_boundary.modularity_risks)
    assert any(finding.kind == "module-boundary" for finding in report.findings)


def test_analyzer_reports_cross_boundary_and_shared_contract_pressure_as_readiness_blocker(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        "export const billing = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "index.ts",
        "export const orders = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "inventory" / "index.ts",
        "export const inventory = {};\n",
    )
    write_file(
        tmp_path / "src" / "shared" / "types" / "contracts.ts",
        "export type SharedContract = { id: string };\n",
    )
    write_file(
        tmp_path / "src" / "main.ts",
        "import './features/billing/services';\n"
        "import './features/orders/controllers';\n"
        "import './features/inventory/api';\n"
        "import { SharedContract } from './shared/types/contracts';\n",
    )
    write_file(
        tmp_path / "src" / "features" / "billing" / "services.ts",
        "import { SharedContract } from '../../shared/types/contracts';\n"
        "import '../../features/orders/controllers';\n",
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "controllers.ts",
        "import { SharedContract } from '../../shared/types/contracts';\n",
    )
    write_file(
        tmp_path / "src" / "features" / "inventory" / "api.ts",
        "import { SharedContract } from '../../shared/types/contracts';\n",
    )

    report = analyze_repository(tmp_path)

    assert report.validation_readiness.shared_core_coupling_risks
    assert report.validation_readiness.validation_blockers
    assert report.validation_readiness.broad_validation_triggers
    assert not report.validation_readiness.narrow_validation_candidates
    assert any(
        "contract-style" in trigger or "module internals" in trigger
        for trigger in report.validation_readiness.broad_validation_triggers
    )
    assert any(
        "src/main.ts" in blocker
        for blocker in report.validation_readiness.validation_blockers
    )
    assert any(
        finding.kind == "validation-readiness" for finding in report.findings
    )
    assert any(
        finding.kind == "shared-core-coupling" for finding in report.findings
    )


def test_analyzer_reports_half_detached_module_as_safe_detach_risk(tmp_path: Path) -> None:
    write_file(
        tmp_path / "src" / "features" / "payments-old" / "index.ts",
        "export const paymentsOld = {};\n",
    )
    write_file(
        tmp_path / "src" / "app" / "router.ts",
        "import * as paymentsOld from '../features/payments-old';\n",
    )

    report = analyze_repository(tmp_path)

    assert report.module_boundary.safe_detach_risks
    assert any(finding.kind == "safe-detach-risk" for finding in report.findings)


def test_analyzer_reports_edge_function_isolation_as_strength(tmp_path: Path) -> None:
    write_file(
        tmp_path / "supabase" / "functions" / "send-email" / "index.ts",
        "export const handler = async () => null;\n",
    )
    write_file(
        tmp_path / "supabase" / "functions" / "sync-users" / "index.ts",
        "export const handler = async () => null;\n",
    )
    write_file(
        tmp_path / "supabase" / "functions" / "_shared" / "client.ts",
        "export const client = {};\n",
    )

    report = analyze_repository(tmp_path)

    assert any(
        candidate.kind == "edge-function"
        for candidate in report.module_boundary.candidate_modules
    )
    assert any("edge-function" in strength for strength in report.module_boundary.strengths)
    assert not report.module_boundary.safe_detach_risks


def test_edge_functions_with_shared_core_dependencies_reduce_readiness(tmp_path: Path) -> None:
    write_file(
        tmp_path / "supabase" / "functions" / "send-email" / "index.ts",
        "import { client } from '../_shared/client';\n",
    )
    write_file(
        tmp_path / "supabase" / "functions" / "sync-users" / "index.ts",
        "import { client } from '../_shared/client';\n",
    )
    write_file(
        tmp_path / "supabase" / "functions" / "_shared" / "client.ts",
        "export const client = {};\n",
    )

    report = analyze_repository(tmp_path)

    assert report.validation_readiness.shared_core_coupling_risks
    assert report.validation_readiness.validation_blockers
    assert report.validation_readiness.broad_validation_triggers
    assert any(
        "edge-function" in blocker
        for blocker in report.validation_readiness.validation_blockers
    )
    assert any(
        "edge-function" in trigger or "service-style" in trigger
        for trigger in report.validation_readiness.broad_validation_triggers
    )


def test_analyzer_marks_suspicious_files_as_temporary_and_orphaned(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Sample Repo\n")
    write_file(tmp_path / "docs" / "validation.md", "Run pytest.\n")
    write_file(tmp_path / "scratch-notes.md", "Temporary cleanup notes.\n")

    report = analyze_repository(tmp_path)
    categories = {assessment.path: assessment.category for assessment in report.assessments}

    assert categories["scratch-notes.md"] is FileCategory.TEMPORARY
    assert any(finding.kind == "orphaned-artifacts" for finding in report.findings)


def test_analyzer_applies_repo_config_for_ignores_mirrors_generated_paths_and_suppressions(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "repo-cleanser.toml",
        'ignored_paths = ["notes"]\n'
        'generated_paths = ["coverage"]\n\n'
        "[[mirrored_docs]]\n"
        'source = "documentation"\n'
        'publish = "public/docs"\n\n'
        "[[advisory_suppressions]]\n"
        'finding = "unclear-authority"\n'
        'path_pattern = "documentation/*"\n'
        'reason = "Known non-canonical source-doc location."\n',
    )
    write_file(tmp_path / "README.md", "# Sample Repo\n")
    write_file(
        tmp_path / "documentation" / "architecture.md",
        "Canonical architecture content.\n",
    )
    write_file(
        tmp_path / "public" / "docs" / "architecture.md",
        "Canonical architecture content.\n",
    )
    write_file(tmp_path / "scratch-notes.md", "Temporary cleanup notes.\n")
    write_file(tmp_path / "notes" / "draft.md", "Ignore this folder.\n")
    write_file(tmp_path / "coverage" / "summary.json", '{"ok": true}\n')

    report = analyze_repository(tmp_path)
    assessed_paths = {assessment.path for assessment in report.assessments}

    assert report.config_summary.path == "repo-cleanser.toml"
    assert report.config_summary.ignored_paths == ["notes"]
    assert report.config_summary.generated_paths == ["coverage"]
    assert report.skipped_directories == ["coverage", "notes"]
    assert "notes/draft.md" not in assessed_paths
    assert "coverage/summary.json" not in assessed_paths
    assert not any(finding.kind == "duplicate-docs" for finding in report.findings)
    assert not any(finding.kind == "unclear-authority" for finding in report.findings)
    assert any(
        finding.kind == "duplicate-docs"
        and "Configured mirrored docs" in finding.reason
        for finding in report.suppressed_findings
    )
    assert any(
        finding.kind == "unclear-authority"
        and "public/docs/architecture.md" in ",".join(finding.paths)
        for finding in report.suppressed_findings
    )
    assert any(
        finding.kind == "unclear-authority"
        and "Known non-canonical source-doc location." in finding.reason
        for finding in report.suppressed_findings
    )


def test_advisory_suppression_does_not_hide_grouped_finding_with_unmatched_paths(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[advisory_suppressions]]\n"
        'finding = "duplicate-docs"\n'
        'path_pattern = "public/docs/*"\n'
        'reason = "Publish mirror path only."\n',
    )
    write_file(tmp_path / "docs" / "architecture.md", "Same content.\n")
    write_file(tmp_path / "public" / "docs" / "architecture.md", "Same content.\n")
    write_file(tmp_path / "notes" / "architecture-copy.md", "Same content.\n")

    report = analyze_repository(tmp_path)

    duplicate_findings = [
        finding for finding in report.findings if finding.kind == "duplicate-docs"
    ]

    assert duplicate_findings
    assert any("notes/architecture-copy.md" in finding.paths for finding in duplicate_findings)
    assert not any(
        finding.kind == "duplicate-docs"
        and "Publish mirror path only." in finding.reason
        for finding in report.suppressed_findings
    )


def test_advisory_suppression_can_target_single_subject_finding_with_context_paths(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[advisory_suppressions]]\n"
        'finding = "safe-detach-risk"\n'
        'path_pattern = "src/features/payments-old"\n'
        'reason = "Known legacy area under manual review."\n',
    )
    write_file(
        tmp_path / "src" / "features" / "payments-old" / "index.ts",
        "export const paymentsOld = {};\n",
    )
    write_file(
        tmp_path / "src" / "app" / "router.ts",
        "import * as paymentsOld from '../features/payments-old';\n",
    )

    report = analyze_repository(tmp_path)

    assert not any(finding.kind == "safe-detach-risk" for finding in report.findings)
    assert any(
        finding.kind == "safe-detach-risk"
        and "Known legacy area under manual review." in finding.reason
        and "src/features/payments-old" in finding.paths
        and "repo-cleanser.toml" not in finding.paths
        for finding in report.suppressed_findings
    )


def test_single_star_suppression_pattern_does_not_cross_directory_boundaries(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[advisory_suppressions]]\n"
        'finding = "orphaned-artifacts"\n'
        'path_pattern = "notes/*.md"\n'
        'reason = "Suppress direct child notes only."\n',
    )
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / "notes" / "scratch.md", "Temporary cleanup notes.\n")
    write_file(
        tmp_path / "notes" / "nested" / "scratch.md",
        "Temporary cleanup notes.\n",
    )

    report = analyze_repository(tmp_path)

    assert any(
        finding.kind == "orphaned-artifacts" and "notes/nested/scratch.md" in finding.paths
        for finding in report.findings
    )
    assert not any(
        finding.kind == "orphaned-artifacts" and "notes/scratch.md" in finding.paths
        for finding in report.findings
    )
    assert any(
        finding.kind == "orphaned-artifacts"
        and "notes/scratch.md" in finding.paths
        and "Suppress direct child notes only." in finding.reason
        for finding in report.suppressed_findings
    )


def test_double_star_suppression_pattern_can_match_nested_paths(tmp_path: Path) -> None:
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[advisory_suppressions]]\n"
        'finding = "orphaned-artifacts"\n'
        'path_pattern = "notes/**/*.md"\n'
        'reason = "Suppress nested notes recursively."\n',
    )
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / "notes" / "scratch.md", "Temporary cleanup notes.\n")
    write_file(
        tmp_path / "notes" / "nested" / "scratch.md",
        "Temporary cleanup notes.\n",
    )
    write_file(
        tmp_path / "notes" / "nested" / "deeper" / "scratch.md",
        "Temporary cleanup notes.\n",
    )

    report = analyze_repository(tmp_path)

    assert not any(finding.kind == "orphaned-artifacts" for finding in report.findings)
    assert any(
        finding.kind == "orphaned-artifacts"
        and "notes/scratch.md" in finding.paths
        and "Suppress nested notes recursively." in finding.reason
        for finding in report.suppressed_findings
    )
    assert any(
        finding.kind == "orphaned-artifacts"
        and "notes/nested/scratch.md" in finding.paths
        and "Suppress nested notes recursively." in finding.reason
        for finding in report.suppressed_findings
    )
    assert any(
        finding.kind == "orphaned-artifacts"
        and "notes/nested/deeper/scratch.md" in finding.paths
        and "Suppress nested notes recursively." in finding.reason
        for finding in report.suppressed_findings
    )


def test_question_mark_suppression_pattern_matches_single_path_character(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[advisory_suppressions]]\n"
        'finding = "orphaned-artifacts"\n'
        'path_pattern = "notes/scratch-?.md"\n'
        'reason = "Suppress one-character note variants."\n',
    )
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / "notes" / "scratch-a.md", "Temporary cleanup notes.\n")
    write_file(tmp_path / "notes" / "scratch-ab.md", "Temporary cleanup notes.\n")

    report = analyze_repository(tmp_path)

    assert any(
        finding.kind == "orphaned-artifacts" and "notes/scratch-ab.md" in finding.paths
        for finding in report.findings
    )
    assert any(
        finding.kind == "orphaned-artifacts"
        and "notes/scratch-a.md" in finding.paths
        and "Suppress one-character note variants." in finding.reason
        for finding in report.suppressed_findings
    )


def test_character_class_suppression_pattern_matches_single_segment_character(
    tmp_path: Path,
) -> None:
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[advisory_suppressions]]\n"
        'finding = "orphaned-artifacts"\n'
        'path_pattern = "notes/scratch-[ab].md"\n'
        'reason = "Suppress selected note variants."\n',
    )
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / "notes" / "scratch-a.md", "Temporary cleanup notes.\n")
    write_file(tmp_path / "notes" / "scratch-c.md", "Temporary cleanup notes.\n")

    report = analyze_repository(tmp_path)

    assert any(
        finding.kind == "orphaned-artifacts" and "notes/scratch-c.md" in finding.paths
        for finding in report.findings
    )
    assert any(
        finding.kind == "orphaned-artifacts"
        and "notes/scratch-a.md" in finding.paths
        and "Suppress selected note variants." in finding.reason
        for finding in report.suppressed_findings
    )


def test_documentation_mentions_do_not_create_safe_detach_risk(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "src" / "features" / "payments-old" / "index.ts",
        "export const paymentsOld = {};\n",
    )
    write_file(
        tmp_path / "docs" / "architecture.md",
        "Legacy note: src/features/payments-old still exists.\n",
    )

    report = analyze_repository(tmp_path)

    assert not any(finding.kind == "safe-detach-risk" for finding in report.findings)


def test_documentation_mentions_do_not_create_cross_boundary_validation_blocker(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        "export const billing = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "index.ts",
        "export const orders = {};\n",
    )
    write_file(
        tmp_path / "docs" / "architecture.md",
        "Uses billing/services and orders/controllers internally.\n",
    )

    report = analyze_repository(tmp_path)

    assert not any(
        finding.kind == "validation-readiness"
        and "docs/architecture.md" in finding.paths
        for finding in report.findings
    )
    assert not any(
        "docs/architecture.md" in blocker
        for blocker in report.validation_readiness.validation_blockers
    )
    assert not any(
        "docs/architecture.md" in trigger
        for trigger in report.validation_readiness.broad_validation_triggers
    )


def test_repo_config_accepts_utf8_bom(tmp_path: Path) -> None:
    (tmp_path / "repo-cleanser.toml").write_bytes(
        '\ufeffignored_paths = ["dist"]\n'.encode()
    )
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / "dist" / "ignored.txt", "generated\n")

    report = analyze_repository(tmp_path)

    assert report.config_summary.ignored_paths == ["dist"]
    assert "dist" in report.skipped_directories


def test_gitignore_mentions_do_not_count_as_structural_references(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / ".gitignore", "src/features/payments-old/\n")
    write_file(
        tmp_path / "src" / "features" / "payments-old" / "index.ts",
        "export const paymentsOld = {};\n",
    )

    report = analyze_repository(tmp_path)

    assert not any(finding.kind == "safe-detach-risk" for finding in report.findings)


def test_comment_only_module_mentions_do_not_create_safe_detach_risk(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "src" / "features" / "payments-old" / "index.ts",
        "export const paymentsOld = {};\n",
    )
    write_file(
        tmp_path / "src" / "app" / "router.ts",
        "// TODO remove src/features/payments-old later\nexport const router = {};\n",
    )

    report = analyze_repository(tmp_path)

    assert not any(finding.kind == "safe-detach-risk" for finding in report.findings)


def test_comment_only_internal_mentions_do_not_create_validation_blocker(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        "export const billing = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "index.ts",
        "export const orders = {};\n",
    )
    write_file(
        tmp_path / "src" / "main.ts",
        "// billing/services and orders/controllers are legacy\nexport const main = {};\n",
    )

    report = analyze_repository(tmp_path)

    assert not any(
        finding.kind == "validation-readiness" and "src/main.ts" in finding.paths
        for finding in report.findings
    )
    assert not any(
        "src/main.ts" in blocker for blocker in report.validation_readiness.validation_blockers
    )
    assert not any(
        "src/main.ts" in trigger
        for trigger in report.validation_readiness.broad_validation_triggers
    )


def test_gitignore_entries_do_not_prevent_orphan_detection(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / ".gitignore", "scratch-notes.md\n")
    write_file(tmp_path / "scratch-notes.md", "Temporary cleanup notes.\n")

    report = analyze_repository(tmp_path)

    assert any(finding.kind == "orphaned-artifacts" for finding in report.findings)


def test_near_match_filename_does_not_hide_orphan_candidate(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / "scratch-app.md", "Temporary cleanup notes.\n")
    write_file(
        tmp_path / "docs" / "validation.md",
        "See my-scratch-app.md before cleanup.\n",
    )

    report = analyze_repository(tmp_path)

    assert any(
        finding.kind == "orphaned-artifacts" and "scratch-app.md" in finding.paths
        for finding in report.findings
    )


def test_exact_filename_reference_still_prevents_orphan_candidate(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(tmp_path / "scratch-app.md", "Temporary cleanup notes.\n")
    write_file(
        tmp_path / "docs" / "validation.md",
        "See ./scratch-app.md before cleanup.\n",
    )

    report = analyze_repository(tmp_path)

    assert not any(
        finding.kind == "orphaned-artifacts" and "scratch-app.md" in finding.paths
        for finding in report.findings
    )


def test_repo_config_rejects_parent_traversal_patterns(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "repo-cleanser.toml",
        'ignored_paths = ["../outside"]\n',
    )

    try:
        analyze_repository(tmp_path)
    except ValueError as exc:
        assert "must stay inside the repository path space" in str(exc)
    else:
        raise AssertionError("Expected parent-traversal config path to be rejected.")


def test_repo_config_rejects_drive_relative_patterns(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "repo-cleanser.toml",
        'ignored_paths = ["C:tmp"]\n',
    )

    try:
        analyze_repository(tmp_path)
    except ValueError as exc:
        assert "repo-relative paths" in str(exc)
    else:
        raise AssertionError("Expected drive-relative config path to be rejected.")


def test_analyzer_skips_symlinked_files_to_stay_inside_repo_boundary(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    outside_file = tmp_path.parent / "outside-secret.md"
    outside_file.write_text("outside data\n", encoding="utf-8")
    symlink_path = tmp_path / "linked-secret.md"

    try:
        os.symlink(outside_file, symlink_path)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable in test environment: {exc}")

    report = analyze_repository(tmp_path)

    assert "linked-secret.md" not in {assessment.path for assessment in report.assessments}
    assert "linked-secret.md" in report.skipped_directories


def test_repo_config_rejects_symlinked_root_config(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    external_config = tmp_path.parent / "outside-config.toml"
    external_config.write_text('ignored_paths = ["docs"]\n', encoding="utf-8")
    config_link = tmp_path / "repo-cleanser.toml"

    try:
        os.symlink(external_config, config_link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable in test environment: {exc}")

    with pytest.raises(ValueError, match="must be a regular file at the repository root"):
        analyze_repository(tmp_path)


def test_repo_config_rejects_broken_symlinked_root_config(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    config_link = tmp_path / "repo-cleanser.toml"

    try:
        os.symlink(tmp_path.parent / "missing-config.toml", config_link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable in test environment: {exc}")

    with pytest.raises(ValueError, match="must be a regular file at the repository root"):
        analyze_repository(tmp_path)


def test_analyzer_skips_symlinked_directories_to_stay_inside_repo_boundary(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    outside_dir = tmp_path.parent / "outside-linked-dir"
    outside_dir.mkdir(exist_ok=True)
    write_file(outside_dir / "secret.md", "outside data\n")
    symlink_dir = tmp_path / "linked-dir"

    try:
        os.symlink(outside_dir, symlink_dir, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable in test environment: {exc}")

    report = analyze_repository(tmp_path)

    assert "linked-dir" in report.skipped_directories
    assert not any(assessment.path.startswith("linked-dir/") for assessment in report.assessments)


def test_analyzer_records_unreadable_walk_paths_in_skipped_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")

    def fake_walk(root: Path, onerror=None):  # type: ignore[no-untyped-def]
        if onerror is not None:
            error = OSError("Access denied")
            error.filename = str(Path(root) / "blocked-dir")
            onerror(error)
        yield str(root), [], ["README.md"]

    monkeypatch.setattr("repo_cleanser.analyzer.os.walk", fake_walk)

    report = analyze_repository(tmp_path)

    assert "blocked-dir" in report.skipped_directories


def test_analyzer_records_stat_failures_in_skipped_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    blocked_file = tmp_path / "blocked.md"
    write_file(blocked_file, "blocked\n")
    original_stat = Path.stat

    def fake_stat(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self == blocked_file:
            raise OSError("Access denied")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)

    report = analyze_repository(tmp_path)

    assert "blocked.md" in report.skipped_directories
    assert "blocked.md" not in {assessment.path for assessment in report.assessments}


def test_plain_variable_name_does_not_count_as_module_registration(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        "export const feature = {};\n",
    )
    write_file(
        tmp_path / "src" / "app" / "router.ts",
        "const billing = true;\nexport const router = billing;\n",
    )

    report = analyze_repository(tmp_path)

    assert not report.module_boundary.candidate_modules[0].registration_paths
    assert any(finding.kind == "module-boundary" for finding in report.findings)


def test_repo_config_rejects_blank_suppression_finding(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[advisory_suppressions]]\n"
        'finding = "   "\n'
        'path_pattern = "scratch-notes.md"\n'
        'reason = "Intentional local scratch note."\n',
    )

    try:
        analyze_repository(tmp_path)
    except ValueError as exc:
        assert "non-empty 'finding'" in str(exc)
    else:
        raise AssertionError("Expected blank suppression finding to be rejected.")


def test_repo_config_rejects_unknown_suppression_finding(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[advisory_suppressions]]\n"
        'finding = "duplicate_docs"\n'
        'path_pattern = "scratch-notes.md"\n'
        'reason = "Intentional local scratch note."\n',
    )

    try:
        analyze_repository(tmp_path)
    except ValueError as exc:
        assert "supported finding id" in str(exc)
    else:
        raise AssertionError("Expected unknown suppression finding to be rejected.")


def test_repo_config_rejects_duplicate_suppression_target_with_different_reason(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[advisory_suppressions]]\n"
        'finding = "orphaned-artifacts"\n'
        'path_pattern = "scratch-notes.md"\n'
        'reason = "Intentional scratch note."\n\n'
        "[[advisory_suppressions]]\n"
        'finding = "orphaned-artifacts"\n'
        'path_pattern = "scratch-notes.md"\n'
        'reason = "Conflicting explanation."\n',
    )

    try:
        analyze_repository(tmp_path)
    except ValueError as exc:
        assert "different reasons" in str(exc)
    else:
        raise AssertionError("Expected duplicate suppression target to be rejected.")


def test_repo_config_rejects_overlapping_mirror_paths(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[mirrored_docs]]\n"
        'source = "documentation"\n'
        'publish = "documentation/public"\n',
    )

    try:
        analyze_repository(tmp_path)
    except ValueError as exc:
        assert "distinct non-overlapping" in str(exc)
    else:
        raise AssertionError("Expected overlapping mirrored-doc roots to be rejected.")


def test_repo_config_rejects_mirror_path_overlap_across_entries(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "repo-cleanser.toml",
        "[[mirrored_docs]]\n"
        'source = "documentation"\n'
        'publish = "public/docs"\n\n'
        "[[mirrored_docs]]\n"
        'source = "documentation/api"\n'
        'publish = "public/api"\n',
    )

    try:
        analyze_repository(tmp_path)
    except ValueError as exc:
        assert "distinct non-overlapping" in str(exc)
    else:
        raise AssertionError("Expected overlapping mirrored-doc entries to be rejected.")


def test_string_literal_path_does_not_create_safe_detach_risk(tmp_path: Path) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "src" / "features" / "payments-old" / "index.ts",
        "export const paymentsOld = {};\n",
    )
    write_file(
        tmp_path / "src" / "app" / "router.ts",
        'const msg = "src/features/payments-old is legacy";\nexport const router = msg;\n',
    )

    report = analyze_repository(tmp_path)

    assert not any(finding.kind == "safe-detach-risk" for finding in report.findings)


def test_string_literal_internal_paths_do_not_create_validation_blocker(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        "export const billing = {};\n",
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "index.ts",
        "export const orders = {};\n",
    )
    write_file(
        tmp_path / "src" / "main.ts",
        'const msg = "billing/services and orders/controllers are legacy";\n'
        "export const main = msg;\n",
    )

    report = analyze_repository(tmp_path)

    assert not any(
        finding.kind == "validation-readiness" and "src/main.ts" in finding.paths
        for finding in report.findings
    )
    assert not any(
        "src/main.ts" in blocker for blocker in report.validation_readiness.validation_blockers
    )
    assert not any(
        "src/main.ts" in trigger
        for trigger in report.validation_readiness.broad_validation_triggers
    )


def test_string_literal_shared_core_paths_do_not_count_as_dependency_pressure(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        'const msg = "shared/contracts/billing is legacy";\nexport const x = msg;\n',
    )
    write_file(
        tmp_path / "src" / "features" / "orders" / "index.ts",
        'const msg = "shared/contracts/orders is legacy";\nexport const x = msg;\n',
    )
    write_file(
        tmp_path / "src" / "shared" / "contracts" / "billing.ts",
        "export const billingContract = {};\n",
    )
    write_file(
        tmp_path / "src" / "shared" / "contracts" / "orders.ts",
        "export const orderContract = {};\n",
    )

    report = analyze_repository(tmp_path)

    assert not any(
        "appear to reference shared/core code directly" in risk
        for risk in report.validation_readiness.shared_core_coupling_risks
    )
    assert not any(
        finding.kind == "shared-core-coupling"
        and "src/features/billing" in finding.paths
        for finding in report.findings
    )


def test_string_literal_import_text_does_not_count_as_module_registration(
    tmp_path: Path,
) -> None:
    write_file(tmp_path / "README.md", "# Repo\n")
    write_file(
        tmp_path / "src" / "features" / "billing" / "index.ts",
        "export const feature = {};\n",
    )
    write_file(
        tmp_path / "src" / "main.ts",
        'const msg = \'import "billing"\';\nexport const main = msg;\n',
    )

    report = analyze_repository(tmp_path)

    assert not report.module_boundary.candidate_modules[0].registration_paths
