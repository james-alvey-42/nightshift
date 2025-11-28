# Step 3: Integration Tests Implementation Plan (GPT-5.1)

**Generated**: 2025-11-27
**Context**: Comprehensive testing strategy for NightShift TUI - Step 3 (Integration Tests)

---

## 1. Test Infrastructure

### 1.1 `create_app_for_test` factory

Add a dedicated factory that:

- Uses existing test doubles (DummyQueue, DummyConfig, DummyPlanner, DummyAgent, DummyLogger)
- Returns both the `Application` and the `UIState` (and optionally the `TUIController` & DummyQueue/Agent) so tests can assert on state instead of spelunking into the layout

Example (new file `nightshift/interfaces/tui/test_app_factory.py` or add to `app.py` behind a guard):

```python
# nightshift/interfaces/tui/app.py

from prompt_toolkit.application import Application
from prompt_toolkit.styles import Style

from .models import UIState
from .layout import create_layout, create_command_line
from .keybindings import create_keybindings
from .controllers import TUIController

# Only imported by tests
try:
    from tests.conftest import DummyQueue, DummyConfig, DummyPlanner, DummyAgent, DummyLogger
except Exception:  # pragma: no cover
    DummyQueue = DummyConfig = DummyPlanner = DummyAgent = DummyLogger = None


def create_app_for_test(tasks=None, tmp_path=None, disable_auto_refresh: bool = True):
    """
    Create an Application wired with test doubles.

    Returns:
        (app, state, controller, queue, agent, logger)
    """
    assert DummyQueue is not None, "create_app_for_test should only be used in tests"

    # Backends
    config = DummyConfig(tmp_path)
    logger = DummyLogger()

    # Default tasks list
    if tasks is None:
        tasks = []

    queue = DummyQueue(tasks)
    planner = DummyPlanner()
    agent = DummyAgent()

    # UI state + controller
    state = UIState()
    controller = TUIController(state, queue, config, planner, agent, logger)

    # Initial load
    controller.refresh_tasks()
    state.message = f"Loaded {len(state.tasks)} tasks"

    # UI pieces
    cmd_widget = create_command_line(state)
    layout = create_layout(state, cmd_widget)
    key_bindings = create_keybindings(state, controller, cmd_widget)

    style = Style.from_dict({
        # minimal style is fine; re-use from create_app or inline
        "statusbar": "reverse",
    })

    app = Application(
        layout=layout,
        key_bindings=key_bindings,
        full_screen=False,
        style=style,
        mouse_support=False,
    )

    if not disable_auto_refresh:
        # Copy auto_refresh logic from create_app, but keep it optional
        import asyncio

        async def auto_refresh():
            while True:
                await asyncio.sleep(2)
                try:
                    controller.refresh_tasks()
                    app.invalidate()
                except Exception as e:
                    logger.error(f"Auto-refresh failed: {e}")

        app.pre_run_callables.append(
            lambda: app.create_background_task(auto_refresh())
        )

    return app, state, controller, queue, agent, logger
```

Notes:

- `full_screen=False` in tests makes things faster and simpler; layout still works the same
- `disable_auto_refresh=True` by default so tests don't have background tasks; you can explicitly turn it on in a specific test if desired

### 1.2 Handling `Application.run_async()` in tests

Use `pytest-asyncio` and run `app.run_async()` inside an async test. Ensure you always have a path to call `app.exit()` so it doesn't hang:

```python
@pytest.mark.asyncio
async def test_something():
    app, state, *_ = create_app_for_test(...)
    async def stop_soon():
        await asyncio.sleep(0.05)
        app.exit()

    asyncio.create_task(stop_soon())
    await app.run_async()
    # assert on state
```

Better: don't rely on timeouts; instead, exit the app when your scripted key sequence finishes.

### 1.3 Mock/control auto-refresh

Options:

- Primary: use `create_app_for_test(..., disable_auto_refresh=True)` in all integration tests
- If you want a test that specifically checks "auto-refresh doesn't crash":
  - Enable it in that test only (pass `disable_auto_refresh=False`)
  - Monkeypatch `asyncio.sleep` inside that test to return immediately or with a tiny delay
  - Or monkeypatch `controller.refresh_tasks` to a lightweight stub that toggles a flag, so you can observe it being called

Example:

```python
@pytest.mark.asyncio
async def test_auto_refresh_runs_without_crashing(monkeypatch):
    app, state, controller, *_ = create_app_for_test(disable_auto_refresh=False)

    calls = []

    def safe_refresh():
        calls.append("refresh")

    monkeypatch.setattr(controller, "refresh_tasks", safe_refresh)

    async def stopper():
        # let the auto-refresh run a couple of times
        await asyncio.sleep(0.05)
        app.exit()

    asyncio.create_task(stopper()
    await app.run_async()

    assert calls  # at least one refresh occurred
```

### 1.4 Injecting test doubles

Two approaches:

