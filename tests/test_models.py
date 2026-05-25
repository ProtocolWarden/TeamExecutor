# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import pytest

from team_executor.models import (
    CycleVerdict,
    GoalStage,
    Role,
    StageResult,
    TeamConfig,
    TeamSession,
    VerifierRole,
    VerdictStatus,
)


def _role(name: str = "worker") -> Role:
    return Role(name=name, model="claude-sonnet-4-6", system_prompt="You work.")


def _verifier_role(kind: str = "reviewer") -> VerifierRole:
    return VerifierRole(kind=kind, role=_role(kind))


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

    def test_parallel_group_defaults_to_none(self):
        stage = GoalStage(index=0, description="Do it", acceptance_criteria=[])
        assert stage.parallel_group is None

    def test_parallel_group_set(self):
        stage = GoalStage(index=1, description="A", acceptance_criteria=[], parallel_group=2)
        assert stage.parallel_group == 2


class TestVerifierRole:
    def test_tester_kind(self):
        vr = _verifier_role("tester")
        assert vr.kind == "tester"
        assert vr.role.name == "tester"

    def test_reviewer_kind(self):
        vr = _verifier_role("reviewer")
        assert vr.kind == "reviewer"


class TestTeamConfig:
    def test_verifiers_list(self):
        config = TeamConfig(
            team_name="t",
            coordinator=_role("coord"),
            workers=[_role("w")],
            verifiers=[_verifier_role("tester"), _verifier_role("reviewer")],
        )
        assert len(config.verifiers) == 2
        assert config.verifiers[0].kind == "tester"

    def test_verifier_property_returns_first(self):
        config = TeamConfig(
            team_name="t",
            coordinator=_role("coord"),
            workers=[_role("w")],
            verifiers=[_verifier_role("tester")],
        )
        assert config.verifier.name == "tester"

    def test_verifier_property_raises_when_empty(self):
        config = TeamConfig(
            team_name="t",
            coordinator=_role("coord"),
            workers=[_role("w")],
            verifiers=[],
        )
        with pytest.raises(ValueError):
            _ = config.verifier

    def test_worker_backend_default(self):
        config = TeamConfig(
            team_name="t",
            coordinator=_role("coord"),
            workers=[_role("w")],
            verifiers=[_verifier_role()],
        )
        assert config.worker_backend == "claude_code"

    def test_worker_backend_codex(self):
        config = TeamConfig(
            team_name="t",
            coordinator=_role("coord"),
            workers=[_role("w")],
            verifiers=[_verifier_role()],
            worker_backend="codex_cli",
        )
        assert config.worker_backend == "codex_cli"


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
        role = Role(name="worker", model="claude-sonnet-4-6", system_prompt="You work.")
        assert role.max_turns == 10
        assert role.timeout_seconds == 3600
        assert role.fallback_model is None
        assert role.effort is None

    def test_custom_values(self):
        role = Role(
            name="coordinator",
            model="claude-opus-4-7",
            system_prompt="You coordinate.",
            max_turns=20,
            timeout_seconds=7200,
            fallback_model="claude-sonnet-4-6",
            effort="high",
            backend_models={"codex_cli": "gpt-5.4"},
            backend_efforts={"codex_cli": "medium"},
        )
        assert role.max_turns == 20
        assert role.fallback_model == "claude-sonnet-4-6"
        assert role.model_for_backend("claude_code") == "claude-opus-4-7"
        assert role.model_for_backend("codex_cli") == "gpt-5.4"
        assert role.effort_for_backend("claude_code") == "high"
        assert role.effort_for_backend("codex_cli") == "medium"


class TestVerdictStatus:
    def test_accept_value(self):
        assert VerdictStatus.ACCEPT == "accept"

    def test_reject_value(self):
        assert VerdictStatus.REJECT == "reject"
