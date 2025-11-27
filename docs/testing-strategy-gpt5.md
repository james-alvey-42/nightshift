# NightShift TUI Testing Strategy (GPT-5.1 Analysis)

**Original Question**: How easy would it be to write a comprehensive test suite for this TUI?

**GPT-5.1 Response** (2025-11-27):

---

## 1. How easy would it be to write a comprehensive test suite for this TUI?

Not "easy", but very doable if you slice it correctly.

Your current structure is actually quite testable:

- `TUIController` is pure Python logic with clear inputs/outputs.
- `UIState` is a plain dataclass.
- `widgets.py` uses `FormattedTextControl` with a `get_text` function that's easy to call directly.
- `app.create_app()` wires everything together.

The hard parts:

- Full end‑to‑end tests that drive real keypresses through `prompt_toolkit` and wait for async/background behaviors.
- Integration with real `TaskQueue`, `TaskPlanner`, `AgentManager`, filesystem, and the async auto‑refresh.

So you can get good coverage of behavior and regressions by focusing heavily on controller + widgets, and only doing a small number of higher‑level prompt_toolkit integration tests.

---

## 2. What testing approaches would you recommend for prompt_toolkit applications?

Three layers:

### A. Unit tests of controller and pure helpers

- Use `pytest` and `unittest.mock`.
- Instantiate `UIState` + `TUIController` with **fake/mocked**:
  - `TaskQueue`
  - `TaskPlanner`
  - `AgentManager`
  - `NightShiftLogger`
  - `Config` (or give a simple stub)

You can test:

- Task list refresh & filtering.
- Selection changes (`selected_index`) + `load_selected_task_details`.
- Command parsing (`execute_command`).
- Exec log loading & auto‑update logic (`_load_exec_snippet`, `_maybe_reload_exec_snippet`).
- Actions (`approve_selected_task`, `reject_selected_task`, pause/resume/kill, submit).

These are synchronous functions and easy to test.

### B. Unit tests of widgets / rendering

- Instantiate `UIState` in a test.
- Call `DetailControl(state).get_text()` and `TaskListControl(state).get_text()` directly.
- Assert on the formatted output tuples: styles and strings.

No terminal is needed; they are just functions.

### C. Targeted integration tests with prompt_toolkit

- Use `prompt_toolkit`'s `create_app_session` or `DummyApplication` and `AppTest` pattern.
- Simulate key presses and assert how `UIState` changes, or how `get_text()` output changes.

Example: press `j` and see `selected_index` increment; press `2` to switch tabs and see detail panel render exec log.

These tests are more complex but you only need a few to verify that:

- Keybindings are wired.
- Focus switching and command mode works.
- Auto‑refresh doesn't crash.

---

## 3. Main challenges in testing this kind of interactive UI

- **Asynchronous behavior**:
  - `auto_refresh()` is a background coroutine.
  - `_run_in_thread` spawns threads that mutate `state` and call `invalidate`.
- **Terminal‑driven event loop**:
  - `Application.run_async()` usually blocks; you need to run it in a controlled test context and not wait indefinitely.
- **Prompt_toolkit rendering**:
  - Output is not a simple string; it's a sequence of styled fragments.
- **External dependencies**:
  - SQLite `TaskQueue`
  - `TaskPlanner` / `AgentManager` (which talk to Claude CLI and the filesystem)
- **Global functions** like `get_app()` in the controller and widgets; in tests you often don't have a live prompt_toolkit app, so you must stub/mask that.

All of this argues for a heavy focus on **controller + widgets** with mocks, and a light touch for full E2E.

---

## 4. Should we test at the controller level, the widget level, or both?

Both, with different goals:

- **Controller tests**: "Does the right state and file I/O happen when commands/actions run?"
  - Example: `pause_selected_task` calls `agent.pause_task`, updates `message`, and refreshes tasks when status is RUNNING.
  - Example: `load_selected_task_details` correctly reloads exec logs for RUNNING tasks only when the file changes.
- **Widget tests**: "Given a particular `UIState`, what do we render?"
  - Example: exec tab shows "No execution log available" when `exec_snippet` is empty.
  - Example: overview tab shows correct emoji/color for `RUNNING`.
  - Example: summary tab includes truncated error block.

Use integration tests only to ensure that keybindings and layout wiring actually call into these tested units.

---

