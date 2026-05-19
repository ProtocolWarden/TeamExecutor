# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json

from team_executor.models import CycleVerdict, GoalStage, Role, VerdictStatus

_VERIFY_PROMPT = """\
Stage description: {description}

Acceptance criteria:
{criteria}

Worker output:
{output}

Evaluate whether the output satisfies all acceptance criteria.
Respond with JSON only — no markdown, no explanation:
{{"status": "accept" or "reject", "reason": "brief explanation"}}
"""


def verify_stage(
    stage: GoalStage,
    output: str,
    verifier_role: Role,
    anthropic_client,
    round_num: int,
) -> CycleVerdict:
    criteria_text = "\n".join(f"- {c}" for c in stage.acceptance_criteria) or "(none specified)"
    prompt = _VERIFY_PROMPT.format(
        description=stage.description,
        criteria=criteria_text,
        output=output,
    )
    response = anthropic_client.messages.create(
        model=verifier_role.model,
        max_tokens=512,
        system=verifier_role.system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        parsed = json.loads(raw_text)
        status_str = parsed.get("status", "reject").lower()
        status = VerdictStatus.ACCEPT if status_str == "accept" else VerdictStatus.REJECT
        reason = parsed.get("reason", "")
    except (json.JSONDecodeError, AttributeError):
        # Safe default: malformed response → reject so the stage is retried
        status = VerdictStatus.REJECT
        reason = f"Verifier returned malformed JSON: {raw_text[:200]}"

    return CycleVerdict(status=status, reason=reason, round=round_num)
