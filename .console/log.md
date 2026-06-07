# Log

## 2026-06-07 — fix(stage_planner): tolerate preambled JSON from agent

Agent responses sometimes include conversational text before the JSON array
("Now I'll provide the decomposition:"). The stage planner raised RuntimeError
on strict `json.loads()`. Fixed with `JSONDecoder.raw_decode()` fallback at the
first `[` — handles both leading preamble and trailing text. 3 new tests; 154/154 pass.

## 2026-06-04 — Console reconciliation (enforce-only)

Reconciled `.console/` per the console-reconciliation spec. This repo was already
clean and under budget, so this is enforce-only:

- Confirmed no scrub-target leaks in tracked `.console/`/`docs` (git grep clean,
  excluding detector-ID forms).
- `cl reconcile check` reports GREEN (prune-ready); log.md well under the 400-line R1 budget.
- Set `audit.reconcile_enforce: true` in `.custodian/config.yaml` so Custodian R1/R2
  now enforce on this repo.

## 2026-05-23 — Clear Custodian findings + add real unit tests

Took the repo from 37 Custodian findings to 0 (clean) on branch
`chore/custodian-clean-and-tests`:

- **C11**: added `timeout=` (300s `_GIT_TIMEOUT_SECONDS` constant) to every
  `subprocess.run` in `git_ops.py`. Behavior otherwise unchanged.
- **C41 / C16**: `checkpoint.py` now writes JSON with `ensure_ascii=False` and
  reads/writes with `encoding="utf-8"`; `config_loader.py` reads with
  `encoding="utf-8"`.
- **S4**: added a project-venv guard to `tests/conftest.py` (matches the OC/
  Custodian pattern, CI-exempt).
- **T2**: `test_delete_missing_is_noop` now asserts the file stays absent and
  reads back as None.
- **T1/T6/T7**: real unit tests under `tests/unit/` for `git_ops`, `agent_call`,
  `worker`, `summarizer`, `advisor`, `quick_check` — mock subprocess/safe_run/
  agent calls and exercise success, failure, timeout, and parsing branches.
- **W5/W6/W7**: added `.env.example`, `.hooks/pre-commit` (log-gate), and the
  `.console/*` + `CLAUDE.md` `.gitignore` policy; set `core.hooksPath .hooks`.
- **R3/R4/DC4/M1**: rewrote README (What this repo is / is not / Quick start /
  Architecture) and added a Keep-a-Changelog `CHANGELOG.md`.

150 tests pass; Custodian reports 0 findings | clean.

## 2026-05-21 — Add closing fence to console-context block

Added <!-- /console-context --> end marker so OperatorConsole only replaces its
managed block and leaves repo-owned content below it untouched.

## 2026-05-19 — ADR 0006 Phase 2: wire safe_run() in agent_call.py

- Replaced subprocess.run() in _claude_call() and _codex_call() with core_runner.process.safe_run().
- Removed subprocess import; removed TimeoutExpired catch (safe_run returns timed_out=True instead).
- Kept FileNotFoundError handling for missing binary (safe_run lets this propagate from Popen).
- Added core-runner dep to pyproject.toml; conftest.py adds ExecutorRuntime/src to sys.path.
- 108 tests pass.

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


## 2026-05-22 — P5: Revert to CL shim (manifest-cognition work order)

Per PlatformDeployment/docs/architecture/adr/0002-work-order-manifest-cognition.md Phase 5:

- Deleted `.context/` (config.yaml + templates/) — cognition now hosted by anchoring manifest.
- Replaced `.claude/hooks/pre_tool_use.sh` (~330 lines) and `.claude/hooks/stop.sh` (~116 lines) with thin ~10-line shims that exec `cl hook <event>`. Logic lives in the CL package.
- Updated CLAUDE.md "Cognition Lifecycle" section to reflect library-consumer posture; sessions must `eval $(cl session start <manifest>)` before tools fire, else hooks fail closed.
- Cleaned `.gitignore` of stale `.context/*` rules.
- Confirmed zero CL imports in src/ (executor never coupled to CL Python API).

Branch: feat/p5-revert-to-shim. Staged, not committed.

## 2026-05-23 — Standardize pre-push hook (file only)

- Updated `.hooks/pre-push` to the auto-discovering variant. NOT activating core.hooksPath yet: repo has pre-existing audit findings that would block pushes under the fail-closed guard; activate after that cleanup.

## 2026-05-25 — Add backend-specific model and effort tiers

- Added backend-aware role runtime fields: `backend_models`, `backend_efforts`, plus helper selectors on `Role`.
- Claude subprocess calls now pass explicit `--effort`; Codex subprocess calls now pass `model_reasoning_effort`.
- Built-in `budget` / `default` / `premium` team YAMLs now define both Claude and Codex model+effort tiers:
  - budget = haiku/mini @ low
  - default = sonnet/gpt-5.4 @ medium
  - premium = opus/gpt-5.4 @ high
- Added coverage for backend-specific config loading and command construction. Focused TeamExecutor test slice passed.

## 2026-05-26 — Standard tier hard cutover

- Renamed the built-in middle team from `default` to `standard` and changed `TeamExecutorRunner` to default to `standard`.
- Removed the built-in `default.yaml`; loader now requires `standard` for the middle tier with no compatibility alias.
- Updated README and tests to use `standard`.
- Verified with focused tests and full `pytest`.
