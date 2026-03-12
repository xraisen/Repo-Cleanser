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

## Fallback Behavior

`scripts/validate.py` falls back to `python -m uv` automatically when `uv` is
not directly available on `PATH`.
