# TeamExecutor

Team topology executor for the OperationsCenter owned execution topology layer.

Implements a coordinator → workers → verifier loop:
- **Coordinator**: Anthropic API call that breaks the goal into stages
- **Workers**: Claude Code subprocesses that execute each stage
- **Verifier**: Anthropic API call that validates each stage output

## RxP Integration

Returns `RuntimeResult` from the RxP contract layer. Accepts `RuntimeInvocation` from OC via CxRP.

## D1 Invariant

`goal_text` reaches the coordinator verbatim as its first input. Workers receive stage descriptions with goal embedded but NOT re-framed.

## Usage

```python
from team_executor.executor import TeamExecutorRunner

runner = TeamExecutorRunner(team_name="default", working_dir="/path/to/project")
result = runner.run("Implement feature X in the codebase")
```

## Configuration

Team configs are YAML files loaded from:
1. `{working_dir}/.team_executor/teams/{team_name}.yaml`
2. `~/.team_executor/teams/{team_name}.yaml`
