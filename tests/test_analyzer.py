from __future__ import annotations

from pathlib import Path

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
