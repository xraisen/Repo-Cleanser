# Validation

## Toolchain

- Package manager: `uv`
- Lint: `ruff`
- Typecheck: `mypy`
- Tests: `pytest`

## Default Order

When finishing work in this repository, validate in this order:

1. lint
2. typecheck
3. tests
4. full validation script

That keeps failures narrow and easier to diagnose before the aggregate command
runs.

## Commands

Install dependencies:

```powershell
uv sync --group dev
```

If `uv` is installed but not on `PATH`, use:

```powershell
python -m uv sync --group dev
```

Run lint:

```powershell
uv run --group dev ruff check .
```

Run typecheck:

```powershell
uv run --group dev mypy src tests
```

Run tests:

```powershell
uv run --group dev pytest
```

Run the full validation script:

```powershell
uv run python scripts/validate.py
```

## Regression Guardrails

The current test suite explicitly guards against these bug classes so they do
not quietly reappear:

- grouped findings being suppressed too broadly
- single-subject findings with context paths becoming impossible to suppress
- `repo-cleanser.toml` or `.gitignore` text being mistaken for real references
- markdown docs, comment-only text, or plain string literals looking like live
  imports, module registration, or shared/core coupling
- orphan detection being suppressed by ignore-file mentions or loose string
  matches, including near-match filenames like `draft-plan.md.backup`
- invalid UTF-8 or BOM-prefixed config files failing in uncontrolled ways
- unsafe control or escape characters leaking into terminal report output
- config paths escaping the repository path space
- mirrored-doc roots overlapping or suppression finding kinds being blank

## Fallback Behavior

`scripts/validate.py` falls back to `python -m uv` automatically when `uv` is
not directly available on `PATH`.
