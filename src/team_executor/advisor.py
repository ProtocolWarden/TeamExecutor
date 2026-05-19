# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
"""advisor.py — adaptive advisor that runs after each stage and can inject new stages."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Literal

from team_executor.agent_call import call_agent
from team_executor.models import GoalStage, StageResult, TeamConfig

logger = logging.getLogger(__name__)

_ADVISOR_PROMPT = """\
You are an adaptive planning advisor reviewing the result of a completed execution stage.

Overall goal:
{goal_text}

Completed stage {stage_index}: {stage_description}
Stage success: {success}
Stage output (truncated to 1000 chars):
{output_snippet}

Remaining planned stages ({remaining_count}):
{remaining_summary}

Decide one of:
- "continue": proceed with the remaining plan as-is
- "done": the goal is fully achieved; skip remaining stages
- "add_stage": insert one additional stage before the remaining stages

Respond with JSON only:
{{"action": "continue" | "done" | "add_stage", "reason": "brief explanation", "new_stage_description": "...(only when action=add_stage)", "new_stage_criteria": ["...", "..."]}}
"""


@dataclass
class AdvisorResult:
    action: Literal["continue", "done", "add_stage"]
    reason: str
    new_stage: GoalStage | None = None


def advise_after_stage(
    goal_text: str,
    stage: GoalStage,
    result: StageResult,
    remaining_stages: list[GoalStage],
    next_index: int,
    config: TeamConfig,
    working_dir: str,
    backend: str,
) -> AdvisorResult:
    """Ask the coordinator LLM whether to continue, stop, or add a stage."""
    remaining_summary = "\n".join(
        f"  {s.index}. {s.description}" for s in remaining_stages
    ) or "  (none — this was the last planned stage)"

    prompt = _ADVISOR_PROMPT.format(
        goal_text=goal_text,
        stage_index=stage.index,
        stage_description=stage.description,
        success=result.success,
        output_snippet=result.output[:1000],
        remaining_count=len(remaining_stages),
        remaining_summary=remaining_summary,
    )

    try:
        raw = call_agent(config.coordinator, prompt, working_dir, backend=backend).strip()
    except Exception as exc:
        logger.warning("advisor: call_agent raised %s — defaulting to continue", exc)
        return AdvisorResult(action="continue", reason=f"advisor error: {exc}")

    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("advisor: malformed JSON — defaulting to continue")
        return AdvisorResult(action="continue", reason="advisor returned malformed JSON")

    action = parsed.get("action", "continue")
    if action not in ("continue", "done", "add_stage"):
        action = "continue"

    reason = parsed.get("reason", "")

    new_stage: GoalStage | None = None
    if action == "add_stage":
        desc = parsed.get("new_stage_description", "Additional stage")
        criteria = parsed.get("new_stage_criteria", [])
        new_stage = GoalStage(
            index=next_index,
            description=desc,
            acceptance_criteria=criteria if isinstance(criteria, list) else [],
        )
        logger.info("advisor: injecting new stage %d — %s", next_index, desc)

    return AdvisorResult(action=action, reason=reason, new_stage=new_stage)
