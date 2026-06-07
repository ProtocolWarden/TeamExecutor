# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
from typing import Literal

from team_executor.agent_call import call_agent
from team_executor.models import GoalStage, Role

_PLAN_PROMPT = """\
You are a coordinator. Decompose the following goal into stages for a team of agents.

Goal:
{goal_text}

Respond with a JSON array only — no markdown, no preamble, no tool use. Each element must have:
  "description": string — what to accomplish in this stage
  "acceptance_criteria": array of strings — measurable conditions for success
  "parallel_group": integer or null — stages sharing the same integer run concurrently; null means sequential

Assign a parallel_group when stages are genuinely independent and can run simultaneously.
Sequential dependencies must be separate groups or null.

Example:
[
  {{"description": "Set up project structure", "acceptance_criteria": ["pyproject.toml present"], "parallel_group": null}},
  {{"description": "Implement feature A", "acceptance_criteria": ["tests pass"], "parallel_group": 1}},
  {{"description": "Implement feature B", "acceptance_criteria": ["tests pass"], "parallel_group": 1}},
  {{"description": "Integration test", "acceptance_criteria": ["all tests green"], "parallel_group": null}}
]
"""


def plan_stages(
    goal_text: str,
    coordinator: Role,
    working_dir: str,
    backend: Literal["claude_code", "codex_cli"] = "claude_code",
) -> list[GoalStage]:
    prompt = _PLAN_PROMPT.format(goal_text=goal_text)
    raw_text = call_agent(coordinator, prompt, working_dir, backend=backend)
    raw_text = raw_text.strip()

    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        stages_data = json.loads(raw_text)
    except json.JSONDecodeError:
        # Agent may include conversational preamble before the JSON array.
        bracket_start = raw_text.find("[")
        if bracket_start != -1:
            try:
                stages_data, _ = json.JSONDecoder().raw_decode(raw_text, bracket_start)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Stage planner received non-JSON from agent (session limit or error): {raw_text[:300]}"
                ) from exc
        else:
            raise RuntimeError(
                f"Stage planner received non-JSON from agent (session limit or error): {raw_text[:300]}"
            )
    return [
        GoalStage(
            index=i,
            description=item["description"],
            acceptance_criteria=item.get("acceptance_criteria", []),
            parallel_group=item.get("parallel_group"),
        )
        for i, item in enumerate(stages_data)
    ]
