# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

from team_executor import worker
from team_executor.models import GoalStage, Role


def _role() -> Role:
    return Role(name="w", model="sonnet", system_prompt="sp", timeout_seconds=99, effort="medium")


def _stage() -> GoalStage:
    return GoalStage(index=2, description="build it", acceptance_criteria=["compiles"])


def _cp(stdout="", returncode=0):
    return subprocess.CompletedProcess(args=["claude"], returncode=returncode, stdout=stdout, stderr="")


def test_message_embeds_goal_as_reference_not_directive():
    captured = {}

    def fake_run(cmd, *a, **kw):
        captured["msg"] = cmd[-1]
        captured["cmd"] = cmd
        captured["timeout"] = kw.get("timeout")
        return _cp(stdout="done")

    with patch("team_executor.worker.subprocess.run", side_effect=fake_run):
        worker.run_worker(_role(), _stage(), "OVERALL GOAL", "/wd")

    msg = captured["msg"]
    assert "Stage 2: build it" in msg
    assert "reference only" in msg
    assert "OVERALL GOAL" in msg
    assert "compiles" in msg
    assert captured["timeout"] == 99
    assert "--effort" in captured["cmd"]
    assert "medium" in captured["cmd"]


def test_rejection_reason_appended_to_message():
    captured = {}

    def fake_run(cmd, *a, **kw):
        captured["msg"] = cmd[-1]
        return _cp(stdout="ok")

    with patch("team_executor.worker.subprocess.run", side_effect=fake_run):
        worker.run_worker(_role(), _stage(), "g", "/wd", rejection_reason="tests failed")

    assert "Previous attempt was rejected: tests failed" in captured["msg"]


def test_claude_success_parses_json_result():
    payload = json.dumps({"result": "extracted"})
    with patch("team_executor.worker.subprocess.run", return_value=_cp(stdout=payload)):
        ok, out = worker.run_worker(_role(), _stage(), "g", "/wd")
    assert ok is True
    assert out == "extracted"


def test_claude_nonzero_returncode_is_failure():
    with patch("team_executor.worker.subprocess.run", return_value=_cp(stdout="raw", returncode=1)):
        ok, out = worker.run_worker(_role(), _stage(), "g", "/wd")
    assert ok is False
    assert out == "raw"


def test_claude_timeout_returns_failure_message():
    with patch("team_executor.worker.subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 99)):
        ok, out = worker.run_worker(_role(), _stage(), "g", "/wd")
    assert ok is False
    assert "timed out after 99s" in out


def test_claude_missing_binary_returns_failure():
    with patch("team_executor.worker.subprocess.run", side_effect=FileNotFoundError):
        ok, out = worker.run_worker(_role(), _stage(), "g", "/wd")
    assert ok is False
    assert "claude binary not found" in out


def test_codex_backend_invoked_and_returns_stdout():
    captured = {}

    def fake_run(cmd, *a, **kw):
        captured["cmd"] = cmd
        return _cp(stdout="codex out")

    role = Role(
        name="w",
        model="claude-sonnet-4-6",
        effort="medium",
        backend_models={"codex_cli": "gpt-5.4-mini"},
        backend_efforts={"codex_cli": "low"},
        system_prompt="sp",
        timeout_seconds=99,
    )
    with patch("team_executor.worker.subprocess.run", side_effect=fake_run):
        ok, out = worker.run_worker(role, _stage(), "g", "/wd", backend="codex_cli")
    assert ok is True
    assert out == "codex out"
    assert captured["cmd"][0] == "codex"
    assert captured["cmd"][2] == "gpt-5.4-mini"
    assert 'model_reasoning_effort="low"' in captured["cmd"]


def test_codex_timeout_returns_failure():
    with patch("team_executor.worker.subprocess.run", side_effect=subprocess.TimeoutExpired("codex", 99)):
        ok, out = worker.run_worker(_role(), _stage(), "g", "/wd", backend="codex_cli")
    assert ok is False
    assert "timed out" in out
