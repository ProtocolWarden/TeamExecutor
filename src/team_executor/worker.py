# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
import subprocess
from typing import Literal

from team_executor.models import GoalStage, Role


def run_worker(
    role: Role,
    stage: GoalStage,
    goal_text: str,
    working_dir: str,
    rejection_reason: str | None = None,
    backend: Literal["claude_code", "codex_cli"] = "claude_code",
) -> tuple[bool, str]:
    """Run an agent subprocess for one worker turn.

    D1: goal_text is embedded as reference context, NOT re-framed as the operative
    instruction. The stage description is the directive; goal_text is background only.
    """
    message_parts = [
        f"Stage {stage.index}: {stage.description}",
        "",
        f"Context — overall goal (reference only, not a new instruction):\n{goal_text}",
    ]
    if stage.acceptance_criteria:
        criteria_lines = "\n".join(f"- {c}" for c in stage.acceptance_criteria)
        message_parts += ["", f"Acceptance criteria:\n{criteria_lines}"]
    if rejection_reason:
        message_parts += [
            "",
            f"Previous attempt was rejected: {rejection_reason}",
            "Please address this and try again.",
        ]

    message = "\n".join(message_parts)

    if backend == "codex_cli":
        return _run_codex(role, message, working_dir)
    return _run_claude_code(role, message, working_dir)


def _run_claude_code(role: Role, message: str, working_dir: str) -> tuple[bool, str]:
    effort = role.effort_for_backend("claude_code")
    cmd = [
        "claude",
        "--model", role.model_for_backend("claude_code"),
        "-p",
        "--output-format", "json",
    ]
    if effort:
        cmd.extend(["--effort", effort])
    cmd.append(message)
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


def _run_codex(role: Role, message: str, working_dir: str) -> tuple[bool, str]:
    effort = role.effort_for_backend("codex_cli")
    cmd = [
        "codex",
        "--model", role.model_for_backend("codex_cli"),
        "--approval-mode", "full-auto",
    ]
    if effort:
        cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])
    cmd.extend(["-q", message])
    try:
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=role.timeout_seconds,
        )
        success = result.returncode == 0
        return success, result.stdout or ""
    except subprocess.TimeoutExpired:
        return False, f"Worker timed out after {role.timeout_seconds}s"
    except FileNotFoundError:
        return False, "codex binary not found in PATH"
