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
    cmd = [
        "claude",
        "--model", role.model,
        "--message", prompt,
        "--no-auto-commits",
        "--output-format", "json",
    ]
    try:
        result = safe_run(cmd, cwd=working_dir, timeout_seconds=role.timeout_seconds)
    except FileNotFoundError:
        raise RuntimeError("claude binary not found in PATH")
    if result.timed_out:
        raise RuntimeError(f"Agent call timed out after {role.timeout_seconds}s")
    stdout = result.stdout or ""
    try:
        parsed = json.loads(stdout)
        if isinstance(parsed, dict) and "result" in parsed:
            return str(parsed["result"])
    except (json.JSONDecodeError, KeyError):
        pass
    return stdout


def _codex_call(role: Role, prompt: str, working_dir: str) -> str:
    cmd = [
        "codex",
        "--model", role.model,
        "--approval-mode", "full-auto",
        "-q", prompt,
    ]
    try:
        result = safe_run(cmd, cwd=working_dir, timeout_seconds=role.timeout_seconds)
    except FileNotFoundError:
        raise RuntimeError("codex binary not found in PATH")
    if result.timed_out:
        raise RuntimeError(f"Agent call timed out after {role.timeout_seconds}s")
    return result.stdout or ""
