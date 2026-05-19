# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
import subprocess
from typing import Literal

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
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=role.timeout_seconds,
        )
        stdout = result.stdout or ""
        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict) and "result" in parsed:
                return str(parsed["result"])
        except (json.JSONDecodeError, KeyError):
            pass
        return stdout
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Agent call timed out after {role.timeout_seconds}s")
    except FileNotFoundError:
        raise RuntimeError("claude binary not found in PATH")


def _codex_call(role: Role, prompt: str, working_dir: str) -> str:
    cmd = [
        "codex",
        "--model", role.model,
        "--approval-mode", "full-auto",
        "-q", prompt,
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=role.timeout_seconds,
        )
        return result.stdout or ""
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Agent call timed out after {role.timeout_seconds}s")
    except FileNotFoundError:
        raise RuntimeError("codex binary not found in PATH")
