# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from unittest.mock import patch


from team_executor.executor import TeamExecutorRunner
from team_executor.models import (
    CycleVerdict,
    GoalStage,
    Role,
    StageResult,
    TeamConfig,
    VerifierRole,
    VerdictStatus,
)


def _make_config() -> TeamConfig:
    return TeamConfig(
        team_name="standard",
        coordinator=Role(name="coordinator", model="claude-opus-4-7", system_prompt="coord"),
        workers=[Role(name="worker", model="claude-sonnet-4-6", system_prompt="work")],
        verifiers=[VerifierRole(kind="reviewer", role=Role(name="reviewer", model="claude-sonnet-4-6", system_prompt="verify"))],
        max_cycles_per_stage=3,
    )


def _success_result() -> StageResult:
    stage = GoalStage(index=0, description="Do X", acceptance_criteria=["X done"])
    verdict = CycleVerdict(status=VerdictStatus.ACCEPT, reason="ok", round=0)
    return StageResult(stage=stage, output="done", cycles=1, verdicts=[verdict], success=True)


def _failed_result() -> StageResult:
    stage = GoalStage(index=0, description="Do Y", acceptance_criteria=["Y done"])
    verdict = CycleVerdict(status=VerdictStatus.REJECT, reason="fail", round=2)
    return StageResult(stage=stage, output="", cycles=3, verdicts=[verdict], success=False)


class TestTeamExecutorRunner:
    def test_successful_run_returns_succeeded_status(self, tmp_path):
        runner = TeamExecutorRunner(working_dir=str(tmp_path))
        with (
            patch("team_executor.executor.load_team_config", return_value=_make_config()),
            patch("team_executor.executor.TeamCoordinator") as mock_coord_cls,
        ):
            mock_coord_cls.return_value.run.return_value = [_success_result()]
            result = runner.run("Build something")
        assert result.status == "succeeded"
        assert result.exit_code == 0
        assert result.error_summary is None

    def test_failed_stage_returns_failed_status(self, tmp_path):
        runner = TeamExecutorRunner(working_dir=str(tmp_path))
        with (
            patch("team_executor.executor.load_team_config", return_value=_make_config()),
            patch("team_executor.executor.TeamCoordinator") as mock_coord_cls,
        ):
            mock_coord_cls.return_value.run.return_value = [_failed_result()]
            result = runner.run("Build something")
        assert result.status == "failed"
        assert result.exit_code == 1
        assert result.error_summary is not None

    def test_config_load_exception_returns_failed(self, tmp_path):
        runner = TeamExecutorRunner(team_name="missing", working_dir=str(tmp_path))
        with patch("team_executor.executor.load_team_config", side_effect=FileNotFoundError("no config")):
            result = runner.run("Goal")
        assert result.status == "failed"
        assert "no config" in result.error_summary

    def test_invocation_id_forwarded(self, tmp_path):
        runner = TeamExecutorRunner(working_dir=str(tmp_path))
        with (
            patch("team_executor.executor.load_team_config", return_value=_make_config()),
            patch("team_executor.executor.TeamCoordinator") as mock_coord_cls,
        ):
            mock_coord_cls.return_value.run.return_value = [_success_result()]
            result = runner.run("Goal", invocation_id="test-run-123")
        assert result.invocation_id == "test-run-123"

    def test_invocation_id_generated_when_absent(self, tmp_path):
        runner = TeamExecutorRunner(working_dir=str(tmp_path))
        with (
            patch("team_executor.executor.load_team_config", return_value=_make_config()),
            patch("team_executor.executor.TeamCoordinator") as mock_coord_cls,
        ):
            mock_coord_cls.return_value.run.return_value = [_success_result()]
            result = runner.run("Goal")
        assert result.invocation_id is not None and len(result.invocation_id) > 0

    def test_metadata_contains_evidence(self, tmp_path):
        runner = TeamExecutorRunner(working_dir=str(tmp_path))
        with (
            patch("team_executor.executor.load_team_config", return_value=_make_config()),
            patch("team_executor.executor.TeamCoordinator") as mock_coord_cls,
        ):
            mock_coord_cls.return_value.run.return_value = [_success_result()]
            result = runner.run("Goal")
        assert result.metadata["stages_total"] == "1"

    def test_codex_backend_propagated(self, tmp_path):
        runner = TeamExecutorRunner(working_dir=str(tmp_path), worker_backend="codex_cli")
        config = _make_config()
        with (
            patch("team_executor.executor.load_team_config", return_value=config),
            patch("team_executor.executor.TeamCoordinator") as mock_coord_cls,
        ):
            mock_coord_cls.return_value.run.return_value = [_success_result()]
            runner.run("Goal")
        # config.worker_backend should have been set to codex_cli
        assert config.worker_backend == "codex_cli"
