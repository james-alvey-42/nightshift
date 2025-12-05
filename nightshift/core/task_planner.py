"""
Task Planner - Uses Claude to analyze task descriptions and plan execution
Determines which tools are needed and generates appropriate prompts
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from .logger import NightShiftLogger
from .mcp_config_manager import MCPConfigManager


class TaskPlanner:
    """Plans task execution using Claude to analyze requirements"""

    def __init__(
        self,
        logger: NightShiftLogger,
        tools_reference_path: Optional[str] = None,
        directory_map_path: Optional[str] = None,
        claude_bin: str = "claude",
        mcp_config_path: Optional[str] = None,
    ):
        self.logger = logger
        self.claude_bin = claude_bin

        # Initialize MCP config manager for dynamic config generation
        self.mcp_manager = MCPConfigManager(
            base_config_path=mcp_config_path, logger=logger
        )

        # Default to package's config directory
        if tools_reference_path is None:
            # Get the directory where this module is installed
            package_dir = Path(__file__).parent.parent
            tools_reference_path = (
                package_dir / "config" / "claude-code-tools-reference.md"
            )

        if directory_map_path is None:
            package_dir = Path(__file__).parent.parent
            directory_map_path = package_dir / "config" / "directory-map.md"

        self.tools_reference_path = Path(tools_reference_path)
        self.directory_map_path = Path(directory_map_path)

        # Load tools reference (optional)
        if self.tools_reference_path.exists():
            with open(self.tools_reference_path) as f:
                self.tools_reference = f.read()
        else:
            self.logger.warning(
                f"Tools reference not found at {self.tools_reference_path}"
            )
            self.tools_reference = ""

        # Load directory map (optional)
        if self.directory_map_path.exists():
            with open(self.directory_map_path) as f:
                self.directory_map = f.read()
            self.logger.info(f"Loaded directory map from {self.directory_map_path}")
        else:
            self.logger.info(
                f"Directory map not found at {self.directory_map_path} (this is optional)"
            )
            self.directory_map = ""

    def plan_task(self, description: str, timeout: int = 120) -> Dict[str, Any]:
        """
        Use Claude to analyze task and create execution plan

        Args:
            description: The user's task description
            timeout: Timeout in seconds for the planning subprocess (default: 120)

        Returns:
            Dict with keys:
                - enhanced_prompt: The full prompt to send to executor
                - allowed_tools: List of tool names needed
                - system_prompt: System prompt for the executor
                - estimated_tokens: Rough token estimate
                - reasoning: Why these tools were chosen
        """

        planning_prompt = f"""You are a task planning agent for NightShift, an automated research assistant system.

Your job is to analyze a user's task description and determine:
1. Which tools from the available MCP servers are needed
2. What system prompt the executor agent should use
3. How to enhance/clarify the user's prompt if needed
4. Estimated resource usage
5. **SECURITY: Which directories the task needs write access to (for sandboxing)**

USER TASK:
{description}

CURRENT WORKING DIRECTORY:
{Path.cwd()}

AVAILABLE TOOLS:
{self.tools_reference}

{self._format_directory_map_section()}

Respond with ONLY a JSON object (no other text) with this structure:
{{
    "enhanced_prompt": "The full detailed prompt for the executor agent",
    "allowed_tools": ["tool1", "tool2", ...],
    "allowed_directories": ["/absolute/path/to/dir1", "/absolute/path/to/dir2"],
    "needs_git": false,
    "system_prompt": "System prompt for the executor",
    "use_scratch": true,
    "working_directory": null,
    "scratch_git_repos": [{{"source": "/path/to/repo1"}}, {{"source": "/path/to/repo2", "dest": "custom_name"}}],
    "scratch_copy_paths": [{{"source": "/path/to/file_or_dir"}}],
    "reasoning": "Brief explanation of tool choices and directory permissions"
}}

Field explanations:
- use_scratch: true (default) to use isolated scratch directory, false to run in specified working_directory
- working_directory: If use_scratch=false, the absolute path to run in. If null, uses current directory.
- scratch_git_repos: Only used if use_scratch=true. Git repos to clone into scratch.
- scratch_copy_paths: Only used if use_scratch=true. Files/directories to copy into scratch.

