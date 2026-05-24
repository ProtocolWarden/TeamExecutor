# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Unit tests for `agent_call`, `git_ops`, `summarizer`, `worker`, `advisor`, and
  `quick_check` modules under `tests/unit/`.
- `.hooks/pre-commit` requiring a `.console/log.md` entry alongside source changes.
- `.env.example` documenting optional environment variables.
- `CHANGELOG.md` and expanded `README.md` (scope, quick start, architecture).

### Changed
- All `subprocess.run` calls in `git_ops` now pass an explicit `timeout=`.
- Checkpoint and config file I/O now specify `encoding="utf-8"`; checkpoint JSON
  is written with `ensure_ascii=False`.
- `tests/conftest.py` now enforces a project-venv guard.
