<!-- console-context -->
## OperatorConsole Context

At the start of each session, read the compiled context before acting:

- `.console/.context` — compiled startup context (generated fresh each launch)

The context file contains your current task, guidelines, backlog, log, and runtime context.

**Source files** (editable truth — update these, not the context file):

| File | Role |
|------|------|
| `.console/task.md` | Current objective and definition of done |
| `.console/guidelines.md` | Repo policy, branch rules, operating constraints |
| `.console/backlog.md` | Work inventory — in-progress, up-next, done |
| `.console/log.md` | Recent decisions, stop points, what changed and why |

After meaningful progress, update `.console/backlog.md` and `.console/log.md`.
Do not edit `.console/.context` directly — it is regenerated at each launch.
<!-- /console-context -->

## Cognition Lifecycle

This executor is a library consumer. **Cognition is hosted by the anchoring manifest** — this repo carries no `.context/` of its own. Per Phase 5 of `PlatformDeployment/docs/architecture/adr/0002-work-order-manifest-cognition.md`, every Claude Code session targeting this repo must first run `eval $(cl session start <manifest>)` (PlatformManifest or your private-manifest repo depending on scope). All capsules, checkpoints, and handoffs land under the anchor's `.context/sessions/<CL_SESSION_ID>/` subtree.

| Surface       | Purpose                                                                |
|---------------|------------------------------------------------------------------------|
| `.console/`   | Operational truth — task, guidelines, backlog, log                     |
| `.claude/hooks/` | Thin shim that execs `cl hook <event>` (logic lives in CL package)  |

Sessions without `CL_ANCHOR` set will fail closed at the first hook fire — no fallback, no silent pass-through. Install: set `CL_HOME=/path/to/ContextLifecycle` or `pipx install context-lifecycle`.
