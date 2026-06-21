# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from team_executor.evidence import aggregate_evidence, describe_failed_stages
from team_executor.models import CycleVerdict, GoalStage, StageResult, VerdictStatus


def _stage(index: int = 0) -> GoalStage:
    return GoalStage(index=index, description=f"Stage {index}", acceptance_criteria=[])


def _accept_verdict(round_num: int = 0) -> CycleVerdict:
    return CycleVerdict(status=VerdictStatus.ACCEPT, reason="ok", round=round_num)


def _reject_verdict(round_num: int = 0) -> CycleVerdict:
    return CycleVerdict(status=VerdictStatus.REJECT, reason="no", round=round_num)


class TestAggregateEvidence:
    def test_all_success(self):
        results = [
            StageResult(stage=_stage(0), output="ok", cycles=1, verdicts=[_accept_verdict()], success=True),
            StageResult(stage=_stage(1), output="ok", cycles=1, verdicts=[_accept_verdict()], success=True),
        ]
        ev = aggregate_evidence(results)
        assert ev["stages_total"] == 2
        assert ev["stages_succeeded"] == 2
        assert ev["stages_failed"] == 0
        assert ev["total_cycles"] == 2
        assert ev["rejection_rounds"] == 0

    def test_mixed_results(self):
        results = [
            StageResult(
                stage=_stage(0),
                output="ok",
                cycles=2,
                verdicts=[_reject_verdict(0), _accept_verdict(1)],
                success=True,
            ),
            StageResult(
                stage=_stage(1),
                output="bad",
                cycles=3,
                verdicts=[_reject_verdict(0), _reject_verdict(1), _reject_verdict(2)],
                success=False,
            ),
        ]
        ev = aggregate_evidence(results)
        assert ev["stages_total"] == 2
        assert ev["stages_succeeded"] == 1
        assert ev["stages_failed"] == 1
        assert ev["total_cycles"] == 5
        assert ev["rejection_rounds"] == 4  # 1 reject in stage 0 + 3 rejects in stage 1

    def test_empty_results(self):
        ev = aggregate_evidence([])
        assert ev["stages_total"] == 0
        assert ev["stages_succeeded"] == 0
        assert ev["stages_failed"] == 0
        assert ev["total_cycles"] == 0
        assert ev["rejection_rounds"] == 0

    def test_single_failed_stage(self):
        results = [
            StageResult(
                stage=_stage(0),
                output="",
                cycles=3,
                verdicts=[_reject_verdict(0), _reject_verdict(1), _reject_verdict(2)],
                success=False,
            )
        ]
        ev = aggregate_evidence(results)
        assert ev["stages_failed"] == 1
        assert ev["rejection_rounds"] == 3


class TestDescribeFailedStages:
    def test_empty_when_all_succeed(self):
        results = [
            StageResult(stage=_stage(0), output="ok", cycles=1, verdicts=[_accept_verdict()], success=True),
        ]
        assert describe_failed_stages(results) == ""

    def test_surfaces_index_description_and_last_reason(self):
        stage = GoalStage(index=3, description="Implement the alert", acceptance_criteria=[])
        results = [
            StageResult(stage=_stage(0), output="ok", cycles=1, verdicts=[_accept_verdict()], success=True),
            StageResult(
                stage=stage,
                output="...",
                cycles=2,
                verdicts=[_reject_verdict(0), CycleVerdict(status=VerdictStatus.REJECT, reason="missing tests", round=1)],
                success=False,
            ),
        ]
        out = describe_failed_stages(results)
        assert "stage 3" in out
        assert "Implement the alert" in out
        assert "missing tests" in out  # the LAST verdict's reason

    def test_falls_back_to_output_when_no_verdicts(self):
        results = [
            StageResult(stage=_stage(1), output="boom: traceback here", cycles=1, verdicts=[], success=False),
        ]
        out = describe_failed_stages(results)
        assert "stage 1" in out
        assert "boom: traceback here" in out

    def test_joins_multiple_failed_stages(self):
        results = [
            StageResult(stage=_stage(0), output="x", cycles=1, verdicts=[_reject_verdict()], success=False),
            StageResult(stage=_stage(1), output="y", cycles=1, verdicts=[_reject_verdict()], success=False),
        ]
        out = describe_failed_stages(results)
        assert out.count("stage ") == 2
        assert ";" in out
