# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import os
from pathlib import Path

import yaml

from team_executor.models import Role, TeamConfig


def _role_from_dict(data: dict, name_fallback: str) -> Role:
    return Role(
        name=data.get("name", name_fallback),
        model=data["model"],
        system_prompt=data["system_prompt"],
        max_turns=data.get("max_turns", 10),
        timeout_seconds=data.get("timeout_seconds", 3600),
        fallback_model=data.get("fallback_model"),
    )


def _parse_team_config(raw: dict) -> TeamConfig:
    coordinator = _role_from_dict(raw["coordinator"], "coordinator")
    workers = [_role_from_dict(w, w.get("name", f"worker_{i}")) for i, w in enumerate(raw["workers"])]
    verifier = _role_from_dict(raw["verifier"], "verifier")
    return TeamConfig(
        team_name=raw["team_name"],
        coordinator=coordinator,
        workers=workers,
        verifier=verifier,
        max_cycles_per_stage=raw.get("max_cycles_per_stage", 3),
    )


def load_team_config(team_name: str, working_directory: str = ".") -> TeamConfig:
    candidates = [
        Path(working_directory) / ".team_executor" / "teams" / f"{team_name}.yaml",
        Path.home() / ".team_executor" / "teams" / f"{team_name}.yaml",
    ]
    for path in candidates:
        if path.exists():
            raw = yaml.safe_load(path.read_text())
            return _parse_team_config(raw)
    searched = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"Team config '{team_name}' not found. Searched: {searched}")