Guidelines:
- Be specific about which tools are needed
- Include file operations tools (Write, Read) if outputs need to be saved
- For arxiv tasks, include mcp__arxiv__download and either mcp__gemini__ask or mcp__claude__ask for summarization

**NEEDS_GIT FLAG (CRITICAL):**
- Set needs_git to true if the task involves ANY of these:
  * Direct git operations (commit, push, pull, branch, merge, rebase, etc.)
  * Using the 'gh' CLI tool for GitHub operations (issues, PRs, releases, etc.)
  * Any GitHub API interactions via gh command
- The needs_git flag enables access to /dev/null and /dev/tty which gh CLI requires
- When in doubt, if task mentions "gh", "GitHub", or git commands → set needs_git=true

**SECURITY - Directory Sandboxing (CRITICAL):**
- The executor will run in a macOS sandbox that BLOCKS all filesystem writes except to allowed_directories
- Be DEFENSIVE: Only grant write access to the MINIMUM directories needed
- Use ABSOLUTE PATHS only (resolve relative paths from current working directory shown above)
- Common patterns:
  * If task mentions "current directory" or no specific location → ["{Path.cwd()}"]
  * If task specifies a project path → use that exact path
  * If task needs output files → only allow the output directory
  * If task modifies multiple repos → list all needed directories separately
  * NEVER allow "/" or home directory unless explicitly required
- Default to current directory if uncertain, but explain in reasoning
- The sandbox automatically allows /tmp for temporary files (no need to specify)

**SYSTEM PROMPT - Working Directory (CRITICAL):**
- The system_prompt MUST instruct the executor to work within allowed_directories, NOT /tmp
- Include this directive: "IMPORTANT: Do all work in the specified allowed paths. Do NOT use /tmp for task outputs unless specifically required for temporary intermediate files."
- The executor should save all final outputs to the explicitly specified allowed paths

