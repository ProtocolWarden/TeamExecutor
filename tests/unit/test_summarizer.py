# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from unittest.mock import patch

from team_executor import summarizer
from team_executor.models import GoalStage, Role, StageResult


def _role() -> Role:
    return Role(name="coordinator", model="gpt-4", system_prompt="sp")


def _stage() -> GoalStage:
    return GoalStage(index=0, description="desc", acceptance_criteria=[])


def _result(output: str) -> StageResult:
    return StageResult(stage=_stage(), output=output, cycles=1, verdicts=[], success=True)


def test_short_output_returned_verbatim_without_agent_call():
    result = _result("short output")
    with patch("team_executor.summarizer._count_tokens", return_value=10) as ct, \
         patch("team_executor.summarizer.call_agent") as ca:
        out = summarizer.summarize_stage(_stage(), result, _role(), "/wd")
    assert out == "short output"
    ca.assert_not_called()
    ct.assert_called_once()


def test_long_output_triggers_agent_summarization():
    result = _result("x" * 50000)
    with patch("team_executor.summarizer._count_tokens", return_value=99999), \
         patch("team_executor.summarizer.call_agent", return_value="  a summary  ") as ca:
        out = summarizer.summarize_stage(_stage(), result, _role(), "/wd", backend="claude_code")
    assert out == "a summary"  # stripped
    ca.assert_called_once()
    # prompt passed to the agent contains the stage description and output
    prompt = ca.call_args.args[1]
    assert "desc" in prompt


def test_count_tokens_falls_back_for_unknown_model():
    # An unknown model name must not raise; it falls back to cl100k_base.
    n = summarizer._count_tokens("hello world", "not-a-real-model-xyz")
    assert isinstance(n, int) and n > 0
