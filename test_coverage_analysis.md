# Test Coverage Gap Analysis for NightShift

## Executive Summary

NightShift's tests are concentrated in the TUI layer (~63 tests, very high coverage there) plus a few controller helpers. The entire rest of the system—the core task lifecycle, CLI, sandboxing, Slack integration, planner/executor, and even small utilities—is effectively untested. Overall coverage (~26%) hides that almost all high-risk, side-effect-heavy code paths (subprocesses, SQLite, filesystem, Slack/Flask) have no automated tests.

Below is a structured gap analysis and concrete, prioritized recommendations.

---

## 1. Untested/Undertested Modules

### Critical Gaps (No Tests)

These have no dedicated tests and are central to system correctness:

- **Core**
  - `nightshift/core/task_queue.py`
  - `nightshift/core/agent_manager.py`
  - `nightshift/core/task_planner.py`
  - `nightshift/core/file_tracker.py`
  - `nightshift/core/logger.py`
  - `nightshift/core/notifier.py`
  - `nightshift/core/output_viewer.py`
  - `nightshift/core/sandbox.py`
  - `nightshift/core/config.py`

- **CLI & entry points**
  - `nightshift/interfaces/cli.py` (all commands)
  - `nightshift/__main__.py`

- **Slack integration**
  - `nightshift/integrations/slack_client.py`
  - `nightshift/integrations/slack_formatter.py`
  - `nightshift/integrations/slack_handler.py`
  - `nightshift/integrations/slack_metadata.py`
  - `nightshift/integrations/slack_middleware.py`
  - `nightshift/integrations/slack_server.py`

- **Migrations & utilities**
  - `nightshift/migrations/add_allowed_directories.py`
  - `csv_to_json.py`
  - `palindrome.py` (toy, but completely untested)

### Insufficient Coverage

These files are partially exercised only via TUI tests (if at all), but have significant logic not validated in isolation:

- **TUI**
  - `nightshift/interfaces/tui/app.py`
    - `create_app()` wiring with real `Config`, `TaskQueue`, `TaskPlanner`, `AgentManager`
    - `auto_refresh` behavior with real backends (currently only via integration tests with dummy backends)
  - `nightshift/interfaces/tui/controllers.py`
    - Basic exec log / summary / files paths are covered, but:
      - Submit/approve/reject/pause/resume/kill flows are exercised only with Dummy*; no tests where controller drives real `TaskQueue`/`AgentManager`.
      - No tests for error paths in these methods, just happy-path logic.
  - `nightshift/interfaces/tui/keybindings.py`
    - Integration tests cover only:
      - `j/k` navigation
      - `1–4` tab switching
      - `:` + `:help`
      - `:queue running`
    - Not covered:
      - `H/L` tab cycling
      - `R` / `Ctrl-L` refresh error handling
      - Task actions (`a/r/p/P/X/s`)
      - Command variants: `status`, `results`, `pause/resume/kill/cancel`, `quit`
      - `s` keypath (vim editor / subprocess)

- **Config**
  - `Config._load_slack_config`, `set_slack_config`, `get_slack_config` – not validated, even though they underpin Slack server startup.

---

## 2. Missing Edge Case Tests

### nightshift/core/task_queue.py

- **State machine invariants**
  - No tests enforcing valid transitions:
    - STAGED → COMMITTED → RUNNING → COMPLETED/FAILED
    - STAGED/COMMITTED → CANCELLED
    - RUNNING/PAUSED → CANCELLED via `kill_task`
  - No tests that `update_status` correctly:
    - Sets `started_at` only on RUNNING
    - Sets `completed_at` only on COMPLETED/FAILED/CANCELLED
    - Updates `process_id`, `result_path`, `token_usage`, `execution_time` fields as expected.

- **Boundary conditions**
  - `list_tasks(status=...)` with invalid `TaskStatus` (e.g., string vs Enum)
  - Empty DB / no tasks
  - Very long descriptions or large `allowed_directories`/`allowed_tools` lists

- **Error handling**
  - Behavior when DB file is missing or unreadable
  - Corrupted JSON in `allowed_tools` / `allowed_directories`

### nightshift/core/agent_manager.py

