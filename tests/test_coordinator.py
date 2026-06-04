# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from unittest.mock import patch


from team_executor.coordinator import TeamCoordinator, _build_execution_batches
from team_executor.models import (
    CycleVerdict,
    GoalStage,
    Role,
    StageResult,
    TeamConfig,
    VerifierRole,
    VerdictStatus,
)


def _role(name: str = "worker", model: str = "claude-sonnet-4-6") -> Role:
    return Role(name=name, model=model, system_prompt=f"You are {name}.")


def _vr(kind: str = "reviewer") -> VerifierRole:
    return VerifierRole(kind=kind, role=_role(kind))


def _make_config(max_cycles: int = 3) -> TeamConfig:
    return TeamConfig(
        team_name="test",
        coordinator=_role("coordinator", "claude-opus-4-7"),
        workers=[_role("implementer")],
        verifiers=[_vr("reviewer")],
        max_cycles_per_stage=max_cycles,
    )


def _stage(index: int = 0, parallel_group: int | None = None) -> GoalStage:
    return GoalStage(
        index=index, description=f"Stage {index}",
        acceptance_criteria=["done"], parallel_group=parallel_group,
    )


def _accept(round_num: int = 0) -> CycleVerdict:
    return CycleVerdict(status=VerdictStatus.ACCEPT, reason="ok", round=round_num)


def _reject(round_num: int = 0) -> CycleVerdict:
    return CycleVerdict(status=VerdictStatus.REJECT, reason="not done", round=round_num)


class TestBuildExecutionBatches:
    def test_all_sequential(self):
        stages = [_stage(0), _stage(1), _stage(2)]
        batches = _build_execution_batches(stages)
        assert len(batches) == 3
        assert all(len(b) == 1 for b in batches)

    def test_two_parallel_then_sequential(self):
        stages = [_stage(0, parallel_group=1), _stage(1, parallel_group=1), _stage(2)]
        batches = _build_execution_batches(stages)
        assert len(batches) == 2
        assert len(batches[0]) == 2
        assert len(batches[1]) == 1

    def test_sequential_then_parallel(self):
        stages = [_stage(0), _stage(1, parallel_group=2), _stage(2, parallel_group=2)]
        batches = _build_execution_batches(stages)
        assert len(batches) == 2
        assert len(batches[0]) == 1
        assert len(batches[1]) == 2

    def test_multiple_parallel_groups(self):
        stages = [
            _stage(0, parallel_group=1), _stage(1, parallel_group=1),
            _stage(2, parallel_group=2), _stage(3, parallel_group=2),
        ]
        batches = _build_execution_batches(stages)
        assert len(batches) == 2
        assert len(batches[0]) == 2
        assert len(batches[1]) == 2

    def test_empty_stages(self):
        assert _build_execution_batches([]) == []


