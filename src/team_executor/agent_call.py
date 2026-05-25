# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
from typing import Literal

from core_runner.process import safe_run

from team_executor.models import Role


def call_agent(
    role: Role,
    prompt: str,
    working_dir: str,
    backend: Literal["claude_code", "codex_cli"] = "claude_code",
) -> str:
    """Call an agent subprocess for a planning or review task and return its text output.

    Uses --no-auto-commits since coordinator and verifier roles do not write code.
    """
    if backend == "codex_cli":
        return _codex_call(role, prompt, working_dir)
    return _claude_call(role, prompt, working_dir)


def _claude_call(role: Role, prompt: str, working_dir: str) -> str:
    effort = role.effort_for_backend("claude_code")
    cmd = [
        "claude",
        "--model", role.model_for_backend("claude_code"),
        "-p",
        "--output-format", "json",
    ]
    if effort:
        cmd.extend(["--effort", effort])
    cmd.append(prompt)
    try:
        result = safe_run(cmd, cwd=working_dir, timeout_seconds=role.timeout_seconds)
    except FileNotFoundError:
        raise RuntimeError("claude binary not found in PATH")
    if result.timed_out:
        raise RuntimeError(f"Agent call timed out after {role.timeout_seconds}s")
    stdout = result.stdout or ""
    if not stdout:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            f"claude exited {result.returncode} with no stdout"
            + (f"; stderr: {stderr[:400]}" if stderr else "")
        )
    try:
        parsed = json.loads(stdout)
        if isinstance(parsed, dict) and "result" in parsed:
            if parsed.get("is_error"):
                raise RuntimeError(
                    f"claude returned is_error=true: {str(parsed['result'])[:400]}"
                )
            return str(parsed["result"])
    except (json.JSONDecodeError, KeyError):
        pass
    return stdout


def _codex_call(role: Role, prompt: str, working_dir: str) -> str:
    effort = role.effort_for_backend("codex_cli")
    cmd = [
        "codex",
        "--model", role.model_for_backend("codex_cli"),
        "--approval-mode", "full-auto",
    ]
    if effort:
        cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])
    cmd.extend(["-q", prompt])
    try:
        result = safe_run(cmd, cwd=working_dir, timeout_seconds=role.timeout_seconds)
    except FileNotFoundError:
        raise RuntimeError("codex binary not found in PATH")
    if result.timed_out:
        raise RuntimeError(f"Agent call timed out after {role.timeout_seconds}s")
    return result.stdout or ""
