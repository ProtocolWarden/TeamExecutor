# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import tiktoken

from team_executor.models import GoalStage, StageResult

_TOKEN_THRESHOLD = 4000

_SUMMARIZE_PROMPT = """\
Summarize the following completed stage output in 2-4 sentences for use as context in the next stage.
Be factual and specific about what was accomplished.

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
    coordinator_model: str,
    anthropic_client,
) -> str:
    token_count = _count_tokens(result.output, coordinator_model)
    if token_count <= _TOKEN_THRESHOLD:
        return result.output

    prompt = _SUMMARIZE_PROMPT.format(
        description=stage.description,
        output=result.output,
    )
    response = anthropic_client.messages.create(
        model=coordinator_model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