class TestTeamCoordinator:
    def test_single_stage_accept_on_first_cycle(self):
        coordinator = TeamCoordinator(_make_config(), working_dir="/tmp")
        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[_stage(0)]),
            patch("team_executor.coordinator.worker_module.run_worker", return_value=(True, "output")),
            patch("team_executor.coordinator.verifier_module.verify_stage", return_value=_accept(0)),
            patch("team_executor.coordinator.summarizer_module.summarize_stage", return_value="summary"),
        ):
            results = coordinator.run("Build something")
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].cycles == 1

    def test_reject_then_accept(self):
        coordinator = TeamCoordinator(_make_config(max_cycles=3), working_dir="/tmp")
        verdicts = iter([_reject(0), _accept(1)])
        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[_stage(0)]),
            patch("team_executor.coordinator.worker_module.run_worker", return_value=(True, "output")),
            patch("team_executor.coordinator.verifier_module.verify_stage", side_effect=verdicts),
            patch("team_executor.coordinator.summarizer_module.summarize_stage", return_value="summary"),
        ):
            results = coordinator.run("Goal")
        assert results[0].success is True
        assert results[0].cycles == 2

    def test_max_cycles_exceeded_returns_failed(self):
        coordinator = TeamCoordinator(_make_config(max_cycles=2), working_dir="/tmp")
        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[_stage(0)]),
            patch("team_executor.coordinator.worker_module.run_worker", return_value=(False, "bad")),
            patch("team_executor.coordinator.verifier_module.verify_stage", side_effect=[_reject(0), _reject(1)]),
            patch("team_executor.coordinator.summarizer_module.summarize_stage", return_value="summary"),
        ):
            results = coordinator.run("Goal")
        assert results[0].success is False
        assert results[0].cycles == 2

    def test_multiple_sequential_stages(self):
        coordinator = TeamCoordinator(_make_config(), working_dir="/tmp")
        stages = [_stage(0), _stage(1), _stage(2)]
        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=stages),
            patch("team_executor.coordinator.worker_module.run_worker", return_value=(True, "ok")),
            patch("team_executor.coordinator.verifier_module.verify_stage", return_value=_accept(0)),
            patch("team_executor.coordinator.summarizer_module.summarize_stage", return_value="summary"),
        ):
            results = coordinator.run("Big goal")
        assert len(results) == 3
        assert all(r.success for r in results)

    def test_rejection_reason_passed_to_next_worker(self):
        coordinator = TeamCoordinator(_make_config(max_cycles=3), working_dir="/tmp")
        worker_calls = []

        def tracking_worker(role, stage, goal_text, working_dir, rejection_reason=None, backend="claude_code"):
            worker_calls.append(rejection_reason)
            return (True, "output")

        verdicts = iter([_reject(0), _accept(1)])
        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[_stage(0)]),
            patch("team_executor.coordinator.worker_module.run_worker", side_effect=tracking_worker),
            patch("team_executor.coordinator.verifier_module.verify_stage", side_effect=verdicts),
            patch("team_executor.coordinator.summarizer_module.summarize_stage", return_value="summary"),
        ):
            coordinator.run("Goal")
        assert worker_calls[0] is None
        assert worker_calls[1] == "not done"

    def test_parallel_stages_both_run(self):
        coordinator = TeamCoordinator(_make_config(), working_dir="/tmp")
        stages = [_stage(0, parallel_group=1), _stage(1, parallel_group=1)]
        executed = []

        def tracking_worker(role, stage, goal_text, working_dir, rejection_reason=None, backend="claude_code"):
            executed.append(stage.index)
            return (True, f"output {stage.index}")

        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=stages),
            patch("team_executor.coordinator.worker_module.run_worker", side_effect=tracking_worker),
            patch("team_executor.coordinator.verifier_module.verify_stage", return_value=_accept(0)),
            patch("team_executor.coordinator.summarizer_module.summarize_stage", return_value="summary"),
            patch("team_executor.coordinator.checkpoint_module.write_checkpoint"),
            patch("team_executor.coordinator.checkpoint_module.delete_checkpoint"),
        ):
            results = coordinator.run("Goal", run_id="test-run")
        assert sorted(executed) == [0, 1]
        assert len(results) == 2

    def test_checkpoint_resume_skips_completed_stage(self, tmp_path):
        coordinator = TeamCoordinator(_make_config(), working_dir=str(tmp_path))
        stage0 = _stage(0)
        stage1 = _stage(1)
        completed_result = StageResult(stage=stage0, output="already done", cycles=1, verdicts=[_accept(0)], success=True)

        worker_calls = []
        def tracking_worker(role, stage, goal_text, working_dir, rejection_reason=None, backend="claude_code"):
            worker_calls.append(stage.index)
            return (True, "output")

        with (
            patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[stage0, stage1]),
            patch("team_executor.coordinator.checkpoint_module.read_checkpoint", return_value=[completed_result]),
            patch("team_executor.coordinator.checkpoint_module.write_checkpoint"),
            patch("team_executor.coordinator.checkpoint_module.delete_checkpoint"),
            patch("team_executor.coordinator.worker_module.run_worker", side_effect=tracking_worker),
            patch("team_executor.coordinator.verifier_module.verify_stage", return_value=_accept(0)),
            patch("team_executor.coordinator.summarizer_module.summarize_stage", return_value="summary"),
        ):
            results = coordinator.run("Goal", run_id="resume-run")

        # Only stage 1 should have had a worker call
        assert worker_calls == [1]
        assert results[0].output == "already done"
        assert results[1].success is True
