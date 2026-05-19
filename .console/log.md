# Log

## 2026-05-19 — Primitives 1–4

- **persist_changes** on GoalStage: parallel stages with persist_changes=True each get an isolated git worktree; changes committed in worktree then cherry-picked back into main working dir
- **QuickCheck + verification field**: GoalStage.verification can be "full" (agent verifiers), "skip" (immediate accept), or list[QuickCheck] (scripted commands); quick_check.py runs commands with expected exit code, timeout, and file-not-found handling
- **Adaptive advisor** (advisor.py): after each sequential stage, coordinator LLM is asked "continue / done / add_stage"; "done" stops early; "add_stage" injects a new GoalStage into the live batch list
- **auto_commit** on TeamConfig: coordinator calls git_ops.commit_stage() after each successful sequential stage
- **git_ops.py**: create_worktree, remove_worktree, commit_worktree, merge_worktree_into_base, commit_stage helpers
- 108 tests passing (was 79)

## 2026-05-19 — Phase 2 primitives

- **parallel_group** on GoalStage: stages with same int run concurrently via ThreadPoolExecutor; coordinator batches them
- **checkpoint/resume**: checkpoint.py serialises StageResult list; coordinator writes after each batch, deletes on clean finish; invocation_id from RxP flows as run_id
- **multi-verifier**: verifiers list replaces single verifier; tester before reviewer; first reject short-circuits; legacy verifier: key wrapped automatically
- **codex_cli worker backend**: agent_call.py wraps both claude and codex CLI; all roles (coordinator, workers, verifiers, summarizer) route through it; SB injects via RxP metadata
- **all-subprocess coordinator**: removed anthropic_client from all roles; no direct Anthropic API calls
- **built-in teams**: default/premium/budget YAML shipped in teams/; config_loader priority: project → home → built-in
- **model flag**: --model {role.model} passed to claude CLI in all subprocess calls
- anthropic dep removed from pyproject.toml; teams/*.yaml in package-data
- 79 tests passing (was 45)

## 2026-05-18 — Initial scaffold

- Built complete Phase 2 package from spec
- D1 invariant enforced in worker.py: goal_text passed as context, not re-framed
- Verifier falls back to REJECT on malformed JSON (safe default)
- summarizer.py uses tiktoken to gate summarization at 4000 tokens
- Tests mock anthropic client; rxp/cxrp imports mocked at conftest level
- All tests pass without live API
