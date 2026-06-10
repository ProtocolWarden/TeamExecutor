# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import json
from unittest.mock import patch


from team_executor.models import GoalStage, Role
from team_executor.stage_planner import plan_stages


def _role(model: str = "claude-opus-4-7") -> Role:
    return Role(name="coordinator", model=model, system_prompt="You coordinate.")


class TestPlanStages:
    def test_parses_two_stages(self):
        payload = json.dumps([
            {"description": "Set up project", "acceptance_criteria": ["pyproject.toml exists"], "parallel_group": None},
            {"description": "Write tests", "acceptance_criteria": ["tests pass"], "parallel_group": None},
        ])
        with patch("team_executor.stage_planner.call_agent", return_value=payload):
            stages = plan_stages("Build a Python package", _role(), "/tmp")
        assert len(stages) == 2
        assert isinstance(stages[0], GoalStage)
        assert stages[0].index == 0
        assert stages[0].description == "Set up project"
        assert stages[1].index == 1

    def test_parses_single_stage(self):
        payload = json.dumps([{"description": "Do everything", "acceptance_criteria": ["it works"], "parallel_group": None}])
        with patch("team_executor.stage_planner.call_agent", return_value=payload):
            stages = plan_stages("Simple goal", _role(), "/tmp")
        assert len(stages) == 1

    def test_acceptance_criteria_preserved(self):
        payload = json.dumps([{"description": "Step A", "acceptance_criteria": ["c1", "c2"], "parallel_group": None}])
        with patch("team_executor.stage_planner.call_agent", return_value=payload):
            stages = plan_stages("Goal", _role(), "/tmp")
        assert stages[0].acceptance_criteria == ["c1", "c2"]

    def test_parallel_group_parsed(self):
        payload = json.dumps([
            {"description": "A", "acceptance_criteria": [], "parallel_group": 1},
            {"description": "B", "acceptance_criteria": [], "parallel_group": 1},
            {"description": "C", "acceptance_criteria": [], "parallel_group": None},
        ])
        with patch("team_executor.stage_planner.call_agent", return_value=payload):
            stages = plan_stages("Goal", _role(), "/tmp")
        assert stages[0].parallel_group == 1
        assert stages[1].parallel_group == 1
        assert stages[2].parallel_group is None

    def test_strips_markdown_fences(self):
        payload = "```json\n" + json.dumps([{"description": "X", "acceptance_criteria": [], "parallel_group": None}]) + "\n```"
        with patch("team_executor.stage_planner.call_agent", return_value=payload):
            stages = plan_stages("Goal", _role(), "/tmp")
        assert len(stages) == 1

    def test_empty_criteria_defaults_to_empty_list(self):
        payload = json.dumps([{"description": "Do something", "parallel_group": None}])
        with patch("team_executor.stage_planner.call_agent", return_value=payload):
            stages = plan_stages("Goal", _role(), "/tmp")
        assert stages[0].acceptance_criteria == []

    def test_parses_preambled_json(self):
        # Agent sometimes outputs conversational text before the JSON array
        json_part = json.dumps([{"description": "Do X", "acceptance_criteria": ["x done"], "parallel_group": None}])
        payload = f"Now I'll respond with the stage decomposition:\n{json_part}"
        with patch("team_executor.stage_planner.call_agent", return_value=payload):
            stages = plan_stages("Goal", _role(), "/tmp")
        assert len(stages) == 1
        assert stages[0].description == "Do X"

    def test_parses_preamble_with_trailing_text(self):
        json_part = json.dumps([{"description": "Stage A", "acceptance_criteria": [], "parallel_group": None}])
        payload = f"Here is the JSON:\n{json_part}\n\nLet me know if you need adjustments."
        with patch("team_executor.stage_planner.call_agent", return_value=payload):
            stages = plan_stages("Goal", _role(), "/tmp")
        assert len(stages) == 1
        assert stages[0].description == "Stage A"

    def test_raises_on_no_json_array(self):
        import pytest
        payload = "I cannot provide a JSON response right now."
        with patch("team_executor.stage_planner.call_agent", return_value=payload):
            with pytest.raises(RuntimeError, match="non-JSON"):
                plan_stages("Goal", _role(), "/tmp")

    def test_goal_text_included_in_prompt(self):
        payload = json.dumps([{"description": "A", "acceptance_criteria": [], "parallel_group": None}])
        captured_prompts = []

        def capture(role, prompt, working_dir, backend="claude_code"):
            captured_prompts.append(prompt)
            return payload

        with patch("team_executor.stage_planner.call_agent", side_effect=capture):
            plan_stages("Build X verbatim", _role(), "/tmp")
        assert "Build X verbatim" in captured_prompts[0]
