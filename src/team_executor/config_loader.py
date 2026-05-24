# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

from pathlib import Path

import yaml

from team_executor.models import Role, TeamConfig, VerifierRole

_BUILTIN_TEAMS_DIR = Path(__file__).parent / "teams"


def _role_from_dict(data: dict, name_fallback: str) -> Role:
    return Role(
        name=data.get("name", name_fallback),
        model=data["model"],
        system_prompt=data["system_prompt"],
        max_turns=data.get("max_turns", 10),
        timeout_seconds=data.get("timeout_seconds", 3600),
        fallback_model=data.get("fallback_model"),
    )


def _verifiers_from_raw(raw: dict) -> list[VerifierRole]:
    """Parse `verifiers:` list (new) or single `verifier:` key (legacy)."""
    if "verifiers" in raw:
        result = []
        for item in raw["verifiers"]:
            kind = item.get("kind", "reviewer")
            role = _role_from_dict(item, kind)
            result.append(VerifierRole(kind=kind, role=role))
        return result
    if "verifier" in raw:
        role = _role_from_dict(raw["verifier"], "verifier")
        return [VerifierRole(kind="reviewer", role=role)]
    return []


def _parse_team_config(raw: dict) -> TeamConfig:
    coordinator = _role_from_dict(raw["coordinator"], "coordinator")
    workers = [_role_from_dict(w, w.get("name", f"worker_{i}")) for i, w in enumerate(raw["workers"])]
    verifiers = _verifiers_from_raw(raw)
    return TeamConfig(
        team_name=raw["team_name"],
        coordinator=coordinator,
        workers=workers,
        verifiers=verifiers,
        max_cycles_per_stage=raw.get("max_cycles_per_stage", 3),
        worker_backend=raw.get("worker_backend", "claude_code"),
    )


def load_team_config(team_name: str, working_directory: str = ".") -> TeamConfig:
    """Load team config. Priority: project dir → home dir → built-in."""
    candidates = [
        Path(working_directory) / ".team_executor" / "teams" / f"{team_name}.yaml",
        Path.home() / ".team_executor" / "teams" / f"{team_name}.yaml",
        _BUILTIN_TEAMS_DIR / f"{team_name}.yaml",
    ]
    for path in candidates:
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            return _parse_team_config(raw)
    searched = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(f"Team config '{team_name}' not found. Searched: {searched}")