- As shown above: import them in `app.py` under a try/except that only works in tests. This keeps tests simple but adds a soft test dependency to your prod code.
- Or, better: move the Dummy* classes into a new module under `nightshift/interfaces/tui/testing_doubles.py` so they're importable from both `tests` and `app.py` without circularity. You can still only use `create_app_for_test` in tests.

Example refactor:

```python
# nightshift/interfaces/tui/testing_doubles.py
class DummyQueue: ...
class DummyConfig: ...
...

# tests/conftest.py
from nightshift.interfaces.tui.testing_doubles import DummyQueue, DummyConfig, ...
```

Then `create_app_for_test` imports them from this new module.

---

## 2. Specific Test Cases

Aim for 3–5 integration tests that each validate a distinct "wiring" behavior.

### 2.1 Test 1 – Basic list navigation keybindings

**Behavior**: `j` and `k` keybindings move `state.selected_index` up/down in the task list.

- **Keys**: `j`, `j`, `k`, then exit (`q` or Ctrl-C or explicit `get_app().exit()`)
- **Setup**:
  - Create 3 dummy tasks
  - Use `create_app_for_test` with those tasks
- **Assertions**:
  - After one `j`, `selected_index == 1`
  - After second `j`, `selected_index == 2`
  - After `k`, `selected_index == 1`

Example:

```python
# tests/test_app_integration_navigation.py
import types
import pytest
from nightshift.interfaces.tui.app import create_app_for_test

def make_task(task_id, status="running"):
    t = types.SimpleNamespace(
        task_id=task_id,
        status=status,
        description=f"Task {task_id}",
        created_at="2025-01-01T00:00:00",
        result_path=None,
    )
    t.to_dict = lambda: {
        "task_id": t.task_id,
        "status": t.status,
        "description": t.description,
        "created_at": t.created_at,
        "result_path": t.result_path,
    }
    return t

@pytest.mark.asyncio
async def test_j_k_navigation_moves_selection():
    tasks = [make_task(f"task_{i}") for i in range(3)]
    app, state, *_ = create_app_for_test(tasks=tasks)

    async def drive_keys():
        # start at 0
        assert state.selected_index == 0
        await app.key_processor.feed("j")
        await app.key_processor.feed("j")
        await app.key_processor.feed("k")
        app.exit()

    # Kick off key driving and run the app
    import asyncio
    asyncio.create_task(drive_keys())
    await app.run_async()

    # After j, j, k we should be on index 1
    assert state.selected_index == 1
```

### 2.2 Test 2 – Tab switching via `1`–`4` keybindings

**Behavior**: numeric keys switch `state.detail_tab` between `"overview"`, `"exec"`, `"files"`, `"summary"`.

- **Keys**: `'2'`, `'3'`, `'4'`, `'1'`, then exit
- **Setup**:
  - Single dummy task with `to_dict()` returning minimal details so overview is non-empty
- **Assertions**:
  - After `'2'` → `detail_tab == "exec"`
  - After `'3'` → `"files"`
  - After `'4'` → `"summary"`
  - After `'1'` → `"overview"`

### 2.3 Test 3 – Command mode toggle and execute `:help`

**Behavior**:

- `:` enters command mode (`state.command_active=True`)
- Typing `help` and pressing Enter calls `execute_command` and populates a help message

- **Keys sequence**:
  - `':'`, `h`, `e`, `l`, `p`, `Enter`, then exit
- **Assertions**:
  - Command mode is activated when `:` is pressed
  - After Enter:
    - `state.command_active` is False again
    - `state.message` contains `"Commands:"` and `":queue"` (or use a substring check based on `_cmd_help`)

### 2.4 Test 4 – `:queue` filter updates task list

**Behavior**: `:queue running` filters visible tasks by status and updates `state.status_filter`.

- **Setup**:
  - DummyQueue with a mix of statuses: staged, running, failed
- **Keys**:
  - `':'`, `q`, `u`, `e`, `u`, `e`, `space`, `r`, `u`, `n`, `n`, `i`, `n`, `g`, `Enter`
  - Then exit
- **Assertions**:
  - `state.status_filter == "running"`
  - `len(state.tasks)` equals number of running tasks in DummyQueue
  - `all(row.status == "running" for row in state.tasks)`

### 2.5 Test 5 – Auto-refresh background task doesn't crash (optional)

**Behavior**:

- The auto-refresh coroutine runs periodically and calls `controller.refresh_tasks()` and `app.invalidate()`
- Test ensures no exceptions, and refresh is called at least once

As described in 1.3.

---

## 3. Technical Approach

### 3.1 Recommended prompt_toolkit utilities / patterns

For your needs:

- `Application` directly with:
  - `create_app_session()` and `create_pipe_input()` to simulate keyboard input at the terminal level
  - Or `app.key_processor` / `app.create_background_task` for more fine-grained integration

If you prefer a higher-level pattern, you can emulate an `AppTest`:

- Create an input pipe
- Create the application with that pipe as `input`
- Write key sequences into the pipe
- Run `run_async()` and exit when done

### 3.2 Async event loop with pytest

Install `pytest-asyncio` and use:

