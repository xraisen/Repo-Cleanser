# Architecture

## Goal

Repo Cleanser scans a repository, classifies governance and cleanup-risk
signals, and emits one non-destructive report that is cautious enough to trust
and practical enough to act on.

## Runtime Flow

At a high level, the current flow is:

1. resolve the target repository
2. load one explicit root `repo-cleanser.toml` file when present
3. walk the repository while pruning ignored, generated, symlinked, or unreadable areas
4. analyze governance drift, cleanup-risk signals, and architecture heuristics
5. apply transparent advisory suppressions
6. render one text or JSON report

## Components

### CLI

`src/repo_cleanser/cli.py` exposes the Typer entrypoint. The `scan` command
resolves the target repository, runs analysis, renders the requested format,
and optionally writes the report to disk.

### Analyzer

`src/repo_cleanser/analyzer.py` is the heuristic core.

Main responsibilities:

- walk the repository while pruning obviously generated or explicitly ignored
  directories
- skip symlinked files and directories so scanning stays inside the target
  repository boundary
- surface unreadable files or directories through the skipped-path report area
  instead of silently acting as if the scan was complete
- load and validate one root `repo-cleanser.toml` file when present
- read text-like files safely
- classify files into governance categories
- detect duplicate docs, unclear authority, temporary/stale artifacts, partial
  migration leftovers, and orphan-like candidates
- detect heuristic module-boundary signals such as feature folders,
  entrypoints, registration/registry files, edge-function isolation, and
  possible safe-detach risks
- detect advisory affected-only validation readiness signals such as
  module-local checks, shared/core concentration, and cross-boundary coupling
- keep config-driven noise reductions traceable through suppressed-finding
  reporting
- synthesize repository risks and recommended actions

### Models

`src/repo_cleanser/models.py` defines the report dataclasses and enums shared by
the analyzer and renderers, including config summary and suppressed-finding
traceability.

### Reporting

`src/repo_cleanser/reporting.py` renders either:

- a readable text report for terminal use
- a JSON document for automation or downstream tooling

The wording contract stays conservative:

- duplicate, stale, unclear-authority, and orphan signals are advisory
- orphan wording must remain `likely orphaned` or equivalent
- suppressions must remain visible and attributable
- recommendations must require manual review before destructive follow-up
- text output must escape unsafe control and formatting characters

The CLI also enforces a non-destructive output contract: reports cannot
overwrite existing files and cannot be written inside the scanned repository.

## Heuristic Strategy

Repo Cleanser is intentionally conservative:

- it reports cleanup and architecture risk signals instead of claiming certainty
- it does not delete or rewrite anything
- it favors exact canonical path matches for governance docs
- it treats versioned, copied, final, draft, and scratch-style names as risk
  indicators rather than proof of safe deletion

Current duplicate detection combines:

- canonical document family matching
- versioned or copied filename signals
- text similarity between markdown-like files
- explicit mirror declarations from `repo-cleanser.toml` when present

Current stale and temporary detection relies on filename and path markers such
as `old`, `copy`, `backup`, `final`, `draft`, `scratch`, `temp`, and versioned
variants like `v2`.

Current config handling is explicit and root-scoped. `repo-cleanser.toml` can
declare:

- ignored paths
- generated paths
- known mirrored docs
- advisory suppressions by finding type and path pattern

Those settings can reduce expected noise, but they do not silently turn risky
areas into `safe` ones. Suppressed findings remain visible in the report.
Config path patterns must stay inside the repository path space. Mirrored-doc
source and publish roots must be distinct non-overlapping paths, and advisory
suppression kinds must be explicit non-empty strings.

Current module-boundary analysis is intentionally generic. It looks for
module-like folders, local entrypoints, bootstrap or registry references,
isolated edge-function folders, and legacy-looking module folders that still
appear referenced. It is heuristic only and should never be treated as a
safe-to-remove decision.

Current affected-only validation readiness analysis is also intentionally
generic. It does not compute actual changed files or impact sets. It only
reports whether a repository appears structurally more or less suitable for
smallest-safe affected-scope validation, with shared/core concentration and
cross-boundary coupling treated as first-class blockers. It separates likely
broad validation triggers from possible narrow validation candidates while
explicitly avoiding a readiness score.

Reference heuristics are intentionally narrower than a raw text grep. They
exclude `repo-cleanser.toml`, `.gitignore`, markdown docs, comment-only text,
and plain string literals from dependency-like registration or coupling
signals. The analyzer tries to treat import-like dependency contexts as
stronger evidence than incidental mentions.

## Limitations

- It does not build a semantic dependency graph for arbitrary codebases.
- It does not prove a file is unused.
- It does not claim that a module is safe to validate alone.
- Generated or ignored paths can reduce scan noise, but they are still a
  configuration choice, not a safety proof.
- Orphan detection is intentionally shallow and based on missing textual
  references plus suspicious naming signals.
- It does not identify AI authorship; it only flags patterns commonly seen in
  cluttered or over-generated repositories.
