# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from typing import Literal

import tiktoken

from team_executor.agent_call import call_agent
from team_executor.models import GoalStage, Role, StageResult

_TOKEN_THRESHOLD = 4000

_SUMMARIZE_PROMPT = """\
Summarize the following completed stage output in 2-4 sentences for use as context in the next stage.
Be factual and specific about what was accomplished. Respond with plain text only — no JSON, no tool use.

Stage: {description}
Output:
{output}
"""


def _count_tokens(text: str, model: str) -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def summarize_stage(
    stage: GoalStage,
    result: StageResult,
    coordinator: Role,
    working_dir: str,
    backend: Literal["claude_code", "codex_cli"] = "claude_code",
) -> str:
    token_count = _count_tokens(result.output, coordinator.model)
    if token_count <= _TOKEN_THRESHOLD:
        return result.output

    prompt = _SUMMARIZE_PROMPT.format(
        description=stage.description,
        output=result.output,
    )
    return call_agent(coordinator, prompt, working_dir, backend=backend).strip()
