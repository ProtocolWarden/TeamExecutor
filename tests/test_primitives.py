# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
"""Tests for TeamExecutor primitives 1–4:
1. persist_changes + worktree isolation
2. QuickCheck scripted verification
3. Adaptive advisor
4. auto_commit
"""
from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch


from team_executor.models import (
    CycleVerdict,
    GoalStage,
    QuickCheck,
    Role,
    StageResult,
    TeamConfig,
    VerifierRole,
    VerdictStatus,
)
from team_executor.quick_check import run_quick_checks
from team_executor.verifier import verify_stage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _role(name: str = "worker") -> Role:
    return Role(name=name, model="claude-sonnet-4-6", system_prompt=f"You are {name}.")


def _vr(kind: str = "reviewer") -> VerifierRole:
    return VerifierRole(kind=kind, role=_role(kind))


def _stage(index: int = 0, **kwargs) -> GoalStage:
    return GoalStage(index=index, description="Do stuff", acceptance_criteria=["done"], **kwargs)


def _config(**kwargs) -> TeamConfig:
    return TeamConfig(
        team_name="test",
        coordinator=_role("coordinator"),
        workers=[_role("implementer")],
        verifiers=[_vr()],
        **kwargs,
    )


def _accept_result(stage: GoalStage) -> StageResult:
    return StageResult(
        stage=stage,
        output="done",
        cycles=1,
        verdicts=[CycleVerdict(status=VerdictStatus.ACCEPT, reason="ok", round=0)],
        success=True,
    )


# ---------------------------------------------------------------------------
# Primitive 1: GoalStage.persist_changes field + QuickCheck type exist
# ---------------------------------------------------------------------------

class TestModelFields:
    def test_goal_stage_persist_changes_default_false(self):
        s = _stage()
        assert s.persist_changes is False

    def test_goal_stage_persist_changes_true(self):
        s = _stage(persist_changes=True)
        assert s.persist_changes is True

    def test_goal_stage_verification_default_full(self):
        s = _stage()
        assert s.verification == "full"

    def test_goal_stage_verification_skip(self):
        s = _stage(verification="skip")
        assert s.verification == "skip"

    def test_goal_stage_verification_quick_checks(self):
        checks = [QuickCheck(command="pytest", description="run tests")]
        s = _stage(verification=checks)
        assert isinstance(s.verification, list)
        assert s.verification[0].command == "pytest"

    def test_team_config_adaptive_advisor_default_false(self):
        assert _config().adaptive_advisor is False

    def test_team_config_auto_commit_default_false(self):
        assert _config().auto_commit is False

    def test_quick_check_fields(self):
        qc = QuickCheck(command="make test", expected_exit_code=0, description="unit tests")
        assert qc.command == "make test"
        assert qc.expected_exit_code == 0
        assert qc.description == "unit tests"

    def test_quick_check_default_exit_code(self):
        qc = QuickCheck(command="echo hi")
        assert qc.expected_exit_code == 0


# ---------------------------------------------------------------------------
# Primitive 2: QuickCheck verification
# ---------------------------------------------------------------------------

