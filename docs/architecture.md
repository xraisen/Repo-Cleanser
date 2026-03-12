# Architecture

## Goal

Repo Cleanser scans a repository, classifies file governance roles, detects risky cleanup signals, and emits one non-destructive report.

## Components

### CLI

`src/repo_cleanser/cli.py` exposes the Typer entrypoint. The `scan` command resolves the target repository, runs analysis, renders the requested format, and optionally writes the report to disk.

### Analyzer

`src/repo_cleanser/analyzer.py` contains the repository scan and heuristic engine.

Main responsibilities:

- walk the repository while pruning obviously generated directories
- read text-like files safely
- classify files into governance categories
- detect duplicate docs, unclear authority, temporary/stale artifacts, partial migration leftovers, and orphan-like candidates
- detect heuristic module-boundary signals such as feature folders,
  entrypoints, registration/registry files, edge-function isolation, and
  possible safe-detach risks
- detect advisory affected-only validation readiness signals such as
  module-local checks, shared/core concentration, and cross-boundary coupling
- synthesize repository risks and recommended actions

### Models

`src/repo_cleanser/models.py` defines the report dataclasses and enums shared by the analyzer and renderers.

### Reporting

`src/repo_cleanser/reporting.py` renders either:

- a readable text report for terminal use
- a JSON document for automation or downstream tooling

The report wording should stay conservative:

- duplicate, stale, unclear-authority, and orphan signals are advisory
- orphan wording must remain "likely orphaned" or equivalent
- recommendations must require manual review before destructive follow-up

## Heuristic Strategy

The tool is intentionally conservative:

- it only reports cleanup risk signals
- it does not delete or rewrite anything
- it favors exact canonical path matches for governance docs
- it treats versioned, copied, final, draft, and scratch-style names as risk indicators rather than proof of safe deletion

Current duplicate detection is heuristic and combines:

- canonical document family matching
- versioned or copied filename signals
- text similarity between markdown-like files

Current stale and temporary detection relies on filename/path markers such as
`old`, `copy`, `backup`, `final`, `draft`, `scratch`, `temp`, and versioned
variants like `v2`.

Current module-boundary analysis is intentionally generic. It looks for
module-like folders, local entrypoints, bootstrap or registry references,
isolated edge-function folders, and legacy-looking module folders that still
appear referenced. It is heuristic only and should never be treated as a
safe-to-remove decision.

Current affected-only validation readiness analysis is also intentionally
generic. It does not compute actual changed files or impact sets. It only
reports whether a repository appears structurally more or less suitable for
smallest-safe affected-scope validation, with shared/core concentration and
cross-boundary coupling treated as first-class blockers. It now also separates
likely broad validation triggers from possible narrow validation candidates,
while keeping those candidate signals heuristic only and explicitly not a
safety score.

## Limitations

- It does not build a semantic dependency graph for arbitrary codebases.
- It does not prove a file is unused.
- Generated directories are pruned from deep scanning to keep runs fast and avoid noisy output.
- Orphan detection is intentionally shallow and based on missing textual references plus suspicious naming signals.
- It does not identify AI authorship; it only flags patterns commonly seen in
  cluttered or over-generated repositories.