- **Execute paths**
  - **Success path**:
    - `execute_task` returning success updates:
      - Task to RUNNING then COMPLETED
      - `token_usage` and `execution_time` saved
      - Output file JSON structure is correct
      - Notifier invoked with correct arguments
      - FileTracker's `save_changes` path is exercised
  - **Failure path**:
    - Non-zero return code from subprocess:
      - Task marked FAILED
      - `error_message` from stderr
      - Notification created with error
  - **Timeout path**:
      - `timeout` passed, process killed, FAILED with appropriate message
  - **Unexpected exceptions**:
      - E.g. failure creating output file, JSON dump errors – does `execute_task` return a sensible error dict and update status to FAILED?

- **Boundary/input edge cases**
  - Task with:
    - `allowed_tools = []`
    - `system_prompt = ""` or extremely long prompt
    - `allowed_directories = None` vs empty list → read-only sandbox behavior
    - `needs_git = True` when `gh` is not installed or `gh auth token` fails

- **Concurrent access**
  - Multiple `execute_task` calls in different tasks, ensuring:
    - PIDs are distinct
    - `FileTracker` does not overwrite snapshots between tasks

- **Pause/Resume/Kill**
  - `pause_task`:
    - Missing task → returns `success=False`
    - Non-RUNNING status
    - PID missing
    - `os.kill(..., 0)` raising `ProcessLookupError` or `PermissionError`
    - Successful SIGSTOP leads to status PAUSED
  - `resume_task`:
    - Non-PAUSED status
    - Process dead after pause
  - `kill_task`:
    - Process already dead → status CANCELLED with "already terminated" message
    - SIGKILL success
    - Permission/OS errors

### nightshift/core/task_planner.py

- **Claude wrapper parsing**
  - `plan_task`:
    - Response with `structured_output` vs `result` vs direct JSON
    - Result wrapped in ```json ... ``` or ``` ... ``` code fences
    - Missing required fields (e.g., no `allowed_directories` → ensure exception raised)
    - Timeout (`subprocess.TimeoutExpired`)
    - Non-zero `returncode` from CLI
    - Invalid JSON output from Claude (triggers JSONDecodeError path)
  - `refine_plan`:
    - Same wrapper/code-fence cases as `plan_task`
    - Missing `allowed_directories` in refined plan – note: CLI currently depends on them in revised plan

- **Quick estimate**
  - Descriptions matching and not matching heuristics (arxiv/data/other) – no tests assert these values

### nightshift/core/file_tracker.py

