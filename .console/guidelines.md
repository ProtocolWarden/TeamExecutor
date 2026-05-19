# Guidelines

## Branch Policy

- Never commit to `main` directly — always use a feature branch
- Pre-push hook enforces `.console/log.md` updates

## Code Style

- SPDX headers on all Python files
- Line length 100 (ruff enforced)
- No docstrings on obvious functions
- No print() in library code
- `from __future__ import annotations` on all modules
- Dataclasses for models, no NamedTuples

## Dependency Constraints

- `rxp` is the contract layer — import `RuntimeResult` from `rxp.contracts.runtime_result`
- `cxrp` is the dispatch layer — do not bypass it for OC communication
- `anthropic` client is injected, never instantiated inside core logic modules

## D1 Invariant

`goal_text` MUST reach the coordinator verbatim as its first input. Workers receive stage descriptions with goal embedded but NOT re-framed.
