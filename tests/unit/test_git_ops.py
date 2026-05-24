# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from team_executor import git_ops
from team_executor.models import GoalStage


def _stage(index: int = 1) -> GoalStage:
    return GoalStage(index=index, description="do the thing", acceptance_criteria=[])


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["git"], returncode=returncode, stdout=stdout, stderr="")


def test_all_git_subprocess_calls_pass_timeout():
    """Every subprocess.run in git_ops must carry an explicit timeout (C11)."""
    with patch("team_executor.git_ops.subprocess.run") as run:
        run.return_value = _completed(stdout="?? file\n")
        git_ops.commit_stage("/wd", _stage())
        assert run.call_count >= 1
        for call in run.call_args_list:
            assert call.kwargs.get("timeout") is not None, call


def test_create_worktree_returns_tmp_path_and_runs_git_add():
    with patch("team_executor.git_ops.tempfile.mkdtemp", return_value="/tmp/te_stage_2_x") as mk, \
         patch("team_executor.git_ops.subprocess.run", return_value=_completed()) as run:
        path = git_ops.create_worktree("/base", 2)
    assert path == "/tmp/te_stage_2_x"
    mk.assert_called_once()
    args = run.call_args_list[0].args[0]
    assert args[:3] == ["git", "worktree", "add"]
    assert "/tmp/te_stage_2_x" in args


def test_remove_worktree_prunes_on_failure():
    calls = []

    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        if cmd[:3] == ["git", "worktree", "remove"]:
            raise subprocess.CalledProcessError(1, cmd)
        return _completed()

    with patch("team_executor.git_ops.subprocess.run", side_effect=fake_run):
        git_ops.remove_worktree("/base", "/wt")

    assert ["git", "worktree", "remove", "--force", "/wt"] in calls
    assert ["git", "worktree", "prune"] in calls


def test_commit_worktree_returns_none_when_clean():
    with patch("team_executor.git_ops.subprocess.run", return_value=_completed(stdout="   \n")):
        assert git_ops.commit_worktree("/wt", _stage()) is None


def test_commit_worktree_commits_and_returns_sha():
    seq = [
        _completed(stdout="?? f\n"),                       # status --porcelain (dirty)
        _completed(),                                      # git add -A
        _completed(stdout="[detached HEAD abc1234] msg"),  # git commit
    ]

    def fake_run(cmd, *a, **kw):
        return seq.pop(0)

    with patch("team_executor.git_ops.subprocess.run", side_effect=fake_run):
        sha = git_ops.commit_worktree("/wt", _stage())
    assert sha == "msg"  # last token of commit stdout


def test_merge_worktree_into_base_raises_on_conflict():
    def fake_run(cmd, *a, **kw):
        if cmd[:2] == ["git", "cherry-pick"]:
            raise subprocess.CalledProcessError(1, cmd, stderr="conflict")
        return _completed()

    with patch("team_executor.git_ops.subprocess.run", side_effect=fake_run):
        with pytest.raises(subprocess.CalledProcessError):
            git_ops.merge_worktree_into_base("/base", "deadbeef", _stage())


def test_commit_stage_returns_false_when_clean():
    with patch("team_executor.git_ops.subprocess.run", return_value=_completed(stdout="")):
        assert git_ops.commit_stage("/wd", _stage()) is False


def test_commit_stage_returns_true_on_commit():
    def fake_run(cmd, *a, **kw):
        if cmd[:2] == ["git", "status"]:
            return _completed(stdout=" M f\n")
        return _completed(stdout="[main abc] msg")

    with patch("team_executor.git_ops.subprocess.run", side_effect=fake_run):
        assert git_ops.commit_stage("/wd", _stage()) is True


def test_commit_stage_returns_false_when_commit_fails():
    def fake_run(cmd, *a, **kw):
        if cmd[:2] == ["git", "status"]:
            return _completed(stdout=" M f\n")
        if cmd[:2] == ["git", "add"]:
            return _completed()
        raise subprocess.CalledProcessError(1, cmd, stderr="nothing to commit")

    with patch("team_executor.git_ops.subprocess.run", side_effect=fake_run):
        assert git_ops.commit_stage("/wd", _stage()) is False