- **Snapshots**
  - Empty directory -> `take_snapshot` returns `{}`
  - Directories with:
    - Hidden files/dirs (should be skipped)
    - `node_modules`, `__pycache__`, `venv` (should be skipped)
  - Large number of files (performance isn't tested)

- **Change detection**
  - Created, modified, deleted detection across `start_tracking` / `stop_tracking`
  - Non-existent file on stat (error paths in `get_changes`)

- **save_changes**
  - Error when output dir unwritable (permissions)
  - Content of JSON format validated

### nightshift/core/config.py

- **Slack config loading**
  - Only env vars set
  - Only file present
  - Both present (file overrides env)
  - Invalid JSON in `slack_config.json`
  - Missing fields (ensure defaults used)
  - `slack_enabled` false when incomplete credentials

- **set_slack_config/get_slack_config**
  - Verify mask formatting rules
  - Round-tripping via saved file

### nightshift/core/notifier.py

- **generate_summary**
  - No file changes → `file_changes` sections empty
  - `success=False`, with and without `error_message`
  - No `token_usage`/`result_path`

- **notify**
  - With Slack configured:
    - Valid metadata exists: `slack_client.post_message` invoked, `slack_metadata.delete()` called
    - Metadata missing: `_send_slack` early exit
  - Terminal disabled: `_display_terminal` no-op, error warnings suppressed

- **_display_terminal**
  - Very large descriptions and file lists (truncation)
  - Mix of created/modified/deleted counts >5

### nightshift/core/output_viewer.py

- Error paths: missing file, invalid JSON, malformed stream-json lines
- Render variety:
  - `system` init, assistant with text/tool_use, user/tool_result, result events, usage stats, stderr present

### nightshift/core/sandbox.py

- **Validation**
  - `validate_directories` rejects:
    - `/`, `/var`, `/usr`, `/System`, `/Library`, `/Applications`, etc.
    - Subpaths of these
  - Warn on home directory

- **Profile generation**
  - `needs_git=True` adds appropriate mach-lookup & device file rules
  - Empty `allowed_directories` still produces profile that allows temp dirs only

- **wrap_command & cleanup**
  - Temporary profile file exists during run and is cleaned up
  - `is_available` behavior on systems without `sandbox-exec` (unit test with monkeypatching `shutil.which`)

### nightshift/integrations/slack_client.py

- **Retry logic**
  - Rate limit errors (`error == "rate_limited"` + Retry-After header)
  - No Retry-After header (exponential backoff)
  - Exceeding `max_retries` raises SlackApiError
  - Non-rate-limited errors: no retry

### nightshift/integrations/slack_formatter.py

- **format_approval_message**
  - Many tools (>5) (displays "+N more")
  - Very long descriptions (needs truncation)
  - `task.allowed_tools` missing/None

- **format_completion_notification**
  - `result_path` missing or unreadable JSON:
    - Should skip "What NightShift found/created" section gracefully
  - `file_changes` large lists (created/modified/deleted >5)
  - `status` == failed, cancelled, unknown
  - Very long `error_message` (truncation)
  - `token_usage` None vs 0

- **format_task_list**
  - `status_filter` None/various values
  - >10 tasks (truncation + "Showing 10 of N")

### nightshift/integrations/slack_handler.py

- **handle_submit**
  - Empty text
  - Exceptions from `plan_task` or `create_task`
  - DM vs channel branching
  - Metadata stored correctly

- **_plan_and_stage_task**
  - Failures from TaskPlanner or SlackClient
  - Plan missing `allowed_directories` or `needs_git`

- **handle_approval**
  - Task not found
  - Approve vs reject for wrong status
  - Slack update failures

- **handle_details**
  - `allowed_tools` or `allowed_directories` None
  - Very long `description` and `system_prompt` (truncation & formatting)

- **queue/status/cancel/pause/resume/kill**
  - Invalid/missing task_id
  - Tasks in wrong state (e.g. cancel running, pause staged)
  - `agent_manager.pause_task`/`resume_task`/`kill_task` error returns

- **_execute_and_notify**
  - Task passed as ID vs object
  - Exceptions inside `execute_task`
  - Slack notification on failure (thread_ts usage)

### nightshift/integrations/slack_middleware.py

- **verify_slack_signature**
  - Missing headers
  - Timestamp too old
  - Invalid signature
  - Valid signature

- **extract_user_id**
  - Slash command (form)
  - Interaction payload (JSON)
  - Fallback to IP

### nightshift/integrations/slack_server.py

- **_verify_signature**
  - Body caching & verification for:
    - `/slack/commands`
    - `/slack/interactions`
    - `/slack/events`
  - Missing/invalid timestamp and signature

- **handle_commands**
  - No `_signing_secret` or `_event_handler` set
  - Unknown command, unknown subcommand
  - Each subcommand path calling into handler with correct arguments

- **handle_interactions**
  - Missing payload, invalid JSON
  - `block_actions` with unknown `action_id`
  - `view_submission` path to modal handler
  - DM vs channel id interactions

- **handle_events**
  - `url_verification` echo
  - Other event types (no-op, but signature still checked)

### nightshift/interfaces/cli.py

For each command:

- **submit**
  - Planning timeout
  - `--allow-dir` normalization and deduplication
  - `--debug` sandbox preview on macOS with/without sandbox
  - Auto-approve path (COMMITTED + execute + result printing)
  - Failure of TaskPlanner/AgentManager (e.g., CLI not installed)

- **queue**
  - Each status filter
  - No tasks

- **approve**
  - Missing/invalid task_id
  - Non-STAGED status

- **results**
  - `--show-output` rendering, including JSON decode errors

- **revise** (two duplicate definitions – a bug):
  - Behavior on non-STAGED tasks
  - Planner failure
  - Missing `allowed_directories` in original plan (first version of `current_plan` misses it)

- **display**
  - Missing `result_path`, incomplete outputs

- **cancel/pause/resume/kill/watch**
  - Each state precondition (wrong state)
  - Process existence/permission cases (watch output)
  - `follow` flag currently unimplemented (should show message)

- **slack_server / slack_setup / slack_config**
  - Slack not configured (`slack_enabled=False`)
  - Invalid bot token format
  - App token optional
  - Daemon mode unsupported

- **clear**
  - Confirm prompt vs `--confirm`
  - Missing base_dir

- **tui**
  - That `nightshift tui` runs without raising under basic conditions

### Utilities

- **csv_to_json.py**
  - has_headers vs no headers detection
  - Empty file
  - Invalid CSV (raises ValueError)
  - Bad arguments / `--help` path
  - Permission errors on read/write

- **palindrome.py**
  - Typical palindromes and non-palindromes
  - Empty string, single character
  - Unicode and punctuation

---

## 3. Critical Integration Tests Missing

### Task lifecycle flows

**What needs testing**

- End-to-end flows using real `TaskQueue` and `AgentManager` (but mocked subprocess):

  1. **STAGED → COMMITTED → RUNNING → COMPLETED**:
     - `submit` (no auto-approve): creates STAGED
     - `approve`: COMMITTED & triggers `execute_task`
     - Fake subprocess returns 0 and writes stubbed stream-json
     - DB row has correct timestamps, `result_path`, `token_usage`, `execution_time`
     - Notification file exists and contains expected structure

  2. **STAGED → CANCELLED**:
     - `submit` then `cancel` via CLI or Slack

  3. **RUNNING → PAUSED → RUNNING → COMPLETED**:
     - Set up dummy process with PID
     - Use `agent_manager.pause_task` and `resume_task` via:
       - CLI (`pause`, `resume`)
       - Slack `/nightshift pause/resume`

  4. **RUNNING/PAUSED → CANCELLED via kill**:
     - Validate DB row and notifications

**Why critical**

- This is the primary product behavior: task execution with approvals and process control. Currently only UI-level behaviors and controller logic are tested, not the actual persistence and executor integration.

### AgentManager + FileTracker integration

**What needs testing**

- Execute a task (with subprocess mocked) that:
  - Creates, modifies, and deletes files in a temporary directory
- Ensure:
  - FileTracker snapshots work correctly
  - `_files.json` is written with expected entries
  - Notifier includes `file_changes` from FileTracker

**Why critical**

- File change reporting is a key advertised feature and crucial for trust/safety.

### TaskPlanner + TaskQueue integration

**What needs testing**

- `submit` (CLI) end-to-end:
  - TaskPlanner called with description, returns a plan
  - Plan's fields are persisted correctly to DB via `create_task`
  - `revise` flows call `refine_plan` and update the same row's fields (`update_plan`)

- `needs_git` propagation:
  - TaskPlanner sets `needs_git` = True → stored in DB → used by AgentManager to enable GH_TOKEN and sandbox allowances

**Why critical**

- Directory sandboxing and git token handling hinge on this chain of fields being consistent.

### CLI commands + core components integration

Add a suite of tests invoking `nightshift.interfaces.cli.cli` via `CliRunner` (Click):

- `submit`, `queue`, `approve`, `results`, `display`, `revise`, `cancel`, `pause`, `resume`, `kill`, `watch`, `clear`

Use a temp base directory (`Config(base_dir=tmp_path)` via monkeypatch) to keep DB/logs isolated.

**Why critical**

- CLI is a primary user-facing interface; no automated tests exist to guard regressions.

### Slack server + core components integration

At least minimal integration tests using Flask's test client:

- Configure a fake `Config`/`SlackClient`/`TaskQueue`/`AgentManager`
- Simulate:

  - `/slack/commands` submit:
    - Verified signature header
    - Ensure:
      - SlackEventHandler gets called
      - TaskPlanner.plan_task mocked; TaskQueue.create_task called
      - SlackMetadata file written

  - `/slack/interactions` approve/reject buttons:
    - Handler sees `action_id`, calls TaskQueue + AgentManager

  - `/slack/commands` queue/status/cancel/pause/resume/kill:
    - Each endpoint path

**Why critical**

- Slack integration is large and complex, currently verified only by manual testing. Even a handful of integration tests would catch signature regressions, routing issues, and DM vs channel bugs.

### Subprocess execution and stream-json parsing

**What needs testing**

- `_parse_output` in `AgentManager`:
  - Typical stream-json from Claude:
    - `type="text"`, `usage` blocks, `tool_use` blocks
  - Mixed plain text lines
- `OutputViewer`:
  - Same kinds of events rendered in human-readable logs

**Why critical**

- Incorrect parsing → bogus token usage, truncated contents, broken notifications and viewers.

---

## 4. Test Double/Mock Gaps

### Core components that lack test doubles

- **TaskQueue**: you have `DummyQueue` tailored for TUI tests, but not for core/CLI/Slack tests:
  - No fake that simulates DB errors or enforces the lifecycle state machine
- **AgentManager**:
  - Only `DummyAgent` used in TUI tests, with no notion of success/failure, timeouts, or file tracking
- **TaskPlanner**:
  - `DummyPlanner` returns only `enhanced_prompt`, `estimated_tokens`, `estimated_time` – no tools, directories, needs_git, system_prompt
  - This is OK for narrow TUI tests but insufficient to simulate sandbox & git behaviors in higher-level tests

### Limitations of existing test doubles

- `DummyQueue.create_task` generates its own `task_id` (`task_{len(self._tasks)}`) ignoring real IDs:
  - Good for TUI; not appropriate for CLI/Slack tests where task IDs matter
- `DummyAgent.execute_task` purely appends IDs; does not:
  - Create `result_path` files
  - Trigger Notifier
  - Change task status
- `DummyPlanner.plan_task` ignores `allowed_directories`, `needs_git`, `system_prompt`:
  - Tests that rely on sandbox or git flags cannot be written without more realistic behavior

### Recommended improvements

- Create **core-level fakes**:

  - `FakeTaskQueue` (under `tests/fakes` or `nightshift/core/testing_doubles.py`):
    - Enforce valid transitions
    - Optionally simulate DB errors

  - `FakeAgentManager`:
    - Instead of shelling out, writes deterministic `output.json` and `files.json` and updates status

  - `FakeTaskPlanner`:
    - Returns full plan dict with tools, directories, `needs_git`, system_prompt

- Extend `DummyConfig`:
  - Support `get_database_path`, `get_log_dir`, `get_tools_reference_path` when used outside TUI

- Mock external processes via `subprocess.run` / `Popen` monkeypatches in unit tests, instead of faking at higher levels, for AgentManager/TaskPlanner

---

## 5. Priority Recommendations

### High Priority (Do First)

1. **Core task lifecycle & persistence**
   - Unit tests for `TaskQueue` and `AgentManager` (focus on status transitions, timing, error cases)
   - Rationale: Central to correctness; currently unguarded; high risk due to stateful DB and subprocesses

2. **Planner robustness**
   - Tests for `TaskPlanner.plan_task` / `refine_plan`, including JSON wrapper/code-fence cases and timeouts
   - Rationale: Frequent source of subtle bugs (already fixed once), and directly shapes sandbox and git behavior

3. **CLI end-to-end flows (no Slack)**
   - Use Click's `CliRunner` with temporary base dir and monkeypatched Planner/Agent
   - Rationale: Primary UX, lots of branching, currently untested

4. **Sandbox validation**
   - Unit tests around `SandboxManager.validate_directories`, `create_profile`, `wrap_command`
   - Rationale: Direct security boundary; mistakes could expose `/` or system dirs

### Medium Priority

5. **Slack integration**
   - Unit tests for `slack_formatter`, `slack_client`, `slack_metadata`, `slack_middleware`
   - Flask test-client integration tests for `slack_server` + `slack_handler` basic happy paths and common errors
   - Rationale: Big surface area and tricky security, but a secondary interface vs CLI

6. **Notifier & OutputViewer**
   - Maximize coverage of notification generation and stream-json viewing
   - Rationale: Important UX, moderate complexity, relies on core artifacts

7. **TUI/CLI parity**
   - Tests that controller actions (submit/approve/reject/pause/resume/kill) behave correctly with real TaskQueue/AgentManager fakes, not just DummyAgent
   - Rationale: Ensure the same semantics across interfaces

### Low Priority

8. **Migrations and small utilities**
   - `csv_to_json`, `palindrome`, `add_allowed_directories` migration
   - Rationale: Lower impact, easy to test, but not core to NightShift operation

9. **Edge-case styling behaviors in TUI beyond current tests**
   - Most widget rendering is already very well covered

---

## 6. Specific Test Scenarios to Add

Concrete scenarios for top-priority areas:

### A. TaskQueue + AgentManager lifecycle

1. **Happy-path CLI run (unit/integration)**
   - Setup:
     - Temp base dir
     - Monkeypatch `TaskPlanner.plan_task` to return deterministic plan
     - Monkeypatch `AgentManager.execute_task` to:
       - Write an `output.json` with known stdout and `token_usage`
       - Call `task_queue.update_status(... COMPLETED ...)`
   - Steps:
     - Run `nightshift submit "simple task" --auto-approve` via `CliRunner`
   - Assert:
     - Exit code 0
     - DB has one task with status COMPLETED
     - Output file exists
     - Notification JSON exists
     - CLI prints success summary

2. **Failure path with non-zero return code**
   - Unit-test `AgentManager.execute_task` with patched `subprocess.Popen` that:
     - Sets `returncode=1`, writes stderr `"boom"`, empty stdout
   - Assert:
     - Task moves to FAILED
     - `error_message` contains `"boom"`
     - Notification status `"failed"` and `error_message` stored

3. **Timeout path**
   - Patch `time.time` or `timeout` small and `process` never finishing:
     - Simulate `subprocess.TimeoutExpired`
   - Assert:
     - Task FAILED with timeout message referencing `timeout` or `estimated_time`
     - Notification indicates timeout

4. **Pause/resume/kill**
   - Use a fake `TaskQueue` with tasks having `status=RUNNING/PAUSED`, `process_id` set
   - Patch `os.kill` to:
     - Succeed and track signals
     - Raise `ProcessLookupError`/`PermissionError`
   - Assert all error messages and state transitions are correct

### B. TaskPlanner robustness

5. **Structured_output vs result wrapper**
   - Provide three mocked `subprocess.run` outputs:
     - `{"structured_output": {...}}`
     - `{"result": "```json\n{...}\n```"}`
     - `"{...}"` raw JSON
   - Assert `plan_task` normalizes to the same dict and all required fields are present

6. **Invalid JSON & timeouts**
   - `stdout` invalid JSON → must log error and raise a clear exception
   - `TimeoutExpired` → appropriate error and exception message

### C. Sandbox validation

7. **Reject system directories**
   - `SandboxManager.validate_directories(["/var/log", "/System/Library"])` → `ValueError`
   - `["/home/user/project", "/usr/local"]` → error for `/usr/local`, ok for project

8. **Wrap command & profile content**
   - Given `allowed_directories=["/tmp/project"]`, `needs_git=True`:
     - `wrap_command` returns string starting with `sandbox-exec -f "<profile>" claude ...`
     - Open profile file and assert:
       - `(deny default)` present
       - `file-write* (subpath "/tmp/project")` present
       - Device file rules and mach-lookup lines included

### D. CLI flows

9. **submit → staged (no auto-approve)**
   - Fake planner returns known plan
   - Run `nightshift submit "task"`
   - Assert CLI prints STAGED status and hints to use `approve`/`revise`
   - DB row has correct `allowed_directories`, `needs_git`

10. **approve on wrong state**
    - Create task in DB with status COMPLETED
    - `nightshift approve task_x` → returns non-zero exit code, error message

11. **revise updates allowed_directories**
    - Build initial task with some plan
    - Fake `refine_plan` returns updated `allowed_directories`
    - Assert DB row changed accordingly; CL output includes sandbox info

### E. Slack basic integration

12. **Signature verification**
    - Use Flask test client
    - Construct a valid Slack signature for a known body with known secret
    - POST to `/slack/commands` with that body and headers
    - Assert:
      - `_verify_signature()` returns True
      - Handler called

13. **submit via slash command (high-level)**
    - Setup:
      - Fake `SlackClient.post_message` capturing channel/blocks
      - Fake `TaskPlanner.plan_task` returning simple plan
      - SlackMetadataStore pointing to temp dir
    - POST `/slack/commands` with:
      - `command=/nightshift`
      - `text=submit "hello"`
    - Assert:
      - Immediate ephemeral response ("Planning task…")
      - Background planner thread created:
        - Metadata file written
        - `post_message` called with approval blocks

14. **approve interaction**
    - POST `/slack/interactions` with payload for `approve_task_x`
    - Assert:
      - `task_queue.update_status(task_x, COMMITTED)` called
      - A background thread starts `execute_task`
      - Slack message updated

---

Focusing on these concrete tests will quickly raise coverage in the most critical, high-risk areas (core lifecycle, sandboxing, CLI, Slack bindings), and drastically reduce regression risk without needing to exhaustively test every styling detail already covered in the TUI suite.
