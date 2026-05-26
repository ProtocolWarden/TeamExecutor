# TeamExecutor

Team topology execution backend for the OperationsCenter-owned execution layer.

## What this repo is

A thin execution backend that drives a **coordinator → workers → verifier** loop
over a single goal. Given a goal and a named team config, it:

- **Coordinator** breaks the goal into ordered stages.
- **Workers** are agent subprocesses (Claude Code or Codex CLI) that execute each
  stage in a working directory.
- **Verifier** validates each stage's output and accepts or rejects it, driving
  re-attempts up to a per-stage cycle limit.
- Optional **adaptive advisor** can revise the plan between stages, **quick checks**
  run scripted shell verifications, **git worktrees** isolate parallel stages, and
  **checkpoints** persist completed-stage results so a run can resume.

It returns a `RuntimeResult` from the RxP contract layer and accepts a
`RuntimeInvocation` from OC via CxRP.

### D1 invariant

`goal_text` reaches the coordinator verbatim as its first input. Workers receive
the stage description with the goal embedded as reference context only — never
re-framed as a new operative instruction.

## What this repo is not

- Not an agent runtime or model host — it shells out to external agent CLIs
  (`claude`, `codex`) and does not implement an LLM client itself.
- Not a planner or orchestration UI — it is a backend invoked by OperationsCenter;
  it carries no scheduling, queueing, or persistence beyond per-run checkpoints.
- Not a general-purpose git tool — its `git_ops` helpers exist only to isolate and
  merge parallel stage work.

## Quick start

```python
from team_executor.executor import TeamExecutorRunner

runner = TeamExecutorRunner(team_name="standard", working_dir="/path/to/project")
result = runner.run("Implement feature X in the codebase")
```

Run the tests inside the project virtualenv:

```bash
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m pytest -q
```

## Architecture

```
                         goal_text
                            │
                            ▼
   ┌──────────────┐   stages   ┌──────────────┐  accept/reject  ┌────────────┐
   │ coordinator  │ ─────────▶ │   worker(s)  │ ──────────────▶ │  verifier  │
   │ (agent_call) │            │   (worker)   │                 │ (quick_check│
   └──────────────┘            └──────────────┘                 │  + agent)  │
                            │            ▲                       └────────────┘
                            │            │ rejection_reason            │
                            └────────────┴─────────────────────────────┘
                            │
                            ▼
              advisor (optional) → revise plan
              git_ops → isolate/merge parallel stages
              checkpoint → persist completed stages
              summarizer → compress long stage output for next stage
```

| Module          | Responsibility                                                    |
|-----------------|-------------------------------------------------------------------|
| `executor`      | Top-level `TeamExecutorRunner`; orchestrates the loop.            |
| `coordinator`   | Plans the goal into ordered stages.                              |
| `worker`        | Runs an agent subprocess for one worker turn.                    |
| `verifier`      | Accept/reject a stage output.                                    |
| `quick_check`   | Runs scripted shell verification commands as a fast verifier.    |
| `advisor`       | Adaptive planner that can continue/stop/inject a stage.          |
| `agent_call`    | Calls a planning/review agent subprocess and returns its text.   |
| `summarizer`    | Compresses long stage output before it feeds the next stage.     |
| `git_ops`       | Worktree isolation and auto-commit helpers for parallel stages.  |
| `checkpoint`    | Persists/reads/deletes completed-stage results for resume.       |
| `config_loader` | Loads team YAML configs (project → home → built-in).             |
| `models`        | Dataclasses for roles, stages, verdicts, results.               |

## Configuration

Team configs are YAML files loaded in priority order:

1. `{working_dir}/.team_executor/teams/{team_name}.yaml`
2. `~/.team_executor/teams/{team_name}.yaml`
3. Built-in configs shipped under `src/team_executor/teams/`.
