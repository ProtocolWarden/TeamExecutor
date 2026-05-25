# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from team_executor import agent_call
from team_executor.models import Role


def _role() -> Role:
    return Role(name="coordinator", model="sonnet", system_prompt="sp", timeout_seconds=42, effort="medium")


class _Result:
    def __init__(self, stdout="", stderr="", returncode=0, timed_out=False):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.timed_out = timed_out


def test_claude_call_parses_json_result_field():
    payload = json.dumps({"result": "the answer", "is_error": False})
    with patch("team_executor.agent_call.safe_run", return_value=_Result(stdout=payload)) as sr:
        out = agent_call.call_agent(_role(), "prompt", "/wd")
    assert out == "the answer"
    # timeout is propagated from the role
    assert sr.call_args.kwargs["timeout_seconds"] == 42
    assert "--effort" in sr.call_args.args[0]
    assert "medium" in sr.call_args.args[0]


def test_claude_call_returns_raw_when_not_result_json():
    with patch("team_executor.agent_call.safe_run", return_value=_Result(stdout="plain text")):
        assert agent_call.call_agent(_role(), "p", "/wd") == "plain text"


def test_claude_call_raises_on_is_error():
    payload = json.dumps({"result": "boom", "is_error": True})
    with patch("team_executor.agent_call.safe_run", return_value=_Result(stdout=payload)):
        with pytest.raises(RuntimeError, match="is_error"):
            agent_call.call_agent(_role(), "p", "/wd")


def test_claude_call_raises_on_timeout():
    with patch("team_executor.agent_call.safe_run", return_value=_Result(timed_out=True)):
        with pytest.raises(RuntimeError, match="timed out"):
            agent_call.call_agent(_role(), "p", "/wd")


def test_claude_call_raises_on_empty_stdout():
    with patch("team_executor.agent_call.safe_run", return_value=_Result(stdout="", stderr="bad", returncode=2)):
        with pytest.raises(RuntimeError, match="no stdout"):
            agent_call.call_agent(_role(), "p", "/wd")


def test_claude_call_raises_when_binary_missing():
    with patch("team_executor.agent_call.safe_run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="claude binary not found"):
            agent_call.call_agent(_role(), "p", "/wd")


def test_codex_backend_returns_stdout_and_builds_codex_cmd():
    captured = {}

    def fake_safe_run(cmd, **kw):
        captured["cmd"] = cmd
        return _Result(stdout="codex output")

    role = Role(
        name="coordinator",
        model="claude-sonnet-4-6",
        effort="medium",
        backend_models={"codex_cli": "gpt-5.4"},
        backend_efforts={"codex_cli": "high"},
        system_prompt="sp",
        timeout_seconds=42,
    )
    with patch("team_executor.agent_call.safe_run", side_effect=fake_safe_run):
        out = agent_call.call_agent(role, "p", "/wd", backend="codex_cli")
    assert out == "codex output"
    assert captured["cmd"][0] == "codex"
    assert captured["cmd"][2] == "gpt-5.4"
    assert 'model_reasoning_effort="high"' in captured["cmd"]


def test_codex_backend_raises_on_timeout():
    with patch("team_executor.agent_call.safe_run", return_value=_Result(timed_out=True)):
        with pytest.raises(RuntimeError, match="timed out"):
            agent_call.call_agent(_role(), "p", "/wd", backend="codex_cli")
