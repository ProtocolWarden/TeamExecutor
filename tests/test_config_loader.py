# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from team_executor.config_loader import load_team_config
from team_executor.models import TeamConfig

_MINIMAL_YAML = textwrap.dedent("""\
    team_name: testteam
    coordinator:
      model: claude-opus-4-7-20251001
      system_prompt: "You coordinate."
      max_turns: 5
    workers:
      - name: implementer
        model: claude-sonnet-4-6
        system_prompt: "You implement."
    verifier:
      model: claude-sonnet-4-6
      system_prompt: "You verify."
    max_cycles_per_stage: 2
""")


def _write_config(directory: Path, team_name: str, content: str) -> None:
    teams_dir = directory / ".team_executor" / "teams"
    teams_dir.mkdir(parents=True, exist_ok=True)
    (teams_dir / f"{team_name}.yaml").write_text(content)


class TestLoadTeamConfig:
    def test_loads_from_project_dir(self, tmp_path):
        _write_config(tmp_path, "testteam", _MINIMAL_YAML)
        config = load_team_config("testteam", working_directory=str(tmp_path))
        assert isinstance(config, TeamConfig)
        assert config.team_name == "testteam"
        assert config.coordinator.model == "claude-opus-4-7-20251001"
        assert len(config.workers) == 1
        assert config.workers[0].name == "implementer"

    def test_loads_from_home_dir(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        _write_config(fake_home, "hometeam", _MINIMAL_YAML.replace("testteam", "hometeam"))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        # project dir has no config
        empty_project = tmp_path / "project"
        empty_project.mkdir()
        config = load_team_config("hometeam", working_directory=str(empty_project))
        assert config.team_name == "hometeam"

    def test_missing_raises_file_not_found(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "emptyhome"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        with pytest.raises(FileNotFoundError):
            load_team_config("nonexistent", working_directory=str(tmp_path))

    def test_project_dir_takes_precedence_over_home(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        _write_config(fake_home, "myteam", _MINIMAL_YAML.replace("testteam", "myteam"))
        project_yaml = _MINIMAL_YAML.replace("testteam", "myteam").replace(
            "claude-opus-4-7-20251001", "claude-haiku-3-5"
        )
        _write_config(tmp_path, "myteam", project_yaml)
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        config = load_team_config("myteam", working_directory=str(tmp_path))
        # Project dir wins — model is the overridden one
        assert config.coordinator.model == "claude-haiku-3-5"

    def test_max_cycles_default(self, tmp_path):
        yaml_no_cycles = textwrap.dedent("""\
            team_name: simple
            coordinator:
              model: claude-opus-4-7
              system_prompt: "coord"
            workers:
              - name: w
                model: claude-sonnet-4-6
                system_prompt: "worker"
            verifier:
              model: claude-sonnet-4-6
              system_prompt: "verify"
        """)
        _write_config(tmp_path, "simple", yaml_no_cycles)
        config = load_team_config("simple", working_directory=str(tmp_path))
        assert config.max_cycles_per_stage == 3

    def test_verifier_fields_parsed(self, tmp_path):
        _write_config(tmp_path, "testteam", _MINIMAL_YAML)
        config = load_team_config("testteam", working_directory=str(tmp_path))
        assert config.verifier.model == "claude-sonnet-4-6"
        assert config.verifier.max_turns == 10  # default
