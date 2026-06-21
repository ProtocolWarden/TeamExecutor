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


def describe_failed_stages(stage_results: list[StageResult], *, max_reason: int = 600) -> str:
    """Diagnostic summary of WHY each failed stage failed.

    For every non-successful stage, emits ``stage <index> (<description>): <why>``
    where ``<why>`` is the last cycle verdict's reason (the reviewer's rejection
    feedback) or, absent verdicts, a tail of the stage output. Returns ``""`` when
    nothing failed. This surfaces the detail that the bare "N of M stages failed"
    count drops — so callers (and downstream diagnostics) can see which stage
    failed and why, instead of an opaque count.
    """
    parts: list[str] = []
    for r in stage_results:
        if r.success:
            continue
        desc_lines = (r.stage.description or "").strip().splitlines()
        desc = desc_lines[0][:60] if desc_lines else f"stage {r.stage.index}"
        why = (r.verdicts[-1].reason if r.verdicts else "") or ""
        why = why.strip() or (r.output or "").strip()[-max_reason:]
        why = " ".join(why.split())[:max_reason]
        parts.append(f"stage {r.stage.index} ({desc}): {why}")
    return "; ".join(parts)