```python
pytest_plugins = ["pytest_asyncio"]

# in pytest.ini or conftest:
[pytest]
asyncio_mode = auto
```

Then decorate tests with `@pytest.mark.asyncio`.

### 3.3 Simulating key presses

The most robust way is via a `PipeInput` and `create_app_session`:

```python
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.application import create_app_session

@pytest.mark.asyncio
async def test_navigation_with_pipe_input():
    from nightshift.interfaces.tui.app import create_app_for_test

    pipe_input = create_pipe_input()
    try:
        with create_app_session(input=pipe_input):
            app, state, *_ = create_app_for_test(...)

            async def drive():
                # Feed actual key sequences: 'j', 'k', ':' etc.
                pipe_input.send_text("j")
                pipe_input.send_text("j")
                pipe_input.send_text("k")
                pipe_input.send_text("q")  # assuming 'q' is bound to quit

            import asyncio
            asyncio.create_task(drive())
            await app.run_async()

        # Now assert on `state`
        assert state.selected_index == 1
    finally:
        pipe_input.close()
```

Details:

- `pipe_input.send_text("j")` sends that character as if typed by a human
- For Enter, use `"\r"` or `"\n"`. Prompt_toolkit usually treats `"\r"` as Enter:

  ```python
  pipe_input.send_text("\r")
  ```

- For colon-commands, you literally type `":"` + text + `"\r"`

### 3.4 Avoiding hangs

Key rules:

- Always have a termination path: a keybinding that calls `app.exit()` (`q` in your keybindings) or schedule `app.exit()` from a task when your scripted sequence finishes
- Keep scripts short: feed the necessary keys in a task, then exit
- Use `asyncio.wait_for` around `app.run_async()` if you're concerned about accidental hangs:

  ```python
  await asyncio.wait_for(app.run_async(), timeout=1.0)
  ```

---

## 4. Challenges & Solutions

### 4.1 `get_app()` in controller without a real app

In controller `_invalidate()`:

```python
def _invalidate(self):
    try:
        get_app().invalidate()
    except Exception:
        pass
```

This is already safe: in tests without an active app, it simply does nothing. When using `create_app_session`, `get_app()` will return the right `Application` instance, so invalidation works.

Nothing special needed beyond ensuring you wrap tests that use `create_app_for_test` inside `create_app_session` so `get_app()` is valid.

### 4.2 Disabling/controlling 2-second auto-refresh

Covered in 1.3:

- Default: disabled in `create_app_for_test`
- Opt-in test: enable and monkeypatch `asyncio.sleep` or `controller.refresh_tasks`

### 4.3 Verifying rendering without a real terminal

You already do this for widgets by calling `get_text()` on the controls.

For integration tests, you usually don't need to assert on "pixels". Instead:

- Assert on `state` changes (e.g., `detail_tab`, `selected_index`, `status_filter`, `command_active`)
- Optionally, after a state change, instantiate the corresponding widget (e.g., `DetailControl(state)`) and call `get_text()` as you do in widget tests

Example:

```python
from nightshift.interfaces.tui.widgets import DetailControl

# After simulating '4' => summary tab:
summary_text = "".join(t for _, t in DetailControl(state).get_text())
assert "Task Summary" in summary_text
```

This keeps integration tests focused on wiring, not rendering.

### 4.4 Other gotchas

- Background threads in controller (`_run_in_thread`) could be triggered if you test submit/approve actions via keybindings. For minimal integration coverage, avoid testing those via PTK—continue covering them at controller level.
- Global state: `create_app_session()` manages the `get_app()` stack; ensure each test that uses it is self-contained and closes its `pipe_input`.
- Flakiness from timing: avoid tests that rely on "wait 0.1s and hope background work is done" unless absolutely necessary.

---

## 5. Implementation Order

Recommended incremental order:

1. **Implement infrastructure:**
   - Add `create_app_for_test` factory (with auto-refresh disabled by default)
   - Optionally move Dummy* classes into a shared module

2. **Test 1 – Simplest navigation:**
   - Implement `test_j_k_navigation_moves_selection` using `create_pipe_input` + `create_app_session` + `create_app_for_test`
   - Confirm you can send keys and exit via `q` or `app.exit()`

3. **Test 2 – Tab switching:**
   - Build on the same pattern to assert `state.detail_tab` transitions when pressing `1`–`4`

4. **Test 3 – Command mode + :help:**
   - Add a test that types `":"`, `help`, `Enter` and asserts `command_active` toggling and `state.message` contents

5. **Test 4 – :queue filter:**
   - Add the filter test validating `status_filter` and filtered tasks

6. **(Optional) Test 5 – auto-refresh robustness:**
   - Enable auto-refresh in one test and assert `refresh_tasks` is called without error

After these, you'll have:

- Verified that keybindings are wired to controller actions (navigation, tab-switching)
- Verified that command mode works end-to-end (keybinding + command-line widget + `execute_command`)
- Optionally verified that background auto-refresh behaves safely

This is minimal but effective integration coverage that complements your strong controller and widget tests.
