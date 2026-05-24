# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import subprocess
from unittest.mock import patch

from team_executor import quick_check
from team_executor.models import GoalStage, QuickCheck, VerdictStatus


def _stage() -> GoalStage:
    return GoalStage(index=1, description="s", acceptance_criteria=[])


def _cp(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=["x"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_all_checks_pass_returns_accept():
    checks = [QuickCheck(command="true"), QuickCheck(command="echo hi")]
    with patch("team_executor.quick_check.subprocess.run", return_value=_cp(returncode=0)) as run:
        verdict = quick_check.run_quick_checks(checks, _stage(), "/wd", round_num=0)
    assert verdict.status == VerdictStatus.ACCEPT
    assert "2 quick check" in verdict.reason
    assert run.call_count == 2
    # every invocation must carry a timeout
    for call in run.call_args_list:
        assert call.kwargs.get("timeout") is not None


def test_first_failure_short_circuits_to_reject():
    calls = []

    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        return _cp(returncode=1, stderr="boom")

    checks = [QuickCheck(command="false", description="lint"), QuickCheck(command="never")]
    with patch("team_executor.quick_check.subprocess.run", side_effect=fake_run):
        verdict = quick_check.run_quick_checks(checks, _stage(), "/wd", round_num=2)

    assert verdict.status == VerdictStatus.REJECT
    assert verdict.round == 2
    assert "lint" in verdict.reason
    assert len(calls) == 1  # second check never runs


def test_expected_nonzero_exit_code_passes():
    check = QuickCheck(command="false", expected_exit_code=1)
    with patch("team_executor.quick_check.subprocess.run", return_value=_cp(returncode=1)):
        verdict = quick_check.run_quick_checks([check], _stage(), "/wd", round_num=0)
    assert verdict.status == VerdictStatus.ACCEPT


def test_timeout_returns_reject():
    with patch("team_executor.quick_check.subprocess.run",
               side_effect=subprocess.TimeoutExpired("cmd", 120)):
        verdict = quick_check.run_quick_checks([QuickCheck(command="sleep 999")], _stage(), "/wd", 0)
    assert verdict.status == VerdictStatus.REJECT
    assert "timed out" in verdict.reason


def test_missing_command_returns_reject():
    with patch("team_executor.quick_check.subprocess.run", side_effect=FileNotFoundError("nope")):
        verdict = quick_check.run_quick_checks([QuickCheck(command="nonexistent-bin")], _stage(), "/wd", 0)
    assert verdict.status == VerdictStatus.REJECT
    assert "not found" in verdict.reason


def test_empty_checks_returns_accept():
    verdict = quick_check.run_quick_checks([], _stage(), "/wd", round_num=0)
    assert verdict.status == VerdictStatus.ACCEPT
