# AGENTS.md

## Mission

This repository builds `repo-cleanser`, a conservative CLI for repository
governance, cleanup-risk review, module-boundary analysis, and advisory
validation-readiness reporting.

## Product Guardrails

- Preserve the non-destructive contract. Do not add automatic deletion,
  rewriting, or auto-fix behavior unless the product scope changes explicitly.
- Keep findings advisory and explainable. The tool should surface risk, not
  pretend to prove safety.
- Do not introduce fake confidence through scores, `safe` labels, or silent
  suppressions.
- Prefer one explicit root config file, `repo-cleanser.toml`, over scattered
  or magical configuration behavior.
- Keep the CLI output understandable for a solo developer reviewing a real repo
  under time pressure.

## Documentation Hygiene

Use one canonical doc chain only:

- `README.md`
- `AGENTS.md`
- `docs/architecture.md`
- `docs/validation.md`
- `docs/project-tree.md`

When behavior changes:

- update the canonical docs that are now out of date
- do not create parallel summaries, v2 notes, or scratch governance files
- keep wording aligned with the actual implementation, not future ambition

## Definition Of Done

Before finishing changes:

- run the commands in `docs/validation.md`
- confirm docs still match reality
- keep suppressions and safety language transparent
