# Contributing to TeamExecutor

TeamExecutor orchestrates a coordinator/worker/verifier team pattern for multi-stage AI task execution. The coordinator plans stages via Anthropic API, workers execute via Claude Code subprocess, and the verifier grades each stage before proceeding.

## Before You Start

- Check open issues to avoid duplicate work
- For significant changes, open an issue first to discuss the approach
- All contributions must pass the test suite and linter before merging

## Development Setup

```bash
git clone https://github.com/ProtocolWarden/TeamExecutor.git
cd TeamExecutor
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Running Tests

```bash
.venv/bin/python -m pytest tests/ -v
```

## Invariants

- **D1**: `goal_text` from the ExecutionRequest must reach worker nodes verbatim (no rewriting).
- Verifier verdicts must be ACCEPT or REJECT — no partial/ambiguous states.
- tiktoken summarization fires only when context exceeds the configured threshold.
