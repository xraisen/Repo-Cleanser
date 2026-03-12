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

Fastest path:

```bash
git clone https://github.com/xraisen/Repo-Cleanser.git
cd Repo-Cleanser
python -m uv run repo-cleanser scan .
```

That command scans the current repository and prints a structural advisory
report to the terminal.

This project uses `uv` as the package manager.

If you do not have `uv` installed:

```bash
pip install uv
```

Install dependencies:

```powershell
uv sync --group dev
```

If `uv` is installed but not on `PATH`, use:

```powershell
python -m uv sync --group dev
```

If Repo Cleanser is installed in the current development repo:

```powershell
uv run repo-cleanser scan D:\path\to\repo
```

If Repo Cleanser is installed in an environment where `repo-cleanser` is already
on `PATH`:

```bash
repo-cleanser scan /path/to/project
```

Write a JSON report:

```powershell
uv run repo-cleanser scan D:\path\to\repo --format json --output .\report.json
```

Show supporting files in the highlights section:

```powershell
uv run repo-cleanser scan D:\path\to\repo --include-supporting
```

## Example: Scanning a Repository

To scan a different repository, point Repo Cleanser at that path.

If Repo Cleanser is installed globally:

```bash
repo-cleanser scan /path/to/project
```

If you are running from inside the development repo:

```bash
uv run repo-cleanser scan /path/to/project
```

Repo Cleanser analyzes:

- documentation drift
- module boundaries
- shared/core coupling pressure
- safe-detach risks
- broad validation triggers
- possible narrow validation candidates

## Report Layers

Repo Cleanser currently reports across four practical layers:

1. Governance and cleanup risk
2. Module-boundary quality
3. Safe-detach risk signals
4. Advisory readiness for narrower affected-scope validation

The tool intentionally keeps those layers separate. A repo can look clean in one
layer and weak in another.

## Example Output

Simplified example:

```text
Structural strengths
- 2 module-like areas show local tests or validation files (`src/features/billing`, `src/features/orders`)

Shared/Core coupling risks
- 3 module-like areas (`src/features/billing`, `src/features/orders`, `src/features/inventory`) appear to reference shared/core code directly

Broad validation triggers
- shared/core hubs referenced from `src/features/billing`, `src/features/orders` may widen validation beyond a single module-like folder

Possible narrow validation candidates
- src/features/billing (feature)
  Signals raising readiness: Entrypoints detected: `src/features/billing/index.ts`; Registration or bootstrap references detected from `src/app/router.ts`; Local checks detected: `src/features/billing/billing.test.ts`
  Still advisory because: Heuristic only. Manual review recommended before treating this area (`src/features/billing`) as a narrow validation candidate; No actual changed-file or dependency impact analysis is being performed
```

The report is heuristic and advisory only. It highlights what deserves manual
review; it does not certify isolation, deletion safety, or impact scope.

## Canonical Config

Repo Cleanser loads one optional root config file named `repo-cleanser.toml`.
If it is absent, the analyzer keeps its default behavior.

### Using a Config File

Create `repo-cleanser.toml` at the root of the repository you want to scan.

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

Another practical example:

```toml
ignored_paths = [
  "node_modules",
  "dist",
  ".next",
  "archive/tmp"
]

generated_paths = [
  "coverage",
  "storybook-static"
]

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
- ignored paths are skipped during scanning
- generated paths reduce expected noise from build or publish output, but do
  not suppress unrelated structural findings
- `mirrored_docs` declares expected source-to-publish doc mirrors so publish
  targets do not generate duplicate-noise on their own
- `advisory_suppressions` silence selected advisory findings, but they remain
  visible in the report under `Suppressed findings`
- prefer `mirrored_docs` for expected publish copies instead of using a broad
  suppression for grouped duplicate-doc findings
- config can reduce expected noise, but it does not mark any path as safe

## Report Categories

Repo Cleanser internally classifies files into the following advisory
categories:

- `canonical`: source-of-truth docs or root governance/config entrypoints
- `supporting`: normal implementation, tests, scripts, and supporting docs
- `duplicate`: overlapping files that likely duplicate an existing source
- `stale`: old, deprecated, copied, backup-like, or migration-leftover artifacts
- `historical`: intentional archive or history material
- `temporary`: scratch, draft, temp, or work-in-progress artifacts
- `generated`: cache, build, or generated output signals
- `unclear-authority`: files that appear to claim governance authority outside
  the canonical location

## Interpreting the Results

- Structural strengths: good modular signals such as entrypoints, local tests,
  or explicit registration patterns
- Shared/Core coupling risks: areas that widen validation scope because many
  modules lean on shared or central internals
- Broad validation triggers: likely reasons broader or full-repo validation is
  still needed
- Narrow validation candidates: areas that might support smaller validation
  scope later, but only after manual review

Repo Cleanser:

- does not delete code
- does not rewrite code
- does not guarantee safe module isolation

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

### Running Validation

To validate the Repo Cleanser project itself:

```bash
python scripts/validate.py
```

That runs:

- lint
- typecheck
- tests

The fuller validation reference still lives in [docs/validation.md](docs/validation.md).
