# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from team_executor.models import CycleVerdict, GoalStage, StageResult, VerdictStatus


def _checkpoint_path(working_dir: str, run_id: str) -> Path:
    return Path(working_dir) / ".team_executor" / f"checkpoint-{run_id}.json"


def write_checkpoint(working_dir: str, run_id: str, completed: list[StageResult]) -> None:
    path = _checkpoint_path(working_dir, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [_serialise_result(r) for r in completed]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_checkpoint(working_dir: str, run_id: str) -> list[StageResult] | None:
    path = _checkpoint_path(working_dir, run_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [_deserialise_result(item) for item in payload]


def delete_checkpoint(working_dir: str, run_id: str) -> None:
    path = _checkpoint_path(working_dir, run_id)
    path.unlink(missing_ok=True)


def _serialise_result(result: StageResult) -> dict:
    return {
        "stage": {
            "index": result.stage.index,
            "description": result.stage.description,
            "acceptance_criteria": result.stage.acceptance_criteria,
            "parallel_group": result.stage.parallel_group,
        },
        "output": result.output,
        "cycles": result.cycles,
        "success": result.success,
        "verdicts": [
            {"status": v.status.value, "reason": v.reason, "round": v.round}
            for v in result.verdicts
        ],
    }


def _deserialise_result(data: dict) -> StageResult:
    stage_data = data["stage"]
    stage = GoalStage(
        index=stage_data["index"],
        description=stage_data["description"],
        acceptance_criteria=stage_data["acceptance_criteria"],
        parallel_group=stage_data.get("parallel_group"),
    )
    verdicts = [
        CycleVerdict(
            status=VerdictStatus(v["status"]),
            reason=v["reason"],
            round=v["round"],
        )
        for v in data["verdicts"]
    ]
    return StageResult(
        stage=stage,
        output=data["output"],
        cycles=data["cycles"],
        success=data["success"],
        verdicts=verdicts,
    )
