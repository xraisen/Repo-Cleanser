# AGENTS.md

## Purpose

This repository builds `repo-cleanser`, a non-destructive CLI for repository governance and cleanup analysis.

## Rules

- Preserve the non-destructive contract. Do not add automatic deletion or rewriting unless the product scope changes explicitly.
- Prefer updating the canonical docs instead of creating parallel summaries or scratch governance files.
- Keep the CLI output understandable by a solo developer reviewing a real repository under time pressure.
- Treat cleanup findings as advisory. A finding should explain why a file is risky and what should be verified before any removal.

## Canonical Docs

- `README.md`
- `AGENTS.md`
- `docs/architecture.md`
- `docs/validation.md`
- `docs/project-tree.md`

## Validation

Before finishing changes, run the commands in `docs/validation.md`.
