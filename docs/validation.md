# Validation

## Tooling

- Package manager: `uv`
- Lint: `ruff`
- Typecheck: `mypy`
- Tests: `pytest`

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

Run all validation steps:

```powershell
uv run python scripts/validate.py
```

`scripts/validate.py` falls back to `python -m uv` automatically when `uv`
is not directly available on `PATH`.
