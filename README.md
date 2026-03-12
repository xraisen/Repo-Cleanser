# Repo Cleanser

> A conservative CLI for cleaning up repository noise without pretending it can
> clean up your repo for you.

Repo Cleanser scans a local repository and produces one readable, non-destructive
report about governance drift, risky cleanup targets, module-boundary quality,
and advisory validation-readiness signals. It is built for long-lived repos
where stale docs, half-finished migrations, mirrored files, and AI-generated
clutter accumulate faster than anyone wants to admit.

## Why It Exists

Real repos rarely fail because one file is obviously broken. They decay because:

- documentation drifts out of authority
- duplicate files survive after migrations
- temp and scratch artifacts never leave
- shared/core code quietly defeats folder-level modularity
- teams start assuming something is safe to delete or validate in isolation
  before that has actually been verified

Repo Cleanser is designed to slow that down. It does not auto-delete, auto-fix,
or auto-certify anything. It gives you a structured report that is useful
enough to review and safe enough to trust.

## What It Does

Version `0.1.0` supports:

- scanning a local repository path
- classifying important files into governance and cleanup-risk categories
- detecting duplicate markdown docs, suspicious stale artifacts, partial
  migration leftovers, unclear-authority docs, and likely orphan candidates
- reporting a first heuristic layer for module boundaries, explicit
  registration signals, and possible safe-detach risks
- reporting an advisory affected-only validation readiness layer that treats
  shared/core coupling as a first-class blocker
- reporting advisory broad validation triggers and possible narrow validation
  candidates without scoring or claiming safety
- loading one explicit `repo-cleanser.toml` file for ignores, known mirrors,
  generated paths, and traceable advisory suppressions
- generating a text or JSON report

## What It Refuses To Do

Out of scope for v1:

- automatic deletion or cleanup
- code rewriting
- dependency-graph certainty claims
- changed-file impact execution
- cloud or multi-user features
- dashboard or IDE integration

## Quick Start

This project uses `uv` as the package manager.

Install dependencies:

```powershell
uv sync --group dev
```

If `uv` is installed but not on `PATH`, use:

```powershell
python -m uv sync --group dev
```

Run a text report:

```powershell
uv run repo-cleanser scan D:\path\to\repo
```

Write a JSON report:

```powershell
uv run repo-cleanser scan D:\path\to\repo --format json --output .\report.json
```

Show supporting files in the highlights section:

```powershell
uv run repo-cleanser scan D:\path\to\repo --include-supporting
```

## Report Layers

Repo Cleanser currently reports across four practical layers:

1. Governance and cleanup risk
2. Module-boundary quality
3. Safe-detach risk signals
4. Advisory readiness for narrower affected-scope validation

The tool intentionally keeps those layers separate. A repo can look clean in one
layer and weak in another.

## Canonical Config

Repo Cleanser loads one optional root config file named `repo-cleanser.toml`.
If it is absent, the analyzer keeps its default behavior.

Example:

```toml
ignored_paths = ["notes", "archive/tmp"]
generated_paths = ["coverage", "storybook-static"]

[[mirrored_docs]]
source = "documentation"
publish = "public/docs"

[[advisory_suppressions]]
finding = "orphaned-artifacts"
path_pattern = "scratch-notes.md"
reason = "Intentional local scratch note."
```

Config rules:

- `ignored_paths` and `generated_paths` are repo-relative path patterns
- `mirrored_docs` declares expected source-to-publish doc mirrors so publish
  copies do not generate duplicate-noise on their own
- `advisory_suppressions` remain visible in the report under
  `Suppressed findings`
- config can reduce expected noise, but it does not mark any path as safe

## Report Categories

- `canonical`: source-of-truth docs or root governance/config entrypoints
- `supporting`: normal implementation, tests, scripts, and supporting docs
- `duplicate`: overlapping files that likely duplicate an existing source
- `stale`: old, deprecated, copied, backup-like, or migration-leftover artifacts
- `historical`: intentional archive or history material
- `temporary`: scratch, draft, temp, or work-in-progress artifacts
- `generated`: cache, build, or generated output signals
- `unclear-authority`: files that appear to claim governance authority outside
  the canonical location

## Safety Model

- `likely orphaned` always means heuristic only
- suppressions are traceable, not silent
- Repo Cleanser never modifies the scanned repository in v1
- the tool does not prove a file is unused, detachable, or safe to remove
- the tool does not claim a module is safe to validate alone

## Canonical Docs

Repo Cleanser uses one canonical doc chain:

1. `README.md`
2. `AGENTS.md`
3. `docs/architecture.md`
4. `docs/validation.md`
5. `docs/project-tree.md`

## Validation

The canonical validation flow lives in [docs/validation.md](docs/validation.md).
