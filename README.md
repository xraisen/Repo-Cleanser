# Repo Cleanser

Repo Cleanser is a non-destructive Python CLI that scans a local repository and
highlights documentation drift, duplicate or stale files, risky cleanup
targets, incomplete migration signals, and suspicious cleanup clutter patterns.

It does not delete or rewrite project files. It produces a readable governance and cleanup report so a developer can make safe follow-up decisions.

## Scope

Version `0.1.0` supports:

- scanning a local repository path
- classifying important files into governance and cleanup-risk categories
- detecting duplicate markdown docs, suspicious stale artifacts, partial
  migration leftovers, unclear-authority docs, and likely orphan candidates
- reporting a first heuristic layer for module boundaries, explicit
  registration signals, and possible safe-detach risks
- reporting an advisory affected-only validation readiness layer that treats
  shared/core coupling as a major blocker
- reporting advisory broad validation triggers and possible narrow validation
  candidates without scoring or claiming safety
- generating a text or JSON report

Out of scope for v1:

- automatic deletion or cleanup
- code rewriting
- cloud or multi-user features
- dashboard or IDE integration

## Install

This project uses `uv` as the package manager.

```powershell
uv sync --group dev
```

## Usage

Run a text report:

```powershell
uv run repo-cleanser scan D:\path\to\repo
```

Write a JSON report to disk:

```powershell
uv run repo-cleanser scan D:\path\to\repo --format json --output .\report.json
```

Show supporting files in the highlights section:

```powershell
uv run repo-cleanser scan D:\path\to\repo --include-supporting
```

## Report Categories

- `canonical`: source-of-truth docs or root governance/config entrypoints
- `supporting`: normal implementation, tests, scripts, and supporting docs
- `duplicate`: overlapping files that likely duplicate an existing source
- `stale`: old, deprecated, copied, or backup-like artifacts
- `historical`: intentional archive or history material
- `temporary`: scratch, draft, temp, or work-in-progress artifacts
- `generated`: cache, build, or generated output signals
- `unclear-authority`: files that appear to claim governance authority outside the canonical location

## Safety Notes

- `likely orphaned` always means heuristic only. Review manually before
  deleting, archiving, or renaming anything.
- Repo Cleanser never modifies the scanned repository in v1.
- The tool does not prove a file is unused or safe to remove.

## Canonical Documentation Chain

Repo Cleanser recommends this governance chain when a repository needs explicit documentation authority:

1. `README.md`
2. `AGENTS.md`
3. `docs/architecture.md`
4. `docs/validation.md`
5. `docs/project-tree.md`

## Validation

The canonical validation commands are documented in [docs/validation.md](docs/validation.md).