class TestQuickCheckVerification:
    def test_skip_verification_accepts_immediately(self):
        stage = _stage(verification="skip")
        verdict = verify_stage(stage, "output", [_vr()], "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.ACCEPT
        assert "skip" in verdict.reason

    def test_quick_check_pass_returns_accept(self):
        stage = _stage(verification=[QuickCheck(command="true")])
        with patch("team_executor.quick_check.subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stderr="", stdout="")
            verdict = verify_stage(stage, "out", [_vr()], "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.ACCEPT
        assert "passed" in verdict.reason

    def test_quick_check_fail_returns_reject(self):
        stage = _stage(verification=[QuickCheck(command="false", description="must fail")])
        with patch("team_executor.quick_check.subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=1, stderr="error output", stdout="")
            verdict = verify_stage(stage, "out", [_vr()], "/tmp", round_num=1)
        assert verdict.status == VerdictStatus.REJECT
        assert "must fail" in verdict.reason
        assert verdict.round == 1

    def test_quick_check_multiple_all_pass(self):
        checks = [QuickCheck(command="cmd1"), QuickCheck(command="cmd2")]
        stage = _stage(verification=checks)
        with patch("team_executor.quick_check.subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stderr="", stdout="")
            verdict = run_quick_checks(checks, stage, "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.ACCEPT
        assert mock_run.call_count == 2

    def test_quick_check_first_fail_short_circuits(self):
        checks = [QuickCheck(command="cmd1"), QuickCheck(command="cmd2")]
        stage = _stage(verification=checks)
        with patch("team_executor.quick_check.subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=1, stderr="", stdout="")
            verdict = run_quick_checks(checks, stage, "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.REJECT
        assert mock_run.call_count == 1

    def test_quick_check_timeout_rejects(self):
        checks = [QuickCheck(command="sleep 9999", description="timeout check")]
        stage = _stage(verification=checks)
        with patch("team_executor.quick_check.subprocess.run", side_effect=subprocess.TimeoutExpired("sleep", 120)):
            verdict = run_quick_checks(checks, stage, "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.REJECT
        assert "timed out" in verdict.reason

    def test_quick_check_command_not_found_rejects(self):
        checks = [QuickCheck(command="nonexistent_cmd_xyz")]
        stage = _stage(verification=checks)
        with patch("team_executor.quick_check.subprocess.run", side_effect=FileNotFoundError("not found")):
            verdict = run_quick_checks(checks, stage, "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.REJECT

    def test_quick_check_custom_expected_exit_code(self):
        checks = [QuickCheck(command="cmd", expected_exit_code=42)]
        stage = _stage(verification=checks)
        with patch("team_executor.quick_check.subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=42, stderr="", stdout="")
            verdict = run_quick_checks(checks, stage, "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.ACCEPT

    def test_skip_does_not_call_agent(self):
        stage = _stage(verification="skip")
        with patch("team_executor.verifier.call_agent") as mock_agent:
            verify_stage(stage, "out", [_vr()], "/tmp", round_num=0)
        mock_agent.assert_not_called()

    def test_quick_check_does_not_call_agent(self):
        stage = _stage(verification=[QuickCheck(command="true")])
        with patch("team_executor.verifier.call_agent") as mock_agent, \
             patch("team_executor.quick_check.subprocess.run") as mock_run:
            mock_run.return_value = SimpleNamespace(returncode=0, stderr="", stdout="")
            verify_stage(stage, "out", [_vr()], "/tmp", round_num=0)
        mock_agent.assert_not_called()


# ---------------------------------------------------------------------------
# Primitive 3: Adaptive advisor
# ---------------------------------------------------------------------------

class TestAdaptiveAdvisor:
    def _make_advisor_response(self, action: str, reason: str = "ok", **extra) -> str:
        d = {"action": action, "reason": reason, **extra}
        return json.dumps(d)

    def test_advisor_continue_does_not_mutate_stages(self):
        from team_executor.advisor import advise_after_stage
        stage = _stage(0)
        result = _accept_result(stage)
        with patch("team_executor.advisor.call_agent", return_value=self._make_advisor_response("continue")):
            advice = advise_after_stage(
                goal_text="do things",
                stage=stage,
                result=result,
                remaining_stages=[_stage(1)],
                next_index=2,
                config=_config(adaptive_advisor=True),
                working_dir="/tmp",
                backend="claude_code",
            )
        assert advice.action == "continue"
        assert advice.new_stage is None

    def test_advisor_done_action(self):
        from team_executor.advisor import advise_after_stage
        stage = _stage(0)
        result = _accept_result(stage)
        with patch("team_executor.advisor.call_agent", return_value=self._make_advisor_response("done", "goal achieved")):
            advice = advise_after_stage("goal", stage, result, [], 1, _config(), "/tmp", "claude_code")
        assert advice.action == "done"

    def test_advisor_add_stage_creates_new_goal_stage(self):
        from team_executor.advisor import advise_after_stage
        stage = _stage(0)
        result = _accept_result(stage)
        resp = self._make_advisor_response(
            "add_stage",
            "needs extra work",
            new_stage_description="Cleanup artifacts",
            new_stage_criteria=["artifacts removed"],
        )
        with patch("team_executor.advisor.call_agent", return_value=resp):
            advice = advise_after_stage("goal", stage, result, [], 5, _config(), "/tmp", "claude_code")
        assert advice.action == "add_stage"
        assert advice.new_stage is not None
        assert advice.new_stage.index == 5
        assert advice.new_stage.description == "Cleanup artifacts"
        assert advice.new_stage.acceptance_criteria == ["artifacts removed"]

    def test_advisor_malformed_json_defaults_to_continue(self):
        from team_executor.advisor import advise_after_stage
        stage = _stage(0)
        result = _accept_result(stage)
        with patch("team_executor.advisor.call_agent", return_value="not json"):
            advice = advise_after_stage("goal", stage, result, [], 1, _config(), "/tmp", "claude_code")
        assert advice.action == "continue"

    def test_advisor_call_agent_exception_defaults_to_continue(self):
        from team_executor.advisor import advise_after_stage
        stage = _stage(0)
        result = _accept_result(stage)
        with patch("team_executor.advisor.call_agent", side_effect=RuntimeError("network error")):
            advice = advise_after_stage("goal", stage, result, [], 1, _config(), "/tmp", "claude_code")
        assert advice.action == "continue"

    def test_advisor_unknown_action_defaults_to_continue(self):
        from team_executor.advisor import advise_after_stage
        stage = _stage(0)
        result = _accept_result(stage)
        with patch("team_executor.advisor.call_agent", return_value=json.dumps({"action": "explode", "reason": "chaos"})):
            advice = advise_after_stage("goal", stage, result, [], 1, _config(), "/tmp", "claude_code")
        assert advice.action == "continue"


# ---------------------------------------------------------------------------
# Primitive 4: auto_commit
# ---------------------------------------------------------------------------

class TestAutoCommit:
    def _setup_coordinator_mocks(self, config: TeamConfig):
        """Return a patched coordinator with instant accept on all calls."""
        from team_executor.coordinator import TeamCoordinator
        coord = TeamCoordinator(config, working_dir="/tmp/test_repo")
        return coord

    def test_auto_commit_called_on_success(self):
        from team_executor.coordinator import TeamCoordinator
        config = _config(auto_commit=True)
        coord = TeamCoordinator(config, working_dir="/tmp/test_repo")
        stage = _stage(0)

        with patch.object(coord, "_run_stage", return_value=_accept_result(stage)), \
             patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[stage]), \
             patch("team_executor.coordinator.checkpoint_module.read_checkpoint", return_value=None), \
             patch("team_executor.coordinator.checkpoint_module.write_checkpoint"), \
             patch("team_executor.coordinator.checkpoint_module.delete_checkpoint"), \
             patch("team_executor.coordinator.git_ops.commit_stage") as mock_commit:
            coord.run("do things", run_id=None)

        mock_commit.assert_called_once_with("/tmp/test_repo", stage)

    def test_auto_commit_not_called_on_failure(self):
        from team_executor.coordinator import TeamCoordinator
        config = _config(auto_commit=True)
        coord = TeamCoordinator(config, working_dir="/tmp/test_repo")
        stage = _stage(0)
        fail_result = StageResult(stage=stage, output="", cycles=3, verdicts=[], success=False)

        with patch.object(coord, "_run_stage", return_value=fail_result), \
             patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[stage]), \
             patch("team_executor.coordinator.checkpoint_module.read_checkpoint", return_value=None), \
             patch("team_executor.coordinator.checkpoint_module.write_checkpoint"), \
             patch("team_executor.coordinator.checkpoint_module.delete_checkpoint"), \
             patch("team_executor.coordinator.git_ops.commit_stage") as mock_commit:
            coord.run("do things", run_id=None)

        mock_commit.assert_not_called()

    def test_auto_commit_false_never_commits(self):
        from team_executor.coordinator import TeamCoordinator
        config = _config(auto_commit=False)
        coord = TeamCoordinator(config, working_dir="/tmp/test_repo")
        stage = _stage(0)

        with patch.object(coord, "_run_stage", return_value=_accept_result(stage)), \
             patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[stage]), \
             patch("team_executor.coordinator.checkpoint_module.read_checkpoint", return_value=None), \
             patch("team_executor.coordinator.checkpoint_module.write_checkpoint"), \
             patch("team_executor.coordinator.checkpoint_module.delete_checkpoint"), \
             patch("team_executor.coordinator.git_ops.commit_stage") as mock_commit:
            coord.run("do things", run_id=None)

        mock_commit.assert_not_called()


# ---------------------------------------------------------------------------
# Primitive 3 (coordinator): advisor early-exit via "done"
# ---------------------------------------------------------------------------

class TestAdaptiveAdvisorCoordinator:
    def test_advisor_done_stops_early(self):
        from team_executor.coordinator import TeamCoordinator
        from team_executor.advisor import AdvisorResult
        config = _config(adaptive_advisor=True)
        coord = TeamCoordinator(config, working_dir="/tmp")
        s0 = _stage(0)
        s1 = _stage(1)

        with patch.object(coord, "_run_stage", return_value=_accept_result(s0)), \
             patch("team_executor.coordinator.stage_planner.plan_stages", return_value=[s0, s1]), \
             patch("team_executor.coordinator.checkpoint_module.read_checkpoint", return_value=None), \
             patch("team_executor.coordinator.checkpoint_module.write_checkpoint"), \
             patch("team_executor.coordinator.checkpoint_module.delete_checkpoint"), \
             patch("team_executor.coordinator.advisor_module.advise_after_stage",
                   return_value=AdvisorResult(action="done", reason="all done")):
            results = coord.run("do things", run_id=None)

        # Should only have stage 0 result
        assert len(results) == 1
        assert results[0].stage.index == 0
