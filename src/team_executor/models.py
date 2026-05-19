# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
class TeamConfig:
    team_name: str
    coordinator: Role
    workers: list[Role]
    verifier: Role
    max_cycles_per_stage: int = 3


@dataclass
class GoalStage:
    index: int
    description: str
    acceptance_criteria: list[str]


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
