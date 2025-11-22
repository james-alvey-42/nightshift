# Claude Code Tools Reference

A comprehensive reference of all built-in and MCP server tools available in Claude Code.

**IMPORTANT NOTE:** This tools list is specific to the user's Claude Code configuration and MCP server setup. Each user must regenerate this file based on their own installed MCP servers. This particular reference is linked to the [handley-lab/mcp-handley-lab](https://github.com/handley-lab/mcp-handley-lab) GitHub repository and includes those specific MCP tools.

To regenerate this file for your own setup, run:
```bash
# List all available tools in your Claude Code environment
# Then update this file accordingly
```

## Built-in Development Tools

### File Operations

**Read** - Reads files from the filesystem
- Supports text files, images (PNG, JPG), PDFs, and Jupyter notebooks
- Can specify line offset and limit for large files
- Returns content with line numbers

**Write** - Writes or overwrites files
- Must read existing files before overwriting
- Prefer editing over creating new files

**Edit** - Performs exact string replacements in files
- Requires reading file first
- Supports replace_all for renaming across files
- Preserves exact indentation

**Glob** - Fast file pattern matching
- Supports glob patterns like `**/*.js` or `src/**/*.ts`
- Returns files sorted by modification time

**Grep** - Powerful code search built on ripgrep
- Full regex syntax support
- Filter by file type or glob pattern
- Multiple output modes: content, files_with_matches, count
- Supports multiline matching with `multiline: true`

**NotebookEdit** - Edit Jupyter notebook cells
- Replace, insert, or delete cells
- Supports code and markdown cells

### Execution & Shell

**Bash** - Executes bash commands in persistent shell
- Supports optional timeout (up to 10 minutes)
- Can run commands in background
- Chain commands with && for sequential execution
- Prefer parallel execution for independent commands

**BashOutput** - Retrieve output from background bash shells
- Monitor long-running processes
- Optional regex filtering

**KillShell** - Terminate background bash shells

### Search & Navigation

**Task** - Launch specialized agents for complex tasks
- **general-purpose**: Multi-step research and complex tasks
- **Explore**: Fast codebase exploration (quick/medium/thorough)
- **Plan**: Planning and architecture tasks
- **claude-code-guide**: Claude Code and SDK documentation

**WebFetch** - Fetch and process web content
- Converts HTML to markdown
- AI-processed results based on prompt
- 15-minute cache for repeated URLs

**WebSearch** - Search the web for current information
- Returns formatted search results with links
- Must include sources in response

### Project Management

**TodoWrite** - Manage structured task lists
- Track progress on complex tasks
- Three states: pending, in_progress, completed
- Requires both content and activeForm for each task

**AskUserQuestion** - Ask user questions during execution
- Gather preferences and clarify requirements
- Support for single or multiple choice
- Multi-select option available

### Mode Control

**ExitPlanMode** - Exit planning mode and proceed to implementation
- Only use after planning implementation steps
- Clarify ambiguities before exiting

### Tools Integration

**Skill** - Execute skills from the skill library

**SlashCommand** - Execute custom slash commands

**ListMcpResourcesTool** - List resources from MCP servers

**ReadMcpResourceTool** - Read specific MCP server resources

---

## MCP Server Tools

### ArXiv (Research Papers)

**mcp__arxiv__search** - Search ArXiv for papers
- Advanced syntax support (au:, ti:, abs:, co:)
- Boolean operators (AND, OR, ANDNOT)
- Sort by relevance, lastUpdatedDate, or submittedDate
- Configurable field inclusion for context management

**mcp__arxiv__download** - Download ArXiv papers
- Formats: src, pdf, tex
- Can list source files
- Custom output path

**mcp__arxiv__server_info** - Check ArXiv tool status

### OpenAI Integration

**mcp__openai__ask** - Delegate queries to OpenAI GPT models
- Default: gpt-5.1 (recommended)
- Other models: gpt-5, gpt-5-mini, gpt-5-nano, gpt-4.1, o3, o4-mini
- Supports prompt templates with variable substitution
- Separate conversation threads via agent_name
- Temperature control (0.0-2.0)

**mcp__openai__analyze_image** - Image analysis via OpenAI vision
- Supports multiple images (paths or base64)
- Focus areas: general, ocr, objects, etc.
- Default model: gpt-4o

