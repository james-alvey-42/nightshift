# NightShift GUI - Quick Start Guide

## 🚀 Getting Started in 2 Minutes

### Installation

```bash
# Clone and install
git clone <repository-url>
cd nightshift
pip install -e .
```

### Launch the GUI

```bash
nightshift-gui
```

Or without installation:

```bash
python test_gui.py
```

## 📋 First Time Setup

1. **Verify NightShift CLI works:**
   ```bash
   nightshift queue
   ```
   If this fails, configure your Claude API key first.

2. **Launch the GUI:**
   ```bash
   nightshift-gui
   ```

3. **Submit your first task:**
   - Type in the description field: "Create a hello world Python script"
   - Click "Submit & Auto-Approve"
   - Wait 30-60 seconds
   - See the task complete in the queue!

## 🎯 Common Tasks

### Submit a Task for Review

1. Enter description: "Analyze data in /path/to/file.csv"
2. Click "Submit"
3. Review the plan in the success message
4. Task appears in queue with STAGED (orange) status
5. Select the task
6. Click "✓ Approve & Execute"
7. Wait for completion

### Submit and Execute Immediately

1. Enter description
2. Click "Submit & Auto-Approve"
3. Done! Task executes immediately

### Monitor Running Tasks

1. Enable "Auto-refresh" checkbox
2. Watch the queue update every 10 seconds
3. Task status changes: STAGED → RUNNING → COMPLETED

### View Task Results

1. Select a completed task in the queue
2. Click "📋 View Full Output"
3. See complete execution details and outputs

### Cancel a Task

1. Select a STAGED or COMMITTED task
2. Click "✗ Cancel"
3. Confirm cancellation

### Filter Tasks

1. Use the "Filter" dropdown
2. Select: all, staged, running, completed, failed, cancelled
3. Queue updates to show only selected status

## 🎨 Status Colors

Learn the colors to quickly identify task states:

| Color | Status | Meaning |
|-------|--------|---------|
| 🟠 Orange | STAGED | Waiting for your approval |
| 🔵 Blue | COMMITTED | Approved, queued for execution |
| 🔷 Cyan | RUNNING | Currently executing (be patient!) |
| 🟢 Green | COMPLETED | Success! Check the results |
| 🔴 Red | FAILED | Something went wrong |
| ⚫ Gray | CANCELLED | You cancelled this |

## ⚡ Pro Tips

1. **Press Enter to submit** - No need to click the button
2. **Enable Auto-refresh** - Stay updated without manual clicking
3. **Double-click tasks** - Opens detailed view in a popup
4. **Filter by status** - Focus on what matters
5. **Use Auto-Approve for trusted tasks** - Skip the approval step

## 🔧 Troubleshooting

### GUI won't launch

```bash
# Check if tkinter is installed
python3 -m tkinter
```

If this fails, install tkinter:
- **Ubuntu/Debian:** `sudo apt-get install python3-tk`
- **macOS:** Already included with Python
- **Windows:** Already included with Python

### "nightshift: command not found"

```bash
# Check if nightshift is installed
which nightshift

# If not found, install it
pip install -e .
```

### Tasks don't appear in queue

```bash
# Verify CLI works
nightshift queue

# Check if database exists
ls ~/.nightshift/database/
```

### Task execution fails

```bash
# Check Claude CLI
which claude

# Test Claude manually
claude -p "Hello"
```

## 📚 Learn More

- **Full GUI Guide:** See `docs/GUI_GUIDE.md`
- **Features:** See `nightshift/gui/FEATURES.md`
- **CLI Documentation:** See `CLAUDE.md`
- **GUI README:** See `nightshift/gui/README.md`

## 🤝 Getting Help

If you encounter issues:

1. Check the logs: `~/.nightshift/logs/`
2. Try the CLI to isolate GUI vs. core issues
3. Run with Python directly: `python test_gui.py`
4. Check task details with: `nightshift results <task_id> --show-output`

## 🎉 You're Ready!

Start managing your NightShift tasks visually. The GUI makes it easy to:

- ✅ Submit tasks quickly
- ✅ Monitor execution
- ✅ Review results
- ✅ Manage your queue

Enjoy using NightShift GUI! 🚀
