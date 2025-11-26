# Repository Guidelines

## Project Structure & Module Organization
NightShift ships as a Python package inside `nightshift/` with `core/` (planning, queue, notifier, file tracker), `integrations/` (Slack client/server/formatter/middleware), `interfaces/cli.py` (CLI entry point), and `config/` (MCP tool references, sample configs). Docs and playbooks live under `docs/` plus the Slack-focused markdown files at repo root. Runtime artifacts land in `~/.nightshift/` (config, database, logs, output, notifications, `slack_metadata/`); inspect them whenever you debug tasks.

## Build, Test, and Development Commands
```bash
pip install -e .        # install deps and register the CLI
nightshift --help       # view CLI verbs
nightshift submit "…"   # enqueue a task (use --auto-approve for smoke tests)
nightshift queue        # inspect staged/completed items
nightshift slack-setup  # write Slack credentials into ~/.nightshift/config/
nightshift slack-server --port 5001  # start the Flask webhook
ngrok http 5001         # expose the Slack server for manual testing
```
Run from the repo root so relative paths resolve correctly.

## Coding Style & Naming Conventions
Target Python 3.8+, follow PEP 8 with four-space indents, type hints, and descriptive docstrings as shown in `core/task_planner.py`. Keep modules snake_case, classes CapWords, constants upper snake. Prefer pathlib over `os.path`, structured logging via `NightShiftLogger`, and validate JSON/CLI responses before using them. Add short comments only for non-obvious flows (sandboxing, signature verification).

## Testing Guidelines
There is no automated suite yet; rely on the manual flows captured in `SLACK_TEST_CHECKLIST.md`, `TESTING_SLACK_INTEGRATION.md`, and `SLACK_QUICK_START.md`. Exercise CLI paths (`nightshift submit|queue|display`) plus end-to-end Slack commands with two terminals (`nightshift slack-server`, `ngrok`) and confirm artifacts under `~/.nightshift/output`, `logs`, and `slack_metadata`. When adding automated coverage, mirror the package tree under `tests/`, name files `test_<module>.py`, functions `test_<behavior>`, and run `pytest`. Record manual or automated results in `SLACK_TESTING_STATUS.md`, noting regressions or coverage gaps.

## Commit & Pull Request Guidelines
Git history uses emoji-prefixed, imperative subjects (`✨ Implement Phase 1 Slack Integration (Issue #11)`); follow that pattern and reference issue numbers or GitHub keywords. For PRs, mirror the structure in `PR_SUMMARY.md`: summarize features, architecture, bug fixes, testing evidence, and documentation updates, plus screenshots or transcripts for Slack surfaces when relevant. Reference task-planner output or CLI logs whenever the change affects execution flows or permissions.

## Security & Configuration Tips
Never commit credentials; instead run `nightshift slack-setup` to create per-user secrets under `~/.nightshift/config/`. Review `SANDBOX.md` before modifying directory permissions, and respect the sandbox prompts enforced in `core/task_planner.py` plus the HMAC checks inside `integrations/slack_middleware.py`. Keep `.env.example` synchronized whenever you add required environment variables or configuration keys.
