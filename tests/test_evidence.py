# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from team_executor.evidence import aggregate_evidence
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
