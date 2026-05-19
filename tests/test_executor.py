# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from team_executor.executor import TeamExecutorRunner
from team_executor.models import (
    CycleVerdict,
    GoalStage,
    Role,
    StageResult,
    TeamConfig,
    VerdictStatus,
)


def _make_config() -> TeamConfig:
    return TeamConfig(
        team_name="default",
        coordinator=Role(name="coordinator", model="claude-opus-4-7", system_prompt="coord"),
        workers=[Role(name="worker", model="claude-sonnet-4-6", system_prompt="work")],
        verifier=Role(name="verifier", model="claude-sonnet-4-6", system_prompt="verify"),
        max_cycles_per_stage=3,
    )


def _success_stage_result() -> StageResult:
    stage = GoalStage(index=0, description="Do X", acceptance_criteria=["X done"])
    verdict = CycleVerdict(status=VerdictStatus.ACCEPT, reason="ok", round=0)
    return StageResult(stage=stage, output="done", cycles=1, verdicts=[verdict], success=True)


def _failed_stage_result() -> StageResult:
    stage = GoalStage(index=0, description="Do Y", acceptance_criteria=["Y done"])
    verdict = CycleVerdict(status=VerdictStatus.REJECT, reason="fail", round=2)
    return StageResult(stage=stage, output="", cycles=3, verdicts=[verdict], success=False)


class TestTeamExecutorRunner:
    def test_successful_run_returns_succeeded_status(self, tmp_path):
        runner = TeamExecutorRunner(team_name="default", working_dir=str(tmp_path), api_key="fake")

        with (
            patch("team_executor.executor.load_team_config", return_value=_make_config()),
            patch("team_executor.executor.anthropic.Anthropic"),
            patch(
                "team_executor.executor.TeamCoordinator.run",
                return_value=[_success_stage_result()],
            ),
        ):
            result = runner.run("Build something")

        assert result.status == "succeeded"
        assert result.exit_code == 0
        assert result.error_summary is None

    def test_failed_stage_returns_failed_status(self, tmp_path):
        runner = TeamExecutorRunner(team_name="default", working_dir=str(tmp_path), api_key="fake")

        with (
            patch("team_executor.executor.load_team_config", return_value=_make_config()),
            patch("team_executor.executor.anthropic.Anthropic"),
            patch(
                "team_executor.executor.TeamCoordinator.run",
                return_value=[_failed_stage_result()],
            ),
        ):
            result = runner.run("Build something")

        assert result.status == "failed"
        assert result.exit_code == 1
        assert result.error_summary is not None

    def test_config_load_exception_returns_failed(self, tmp_path):
        runner = TeamExecutorRunner(team_name="missing", working_dir=str(tmp_path), api_key="fake")

        with patch("team_executor.executor.load_team_config", side_effect=FileNotFoundError("no config")):
            result = runner.run("Goal")

        assert result.status == "failed"
        assert "no config" in result.error_summary

    def test_invocation_id_is_set(self, tmp_path):
        runner = TeamExecutorRunner(working_dir=str(tmp_path), api_key="fake")

        with (
            patch("team_executor.executor.load_team_config", return_value=_make_config()),
            patch("team_executor.executor.anthropic.Anthropic"),
            patch(
                "team_executor.executor.TeamCoordinator.run",
                return_value=[_success_stage_result()],
            ),
        ):
            result = runner.run("Goal")

        assert result.invocation_id is not None
        assert len(result.invocation_id) > 0

    def test_metadata_contains_evidence(self, tmp_path):
        runner = TeamExecutorRunner(working_dir=str(tmp_path), api_key="fake")

        with (
            patch("team_executor.executor.load_team_config", return_value=_make_config()),
            patch("team_executor.executor.anthropic.Anthropic"),
            patch(
                "team_executor.executor.TeamCoordinator.run",
                return_value=[_success_stage_result()],
            ),
        ):
            result = runner.run("Goal")

        assert "stages_total" in result.metadata
        assert result.metadata["stages_total"] == "1"
