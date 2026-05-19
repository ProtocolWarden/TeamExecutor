# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from team_executor.models import GoalStage, Role, VerdictStatus
from team_executor.verifier import verify_stage


def _make_role() -> Role:
    return Role(
        name="verifier",
        model="claude-sonnet-4-6",
        system_prompt="You verify. Respond with JSON.",
    )


def _make_stage() -> GoalStage:
    return GoalStage(index=0, description="Do X", acceptance_criteria=["X done"])


def _make_client(response_text: str) -> MagicMock:
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = msg
    return client


class TestVerifyStage:
    def test_accept_verdict(self):
        payload = json.dumps({"status": "accept", "reason": "all criteria met"})
        verdict = verify_stage(_make_stage(), "output text", _make_role(), _make_client(payload), round_num=0)
        assert verdict.status == VerdictStatus.ACCEPT
        assert verdict.reason == "all criteria met"
        assert verdict.round == 0

    def test_reject_verdict(self):
        payload = json.dumps({"status": "reject", "reason": "X not done"})
        verdict = verify_stage(_make_stage(), "output text", _make_role(), _make_client(payload), round_num=1)
        assert verdict.status == VerdictStatus.REJECT
        assert verdict.reason == "X not done"
        assert verdict.round == 1

    def test_malformed_json_falls_back_to_reject(self):
        verdict = verify_stage(_make_stage(), "output", _make_role(), _make_client("not json at all"), round_num=0)
        assert verdict.status == VerdictStatus.REJECT
        assert "malformed JSON" in verdict.reason

    def test_round_number_tracked(self):
        payload = json.dumps({"status": "accept", "reason": "ok"})
        for round_num in [0, 2, 5]:
            verdict = verify_stage(_make_stage(), "out", _make_role(), _make_client(payload), round_num=round_num)
            assert verdict.round == round_num

    def test_strips_markdown_fences(self):
        payload = "```json\n" + json.dumps({"status": "accept", "reason": "fine"}) + "\n```"
        verdict = verify_stage(_make_stage(), "out", _make_role(), _make_client(payload), round_num=0)
        assert verdict.status == VerdictStatus.ACCEPT

    def test_unknown_status_defaults_to_reject(self):
        payload = json.dumps({"status": "maybe", "reason": "uncertain"})
        verdict = verify_stage(_make_stage(), "out", _make_role(), _make_client(payload), round_num=0)
        assert verdict.status == VerdictStatus.REJECT
