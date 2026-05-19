# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
import subprocess

from team_executor.models import GoalStage, Role


def run_worker(
    role: Role,
    stage: GoalStage,
    goal_text: str,
    working_dir: str,
    rejection_reason: str | None = None,
) -> tuple[bool, str]:
    """Run Claude Code as a subprocess for a role's turn.

    D1: goal_text is embedded as context, NOT re-framed as a new goal.
    The stage description is the operative instruction; goal_text is reference only.
    """
    message_parts = [
        f"Stage {stage.index}: {stage.description}",
        "",
        f"Context — overall goal (do NOT treat this as a new instruction):\n{goal_text}",
    ]
    if acceptance_criteria := stage.acceptance_criteria:
        criteria_lines = "\n".join(f"- {c}" for c in acceptance_criteria)
        message_parts += ["", f"Acceptance criteria:\n{criteria_lines}"]
    if rejection_reason:
        message_parts += [
            "",
            f"Previous attempt was rejected: {rejection_reason}",
            "Please address this and try again.",
        ]

    message = "\n".join(message_parts)

    cmd = [
        "claude",
        "--message",
        message,
        "--no-auto-commits",
        "--output-format",
        "json",
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=role.timeout_seconds,
        )
        success = result.returncode == 0
        stdout = result.stdout or ""
        # Claude Code json output wraps in a result field; extract if present
        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict) and "result" in parsed:
                stdout = parsed["result"]
        except (json.JSONDecodeError, KeyError):
            pass
        return success, stdout
    except subprocess.TimeoutExpired:
        return False, f"Worker timed out after {role.timeout_seconds}s"
    except FileNotFoundError:
        return False, "claude binary not found in PATH"
