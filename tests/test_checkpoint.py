# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import pytest

from team_executor.checkpoint import (
    delete_checkpoint,
    read_checkpoint,
    write_checkpoint,
)
from team_executor.models import CycleVerdict, GoalStage, StageResult, VerdictStatus


def _stage(index: int = 0, parallel_group: int | None = None) -> GoalStage:
    return GoalStage(index=index, description=f"Stage {index}", acceptance_criteria=["done"], parallel_group=parallel_group)


def _result(index: int = 0, success: bool = True) -> StageResult:
    verdict = CycleVerdict(
        status=VerdictStatus.ACCEPT if success else VerdictStatus.REJECT,
        reason="ok" if success else "fail",
        round=0,
    )
    return StageResult(stage=_stage(index), output=f"output {index}", cycles=1, verdicts=[verdict], success=success)


class TestCheckpoint:
    def test_write_and_read_roundtrip(self, tmp_path):
        results = [_result(0), _result(1)]
        write_checkpoint(str(tmp_path), "run-1", results)
        loaded = read_checkpoint(str(tmp_path), "run-1")
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0].stage.index == 0
        assert loaded[1].stage.index == 1
        assert loaded[0].success is True

    def test_read_nonexistent_returns_none(self, tmp_path):
        result = read_checkpoint(str(tmp_path), "no-such-run")
        assert result is None

    def test_failed_result_roundtrip(self, tmp_path):
        result = _result(0, success=False)
        write_checkpoint(str(tmp_path), "run-fail", [result])
        loaded = read_checkpoint(str(tmp_path), "run-fail")
        assert loaded[0].success is False
        assert loaded[0].verdicts[0].status == VerdictStatus.REJECT

    def test_parallel_group_preserved(self, tmp_path):
        stage = GoalStage(index=0, description="parallel", acceptance_criteria=[], parallel_group=3)
        verdict = CycleVerdict(status=VerdictStatus.ACCEPT, reason="ok", round=0)
        result = StageResult(stage=stage, output="out", cycles=1, verdicts=[verdict], success=True)
        write_checkpoint(str(tmp_path), "pg-run", [result])
        loaded = read_checkpoint(str(tmp_path), "pg-run")
        assert loaded[0].stage.parallel_group == 3

    def test_delete_removes_file(self, tmp_path):
        write_checkpoint(str(tmp_path), "run-del", [_result(0)])
        delete_checkpoint(str(tmp_path), "run-del")
        assert read_checkpoint(str(tmp_path), "run-del") is None

    def test_delete_missing_is_noop(self, tmp_path):
        # Deleting a checkpoint that was never written must not raise and must
        # leave no file behind / read back as absent.
        from team_executor.checkpoint import _checkpoint_path

        path = _checkpoint_path(str(tmp_path), "ghost-run")
        assert not path.exists()
        delete_checkpoint(str(tmp_path), "ghost-run")  # should not raise
        assert not path.exists()
        assert read_checkpoint(str(tmp_path), "ghost-run") is None

    def test_multiple_runs_isolated(self, tmp_path):
        write_checkpoint(str(tmp_path), "run-a", [_result(0)])
        write_checkpoint(str(tmp_path), "run-b", [_result(1)])
        a = read_checkpoint(str(tmp_path), "run-a")
        b = read_checkpoint(str(tmp_path), "run-b")
        assert a[0].stage.index == 0
        assert b[0].stage.index == 1

    def test_overwrite_replaces_existing(self, tmp_path):
        write_checkpoint(str(tmp_path), "run-1", [_result(0)])
        write_checkpoint(str(tmp_path), "run-1", [_result(0), _result(1)])
        loaded = read_checkpoint(str(tmp_path), "run-1")
        assert len(loaded) == 2
