# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from team_executor import stage_planner
from team_executor import worker as worker_module
from team_executor import verifier as verifier_module
from team_executor.models import (
    GoalStage,
    StageResult,
    TeamConfig,
    TeamSession,
    VerdictStatus,
)


class TeamCoordinator:
    def __init__(self, config: TeamConfig, anthropic_client, working_dir: str = ".") -> None:
        self._config = config
        self._client = anthropic_client
        self._working_dir = working_dir

    def run(self, goal_text: str) -> list[StageResult]:
        stages = stage_planner.plan_stages(goal_text, self._config.coordinator, self._client)
        results: list[StageResult] = []
        for stage in stages:
            result = self._run_stage(stage, goal_text)
            results.append(result)
        return results

    def _run_stage(self, stage: GoalStage, goal_text: str) -> StageResult:
        verdicts = []
        last_output = ""
        rejection_reason: str | None = None

        # Round-robin worker selection; fall back to first if list is shorter
        workers = self._config.workers
        if not workers:
            return StageResult(
                stage=stage,
                output="",
                cycles=0,
                verdicts=[],
                success=False,
            )

        for cycle in range(self._config.max_cycles_per_stage):
            worker_role = workers[cycle % len(workers)]
            _success, output = worker_module.run_worker(
                role=worker_role,
                stage=stage,
                goal_text=goal_text,
                working_dir=self._working_dir,
                rejection_reason=rejection_reason,
            )
            last_output = output

            verdict = verifier_module.verify_stage(
                stage=stage,
                output=output,
                verifier_role=self._config.verifier,
                anthropic_client=self._client,
                round_num=cycle,
            )
            verdicts.append(verdict)

            if verdict.status == VerdictStatus.ACCEPT:
                return StageResult(
                    stage=stage,
                    output=output,
                    cycles=cycle + 1,
                    verdicts=verdicts,
                    success=True,
                )
            rejection_reason = verdict.reason

        return StageResult(
            stage=stage,
            output=last_output,
            cycles=self._config.max_cycles_per_stage,
            verdicts=verdicts,
            success=False,
        )
