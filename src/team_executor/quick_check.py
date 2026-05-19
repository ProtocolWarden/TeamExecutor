# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
"""quick_check.py — run scripted verification commands as a fast verifier."""
from __future__ import annotations

import logging
import shlex
import subprocess

from team_executor.models import CycleVerdict, GoalStage, QuickCheck, VerdictStatus

logger = logging.getLogger(__name__)


def run_quick_checks(
    checks: list[QuickCheck],
    stage: GoalStage,
    working_dir: str,
    round_num: int,
) -> CycleVerdict:
    """Execute each QuickCheck command. First failure → REJECT."""
    for check in checks:
        label = check.description or check.command
        try:
            proc = subprocess.run(
                shlex.split(check.command),
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            reason = f"QuickCheck timed out: {label}"
            logger.warning("quick_check: stage %d — %s", stage.index, reason)
            return CycleVerdict(status=VerdictStatus.REJECT, reason=reason, round=round_num)
        except FileNotFoundError as exc:
            reason = f"QuickCheck command not found: {check.command!r} — {exc}"
            logger.warning("quick_check: stage %d — %s", stage.index, reason)
            return CycleVerdict(status=VerdictStatus.REJECT, reason=reason, round=round_num)

        if proc.returncode != check.expected_exit_code:
            stderr_snippet = proc.stderr.strip()[-500:] if proc.stderr.strip() else proc.stdout.strip()[-500:]
            reason = (
                f"QuickCheck failed: {label} "
                f"(exit {proc.returncode}, expected {check.expected_exit_code})\n{stderr_snippet}"
            )
            logger.info("quick_check: stage %d REJECT — %s", stage.index, label)
            return CycleVerdict(status=VerdictStatus.REJECT, reason=reason, round=round_num)

        logger.debug("quick_check: stage %d PASS — %s", stage.index, label)

    return CycleVerdict(
        status=VerdictStatus.ACCEPT,
        reason=f"All {len(checks)} quick check(s) passed",
        round=round_num,
    )
