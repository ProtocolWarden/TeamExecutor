# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import anthropic

from team_executor.config_loader import load_team_config
from team_executor.coordinator import TeamCoordinator
from team_executor.evidence import aggregate_evidence


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class TeamExecutorRunner:
    def __init__(
        self,
        team_name: str = "default",
        working_dir: str = ".",
        api_key: str | None = None,
    ) -> None:
        self._team_name = team_name
        self._working_dir = working_dir
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def run(self, goal_text: str):
        """Main entry point. Returns RxP RuntimeResult."""
        # Import here so tests can mock rxp without installing it
        from rxp.contracts.runtime_result import RuntimeResult  # type: ignore[import]

        invocation_id = str(uuid.uuid4())
        started_at = _utcnow()

        try:
            config = load_team_config(self._team_name, self._working_dir)
            client = anthropic.Anthropic(api_key=self._api_key)
            coordinator = TeamCoordinator(config, client, self._working_dir)
            stage_results = coordinator.run(goal_text)
            evidence = aggregate_evidence(stage_results)
            finished_at = _utcnow()

            overall_success = all(r.success for r in stage_results)
            status = "succeeded" if overall_success else "failed"
            exit_code = 0 if overall_success else 1
            error_summary = None if overall_success else (
                f"{evidence['stages_failed']} of {evidence['stages_total']} stages failed"
            )

            return RuntimeResult(
                invocation_id=invocation_id,
                runtime_name="team_executor",
                runtime_kind="subprocess",
                status=status,
                exit_code=exit_code,
                started_at=started_at,
                finished_at=finished_at,
                error_summary=error_summary,
                metadata={k: str(v) for k, v in evidence.items()},
            )
        except Exception as exc:
            finished_at = _utcnow()
            from rxp.contracts.runtime_result import RuntimeResult  # type: ignore[import]

            return RuntimeResult(
                invocation_id=invocation_id,
                runtime_name="team_executor",
                runtime_kind="subprocess",
                status="failed",
                exit_code=1,
                started_at=started_at,
                finished_at=finished_at,
                error_summary=str(exc),
                metadata={},
            )
