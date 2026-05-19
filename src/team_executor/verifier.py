# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
from typing import Literal

from team_executor.agent_call import call_agent
from team_executor.models import CycleVerdict, GoalStage, VerifierRole, VerdictStatus

_VERIFY_PROMPT = """\
Stage description: {description}

Acceptance criteria:
{criteria}

Worker output:
{output}

Evaluate whether the output satisfies all acceptance criteria.
Respond with JSON only — no markdown, no tool use, no explanation outside the JSON:
{{"status": "accept" or "reject", "reason": "brief explanation"}}
"""


def _call_verifier(
    stage: GoalStage,
    output: str,
    vr: VerifierRole,
    working_dir: str,
    round_num: int,
    backend: Literal["claude_code", "codex_cli"] = "claude_code",
) -> CycleVerdict:
    criteria_text = "\n".join(f"- {c}" for c in stage.acceptance_criteria) or "(none specified)"
    prompt = _VERIFY_PROMPT.format(
        description=stage.description,
        criteria=criteria_text,
        output=output,
    )
    raw_text = call_agent(vr.role, prompt, working_dir, backend=backend).strip()

    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        parsed = json.loads(raw_text)
        status_str = parsed.get("status", "reject").lower()
        status = VerdictStatus.ACCEPT if status_str == "accept" else VerdictStatus.REJECT
        reason = parsed.get("reason", "")
    except (json.JSONDecodeError, AttributeError):
        status = VerdictStatus.REJECT
        reason = f"Verifier ({vr.kind}) returned malformed response: {raw_text[:200]}"

    return CycleVerdict(status=status, reason=reason, round=round_num)


def verify_stage(
    stage: GoalStage,
    output: str,
    verifiers: list[VerifierRole],
    working_dir: str,
    round_num: int,
    backend: Literal["claude_code", "codex_cli"] = "claude_code",
) -> CycleVerdict:
    """Run all verifiers sequentially. First rejection short-circuits.

    Testers run before reviewers (list order is authoritative).
    Returns the first rejection, or the last accept if all pass.
    """
    last_verdict: CycleVerdict | None = None
    for vr in verifiers:
        verdict = _call_verifier(stage, output, vr, working_dir, round_num, backend)
        last_verdict = verdict
        if verdict.status == VerdictStatus.REJECT:
            return verdict
    if last_verdict is None:
        return CycleVerdict(status=VerdictStatus.ACCEPT, reason="no verifiers configured", round=round_num)
    return last_verdict
