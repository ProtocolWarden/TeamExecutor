# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import pytest

from team_executor.models import (
    CycleVerdict,
    GoalStage,
    Role,
    StageResult,
    TeamSession,
    VerdictStatus,
)


class TestTeamSession:
    def test_add_user_appends_user_message(self):
        session = TeamSession(role_name="coordinator")
        session.add_user("hello")
        assert session.messages == [{"role": "user", "content": "hello"}]

    def test_add_assistant_appends_assistant_message(self):
        session = TeamSession(role_name="coordinator")
        session.add_assistant("hi back")
        assert session.messages == [{"role": "assistant", "content": "hi back"}]

    def test_mixed_messages_preserve_order(self):
        session = TeamSession(role_name="worker")
        session.add_user("do this")
        session.add_assistant("done")
        session.add_user("verify")
        assert [m["role"] for m in session.messages] == ["user", "assistant", "user"]

    def test_starts_empty(self):
        session = TeamSession(role_name="verifier")
        assert session.messages == []


class TestGoalStage:
    def test_fields_stored_correctly(self):
        stage = GoalStage(index=1, description="Build X", acceptance_criteria=["X exists"])
        assert stage.index == 1
        assert stage.description == "Build X"
        assert stage.acceptance_criteria == ["X exists"]

    def test_empty_criteria(self):
        stage = GoalStage(index=0, description="Do nothing", acceptance_criteria=[])
        assert stage.acceptance_criteria == []


class TestCycleVerdict:
    def test_accept_verdict(self):
        v = CycleVerdict(status=VerdictStatus.ACCEPT, reason="looks good", round=0)
        assert v.status == VerdictStatus.ACCEPT
        assert v.round == 0

    def test_reject_verdict(self):
        v = CycleVerdict(status=VerdictStatus.REJECT, reason="missing tests", round=2)
        assert v.status == VerdictStatus.REJECT
        assert v.reason == "missing tests"


class TestRole:
    def test_defaults(self):
        role = Role(name="worker", model="claude-sonnet-4-6", system_prompt="You are a worker.")
        assert role.max_turns == 10
        assert role.timeout_seconds == 3600
        assert role.fallback_model is None

    def test_custom_values(self):
        role = Role(
            name="coordinator",
            model="claude-opus-4-7",
            system_prompt="You coordinate.",
            max_turns=20,
            timeout_seconds=7200,
            fallback_model="claude-sonnet-4-6",
        )
        assert role.max_turns == 20
        assert role.fallback_model == "claude-sonnet-4-6"


class TestVerdictStatus:
    def test_accept_value(self):
        assert VerdictStatus.ACCEPT == "accept"

    def test_reject_value(self):
        assert VerdictStatus.REJECT == "reject"
