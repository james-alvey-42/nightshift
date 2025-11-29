# NightShift Test Extension Plan

## Overview
Goal: Extend reliable test coverage across core, CLI, and Slack integrations with high-value tests that detect real failures.

## Phase 1 — Persistence, Filesystem, and Config (High Priority)
**Modules:** task_queue.py, file_tracker.py, config.py, logger.py
**Estimated tests:** 27-34

### Test Files:
- tests/core/test_task_queue_basic.py
- tests/core/test_task_queue_concurrency.py
- tests/core/test_file_tracker.py
- tests/core/test_config.py
- tests/core/test_logger.py

## Phase 2 — Planning, Sandboxing, Agent Signals (High Priority)
**Modules:** task_planner.py, sandbox.py, agent_manager.py, notifier.py
**Estimated tests:** 30-36

### Test Files:
- tests/core/test_task_planner.py
- tests/core/test_sandbox.py
- tests/core/test_agent_manager_unit.py
- tests/core/test_notifier.py

## Phase 3 — Executor Service (Medium Priority)
**Module:** task_executor.py
**Estimated tests:** 6-8

### Test Files:
- tests/core/test_task_executor.py

## Phase 4 — CLI Commands (High Priority)
**Module:** cli.py
**Estimated tests:** 10-14

### Test Files:
- tests/cli/test_cli_submit_approve.py
- tests/cli/test_cli_queue_results_watch.py
- tests/cli/test_cli_revise_cancel_pause_resume_kill.py
- tests/cli/test_cli_slack_config_clear_executor.py

## Phase 5 — Slack Integrations (High Priority)
**Modules:** slack_*.py
**Estimated tests:** 28-35

### Test Files:
- tests/integrations/test_slack_formatter.py
- tests/integrations/test_slack_metadata.py
- tests/integrations/test_slack_middleware.py
- tests/integrations/test_slack_server.py
- tests/integrations/test_slack_client.py

## Phase 6 — Optional/Low Priority
- tests/core/test_output_viewer.py (2 tests)

## Total Estimated: 103-129 tests
