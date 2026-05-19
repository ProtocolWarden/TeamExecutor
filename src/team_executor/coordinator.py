# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from team_executor import checkpoint as checkpoint_module
from team_executor import stage_planner
from team_executor import summarizer as summarizer_module
from team_executor import verifier as verifier_module
from team_executor import worker as worker_module
from team_executor.models import (
    GoalStage,
    StageResult,
    TeamConfig,
    VerdictStatus,
)


def _build_execution_batches(stages: list[GoalStage]) -> list[list[GoalStage]]:
    """Partition stages into sequential batches.

    Stages with the same parallel_group int form one batch and run concurrently.
    Stages with parallel_group=None are their own single-stage batch.
    Batch order follows the first occurrence of each group in the stage list.
    """
    batches: list[list[GoalStage]] = []
    seen_groups: set[int] = set()
    for stage in stages:
        if stage.parallel_group is None:
            batches.append([stage])
        elif stage.parallel_group not in seen_groups:
            seen_groups.add(stage.parallel_group)
            group = [s for s in stages if s.parallel_group == stage.parallel_group]
            batches.append(group)
    return batches


class TeamCoordinator:
    def __init__(self, config: TeamConfig, working_dir: str = ".") -> None:
        self._config = config
        self._working_dir = working_dir

    def run(self, goal_text: str, run_id: str | None = None) -> list[StageResult]:
        backend = self._config.worker_backend

        stages = stage_planner.plan_stages(
            goal_text,
            self._config.coordinator,
            self._working_dir,
            backend=backend,
        )

        # Load checkpoint — skip already-completed stages
        completed_by_index: dict[int, StageResult] = {}
        if run_id:
            prior = checkpoint_module.read_checkpoint(self._working_dir, run_id)
            if prior:
                completed_by_index = {r.stage.index: r for r in prior}

        batches = _build_execution_batches(stages)
        all_results: dict[int, StageResult] = dict(completed_by_index)

        for batch in batches:
            # Skip batches fully covered by checkpoint
            if all(s.index in completed_by_index for s in batch):
                continue

            if len(batch) == 1:
                result = self._run_stage(batch[0], goal_text, all_results, backend)
                all_results[batch[0].index] = result
            else:
                # Parallel batch
                with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                    futures = {
                        pool.submit(self._run_stage, s, goal_text, dict(all_results), backend): s
                        for s in batch
                        if s.index not in completed_by_index
                    }
                    for future in as_completed(futures):
                        s = futures[future]
                        all_results[s.index] = future.result()

            # Write checkpoint after each batch
            if run_id:
                checkpoint_module.write_checkpoint(
                    self._working_dir, run_id,
                    [all_results[s.index] for s in stages if s.index in all_results],
                )

        ordered = [all_results[s.index] for s in stages]

        if run_id:
            checkpoint_module.delete_checkpoint(self._working_dir, run_id)

        return ordered

    def _run_stage(
        self,
        stage: GoalStage,
        goal_text: str,
        prior_results: dict[int, StageResult],
        backend: str,
    ) -> StageResult:
        workers = self._config.workers
        if not workers:
            return StageResult(stage=stage, output="", cycles=0, verdicts=[], success=False)

        # Build prior-stage context (summarised if large)
        prior_context = self._build_prior_context(prior_results, stage, backend)
        enriched_goal = goal_text
        if prior_context:
            enriched_goal = f"{goal_text}\n\n--- Completed stages ---\n{prior_context}"

        verdicts = []
        last_output = ""
        rejection_reason: str | None = None

        for cycle in range(self._config.max_cycles_per_stage):
            worker_role = workers[cycle % len(workers)]
            _success, output = worker_module.run_worker(
                role=worker_role,
                stage=stage,
                goal_text=enriched_goal,
                working_dir=self._working_dir,
                rejection_reason=rejection_reason,
                backend=backend,
            )
            last_output = output

            verdict = verifier_module.verify_stage(
                stage=stage,
                output=output,
                verifiers=self._config.verifiers,
                working_dir=self._working_dir,
                round_num=cycle,
                backend=backend,
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

    def _build_prior_context(
        self,
        prior_results: dict[int, StageResult],
        current_stage: GoalStage,
        backend: str,
    ) -> str:
        parts = []
        for idx in sorted(prior_results):
            if idx >= current_stage.index:
                continue
            result = prior_results[idx]
            summary = summarizer_module.summarize_stage(
                result.stage, result, self._config.coordinator,
                self._working_dir, backend=backend,
            )
            parts.append(f"Stage {result.stage.index} ({result.stage.description}):\n{summary}")
        return "\n\n".join(parts)
