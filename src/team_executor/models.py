# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class VerdictStatus(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"


@dataclass
class Role:
    name: str
    model: str
    system_prompt: str
    max_turns: int = 10
    timeout_seconds: int = 3600
    fallback_model: str | None = None


@dataclass
class VerifierRole:
    kind: Literal["tester", "reviewer"]
    role: Role


@dataclass
class TeamConfig:
    team_name: str
    coordinator: Role
    workers: list[Role]
    verifiers: list[VerifierRole]
    max_cycles_per_stage: int = 3
    worker_backend: Literal["claude_code", "codex_cli"] = "claude_code"

    @property
    def verifier(self) -> Role:
        """Backwards-compat: return the first verifier's role."""
        if not self.verifiers:
            raise ValueError("TeamConfig has no verifiers")
        return self.verifiers[0].role


@dataclass
class GoalStage:
    index: int
    description: str
    acceptance_criteria: list[str]
    parallel_group: int | None = None


@dataclass
class CycleVerdict:
    status: VerdictStatus
    reason: str
    round: int


@dataclass
class StageResult:
    stage: GoalStage
    output: str
    cycles: int
    verdicts: list[CycleVerdict]
    success: bool


@dataclass
class TeamSession:
    """Per-role conversation state within a stage."""

    role_name: str
    messages: list[dict[str, Any]] = field(default_factory=list)

    def add_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})