**mcp__openai__generate_image** - Generate images with DALL-E
- Models: dall-e-3, dall-e-2
- Quality: standard or hd
- Various size options

**mcp__openai__get_embeddings** - Generate text embeddings
- Model: text-embedding-3-small (default)
- Supports custom dimensions for v3 models
- Single text or array of texts

**mcp__openai__calculate_similarity** - Calculate cosine similarity between texts
- Returns score from -1.0 to 1.0

**mcp__openai__index_documents** - Create semantic index from documents
- Generates and saves embeddings
- JSON output format

**mcp__openai__search_documents** - Search document index
- Returns ranked results by similarity
- Configurable top_k results

**mcp__openai__list_models** - Catalog of OpenAI models with pricing and capabilities

**mcp__openai__server_info** - Check OpenAI tool status

**mcp__openai__test_connection** - Test OpenAI API connectivity

### Google Gemini Integration

**mcp__gemini__ask** - Delegate queries to Google Gemini
- Default: gemini-3-pro-preview (most intelligent)
- Other models: gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite
- Google Search grounding support
- Template support with variables

**mcp__gemini__analyze_image** - Image analysis via Gemini vision
- Default: gemini-3-pro-preview
- Multiple images support
- Custom focus areas

**mcp__gemini__generate_image** - Generate images with Imagen 3
- Model: imagen-3.0-generate-002
- Saves as PNG files

**mcp__gemini__get_embeddings** - Generate embeddings
- Model: gemini-embedding-001
- Task types: RETRIEVAL_QUERY, RETRIEVAL_DOCUMENT, SEMANTIC_SIMILARITY, CLASSIFICATION, CLUSTERING

**mcp__gemini__calculate_similarity** - Cosine similarity between texts

**mcp__gemini__index_documents** - Create searchable semantic index

**mcp__gemini__search_documents** - Search document index

**mcp__gemini__list_models** - List Gemini models with pricing and capabilities

**mcp__gemini__server_info** - Check Gemini tool status

**mcp__gemini__test_connection** - Test Gemini API connectivity

### Anthropic Claude Integration

**mcp__claude__ask** - Delegate queries to Claude AI
- Default: claude-sonnet-4-5-20250929
- Supports aliases: sonnet, opus, haiku
- Template and file context support
- Separate conversation threads

**mcp__claude__analyze_image** - Image analysis via Claude vision
- Vision-capable Claude models
- Focus specification support

**mcp__claude__list_models** - Catalog of Claude models

**mcp__claude__server_info** - Check Claude tool status

**mcp__claude__test_connection** - Test Claude API connectivity

### Document Processing

#### Word Documents

**mcp__word__detect_format** - Detect and validate Word document format
- Supports .docx, .doc, and extracted XML

**mcp__word__extract_comments** - Extract comments with context
- DOCX and XML support

**mcp__word__extract_tracked_changes** - Extract tracked changes
- Shows insertions, deletions, formatting changes with authors

**mcp__word__docx_to_markdown** - Convert DOCX to Markdown via pandoc

**mcp__word__markdown_to_docx** - Convert Markdown to DOCX via pandoc

**mcp__word__docx_to_html** - Convert DOCX to HTML

**mcp__word__docx_to_text** - Convert DOCX to plain text

**mcp__word__analyze_document** - Comprehensive document analysis
- Metadata, structure, comments, tracked changes

**mcp__word__server_info** - Check Word tool status

**mcp__word__check_dependencies** - Check Word tool dependencies (pandoc, etc.)

#### Jupyter Notebooks

**mcp__py2nb__py_to_notebook** - Convert Python script to notebook
- Comment syntax: #| (markdown), #! (command), #- (split)
- Optional backup creation

**mcp__py2nb__notebook_to_py** - Convert notebook to Python script
- Preserves markdown as comments
- Validation support

**mcp__py2nb__validate_notebook** - Validate notebook structure

**mcp__py2nb__validate_python** - Validate Python script syntax

**mcp__py2nb__test_roundtrip** - Test conversion fidelity (py→nb→py)

**mcp__py2nb__execute_notebook** - Execute all notebook cells
- Populates outputs
- Configurable kernel, timeout, error handling

