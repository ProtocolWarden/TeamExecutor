# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from team_executor.coordinator import TeamCoordinator
from team_executor.models import (
    CycleVerdict,
    GoalStage,
    Role,
    StageResult,
    TeamConfig,
    VerdictStatus,
)


def _make_config(max_cycles: int = 3) -> TeamConfig:
    coordinator = Role(
        name="coordinator",
        model="claude-opus-4-7",
        system_prompt="You coordinate.",
        max_turns=20,
    )
    worker = Role(
        name="implementer",
        model="claude-sonnet-4-6",
        system_prompt="You implement.",
    )
    verifier = Role(
        name="verifier",
        model="claude-sonnet-4-6",
        system_prompt="You verify.",
    )
    return TeamConfig(
        team_name="test",
        coordinator=coordinator,
        workers=[worker],
        verifier=verifier,
        max_cycles_per_stage=max_cycles,
    )


def _stage(index: int = 0) -> GoalStage:
    return GoalStage(index=index, description=f"Stage {index}", acceptance_criteria=["done"])


def _accept_verdict(round_num: int = 0) -> CycleVerdict:
    return CycleVerdict(status=VerdictStatus.ACCEPT, reason="ok", round=round_num)


def _reject_verdict(round_num: int = 0) -> CycleVerdict:
    return CycleVerdict(status=VerdictStatus.REJECT, reason="not done", round=round_num)


class TestTeamCoordinator:
    def test_single_stage_accept_on_first_cycle(self):
        client = MagicMock()
        coordinator = TeamCoordinator(_make_config(), client, working_dir="/tmp")

        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[_stage(0)]),
            patch("team_executor.coordinator.worker_module.run_worker", return_value=(True, "output")),
            patch("team_executor.coordinator.verifier_module.verify_stage", return_value=_accept_verdict(0)),
        ):
            results = coordinator.run("Build something")

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].cycles == 1
        assert results[0].output == "output"

    def test_reject_then_accept(self):
        client = MagicMock()
        coordinator = TeamCoordinator(_make_config(max_cycles=3), client, working_dir="/tmp")

        verdicts = iter([_reject_verdict(0), _accept_verdict(1)])

        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[_stage(0)]),
            patch("team_executor.coordinator.worker_module.run_worker", return_value=(True, "output")),
            patch("team_executor.coordinator.verifier_module.verify_stage", side_effect=verdicts),
        ):
            results = coordinator.run("Goal")

        assert results[0].success is True
        assert results[0].cycles == 2
        assert len(results[0].verdicts) == 2

    def test_max_cycles_exceeded_returns_failed(self):
        client = MagicMock()
        coordinator = TeamCoordinator(_make_config(max_cycles=2), client, working_dir="/tmp")

        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[_stage(0)]),
            patch("team_executor.coordinator.worker_module.run_worker", return_value=(False, "bad")),
            patch(
                "team_executor.coordinator.verifier_module.verify_stage",
                side_effect=[_reject_verdict(0), _reject_verdict(1)],
            ),
        ):
            results = coordinator.run("Goal")

        assert results[0].success is False
        assert results[0].cycles == 2

    def test_multiple_stages_returned(self):
        client = MagicMock()
        coordinator = TeamCoordinator(_make_config(), client, working_dir="/tmp")
        stages = [_stage(0), _stage(1), _stage(2)]

        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=stages),
            patch("team_executor.coordinator.worker_module.run_worker", return_value=(True, "ok")),
            patch(
                "team_executor.coordinator.verifier_module.verify_stage",
                return_value=_accept_verdict(0),
            ),
        ):
            results = coordinator.run("Big goal")

        assert len(results) == 3
        assert all(r.success for r in results)

    def test_rejection_reason_passed_to_next_worker_call(self):
        client = MagicMock()
        coordinator = TeamCoordinator(_make_config(max_cycles=3), client, working_dir="/tmp")

        worker_calls = []

        def tracking_worker(role, stage, goal_text, working_dir, rejection_reason=None):
            worker_calls.append(rejection_reason)
            return (True, "output")

        verdicts = iter([_reject_verdict(0), _accept_verdict(1)])

        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[_stage(0)]),
            patch("team_executor.coordinator.worker_module.run_worker", side_effect=tracking_worker),
            patch("team_executor.coordinator.verifier_module.verify_stage", side_effect=verdicts),
        ):
            coordinator.run("Goal")

        assert worker_calls[0] is None  # first call has no rejection
        assert worker_calls[1] == "not done"  # second call includes rejection reason
