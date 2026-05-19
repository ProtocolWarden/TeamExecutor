# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from team_executor import checkpoint as checkpoint_module
from team_executor import stage_planner
from team_executor import summarizer as summarizer_module
from team_executor import verifier as verifier_module
from team_executor import worker as worker_module
from team_executor import advisor as advisor_module
from team_executor import git_ops
from team_executor.models import (
    GoalStage,
    StageResult,
    TeamConfig,
    VerdictStatus,
)

logger = logging.getLogger(__name__)


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

        # Adaptive advisor may append new stages mid-run; track the live list
        live_stages = list(stages)

        for batch in batches:
            # Skip batches fully covered by checkpoint
            if all(s.index in completed_by_index for s in batch):
                continue

            if len(batch) == 1:
                stage = batch[0]
                result = self._run_stage(stage, goal_text, all_results, backend)
                all_results[stage.index] = result

                if self._config.auto_commit and result.success:
                    git_ops.commit_stage(self._working_dir, stage)

                # Adaptive advisor (sequential stages only)
                if self._config.adaptive_advisor and result.success:
                    processed = {s.index for s in live_stages if s.index in all_results}
                    remaining = [s for s in live_stages if s.index not in processed]
                    next_index = max(s.index for s in live_stages) + 1

                    advice = advisor_module.advise_after_stage(
                        goal_text=goal_text,
                        stage=stage,
                        result=result,
                        remaining_stages=remaining,
                        next_index=next_index,
                        config=self._config,
                        working_dir=self._working_dir,
                        backend=backend,
                    )
                    logger.info("advisor: stage %d → %s (%s)", stage.index, advice.action, advice.reason)

                    if advice.action == "done":
                        # Checkpoint what we have and stop
                        if run_id:
                            checkpoint_module.write_checkpoint(
                                self._working_dir, run_id,
                                [all_results[s.index] for s in live_stages if s.index in all_results],
                            )
                            checkpoint_module.delete_checkpoint(self._working_dir, run_id)
                        return [all_results[s.index] for s in live_stages if s.index in all_results]

                    if advice.action == "add_stage" and advice.new_stage is not None:
                        live_stages.append(advice.new_stage)
                        batches.append([advice.new_stage])
            else:
                # Parallel batch — use worktree isolation for stages with persist_changes
                parallel_results = self._run_parallel_batch(
                    batch, goal_text, all_results, backend, completed_by_index
                )
                all_results.update(parallel_results)

                if self._config.auto_commit:
                    for s in batch:
                        if s.index in parallel_results and parallel_results[s.index].success:
                            # Parallel stages are committed inside worktree; nothing extra needed
                            pass

            # Write checkpoint after each batch
            if run_id:
                checkpoint_module.write_checkpoint(
                    self._working_dir, run_id,
                    [all_results[s.index] for s in live_stages if s.index in all_results],
                )

        ordered = [all_results[s.index] for s in live_stages]

        if run_id:
            checkpoint_module.delete_checkpoint(self._working_dir, run_id)

        return ordered

    def _run_parallel_batch(
        self,
        batch: list[GoalStage],
        goal_text: str,
        prior_results: dict[int, StageResult],
        backend: str,
        completed_by_index: dict[int, StageResult],
    ) -> dict[int, StageResult]:
        """Run a batch of parallel stages.

        Stages with persist_changes=True each get an isolated git worktree.
        After all finish, worktree commits are cherry-picked into the main working dir.
        """
        needs_isolation = any(s.persist_changes for s in batch if s.index not in completed_by_index)
        worktrees: dict[int, str] = {}  # stage_index → worktree path
        shas: dict[int, str | None] = {}
        results: dict[int, StageResult] = {}

        if needs_isolation:
            for s in batch:
                if s.index not in completed_by_index and s.persist_changes:
                    try:
                        wt = git_ops.create_worktree(self._working_dir, s.index)
                        worktrees[s.index] = wt
                    except Exception as exc:
                        logger.warning(
                            "git_ops: worktree creation failed for stage %d (%s) — using shared dir",
                            s.index, exc,
                        )

        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            futures = {}
            for s in batch:
                if s.index in completed_by_index:
                    continue
                work_dir = worktrees.get(s.index, self._working_dir)
                futures[pool.submit(self._run_stage, s, goal_text, dict(prior_results), backend, work_dir)] = s

            for future in as_completed(futures):
                s = futures[future]
                result = future.result()
                results[s.index] = result

                # Commit worktree changes if stage succeeded and uses isolation
                if s.index in worktrees and result.success:
                    try:
                        sha = git_ops.commit_worktree(worktrees[s.index], s)
                        shas[s.index] = sha
                    except Exception as exc:
                        logger.error("git_ops: commit_worktree failed for stage %d: %s", s.index, exc)
                        shas[s.index] = None

        # Merge isolated worktree commits back into main working dir
        for stage_index, wt_path in worktrees.items():
            sha = shas.get(stage_index)
            if sha:
                try:
                    git_ops.merge_worktree_into_base(self._working_dir, sha, batch[0])
                except Exception as exc:
                    logger.error("git_ops: merge failed for stage %d: %s", stage_index, exc)
            git_ops.remove_worktree(self._working_dir, wt_path)

        return results

    def _run_stage(
        self,
        stage: GoalStage,
        goal_text: str,
        prior_results: dict[int, StageResult],
        backend: str,
        working_dir: str | None = None,
    ) -> StageResult:
        wd = working_dir or self._working_dir
        workers = self._config.workers
        if not workers:
            return StageResult(stage=stage, output="", cycles=0, verdicts=[], success=False)

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
                working_dir=wd,
                rejection_reason=rejection_reason,
                backend=backend,
            )
            last_output = output

            verdict = verifier_module.verify_stage(
                stage=stage,
                output=output,
                verifiers=self._config.verifiers,
                working_dir=wd,
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
