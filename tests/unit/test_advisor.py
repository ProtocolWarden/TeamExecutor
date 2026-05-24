# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
from unittest.mock import patch

from team_executor import advisor
from team_executor.models import GoalStage, Role, StageResult, TeamConfig, VerifierRole


def _config() -> TeamConfig:
    role = Role(name="c", model="m", system_prompt="sp")
    return TeamConfig(
        team_name="t",
        coordinator=role,
        workers=[role],
        verifiers=[VerifierRole(kind="reviewer", role=role)],
    )


def _stage(index: int = 1) -> GoalStage:
    return GoalStage(index=index, description="did stuff", acceptance_criteria=[])


def _result() -> StageResult:
    return StageResult(stage=_stage(), output="out", cycles=1, verdicts=[], success=True)


def _advise(raw_or_exc):
    cfg = _config()
    if isinstance(raw_or_exc, Exception):
        cm = patch("team_executor.advisor.call_agent", side_effect=raw_or_exc)
    else:
        cm = patch("team_executor.advisor.call_agent", return_value=raw_or_exc)
    with cm:
        return advisor.advise_after_stage(
            "goal", _stage(), _result(), [_stage(2)], next_index=99, config=cfg,
            working_dir="/wd", backend="claude_code",
        )


def test_continue_action_parsed():
    out = _advise(json.dumps({"action": "continue", "reason": "looks good"}))
    assert out.action == "continue"
    assert out.reason == "looks good"
    assert out.new_stage is None


def test_done_action_parsed():
    out = _advise(json.dumps({"action": "done", "reason": "complete"}))
    assert out.action == "done"


def test_add_stage_builds_new_goalstage_with_next_index():
    out = _advise(json.dumps({
        "action": "add_stage",
        "reason": "need more",
        "new_stage_description": "extra work",
        "new_stage_criteria": ["c1", "c2"],
    }))
    assert out.action == "add_stage"
    assert out.new_stage is not None
    assert out.new_stage.index == 99
    assert out.new_stage.description == "extra work"
    assert out.new_stage.acceptance_criteria == ["c1", "c2"]


def test_unknown_action_coerced_to_continue():
    out = _advise(json.dumps({"action": "explode", "reason": "?"}))
    assert out.action == "continue"


def test_fenced_json_is_unwrapped():
    fenced = "```json\n" + json.dumps({"action": "done", "reason": "ok"}) + "\n```"
    out = _advise(fenced)
    assert out.action == "done"


def test_malformed_json_defaults_to_continue():
    out = _advise("not json at all")
    assert out.action == "continue"
    assert "malformed" in out.reason


def test_agent_exception_defaults_to_continue():
    out = _advise(RuntimeError("boom"))
    assert out.action == "continue"
    assert "advisor error" in out.reason


def test_add_stage_with_non_list_criteria_defaults_empty():
    out = _advise(json.dumps({
        "action": "add_stage", "reason": "r",
        "new_stage_description": "d", "new_stage_criteria": "oops-a-string",
    }))
    assert out.new_stage.acceptance_criteria == []
