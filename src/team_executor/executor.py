# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

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
        worker_backend: Literal["claude_code", "codex_cli"] = "claude_code",
    ) -> None:
        self._team_name = team_name
        self._working_dir = working_dir
        self._worker_backend = worker_backend

    def run(self, goal_text: str, invocation_id: str | None = None):
        """Main entry point. Returns RxP RuntimeResult.

        invocation_id: forwarded from the RxP RuntimeInvocation so checkpoint files
        are named consistently and resumable runs can be correlated by OC.
        """
        from rxp.contracts.runtime_result import RuntimeResult  # type: ignore[import]

        run_id = invocation_id or str(uuid.uuid4())
        started_at = _utcnow()

        try:
            config = load_team_config(self._team_name, self._working_dir)
            # worker_backend from caller overrides team config default
            if self._worker_backend != "claude_code":
                config.worker_backend = self._worker_backend

            coordinator = TeamCoordinator(config, self._working_dir)
            stage_results = coordinator.run(goal_text, run_id=run_id)
            evidence = aggregate_evidence(stage_results)
            finished_at = _utcnow()

            overall_success = all(r.success for r in stage_results)
            status = "succeeded" if overall_success else "failed"
            exit_code = 0 if overall_success else 1
            error_summary = None if overall_success else (
                f"{evidence['stages_failed']} of {evidence['stages_total']} stages failed"
            )

            return RuntimeResult(
                invocation_id=run_id,
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
                invocation_id=run_id,
                runtime_name="team_executor",
                runtime_kind="subprocess",
                status="failed",
                exit_code=1,
                started_at=started_at,
                finished_at=finished_at,
                error_summary=str(exc),
                metadata={},
            )
