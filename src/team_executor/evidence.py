# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from team_executor.models import StageResult, VerdictStatus


def aggregate_evidence(stage_results: list[StageResult]) -> dict:
    return {
        "stages_total": len(stage_results),
        "stages_succeeded": sum(1 for r in stage_results if r.success),
        "stages_failed": sum(1 for r in stage_results if not r.success),
        "total_cycles": sum(r.cycles for r in stage_results),
        "rejection_rounds": sum(
            len([v for v in r.verdicts if v.status == VerdictStatus.REJECT])
            for r in stage_results
        ),
    }
