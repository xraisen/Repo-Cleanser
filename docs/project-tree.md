# Project Tree

```text
repo-cleanser/
├── AGENTS.md
├── README.md
├── docs/
│   ├── architecture.md
│   ├── project-tree.md
│   └── validation.md
├── pyproject.toml
├── uv.lock
├── scripts/
│   └── validate.py
├── src/
│   └── repo_cleanser/
│       ├── __init__.py
│       ├── __main__.py
│       ├── analyzer.py
│       ├── cli.py
│       ├── models.py
│       └── reporting.py
└── tests/
    ├── test_analyzer.py
    └── test_cli.py
```

## Notes

- `README.md`, `AGENTS.md`, and the `docs/` folder make up the canonical doc
  chain for this repository.
- `src/repo_cleanser/` contains the CLI, analyzer, report models, and text/JSON
  rendering logic.
- `tests/` contains focused analyzer and CLI coverage.
- Scanned repositories may optionally include a root `repo-cleanser.toml`
  config file. This repository documents that format but does not need to ship
  one for itself.
