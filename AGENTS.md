# Repository Guidelines

## Project Structure & Module Organization
Source lives in `nightshift/`: `core/` covers orchestration (`agent_manager.py`, `task_queue.py`, `file_tracker.py`), `interfaces/cli.py` exposes the Click CLI, and `config/` stores MCP tool references. Supporting docs sit in `docs/`, while `docker/` and `scripts/` host container assets and helper commands. Runtime artifacts (SQLite DB, logs, outputs) land in `~/.nightshift/`; inspect that tree when verifying planner changes.

## Build, Test, and Development Commands
- `pip install -e .` installs the CLI plus dependencies for iterative work.
- `python -m nightshift --help` validates the entry point and lists subcommands.
- `nightshift submit "task"` (optionally `--auto-approve`) gives an end-to-end smoke test; follow with `nightshift queue`, `approve`, and `results` to observe lifecycle changes.
- `./scripts/build-executor.sh` rebuilds the Claude executor container whenever you add MCP dependencies or patch Dockerfiles.

## Coding Style & Naming Conventions
Write Python 3.10+ with 4-space indentation, type hints, and docstrings when logic is subtle. Keep modules/functions snake_case and classes PascalCase to match existing files. Log via `core/logger.py` instead of `print`, and centralize config in `core/config.py` or env vars. If you have `ruff` or `black` locally, run them before reviews to stay close to the current style.

## Testing Guidelines
There is no committed `tests/` tree yet; create `tests/` at the repo root and use `pytest`. Mirror package paths (`tests/core/test_task_queue.py`) and verify seams such as `task_planner` heuristics or CLI commands via Click’s runner. Every feature should also be exercised manually by running a workflow (`submit` → `approve` → `results`) to confirm data written to `~/.nightshift/` looks correct, especially when altering storage or Docker toggles.

## Commit & Pull Request Guidelines
Commits use short imperative subjects with optional prefixes (`Fix: Re-add /opt mount for Claude CLI`). Keep commits focused, reference issues when applicable, and describe behavioral impact in the body if needed. For PRs provide: a concise problem/solution summary, validation steps (CLI commands or sample tasks), and links to specs. Add screenshots or logs when changing CLI UX, and highlight anything that alters `~/.nightshift/` so reviewers can back up data before testing.

## Security & Configuration Tips
Set `export NIGHTSHIFT_USE_DOCKER=true` while developing planner or executor changes to match production isolation, and rebuild the executor image whenever the MCP stack changes. Treat `~/.nightshift/database/nightshift.db` as end-user data—never delete or commit it. For new MCP integrations, capture setup steps in `docs/` and load credentials exclusively from env vars or host secrets; avoid embedding sample keys in code or Dockerfiles.
