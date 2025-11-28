# Changelog

All notable changes to NightShift are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### ✨ Features

#### Text User Interface (TUI)
- **[bd298a0]** Fix TUI corruption by using thread-safe state updates with `loop.call_soon_threadsafe()` to prevent race conditions
- **[32cf5b7]** Implement Phase 4: Process control (pause/resume/kill) with full keybindings and command support
- **[f49921c]** Replace submit dialog with vim editor for better task composition experience
- **[a3bec54]** Add alternative refresh keybindings (R key and `:refresh` command) for better terminal compatibility
- **[bd92f99]** Implement Phase 3: Task submission and approval workflow
- **[b99c76e]** Implement Phase 1 & 2: TUI queue browser and command mode
- **[0f940ea]** Implement Phase 0: TUI skeleton with prompt_toolkit

#### Slack Integration
- **[4cffbf6]** Update README with Slack integration documentation
- **[6086c7f]** Implement Phase 1 Slack Integration (Issue #11)
- **[9e3f48a]** Add executive summary for Slack integration planning
- **[3a44355]** Create comprehensive Slack API integration plan

#### Task Control
- **[c38e5a5]** Add kill command to terminate running/paused tasks
- **[aa4e8a6]** Add real-time output streaming for watch command
- **[c1f5a66]** Add pause, resume, and watch commands for task control
- **[9f2c5a7]** Add human-readable task execution viewer

#### Security & Sandbox
- **[31777ab]** Implement working gh CLI sandbox support with GH_TOKEN
- **[05da47a]** Add keychain access permissions for gh CLI in sandbox
- **[159b8af]** Allow gh CLI config access in sandbox when needs_git=true
- **[d777fca]** Add NightShift branding to git commit attribution
- **[fdbceed]** Apply sandbox to all tasks, including read-only ones (security fix)
- **[ff249b6]** Add sandbox execution isolation for task execution
- **[527400f]** Add macOS sandbox-exec isolation for task execution
- **[e76f5a0]** Add support for literal file permissions in sandbox

#### Configuration & Planning
- **[8e1c91f]** Add configurable planning timeout option to submit command
- **[ae69d54]** Add plan revision and approval workflow
- **[c4efd6c]** Show sandbox directories in revised plan output
- **[45ecf3b]** Add database migration and allow ~/.claude for Claude CLI

### 🐛 Bug Fixes

#### TUI Fixes
- **[a003ecb]** Add error logging for task submission failures
- **[9428c3f]** Fix task submission: add missing task_id parameter to TaskQueue.create_task()
- **[76645cb]** Add error handling to Ctrl-L refresh keybinding
- **[18bac4a]** Fix TUI corruption after task completion by removing refresh from background threads

#### Sandbox & CLI Fixes
- **[c6452c4]** Fix watch command to properly parse Claude stream-json output
- **[96a2203]** Fix debug sandbox preview to include needs_git permissions
- **[a15e914]** Fix needs_git flag detection for gh CLI usage

#### Planning & Parsing Fixes
- **[236d14b]** Fix plan revision to handle structured_output format
- **[43aa988]** Fix task planner parsing for structured_output format
- **[1eba0fe]** Fix revise command: use task_queue.add_log instead of logger.add_log

### 📝 Documentation
- **[b7ad1c1]** Document gh CLI sandbox authentication solution
- **[09ea0b0]** Document gh CLI keychain workaround for sandbox
- **[cb0a340]** Add code repository management example to README
- **[d4164f0]** Add note about user-specific tools configuration
- **[ab5a166, 4c0cdb8]** Add project logo to README
- **[13d89b6, 6b6ae48, 4328f58, 167866d, ef09fbd, 71ecb6a, c9681e8, 3a33a62]** Multiple README updates

### 🔧 Technical Improvements
- **[7b4a17f]** Add system prompt directive to enforce working directory usage
- **[9068ef9]** Add debug output for sandbox command inspection

### 📦 Project Infrastructure
- **[ff1565d]** Move README.md to project root
- **[7f74631]** Initial commit: NightShift MVP

### 🔀 Merged Pull Requests
- **[4b7dd4e]** #21: Slack API integration
- **[121de54]** #16: Pause/resume/watch v2
- **[aa4fa48]** #15: Task output viewer
- **[1f428bb, 01638bf]** #6: Project logo
- **[d837ed6, a2b1738]** #5: Configurable planning timeout (by @nikhil-sarin)
- **[e4c9e97, 6cb4be5]** #4: Plan revision (by @williamjameshandley)
- **[74d709a, 16441ef]** #3: Task planner structured output fix (by @williamjameshandley)

---

## Summary

This changelog documents **72 commits** with the following major themes:

1. **TUI Development** (11 commits): Complete implementation of a terminal user interface with prompt_toolkit, including task browsing, submission, approval, and process control
2. **Slack Integration** (4 commits): Full Phase 1 implementation of Slack API integration for notifications
3. **Security & Sandboxing** (13 commits): Comprehensive macOS sandbox-exec implementation with gh CLI support and proper permission handling
4. **Task Control** (4 commits): Pause, resume, kill, and watch functionality for running tasks
5. **Bug Fixes** (8 commits): Various stability and parsing fixes, especially for TUI thread safety
6. **Documentation** (15 commits): Extensive README updates, logo addition, and technical documentation
7. **Planning Workflow** (5 commits): Plan revision, configurable timeouts, and approval workflow enhancements

### Contributors
- Will Handley (@williamjameshandley)
- James Alvey (@james-alvey-42)
- Nikhil Sarin (@nikhil-sarin)
- Claude Code (AI assistant)