## 5. Good starting point for adding tests incrementally

A practical incremental plan:

### Step 1: Controller unit tests (no prompt_toolkit)

Create `tests/test_controller_basic.py` and set up a minimal harness:

```python
# tests/conftest.py
import types
import pytest
from nightshift.tui.models import UIState
from nightshift.tui.controllers import TUIController

class DummyQueue:
    def __init__(self, tasks):
        self._tasks = {t.task_id: t for t in tasks}
    def list_tasks(self, status=None):
        # ignore status for now; return everything
        return list(self._tasks.values())
    def get_task(self, task_id):
        return self._tasks.get(task_id)
    # add any minimal methods you need: update_status, create_task, ...

class DummyConfig:
    def get_output_dir(self): return "/tmp"
    def get_notifications_dir(self): return "/tmp"

class DummyPlanner:
    def plan_task(self, desc): return {"enhanced_prompt": desc}

class DummyAgent:
    def execute_task(self, task): pass
    def pause_task(self, tid): pass
    def resume_task(self, tid): pass
    def kill_task(self, tid): pass

class DummyLogger:
    def info(self, msg): pass
    def error(self, msg): pass

@pytest.fixture
def controller(tmp_path):
    from nightshift.core.task_queue import TaskStatus

    # create a fake task object with the attrs the controller expects
    Task = types.SimpleNamespace
    t1 = Task(
        task_id="task_1",
        status=TaskStatus.RUNNING.value,
        description="Test task",
        created_at="2025-01-01T00:00:00",
        result_path=str(tmp_path / "task_1_result.json"),
        to_dict=lambda: {
            "task_id": "task_1",
            "status": TaskStatus.RUNNING.value,
            "description": "Test task",
            "created_at": "2025-01-01T00:00:00",
            "result_path": str(tmp_path / "task_1_result.json"),
        },
    )

    state = UIState()
    queue = DummyQueue([t1])
    cfg = DummyConfig()
    planner = DummyPlanner()
    agent = DummyAgent()
    logger = DummyLogger()

    return state, TUIController(state, queue, cfg, planner, agent, logger), tmp_path
```

Then write specific tests, e.g. for exec log refresh:

```python
# tests/test_controller_exec_log.py
import json
import time
from nightshift.core.task_queue import TaskStatus

def write_result(path, lines):
    data = {"stdout": "\n".join(json.dumps(e) for e in lines)}
    path.write_text(json.dumps(data))

def test_exec_log_updates_for_running_task(controller):
    state, ctl, tmp_path = controller
    # simulate one running task in queue
    ctl.refresh_tasks()
    assert len(state.tasks) == 1

    result_path = tmp_path / "task_1_result.json"

    # Initial log: one line
    write_result(result_path, [{"type": "text", "text": "hello"}])

    # First load: selection changed, so _load_exec_snippet is used
    ctl.load_selected_task_details()
    st = state.selected_task
    assert "hello" in st.exec_snippet

    # Append another line and bump mtime
    time.sleep(0.01)  # ensure mtime changes
    write_result(result_path, [
        {"type": "text", "text": "hello"},
        {"type": "text", "text": "world"},
    ])

    prev_snippet = st.exec_snippet
    prev_mtime = st.log_mtime
    prev_size = st.log_size

    # Simulate auto-refresh: same task selected, status RUNNING
    ctl.load_selected_task_details()
    st = state.selected_task

    # Metadata should have changed
    assert st.log_mtime != prev_mtime or st.log_size != prev_size
    # Snippet should now include "world"
    assert "world" in st.exec_snippet
    assert st.exec_snippet != prev_snippet
```

This directly verifies the logic that was previously failing (and would have caught the bug you had).

### Step 2: Widget tests

Test something like:

```python
# tests/test_widgets_detail.py
from nightshift.tui.models import UIState, SelectedTaskState
from nightshift.tui.widgets import DetailControl

def test_detail_exec_tab_no_log_shows_message():
    state = UIState()
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "running"}
    st.exec_snippet = ""
    state.detail_tab = "exec"

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()
    # last fragment is ("class:dim", "No execution log available\n")
    assert any("No execution log available" in text for style, text in fragments)

def test_detail_exec_tab_renders_log_lines():
    state = UIState()
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "running"}
    st.exec_snippet = "hello\n🔧 tool: arg\n✅ done"
    state.detail_tab = "exec"

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()
    full_text = "".join(text for _, text in fragments)
    assert "hello" in full_text
    assert "tool" in full_text
    assert "done" in full_text
```