**mcp__py2nb__server_info** - Check notebook conversion tool status

#### Code2Prompt

**mcp__code2prompt__generate_prompt** - Generate LLM-ready codebase summary
- Token counting with tiktoken
- Include/exclude patterns
- Git diff support
- Multiple output formats (markdown, json)
- Line numbers, sorting options

**mcp__code2prompt__server_info** - Check Code2Prompt status

### Mathematics (Wolfram Mathematica)

**mcp__mathematica__evaluate** - Evaluate Wolfram Language expressions
- Persistent REPL session
- Output formats: Raw, InputForm, OutputForm, TeXForm
- Supports % references for previous results
- Variables persist across calls

**mcp__mathematica__session_info** - Get session information
- Version, memory usage, evaluation count

**mcp__mathematica__clear_session** - Clear user-defined variables
- Optional builtin preservation

**mcp__mathematica__restart_kernel** - Restart Mathematica kernel
- Complete fresh start

**mcp__mathematica__apply_to_last** - Apply operation to last result
- Use # as placeholder
- Chain operations easily

**mcp__mathematica__convert_latex** - Convert LaTeX to Wolfram Language
- Supports standard mathematical notation
- Fractions, integrals, sums, limits

**mcp__mathematica__save_notebook** - Save session with history
- Formats: md (markdown), wl (wolfram), wls (wolfram with outputs)

**mcp__mathematica__server_info** - Check Mathematica server status

### Google Calendar

**mcp__google-calendar__get_event** - Get event details by ID

**mcp__google-calendar__create_event** - Create new event
- Natural language datetime support
- Mixed timezone support
- Attendees, location, description

**mcp__google-calendar__update_event** - Update existing event
- Natural language rescheduling
- Fix timezone inconsistencies

**mcp__google-calendar__delete_event** - Delete event permanently

**mcp__google-calendar__move_event** - Move event between calendars

**mcp__google-calendar__list_calendars** - List accessible calendars
- IDs, access levels, colors

**mcp__google-calendar__find_time** - Find free time slots
- Defaults to next 7 days
- Work hours only option
- Configurable duration

**mcp__google-calendar__search_events** - Search events in date range
- Text search with advanced operators
- Filter by specific fields
- Case sensitivity and match logic options
- Search across all calendars or specific ones

**mcp__google-calendar__server_info** - Check Calendar tool status

**mcp__google-calendar__test_connection** - Test Calendar API connectivity

### Apple Reminders

**mcp__reminders__list_lists** - List all reminder lists

**mcp__reminders__get_reminders** - Get reminders from list(s)
- Include/exclude completed
- All lists or specific list

**mcp__reminders__create_reminder** - Create new reminder
- Name, notes, due date, priority
- Default list: "Reminders"

**mcp__reminders__update_reminder** - Update existing reminder
- Any field can be updated
- Mark as completed

**mcp__reminders__complete_reminder** - Mark reminder as completed

**mcp__reminders__delete_reminder** - Delete reminder

**mcp__reminders__search_reminders** - Search by name or body text

**mcp__reminders__create_list** - Create new reminder list

**mcp__reminders__server_info** - Check Reminders tool status

### Python Environment Management

**mcp__python-env__list_environments** - List Python environments
- Search directory recursively
- Show current environment info

**mcp__python-env__create_environment** - Create virtual environment
- Optional Python version specification
- Optional pip installation

**mcp__python-env__list_packages** - List installed packages

**mcp__python-env__install_packages** - Install packages
- Space-separated package names
- Requirements file support
- Upgrade option

**mcp__python-env__uninstall_packages** - Uninstall packages

**mcp__python-env__run_python** - Run Python code in environment

**mcp__python-env__get_activate_command** - Get activation command
- Shell-specific: bash, zsh, fish, powershell

**mcp__python-env__server_info** - Check Python environment tool status

---

## Usage Notes

- **Prefer specialized tools over bash** for file operations and common tasks
- **Use parallel tool calls** when operations are independent
- **Read files before editing** to ensure accuracy
- **Use Task tool for exploration** rather than running searches directly
- **Keep communication separate from tools** - output text directly, don't use bash echo or comments
- **MCP tools with dashes** follow the pattern `mcp__servername__toolname`

---

*Generated: 2025-11-22*
