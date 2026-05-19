# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json

from team_executor.models import GoalStage, Role

_PLAN_PROMPT = """\
You are a coordinator. Decompose the following goal into sequential stages.

Goal:
{goal_text}

Respond with a JSON array only — no markdown, no explanation. Each element must have:
  "description": string — what to accomplish in this stage
  "acceptance_criteria": array of strings — measurable conditions for success

Example:
[
  {{
    "description": "Set up project structure",
    "acceptance_criteria": ["Directory layout created", "pyproject.toml present"]
  }}
]
"""


def plan_stages(
    goal_text: str,
    coordinator: Role,
    anthropic_client,
) -> list[GoalStage]:
    prompt = _PLAN_PROMPT.format(goal_text=goal_text)
    response = anthropic_client.messages.create(
        model=coordinator.model,
        max_tokens=4096,
        system=coordinator.system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    stages_data = json.loads(raw_text)
    return [
        GoalStage(
            index=i,
            description=item["description"],
            acceptance_criteria=item.get("acceptance_criteria", []),
        )
        for i, item in enumerate(stages_data)
    ]