These are low‑cost, high‑value: if you change how `selected_task` is interpreted, or break the exec tab, tests will flag it.

### Step 3: Minimal integration test for keybindings / layout

Use `prompt_toolkit`'s test utilities, for example:

```python
# tests/test_app_integration.py
import asyncio
import pytest
from prompt_toolkit.application import Application
from nightshift.tui.app import create_app

@pytest.mark.asyncio
async def test_navigation_updates_selection(monkeypatch):
    app = create_app()

    # initial state
    state = app.layout.container.content.content.children[0].content.state  # brittle: better to expose state from factory

    # Ensure at least 2 tasks exist by mocking queue.list_tasks if needed,
    # or inject a custom app factory for tests.

    # Simulate pressing 'j' then 'k'
    async def runner():
        app.inject_key("j")
        await asyncio.sleep(0)  # let event loop process
        idx_after_j = state.selected_index
        app.inject_key("k")
        await asyncio.sleep(0)
        idx_after_k = state.selected_index
        app.exit()
        return idx_after_j, idx_after_k

    task = asyncio.create_task(runner())
    await app.run_async()
    idx_after_j, idx_after_k = await task

    assert idx_after_j == 1
    assert idx_after_k == 0
```

In practice, you'll want a special `create_app_for_test` that:

- Uses in‑memory queue/planner/agent.
- Disables auto‑refresh, or you control it manually.

So for prompt_toolkit integration, keep it minimal and focused.

---

## 6. Specific testing libraries / patterns for this architecture

Recommended stack:

- `pytest` as the test runner.
- `pytest-asyncio` for async tests when you interact with `Application.run_async`.
- `unittest.mock` (`MagicMock`, `patch`) to replace:
  - `TaskQueue`, `TaskPlanner`, `AgentManager`.
  - `Config` methods to use temp dirs.
  - `prompt_toolkit.application.current.get_app` when you call `_invalidate` in controller.
- `tmp_path` fixture from `pytest` for writing result JSON files.

Patterns:

- **Dependency Injection for tests**: You already construct everything in `create_app()`. Extract a second factory for tests that accepts injected queue/planner/agent/logger/config and returns `(app, state, controller)`. That will make tests easier and avoid touching the real SQLite or Claude CLI.

  For example:

  ```python
  # app.py
  def create_app_with_backends(queue, planner, agent, logger, config) -> Application:
      state = UIState()
      controller = TUIController(state, queue, config, planner, agent, logger)
      controller.refresh_tasks()
      ...
      return app
  ```

- **Controller‑first testing**: Most behavior should be validated via `TUIController` methods and `UIState` assertions.
- **Widget snapshot tests**: Treat `get_text()` output as a "snapshot"; you can compare strings or fragments, or even pretty‑print them and compare against a known baseline.

---

## Putting it together: a practical testing strategy

1. Add a `tests/` directory with `pytest` config.
2. Start with controller tests:
   - `test_refresh_tasks_filters_and_selection`
   - `test_load_selected_task_details_initial_load`
   - `test_exec_log_updates_for_running_task` (like above)
   - `test_execute_command_queue_status_results_help_quit`
   - `test_pause_resume_kill_paths`
3. Add widget tests for `DetailControl` and `TaskListControl` that ensure key UI output for different states.
4. Once these are stable, add 1–3 small integration tests using a test app factory and prompt_toolkit's input simulation to ensure:
   - Keybindings move selection.
   - Tab switching affects which view is rendered.
   - Command mode toggles and calls `execute_command`.

This incremental approach will give you fast, reliable tests that cover most regressions without trying to fully simulate an interactive terminal session for every case.

---

## Implementation Status

**✅ Step 1 Complete**: Controller unit tests (28 tests)
- Exec log loading and real-time updates
- File tracking and summary loading
- Edge cases and error handling

**✅ Step 2 Complete**: Widget rendering tests (31 tests)
- TaskListControl (7 tests)
- DetailControl (24 tests)

**⏳ Step 3 Pending**: Minimal integration tests with prompt_toolkit
- Not yet implemented

**Total Test Coverage**: 59 tests passing in ~0.36s