**SYSTEM PROMPT - Git Commit Attribution (CRITICAL):**
- When creating git commits, ALWAYS end the commit message with:
  * 🌙 Generated by NightShift (https://github.com/james-alvey-42/nightshift)
- Choose a fun emoji prefix based on the type of change (🐛 for bug fixes, ✨ for features, 🔒 for security, 📝 for docs, ♻️ for refactoring, etc.)
- NEVER use "Claude" or "Claude Code" in commit attribution - use "NightShift" instead

**SCRATCH DIRECTORY - Resource Requirements (CRITICAL):**
- Analyze what resources the task needs access to (git repos, files, directories)
- Specify which git repositories need to be cloned into the scratch workspace
- Specify which files or directories need to be copied
- The task will execute in an isolated scratch directory with ONLY the resources you specify
- Examples:
  * Task modifying current git repo → scratch_git_repos: [{"source": "{Path.cwd()}"}]
  * Task analyzing a specific file → scratch_copy_paths: [{"source": "/path/to/file.txt"}]
  * Task working across multiple repos → list all repos in scratch_git_repos
- If uncertain, default to copying the current working directory if it's a git repo
"""

        # Generate empty MCP config for planner (planner doesn't need MCP tools)
        empty_mcp_config = None
        try:
            # Call Claude in headless mode for planning
            # Use --json-schema to enforce structured output
            json_schema = json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "enhanced_prompt": {"type": "string"},
                        "allowed_tools": {"type": "array", "items": {"type": "string"}},
                        "allowed_directories": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "needs_git": {"type": "boolean"},
                        "system_prompt": {"type": "string"},
                        "use_scratch": {"type": "boolean"},
                        "working_directory": {"type": ["string", "null"]},
                        "scratch_git_repos": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source": {"type": "string"},
                                    "dest": {"type": "string"}
                                },
                                "required": ["source"]
                            }
                        },
                        "scratch_copy_paths": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source": {"type": "string"},
                                    "dest": {"type": "string"}
                                },
                                "required": ["source"]
                            }
                        },
                        "reasoning": {"type": "string"},
                    },
                    "required": [
                        "enhanced_prompt",
                        "allowed_tools",
                        "allowed_directories",
                        "needs_git",
                        "system_prompt",
                        "use_scratch",
                        "scratch_git_repos",
                        "scratch_copy_paths",
                    ],
                }
            )

            # Create empty MCP config for planner (huge token savings!)
            empty_mcp_config = self.mcp_manager.get_empty_config(profile_name="planner")
            self.logger.info(f"Using empty MCP config for planner: {empty_mcp_config}")

            cmd = [
                self.claude_bin,
                "-p",
                planning_prompt,
                "--output-format",
                "json",
                "--json-schema",
                json_schema,
                "--mcp-config",
                empty_mcp_config,
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )

            if result.returncode != 0:
                self.logger.error(
                    f"Planning command failed with return code {result.returncode}"
                )
                self.logger.error(f"STDERR: {result.stderr}")
                self.logger.error(f"STDOUT: {result.stdout}")
                raise Exception(f"Planning failed: {result.stderr}")

            # Debug: Print raw output
            self.logger.debug("=" * 60)
            self.logger.debug("RAW PLANNING OUTPUT:")
            self.logger.debug(result.stdout[:500])
            self.logger.debug("=" * 60)

            # Parse the wrapper JSON
            wrapper = json.loads(result.stdout)

            # Extract the actual result from the wrapper
            # Check for structured_output first (new --json-schema format)
            if "structured_output" in wrapper:
                plan = wrapper["structured_output"]
            elif "result" in wrapper and wrapper["result"]:
                result_text = wrapper["result"]

                # Remove markdown code fences if present
                if result_text.startswith("```json"):
                    # Strip ```json at start and ``` at end
                    result_text = result_text.replace("```json\n", "", 1)
                    result_text = result_text.rsplit("```", 1)[0]
                elif result_text.startswith("```"):
                    result_text = result_text.replace("```\n", "", 1)
                    result_text = result_text.rsplit("```", 1)[0]

                result_text = result_text.strip()
                plan = json.loads(result_text)
            else:
                # If no wrapper, try parsing directly
                plan = wrapper

            # Validate required fields
            required_fields = [
                "enhanced_prompt",
                "allowed_tools",
                "allowed_directories",
                "needs_git",
                "system_prompt",
                "use_scratch",
                "scratch_git_repos",
                "scratch_copy_paths",
            ]
            for field in required_fields:
                if field not in plan:
                    raise Exception(f"Planning response missing field: {field}")

            # Default use_scratch to True if not specified
            if plan.get("use_scratch") is None:
                plan["use_scratch"] = True

            self.logger.debug(f"Task plan created: {plan.get('reasoning', 'N/A')}")
            self.logger.debug(f"Tools selected: {', '.join(plan['allowed_tools'])}")

            # Log estimated token savings
            savings = self.mcp_manager.estimate_token_savings(plan["allowed_tools"])
            self.logger.info(
                f"Token optimization: Loading {savings['loaded_servers']}/{savings['total_servers']} "
                f"MCP servers (est. {savings['estimated_tokens_saved']:,} tokens saved, "
                f"{savings['reduction_percent']:.1f}% reduction)"
            )

            return plan

        except subprocess.TimeoutExpired:
            self.logger.error("Task planning timed out")
            raise Exception("Task planning took too long")

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse planning response as JSON: {e}")
            self.logger.error(f"Full response was:")
            self.logger.error(result.stdout)
            raise Exception("Planning response was not valid JSON")

        except Exception as e:
            self.logger.error(f"Task planning failed: {str(e)}")
            raise

        finally:
            # Cleanup temporary MCP config
            if empty_mcp_config:
                try:
                    import os

                    os.remove(empty_mcp_config)
                except:
                    pass  # Ignore cleanup errors

    def refine_plan(
        self, current_plan: Dict[str, Any], feedback: str
    ) -> Dict[str, Any]:
        """
        Refine an existing plan based on user feedback

        Args:
            current_plan: The current plan dictionary
            feedback: User's feedback about what needs to change

        Returns:
            Dict with same structure as plan_task()
        """

        refinement_prompt = f"""You are a task planning agent for NightShift, an automated research assistant system.

A user has reviewed a task plan and requested changes. Your job is to refine the plan based on their feedback.

CURRENT PLAN:
Enhanced Prompt: {current_plan.get('enhanced_prompt', 'N/A')}
Allowed Tools: {', '.join(current_plan.get('allowed_tools', []))}
Allowed Directories: {', '.join(current_plan.get('allowed_directories', []))}
System Prompt: {current_plan.get('system_prompt', 'N/A')}
Estimated Tokens: {current_plan.get('estimated_tokens', 0)}

USER FEEDBACK:
{feedback}

CURRENT WORKING DIRECTORY:
{Path.cwd()}

AVAILABLE TOOLS:
{self.tools_reference}

{self._format_directory_map_section()}

Based on the user's feedback, create a REVISED plan. Respond with ONLY a JSON object (no other text) with this structure:
{{
    "enhanced_prompt": "The revised detailed prompt for the executor agent",
    "allowed_tools": ["tool1", "tool2", ...],
    "allowed_directories": ["/absolute/path/to/dir1", "/absolute/path/to/dir2"],
    "needs_git": false,
    "system_prompt": "Revised system prompt for the executor",
    "use_scratch": true,
    "working_directory": null,
    "scratch_git_repos": [{{"source": "/path/to/repo1"}}],
    "scratch_copy_paths": [{{"source": "/path/to/file_or_dir"}}],
    "estimated_tokens": 1000,
    "reasoning": "Brief explanation of how the feedback was incorporated"
}}

Guidelines:
- Address the specific concerns raised in the user feedback
- Maintain the overall task objectives unless feedback suggests otherwise
- Adjust tool selection if the user requests different capabilities
- Update token estimates based on scope changes
- Explain what changed in the reasoning field
- **NEEDS_GIT**: Set needs_git=true for git operations OR 'gh' CLI usage (GitHub issues, PRs, etc.)
- **SECURITY**: Only allow write access to minimum required directories (use absolute paths)
- **SYSTEM PROMPT**: Instruct executor to work in allowed_directories, NOT /tmp. Include: "IMPORTANT: Do all work in the specified allowed directories. Do NOT use /tmp for task outputs unless specifically required for temporary intermediate files."
- **GIT COMMITS**: For git commits, end with "🌙 Generated by NightShift (https://github.com/james-alvey-42/nightshift)" and use relevant emoji prefix (🐛 bugs, ✨ features, etc.). NEVER use "Claude"
"""

        # Generate empty MCP config for refinement (also doesn't need MCP tools)
        empty_mcp_config = None
        try:
            # Call Claude in headless mode for plan refinement
            json_schema = json.dumps(
                {
                    "type": "object",
                    "properties": {
                        "enhanced_prompt": {"type": "string"},
                        "allowed_tools": {"type": "array", "items": {"type": "string"}},
                        "allowed_directories": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "needs_git": {"type": "boolean"},
                        "system_prompt": {"type": "string"},
                        "use_scratch": {"type": "boolean"},
                        "working_directory": {"type": ["string", "null"]},
                        "scratch_git_repos": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source": {"type": "string"},
                                    "dest": {"type": "string"}
                                },
                                "required": ["source"]
                            }
                        },
                        "scratch_copy_paths": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source": {"type": "string"},
                                    "dest": {"type": "string"}
                                },
                                "required": ["source"]
                            }
                        },
                        "estimated_tokens": {"type": "integer"},
                        "reasoning": {"type": "string"},
                    },
                    "required": [
                        "enhanced_prompt",
                        "allowed_tools",
                        "allowed_directories",
                        "needs_git",
                        "system_prompt",
                        "use_scratch",
                        "scratch_git_repos",
                        "scratch_copy_paths",
                        "estimated_tokens",
                    ],
                }
            )

            # Create empty MCP config for plan refinement
            empty_mcp_config = self.mcp_manager.get_empty_config(
                profile_name="refine_planner"
            )

            cmd = [
                self.claude_bin,
                "-p",
                refinement_prompt,
                "--output-format",
                "json",
                "--json-schema",
                json_schema,
                "--mcp-config",
                empty_mcp_config,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                self.logger.error(
                    f"Plan refinement failed with return code {result.returncode}"
                )
                self.logger.error(f"STDERR: {result.stderr}")
                raise Exception(f"Plan refinement failed: {result.stderr}")

            # Parse the wrapper JSON
            wrapper = json.loads(result.stdout)

            # Extract the actual result from the wrapper
            # Check for structured_output first (new --json-schema format)
            if "structured_output" in wrapper:
                refined_plan = wrapper["structured_output"]
            elif "result" in wrapper and wrapper["result"]:
                result_text = wrapper["result"]

                # Remove markdown code fences if present
                if result_text.startswith("```json"):
                    result_text = result_text.replace("```json\n", "", 1)
                    result_text = result_text.rsplit("```", 1)[0]
                elif result_text.startswith("```"):
                    result_text = result_text.replace("```\n", "", 1)
                    result_text = result_text.rsplit("```", 1)[0]

                result_text = result_text.strip()
                refined_plan = json.loads(result_text)
            else:
                # If no wrapper, try parsing directly
                refined_plan = wrapper

            # Validate required fields (must match JSON schema)
            required_fields = [
                "enhanced_prompt", "allowed_tools", "allowed_directories",
                "needs_git", "system_prompt", "use_scratch",
                "scratch_git_repos", "scratch_copy_paths", "estimated_tokens"
            ]
            for field in required_fields:
                if field not in refined_plan:
                    raise Exception(f"Refined plan missing field: {field}")

            # Default use_scratch to True if not specified
            if refined_plan.get("use_scratch") is None:
                refined_plan["use_scratch"] = True

            self.logger.debug(f"Plan refined: {refined_plan.get('reasoning', 'N/A')}")
            self.logger.debug(
                f"Tools adjusted to: {', '.join(refined_plan['allowed_tools'])}"
            )

            return refined_plan

        except subprocess.TimeoutExpired:
            self.logger.error("Plan refinement timed out")
            raise Exception("Plan refinement took too long")

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse refinement response as JSON: {e}")
            self.logger.error(f"Full response was:")
            self.logger.error(result.stdout)
            raise Exception("Refinement response was not valid JSON")

        except Exception as e:
            self.logger.error(f"Plan refinement failed: {str(e)}")
            raise

        finally:
            # Cleanup temporary MCP config
            if empty_mcp_config:
                try:
                    import os

                    os.remove(empty_mcp_config)
                except:
                    pass  # Ignore cleanup errors

    def quick_estimate(self, description: str) -> Dict[str, int]:
        """
        Fallback quick estimation without calling Claude
        Used if planning fails or for simple tasks
        """
        desc_lower = description.lower()

        # Simple heuristics (generous for debugging)
        if any(word in desc_lower for word in ["arxiv", "paper", "article"]):
            return {
                "estimated_tokens": 2500,
                "estimated_time": 300,  # 5 minutes for paper tasks
            }
        elif any(word in desc_lower for word in ["csv", "data", "analyze", "plot"]):
            return {
                "estimated_tokens": 1500,
                "estimated_time": 300,  # 5 minutes for data analysis
            }
        else:
            return {"estimated_tokens": 500, "estimated_time": 120}  # 2 minutes default

    def _format_directory_map_section(self) -> str:
        """
        Format the directory map section for the planning prompt.
        Returns empty string if no directory map is available.
        """
        if not self.directory_map:
            return ""

        return f"""DIRECTORY STRUCTURE MAP:
{self.directory_map}

When determining allowed_directories, you can use this map to:
- Resolve directory paths by number (e.g., "40.47" for a specific project)
- Find related directories for multi-aspect projects (software, notes, papers, data)
- Identify appropriate locations for task outputs
- Understand the user's file organization structure"""
