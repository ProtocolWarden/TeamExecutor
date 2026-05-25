# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from team_executor.config_loader import load_team_config
from team_executor.models import TeamConfig

_LEGACY_YAML = textwrap.dedent("""\
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

_VERIFIERS_YAML = textwrap.dedent("""\
    team_name: multiverify
    coordinator:
      model: claude-opus-4-7
      system_prompt: "coord"
    workers:
      - name: w
        model: claude-sonnet-4-6
        system_prompt: "work"
    verifiers:
      - kind: tester
        name: tester
        model: claude-sonnet-4-6
        system_prompt: "You test."
      - kind: reviewer
        name: reviewer
        model: claude-sonnet-4-6
        system_prompt: "You review."
    max_cycles_per_stage: 3
""")

_BACKEND_MODELS_YAML = textwrap.dedent("""\
    team_name: backendmodels
    coordinator:
      model: claude-opus-4-7
      effort: high
      backend_models:
        codex_cli: gpt-5.4
      backend_efforts:
        codex_cli: medium
      system_prompt: "coord"
    workers:
      - name: w
        model: claude-sonnet-4-6
        effort: medium
        backend_models:
          codex_cli: gpt-5.4-mini
        backend_efforts:
          codex_cli: low
        system_prompt: "work"
    verifiers:
      - kind: reviewer
        name: reviewer
        model: claude-sonnet-4-6
        effort: medium
        backend_models:
          codex_cli: gpt-5.4-mini
        backend_efforts:
          codex_cli: low
        system_prompt: "review"
""")


def _write_config(directory: Path, team_name: str, content: str) -> None:
    teams_dir = directory / ".team_executor" / "teams"
    teams_dir.mkdir(parents=True, exist_ok=True)
    (teams_dir / f"{team_name}.yaml").write_text(content)


class TestLoadTeamConfig:
    def test_loads_from_project_dir(self, tmp_path):
        _write_config(tmp_path, "testteam", _LEGACY_YAML)
        config = load_team_config("testteam", working_directory=str(tmp_path))
        assert isinstance(config, TeamConfig)
        assert config.team_name == "testteam"
        assert config.coordinator.model == "claude-opus-4-7-20251001"
        assert len(config.workers) == 1

    def test_loads_from_home_dir(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        _write_config(fake_home, "hometeam", _LEGACY_YAML.replace("testteam", "hometeam"))
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        empty_project = tmp_path / "project"
        empty_project.mkdir()
        config = load_team_config("hometeam", working_directory=str(empty_project))
        assert config.team_name == "hometeam"

    def test_builtin_default_team_loads(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        config = load_team_config("default", working_directory=str(tmp_path))
        assert config.team_name == "default"
        assert len(config.verifiers) >= 1

    def test_builtin_premium_team_loads(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        config = load_team_config("premium", working_directory=str(tmp_path))
        assert config.team_name == "premium"
        assert "opus" in config.coordinator.model

    def test_builtin_budget_team_loads(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        config = load_team_config("budget", working_directory=str(tmp_path))
        assert config.team_name == "budget"
        assert "haiku" in config.coordinator.model
        assert config.coordinator.backend_models["codex_cli"] == "gpt-5.4-mini"

    def test_missing_raises_file_not_found(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "emptyhome"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        with pytest.raises(FileNotFoundError):
            load_team_config("nonexistent_xyzzy", working_directory=str(tmp_path))

    def test_project_dir_takes_precedence_over_builtin(self, tmp_path, monkeypatch):
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
        # Write a project-level "default" that overrides the built-in
        override = _LEGACY_YAML.replace("testteam", "default").replace(
            "claude-opus-4-7-20251001", "claude-haiku-3-5"
        )
        _write_config(tmp_path, "default", override)
        config = load_team_config("default", working_directory=str(tmp_path))
        assert config.coordinator.model == "claude-haiku-3-5"

    def test_legacy_verifier_key_parsed_as_reviewer(self, tmp_path):
        _write_config(tmp_path, "testteam", _LEGACY_YAML)
        config = load_team_config("testteam", working_directory=str(tmp_path))
        assert len(config.verifiers) == 1
        assert config.verifiers[0].kind == "reviewer"

    def test_new_verifiers_list_parsed(self, tmp_path):
        _write_config(tmp_path, "multiverify", _VERIFIERS_YAML)
        config = load_team_config("multiverify", working_directory=str(tmp_path))
        assert len(config.verifiers) == 2
        assert config.verifiers[0].kind == "tester"
        assert config.verifiers[1].kind == "reviewer"

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

    def test_worker_backend_default(self, tmp_path):
        _write_config(tmp_path, "testteam", _LEGACY_YAML)
        config = load_team_config("testteam", working_directory=str(tmp_path))
        assert config.worker_backend == "claude_code"

    def test_backend_specific_models_are_loaded(self, tmp_path):
        _write_config(tmp_path, "backendmodels", _BACKEND_MODELS_YAML)
        config = load_team_config("backendmodels", working_directory=str(tmp_path))
        assert config.coordinator.backend_models["codex_cli"] == "gpt-5.4"
        assert config.coordinator.backend_efforts["codex_cli"] == "medium"
        assert config.workers[0].backend_models["codex_cli"] == "gpt-5.4-mini"
        assert config.workers[0].backend_efforts["codex_cli"] == "low"
        assert config.verifiers[0].role.backend_models["codex_cli"] == "gpt-5.4-mini"
        assert config.verifiers[0].role.backend_efforts["codex_cli"] == "low"
