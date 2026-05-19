# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from team_executor.models import GoalStage, Role
from team_executor.stage_planner import plan_stages


def _make_role(model: str = "claude-opus-4-7") -> Role:
    return Role(name="coordinator", model=model, system_prompt="You coordinate.")


def _make_client(response_text: str) -> MagicMock:
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = msg
    return client


class TestPlanStages:
    def test_parses_two_stages(self):
        payload = json.dumps([
            {"description": "Set up project", "acceptance_criteria": ["pyproject.toml exists"]},
            {"description": "Write tests", "acceptance_criteria": ["tests pass"]},
        ])
        client = _make_client(payload)
        stages = plan_stages("Build a Python package", _make_role(), client)
        assert len(stages) == 2
        assert isinstance(stages[0], GoalStage)
        assert stages[0].index == 0
        assert stages[0].description == "Set up project"
        assert stages[1].index == 1

    def test_parses_single_stage(self):
        payload = json.dumps([
            {"description": "Do everything", "acceptance_criteria": ["it works"]},
        ])
        client = _make_client(payload)
        stages = plan_stages("Simple goal", _make_role(), client)
        assert len(stages) == 1
        assert stages[0].index == 0

    def test_acceptance_criteria_preserved(self):
        payload = json.dumps([
            {"description": "Step A", "acceptance_criteria": ["criterion 1", "criterion 2"]},
        ])
        client = _make_client(payload)
        stages = plan_stages("Goal", _make_role(), client)
        assert stages[0].acceptance_criteria == ["criterion 1", "criterion 2"]

    def test_strips_markdown_fences(self):
        payload = "```json\n" + json.dumps([
            {"description": "X", "acceptance_criteria": []},
        ]) + "\n```"
        client = _make_client(payload)
        stages = plan_stages("Goal", _make_role(), client)
        assert len(stages) == 1

    def test_passes_goal_text_to_api(self):
        payload = json.dumps([{"description": "A", "acceptance_criteria": []}])
        client = _make_client(payload)
        plan_stages("Build X verbatim", _make_role(), client)
        call_kwargs = client.messages.create.call_args
        user_content = call_kwargs[1]["messages"][0]["content"]
        assert "Build X verbatim" in user_content

    def test_empty_criteria_defaults_to_empty_list(self):
        payload = json.dumps([{"description": "Do something"}])
        client = _make_client(payload)
        stages = plan_stages("Goal", _make_role(), client)
        assert stages[0].acceptance_criteria == []

    def test_coordinator_model_used(self):
        payload = json.dumps([{"description": "A", "acceptance_criteria": []}])
        client = _make_client(payload)
        plan_stages("Goal", _make_role(model="claude-opus-4-7-20251001"), client)
        assert client.messages.create.call_args[1]["model"] == "claude-opus-4-7-20251001"
