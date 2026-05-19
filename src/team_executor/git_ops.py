# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
"""git_ops.py — worktree isolation and auto-commit helpers for parallel stages."""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile

from team_executor.models import GoalStage

logger = logging.getLogger(__name__)


def _run(cmd: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)


def create_worktree(base_dir: str, stage_index: int) -> str:
    """Add a git worktree for one parallel stage and return its path."""
    tmp = tempfile.mkdtemp(prefix=f"te_stage_{stage_index}_")
    _run(["git", "worktree", "add", "--detach", tmp], cwd=base_dir)
    logger.debug("git_ops: worktree created at %s for stage %d", tmp, stage_index)
    return tmp


def remove_worktree(base_dir: str, worktree_path: str) -> None:
    """Remove a git worktree and prune the reference."""
    try:
        _run(["git", "worktree", "remove", "--force", worktree_path], cwd=base_dir)
    except subprocess.CalledProcessError:
        # Fallback: prune stale entries
        subprocess.run(["git", "worktree", "prune"], cwd=base_dir, capture_output=True)
    logger.debug("git_ops: worktree removed %s", worktree_path)


def commit_worktree(worktree_path: str, stage: GoalStage) -> str | None:
    """Stage all changes in worktree and commit. Returns commit SHA or None if nothing to commit."""
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=worktree_path, capture_output=True, text=True
    )
    if not result.stdout.strip():
        return None

    msg = f"stage {stage.index}: {stage.description}"
    _run(["git", "add", "-A"], cwd=worktree_path)
    proc = _run(["git", "commit", "--no-verify", "-m", msg], cwd=worktree_path)
    sha = proc.stdout.split()[-1] if proc.stdout else ""
    logger.info("git_ops: worktree commit %s (stage %d)", sha, stage.index)
    return sha


def merge_worktree_into_base(base_dir: str, sha: str, stage: GoalStage) -> None:
    """Cherry-pick a worktree commit into the main working directory."""
    try:
        _run(["git", "cherry-pick", "--no-commit", sha], cwd=base_dir)
        logger.info("git_ops: cherry-picked %s for stage %d", sha, stage.index)
    except subprocess.CalledProcessError as exc:
        logger.error("git_ops: cherry-pick failed for stage %d: %s", stage.index, exc.stderr)
        raise


def commit_stage(working_dir: str, stage: GoalStage) -> bool:
    """Stage all changes and commit for a sequential stage. Returns True if committed."""
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=working_dir, capture_output=True, text=True
    )
    if not status.stdout.strip():
        return False

    msg = f"stage {stage.index}: {stage.description}"
    _run(["git", "add", "-A"], cwd=working_dir)
    try:
        _run(["git", "commit", "--no-verify", "-m", msg], cwd=working_dir)
        logger.info("git_ops: committed stage %d in %s", stage.index, working_dir)
        return True
    except subprocess.CalledProcessError as exc:
        logger.warning("git_ops: commit failed for stage %d: %s", stage.index, exc.stderr)
        return False
