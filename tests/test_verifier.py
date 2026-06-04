# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
from unittest.mock import patch


from team_executor.models import GoalStage, Role, VerifierRole, VerdictStatus
from team_executor.verifier import verify_stage


def _stage() -> GoalStage:
    return GoalStage(index=0, description="Do X", acceptance_criteria=["X done", "tests pass"])


def _vr(kind: str = "reviewer", name: str = "reviewer") -> VerifierRole:
    return VerifierRole(kind=kind, role=Role(name=name, model="claude-sonnet-4-6", system_prompt="You verify."))


def _accept_json() -> str:
    return json.dumps({"status": "accept", "reason": "looks good"})


def _reject_json(reason: str = "not done") -> str:
    return json.dumps({"status": "reject", "reason": reason})


class TestVerifyStage:
    def test_single_verifier_accept(self):
        with patch("team_executor.verifier.call_agent", return_value=_accept_json()):
            verdict = verify_stage(_stage(), "output", [_vr()], "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.ACCEPT
        assert verdict.reason == "looks good"

    def test_single_verifier_reject(self):
        with patch("team_executor.verifier.call_agent", return_value=_reject_json("missing tests")):
            verdict = verify_stage(_stage(), "output", [_vr()], "/tmp", round_num=1)
        assert verdict.status == VerdictStatus.REJECT
        assert verdict.reason == "missing tests"
        assert verdict.round == 1

    def test_two_verifiers_both_accept(self):
        with patch("team_executor.verifier.call_agent", return_value=_accept_json()):
            verdict = verify_stage(_stage(), "output", [_vr("tester"), _vr("reviewer")], "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.ACCEPT

    def test_tester_rejects_short_circuits_reviewer(self):
        call_count = 0

        def tracking_agent(role, prompt, working_dir, backend="claude_code"):
            nonlocal call_count
            call_count += 1
            return _reject_json("test failed") if call_count == 1 else _accept_json()

        with patch("team_executor.verifier.call_agent", side_effect=tracking_agent):
            verdict = verify_stage(_stage(), "output", [_vr("tester"), _vr("reviewer")], "/tmp", round_num=0)

        assert verdict.status == VerdictStatus.REJECT
        assert call_count == 1

    def test_tester_accepts_reviewer_rejects(self):
        responses = iter([_accept_json(), _reject_json("style issues")])
        with patch("team_executor.verifier.call_agent", side_effect=lambda *a, **kw: next(responses)):
            verdict = verify_stage(_stage(), "output", [_vr("tester"), _vr("reviewer")], "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.REJECT
        assert "style issues" in verdict.reason

    def test_empty_verifiers_auto_accepts(self):
        verdict = verify_stage(_stage(), "output", [], "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.ACCEPT
        assert "no verifiers" in verdict.reason

    def test_malformed_json_returns_reject(self):
        with patch("team_executor.verifier.call_agent", return_value="not json at all"):
            verdict = verify_stage(_stage(), "output", [_vr()], "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.REJECT

    def test_markdown_fenced_json_is_parsed(self):
        fenced = "```json\n" + _accept_json() + "\n```"
        with patch("team_executor.verifier.call_agent", return_value=fenced):
            verdict = verify_stage(_stage(), "output", [_vr()], "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.ACCEPT

    def test_unknown_status_defaults_to_reject(self):
        with patch("team_executor.verifier.call_agent", return_value=json.dumps({"status": "maybe", "reason": "uncertain"})):
            verdict = verify_stage(_stage(), "output", [_vr()], "/tmp", round_num=0)
        assert verdict.status == VerdictStatus.REJECT

    def test_round_number_tracked(self):
        with patch("team_executor.verifier.call_agent", return_value=_accept_json()):
            for round_num in [0, 2, 5]:
                verdict = verify_stage(_stage(), "out", [_vr()], "/tmp", round_num=round_num)
                assert verdict.round == round_num
