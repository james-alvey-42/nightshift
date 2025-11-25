"""
NightShift CLI Interface
Provides commands for task submission, approval, and monitoring
"""
import click
import uuid
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
import json

from ..core.task_queue import TaskQueue, TaskStatus
from ..core.task_planner import TaskPlanner
from ..core.agent_manager import AgentManager
from ..core.logger import NightShiftLogger
from ..core.config import Config
from ..core.output_viewer import OutputViewer


# Initialize rich console for pretty output
console = Console()


@click.group()
@click.pass_context
def cli(ctx):
    """NightShift - Automated Research Assistant System"""
    # Initialize core components
    ctx.ensure_object(dict)

    # Load configuration
    config = Config()
    ctx.obj['config'] = config

    # Initialize components with config paths
    ctx.obj['logger'] = NightShiftLogger(log_dir=str(config.get_log_dir()))
    ctx.obj['task_queue'] = TaskQueue(db_path=str(config.get_database_path()))
    ctx.obj['task_planner'] = TaskPlanner(
        ctx.obj['logger'],
        tools_reference_path=str(config.get_tools_reference_path())
    )
    ctx.obj['agent_manager'] = AgentManager(
        ctx.obj['task_queue'],
        ctx.obj['logger'],
        output_dir=str(config.get_output_dir())
    )


@cli.command()
@click.argument('description')
@click.option('--auto-approve', is_flag=True, help='Skip approval and execute immediately')
@click.option('--planning-timeout', default=120, type=int, help='Timeout in seconds for task planning (default: 120)')
@click.option('--allow-dir', multiple=True, help='Additional directories to allow writes (can be specified multiple times)')
@click.option('--debug', is_flag=True, help='Show full command and sandbox profile')
@click.pass_context
def submit(ctx, description, auto_approve, planning_timeout, allow_dir, debug):
    """Submit a new task (with sandbox isolation on macOS)"""
    logger = ctx.obj['logger']
    task_queue = ctx.obj['task_queue']
    task_planner = ctx.obj['task_planner']
    agent_manager = ctx.obj['agent_manager']

    console.print(f"\n[bold blue]Planning task...[/bold blue]")

    try:
        # Use Claude to plan the task
        plan = task_planner.plan_task(description, timeout=planning_timeout)

        # Generate unique task ID
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        # Merge planner's suggested directories with user-provided ones
        allowed_directories = list(plan.get('allowed_directories', []))
        if allow_dir:
            # Convert relative paths to absolute
            for dir_path in allow_dir:
                abs_path = str(Path(dir_path).resolve())
                if abs_path not in allowed_directories:
                    allowed_directories.append(abs_path)

        # Create task in STAGED state
        task = task_queue.create_task(
            task_id=task_id,
            description=plan['enhanced_prompt'],
            allowed_tools=plan['allowed_tools'],
            allowed_directories=allowed_directories,
            needs_git=plan.get('needs_git', False),
            system_prompt=plan['system_prompt'],
            estimated_tokens=plan['estimated_tokens'],
            estimated_time=plan['estimated_time']
        )

        logger.log_task_created(task_id, description)

        # Display plan
        console.print(f"\n[bold green]✓ Task created:[/bold green] {task_id}")

        # Format directories display
        dirs_display = "\n".join(f"  • {d}" for d in allowed_directories) if allowed_directories else "  (none)"

        # Add git status if enabled
        git_status = " + git support (device files)" if plan.get('needs_git', False) else ""

        panel = Panel.fit(
            f"[yellow]Original:[/yellow] {description}\n\n"
            f"[yellow]Enhanced prompt:[/yellow] {plan['enhanced_prompt']}\n\n"
            f"[yellow]Tools needed:[/yellow] {', '.join(plan['allowed_tools'])}\n\n"
            f"[yellow]Sandbox (write access):[/yellow]\n{dirs_display}{git_status}\n\n"
            f"[yellow]Estimated:[/yellow] ~{plan['estimated_tokens']} tokens, ~{plan['estimated_time']}s\n\n"
            f"[yellow]Reasoning:[/yellow] {plan.get('reasoning', 'N/A')}",
            title=f"Task Plan: {task_id}",
            border_style="blue"
        )
        console.print(panel)

        if auto_approve:
            console.print(f"\n[bold yellow]Auto-approving and executing...[/bold yellow]")
            task_queue.update_status(task_id, TaskStatus.COMMITTED)
            logger.log_task_approved(task_id)

            # Show debug info if requested
            if debug:
                # Get the command that will be executed
                from ..core.sandbox import SandboxManager
                cmd_parts = [agent_manager.claude_bin, "-p"]
                cmd_parts.append(f'"{task.description}"')
                cmd_parts.extend(["--output-format", "stream-json", "--verbose"])
                if task.allowed_tools:
                    cmd_parts.append(f"--allowed-tools {' '.join(task.allowed_tools)}")
                claude_cmd = " ".join(cmd_parts)

                if agent_manager.sandbox:
                    # Show sandbox profile (all tasks are sandboxed when sandbox is enabled)
                    temp_sandbox = SandboxManager()
                    profile_path = temp_sandbox.create_profile(
                        task.allowed_directories or [],  # Empty list for read-only tasks
                        f"{task_id}_debug",
                        needs_git=bool(task.needs_git)
                    )

                    console.print("\n[bold cyan]🔍 Debug Information[/bold cyan]")
                    console.print(f"[dim]Sandbox profile: {profile_path}[/dim]\n")

                    with open(profile_path) as f:
                        profile_content = f.read()

                    syntax = Syntax(profile_content, "scheme", theme="monokai", line_numbers=True)
                    console.print(Panel(syntax, title="Sandbox Profile", border_style="cyan"))

                    wrapped_cmd = f'sandbox-exec -f "{profile_path}" {claude_cmd}'
                    console.print(f"\n[bold cyan]Full command:[/bold cyan]")
                    console.print(f"[dim]{wrapped_cmd}[/dim]\n")

                    temp_sandbox.cleanup()
                else:
                    console.print(f"\n[bold cyan]🔍 Debug - Full command:[/bold cyan]")
                    console.print(f"[dim]{claude_cmd}[/dim]\n")

            console.print(f"\n[bold blue]▶ Executing task...[/bold blue]\n")
            result = agent_manager.execute_task(task)

            if result['success']:
                console.print(f"\n[bold green]✓ Task completed successfully![/bold green]")
                console.print(f"Token usage: {result.get('token_usage', 'N/A')}")
                console.print(f"Execution time: {result['execution_time']:.1f}s")
                console.print(f"Results saved to: {result.get('result_path', 'N/A')}")
            else:
                console.print(f"\n[bold red]✗ Task failed:[/bold red] {result.get('error')}")
        else:
            console.print(f"\n[dim]⏸  Status:[/dim] STAGED (waiting for approval)")
            console.print(f"[dim]Run 'nightshift approve {task_id}' to execute[/dim]")
            console.print(f"[dim]Or 'nightshift revise {task_id} \"feedback\"' to request changes[/dim]\n")

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}\n")
        logger.error(f"Task submission failed: {str(e)}")
        raise click.Abort()


@cli.command()
@click.option('--status', type=click.Choice(['staged', 'committed', 'running', 'paused', 'completed', 'failed', 'cancelled']),
              help='Filter by status')
@click.pass_context
def queue(ctx, status):
    """View task queue"""
    task_queue = ctx.obj['task_queue']

    # Get tasks
    if status:
        tasks = task_queue.list_tasks(TaskStatus(status))
        title = f"Tasks ({status.upper()})"
    else:
        tasks = task_queue.list_tasks()
        title = "All Tasks"

    if not tasks:
        console.print(f"\n[dim]No tasks found[/dim]\n")
        return

    # Create table
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Description", style="white")
    table.add_column("Est. Time", justify="right")
    table.add_column("Created", style="dim")

    for task in tasks:
        # Color code status
        status_color = {
            "staged": "yellow",
            "committed": "blue",
            "running": "cyan",
            "paused": "magenta",
            "completed": "green",
            "failed": "red",
            "cancelled": "dim"
        }.get(task.status, "white")

        table.add_row(
            task.task_id,
            f"[{status_color}]{task.status.upper()}[/{status_color}]",
            task.description[:60] + "..." if len(task.description) > 60 else task.description,
            f"{task.estimated_time}s" if task.estimated_time else "N/A",
            task.created_at.split('T')[0] if task.created_at else "N/A"
        )

    console.print("\n")
    console.print(table)
    console.print("\n")


@cli.command()
@click.argument('task_id')
@click.pass_context
def approve(ctx, task_id):
    """Approve and execute a staged task"""
    logger = ctx.obj['logger']
    task_queue = ctx.obj['task_queue']
    agent_manager = ctx.obj['agent_manager']

    # Get task
    task = task_queue.get_task(task_id)
    if not task:
        console.print(f"\n[bold red]Error:[/bold red] Task {task_id} not found\n")
        raise click.Abort()

    if task.status != TaskStatus.STAGED.value:
        console.print(f"\n[bold red]Error:[/bold red] Task {task_id} is not in STAGED state (current: {task.status})\n")
        raise click.Abort()

    # Update to COMMITTED and execute
    task_queue.update_status(task_id, TaskStatus.COMMITTED)
    logger.log_task_approved(task_id)

    console.print(f"\n[bold green]✓ Task approved:[/bold green] {task_id}")
    console.print(f"\n[bold blue]▶ Executing...[/bold blue]\n")

    result = agent_manager.execute_task(task)

    if result['success']:
        console.print(f"\n[bold green]✓ Task completed successfully![/bold green]")
        console.print(f"Token usage: {result.get('token_usage', 'N/A')}")
        console.print(f"Execution time: {result['execution_time']:.1f}s")
        console.print(f"Results saved to: {result.get('result_path', 'N/A')}\n")
    else:
        console.print(f"\n[bold red]✗ Task failed:[/bold red] {result.get('error')}\n")


@cli.command()
@click.argument('task_id')
@click.option('--show-output', is_flag=True, help='Display full output')
@click.pass_context
def results(ctx, task_id, show_output):
    """View task results"""
    task_queue = ctx.obj['task_queue']

    # Get task
    task = task_queue.get_task(task_id)
    if not task:
        console.print(f"\n[bold red]Error:[/bold red] Task {task_id} not found\n")
        raise click.Abort()

    # Display task info
    console.print(f"\n[bold cyan]Task:[/bold cyan] {task_id}")
    console.print(f"[yellow]Status:[/yellow] {task.status.upper()}")
    console.print(f"[yellow]Description:[/yellow] {task.description}")
    console.print(f"[yellow]Created:[/yellow] {task.created_at}")

    if task.started_at:
        console.print(f"[yellow]Started:[/yellow] {task.started_at}")
    if task.completed_at:
        console.print(f"[yellow]Completed:[/yellow] {task.completed_at}")
    if task.token_usage:
        console.print(f"[yellow]Token Usage:[/yellow] {task.token_usage}")
    if task.execution_time:
        console.print(f"[yellow]Execution Time:[/yellow] {task.execution_time:.1f}s")

    if task.error_message:
        console.print(f"\n[bold red]Error:[/bold red] {task.error_message}")

    if task.result_path and show_output:
        console.print(f"\n[bold]Output:[/bold]")
        try:
            with open(task.result_path) as f:
                data = json.load(f)
                syntax = Syntax(json.dumps(data, indent=2), "json", theme="monokai")
                console.print(syntax)
        except Exception as e:
            console.print(f"[red]Failed to read output: {e}[/red]")

    console.print()


@cli.command()
@click.argument('task_id')
@click.argument('feedback')
@click.pass_context
def revise(ctx, task_id, feedback):
    """Request plan revision with feedback for a staged task"""
    logger = ctx.obj['logger']
    task_queue = ctx.obj['task_queue']
    task_planner = ctx.obj['task_planner']

    # Get task
    task = task_queue.get_task(task_id)
    if not task:
        console.print(f"\n[bold red]Error:[/bold red] Task {task_id} not found\n")
        raise click.Abort()

    if task.status != TaskStatus.STAGED.value:
        console.print(f"\n[bold red]Error:[/bold red] Task {task_id} is not in STAGED state (current: {task.status})\n")
        console.print(f"[dim]Only staged tasks can be revised[/dim]\n")
        raise click.Abort()

    console.print(f"\n[bold blue]Revising plan based on feedback...[/bold blue]")

    try:
        # Build current plan from task
        current_plan = {
            'enhanced_prompt': task.description,
            'allowed_tools': task.allowed_tools or [],
            'system_prompt': task.system_prompt or '',
            'estimated_tokens': task.estimated_tokens or 0,
            'estimated_time': task.estimated_time or 0
        }

        # Use Claude to refine the plan
        revised_plan = task_planner.refine_plan(current_plan, feedback)

        # Update task with revised plan
        success = task_queue.update_plan(
            task_id=task_id,
            description=revised_plan['enhanced_prompt'],
            allowed_tools=revised_plan['allowed_tools'],
            system_prompt=revised_plan['system_prompt'],
            estimated_tokens=revised_plan['estimated_tokens'],
            estimated_time=revised_plan['estimated_time']
        )

        if not success:
            console.print(f"\n[bold red]Error:[/bold red] Failed to update task plan\n")
            raise click.Abort()

        task_queue.add_log(task_id, "INFO", f"Plan revised based on feedback: {feedback[:100]}")

        # Display revised plan
        console.print(f"\n[bold green]✓ Plan revised:[/bold green] {task_id}")

        panel = Panel.fit(
            f"[yellow]Revised prompt:[/yellow] {revised_plan['enhanced_prompt']}\n\n"
            f"[yellow]Tools needed:[/yellow] {', '.join(revised_plan['allowed_tools'])}\n\n"
            f"[yellow]Estimated:[/yellow] ~{revised_plan['estimated_tokens']} tokens, ~{revised_plan['estimated_time']}s\n\n"
            f"[yellow]Changes:[/yellow] {revised_plan.get('reasoning', 'N/A')}",
            title=f"Revised Plan: {task_id}",
            border_style="green"
        )
        console.print(panel)

        console.print(f"\n[dim]Status:[/dim] STAGED (waiting for approval)")
        console.print(f"[dim]Run 'nightshift approve {task_id}' to execute[/dim]")
        console.print(f"[dim]Or 'nightshift revise {task_id} \"more feedback\"' to revise again[/dim]\n")

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}\n")
        logger.error(f"Plan revision failed for {task_id}: {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument('task_id')
@click.pass_context
def display(ctx, task_id):
    """Display task execution output in human-readable format"""
    task_queue = ctx.obj['task_queue']
    config = ctx.obj['config']

    # Get task
    task = task_queue.get_task(task_id)
    if not task:
        console.print(f"\n[bold red]Error:[/bold red] Task {task_id} not found\n")
        raise click.Abort()

    # Check if task has output
    if not task.result_path:
        console.print(f"\n[bold yellow]Warning:[/bold yellow] Task {task_id} has no output yet\n")
        console.print(f"[dim]Current status: {task.status}[/dim]\n")
        raise click.Abort()

    # Use OutputViewer to display the execution
    viewer = OutputViewer()
    console.print()  # Add spacing
    viewer.display_task_output(task.result_path)


@cli.command()
@click.argument('task_id')
@click.argument('feedback')
@click.pass_context
def revise(ctx, task_id, feedback):
    """Request plan revision with feedback for a staged task"""
    logger = ctx.obj['logger']
    task_queue = ctx.obj['task_queue']
    task_planner = ctx.obj['task_planner']

    # Get task
    task = task_queue.get_task(task_id)
    if not task:
        console.print(f"\n[bold red]Error:[/bold red] Task {task_id} not found\n")
        raise click.Abort()

    if task.status != TaskStatus.STAGED.value:
        console.print(f"\n[bold red]Error:[/bold red] Task {task_id} is not in STAGED state (current: {task.status})\n")
        console.print(f"[dim]Only staged tasks can be revised[/dim]\n")
        raise click.Abort()

    console.print(f"\n[bold blue]Revising plan based on feedback...[/bold blue]")

    try:
        # Build current plan from task
        current_plan = {
            'enhanced_prompt': task.description,
            'allowed_tools': task.allowed_tools or [],
            'allowed_directories': task.allowed_directories or [],
            'system_prompt': task.system_prompt or '',
            'estimated_tokens': task.estimated_tokens or 0,
            'estimated_time': task.estimated_time or 0
        }

        # Use Claude to refine the plan
        revised_plan = task_planner.refine_plan(current_plan, feedback)

        # Update task with revised plan
        success = task_queue.update_plan(
            task_id=task_id,
            description=revised_plan['enhanced_prompt'],
            allowed_tools=revised_plan['allowed_tools'],
            allowed_directories=revised_plan['allowed_directories'],
            system_prompt=revised_plan['system_prompt'],
            estimated_tokens=revised_plan['estimated_tokens'],
            estimated_time=revised_plan['estimated_time']
        )

        if not success:
            console.print(f"\n[bold red]Error:[/bold red] Failed to update task plan\n")
            raise click.Abort()

        task_queue.add_log(task_id, "INFO", f"Plan revised based on feedback: {feedback[:100]}")

        # Display revised plan
        console.print(f"\n[bold green]✓ Plan revised:[/bold green] {task_id}")

        # Format directories display
        dirs_display = "\n".join(f"  • {d}" for d in revised_plan.get('allowed_directories', [])) if revised_plan.get('allowed_directories') else "  (none)"

        panel = Panel.fit(
            f"[yellow]Revised prompt:[/yellow] {revised_plan['enhanced_prompt']}\n\n"
            f"[yellow]Tools needed:[/yellow] {', '.join(revised_plan['allowed_tools'])}\n\n"
            f"[yellow]Sandbox (write access):[/yellow]\n{dirs_display}\n\n"
            f"[yellow]Estimated:[/yellow] ~{revised_plan['estimated_tokens']} tokens, ~{revised_plan['estimated_time']}s\n\n"
            f"[yellow]Changes:[/yellow] {revised_plan.get('reasoning', 'N/A')}",
            title=f"Revised Plan: {task_id}",
            border_style="green"
        )
        console.print(panel)

        console.print(f"\n[dim]Status:[/dim] STAGED (waiting for approval)")
        console.print(f"[dim]Run 'nightshift approve {task_id}' to execute[/dim]")
        console.print(f"[dim]Or 'nightshift revise {task_id} \"more feedback\"' to revise again[/dim]\n")

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {str(e)}\n")
        logger.error(f"Plan revision failed for {task_id}: {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument('task_id')
@click.pass_context
def cancel(ctx, task_id):
    """Cancel a staged task"""
    task_queue = ctx.obj['task_queue']

    task = task_queue.get_task(task_id)
    if not task:
        console.print(f"\n[bold red]Error:[/bold red] Task {task_id} not found\n")
        raise click.Abort()

    if task.status not in [TaskStatus.STAGED.value, TaskStatus.COMMITTED.value]:
        console.print(f"\n[bold red]Error:[/bold red] Cannot cancel task in {task.status} state\n")
        raise click.Abort()

    task_queue.update_status(task_id, TaskStatus.CANCELLED)
    console.print(f"\n[bold yellow]✓ Task cancelled:[/bold yellow] {task_id}\n")


@cli.command()
@click.argument('task_id')
@click.pass_context
def pause(ctx, task_id):
    """Pause a running task"""
    agent_manager = ctx.obj['agent_manager']

    result = agent_manager.pause_task(task_id)

    if result['success']:
        console.print(f"\n[bold yellow]⏸  Task paused:[/bold yellow] {task_id}")
        console.print(f"[dim]{result['message']}[/dim]")
        console.print(f"[dim]Run 'nightshift resume {task_id}' to continue execution[/dim]\n")
    else:
        console.print(f"\n[bold red]Error:[/bold red] {result['error']}\n")
        raise click.Abort()


@cli.command()
@click.argument('task_id')
@click.pass_context
def resume(ctx, task_id):
    """Resume a paused task"""
    agent_manager = ctx.obj['agent_manager']

    result = agent_manager.resume_task(task_id)

    if result['success']:
        console.print(f"\n[bold green]▶  Task resumed:[/bold green] {task_id}")
        console.print(f"[dim]{result['message']}[/dim]")
        console.print(f"[dim]Task is now running. Use 'nightshift watch {task_id}' to monitor progress[/dim]\n")
    else:
        console.print(f"\n[bold red]Error:[/bold red] {result['error']}\n")
        raise click.Abort()


@cli.command()
@click.argument('task_id')
@click.pass_context
def kill(ctx, task_id):
    """Kill a running or paused task"""
    agent_manager = ctx.obj['agent_manager']

    result = agent_manager.kill_task(task_id)

    if result['success']:
        console.print(f"\n[bold red]✖ Task killed:[/bold red] {task_id}")
        console.print(f"[dim]{result['message']}[/dim]")
        console.print(f"[dim]Task status updated to CANCELLED[/dim]\n")
    else:
        console.print(f"\n[bold red]Error:[/bold red] {result['error']}\n")
        raise click.Abort()


@cli.command()
@click.argument('task_id')
@click.option('--follow', '-f', is_flag=True, help='Follow output in real-time (not yet implemented)')
@click.pass_context
def watch(ctx, task_id, follow):
    """Watch task execution output"""
    task_queue = ctx.obj['task_queue']
    config = ctx.obj['config']

    # Get task
    task = task_queue.get_task(task_id)
    if not task:
        console.print(f"\n[bold red]Error:[/bold red] Task {task_id} not found\n")
        raise click.Abort()

    # Display task info
    console.print(f"\n[bold cyan]Task:[/bold cyan] {task_id}")
    console.print(f"[yellow]Status:[/yellow] {task.status.upper()}")

    if task.process_id:
        # Check if process is still running
        try:
            os.kill(task.process_id, 0)
            console.print(f"[yellow]Process:[/yellow] {task.process_id} (running)")
        except ProcessLookupError:
            console.print(f"[yellow]Process:[/yellow] {task.process_id} (terminated)")
        except PermissionError:
            console.print(f"[yellow]Process:[/yellow] {task.process_id} (no permission to check)")
    else:
        console.print(f"[yellow]Process:[/yellow] Not yet started")

    console.print(f"[yellow]Description:[/yellow] {task.description[:80]}{'...' if len(task.description) > 80 else ''}")

    if task.started_at:
        console.print(f"[yellow]Started:[/yellow] {task.started_at}")

    # Show output if available
    if task.result_path and os.path.exists(task.result_path):
        console.print(f"\n[bold]Current Output:[/bold]")
        try:
            with open(task.result_path) as f:
                data = json.load(f)

                # Display stdout content
                if data.get('stdout'):
                    console.print("\n[dim]--- Output Stream ---[/dim]")
                    # Parse stream-json and show key events
                    lines = data['stdout'].strip().split('\n')
                    for line in lines[:50]:  # Limit to first 50 lines
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                            event_type = event.get('type')

                            # Handle assistant messages with content
                            if event_type == 'assistant' and 'message' in event:
                                msg = event['message']
                                if 'content' in msg:
                                    for content_block in msg['content']:
                                        if content_block.get('type') == 'text':
                                            console.print(f"[white]{content_block.get('text', '')}[/white]")
                                        elif content_block.get('type') == 'tool_use':
                                            console.print(f"[cyan]🔧 Tool: {content_block.get('name')}[/cyan]")

                            # Handle direct text blocks
                            elif event_type == 'text':
                                console.print(f"[white]{event.get('text', '')}[/white]", end='')

                            # Handle tool use
                            elif event_type == 'tool_use':
                                console.print(f"\n[cyan]🔧 Tool: {event.get('name')}[/cyan]")

                            # Handle result messages
                            elif event_type == 'result':
                                if event.get('subtype') == 'success':
                                    console.print(f"\n[green]✓ Success[/green]")
                                result_text = event.get('result', '')
                                if result_text and len(result_text) < 200:
                                    console.print(f"[dim]{result_text}[/dim]")

                            # Show token usage from any message
                            if 'usage' in event:
                                usage = event['usage']
                                console.print(f"[dim]📊 Tokens: {usage.get('input_tokens', 0)} in, {usage.get('output_tokens', 0)} out[/dim]")
                            elif event_type == 'assistant' and 'message' in event and 'usage' in event['message']:
                                usage = event['message']['usage']
                                total_tokens = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
                                if total_tokens > 0:  # Only show if there are actual tokens
                                    console.print(f"[dim]📊 Tokens: {usage.get('input_tokens', 0)} in, {usage.get('output_tokens', 0)} out[/dim]")

                        except json.JSONDecodeError:
                            # Plain text line - show first 100 chars
                            if line.strip():
                                console.print(f"[dim]{line[:100]}[/dim]")

                    if len(lines) > 50:
                        remaining = len(lines) - 50
                        console.print(f"\n[dim]... ({remaining} more lines)[/dim]")

        except Exception as e:
            console.print(f"[red]Failed to read output: {e}[/red]")
    else:
        console.print(f"\n[dim]No output available yet[/dim]")

    if follow:
        console.print(f"\n[yellow]Note:[/yellow] Real-time following is not yet implemented")
        console.print(f"[dim]For now, run 'nightshift watch {task_id}' again to refresh[/dim]")

    console.print()


@cli.command()
@click.option('--port', default=5000, type=int, help='Port to run server on (default: 5000)')
@click.option('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
@click.option('--daemon', is_flag=True, help='Run in background (not yet implemented)')
@click.pass_context
def slack_server(ctx, port, host, daemon):
    """Start Slack webhook server"""
    config = ctx.obj['config']

    # Check if Slack is configured
    if not config.slack_enabled:
        console.print("\n[red]✗ Slack integration not configured[/red]")
        console.print("\nRun [bold]nightshift slack-setup[/bold] to configure Slack integration\n")
        raise click.Abort()

    if daemon:
        console.print("\n[yellow]Note:[/yellow] Daemon mode not yet implemented")
        console.print("For now, run in foreground mode\n")
        raise click.Abort()

    # Import Flask app and setup
    from ..integrations.slack_server import app, setup_server
    from ..integrations.slack_handler import SlackEventHandler
    from ..integrations.slack_client import SlackClient
    from ..integrations.slack_metadata import SlackMetadataStore

    console.print("\n[bold blue]Starting Slack webhook server...[/bold blue]\n")

    # Initialize Slack components
    slack_client = SlackClient(bot_token=config.slack_bot_token)
    slack_metadata = SlackMetadataStore(metadata_dir=config.get_slack_metadata_dir())

    # Test connection
    console.print("[dim]Testing Slack connection...[/dim]")
    if not slack_client.test_connection():
        console.print("[red]✗ Failed to connect to Slack API[/red]")
        console.print("[dim]Check your bot token in the configuration[/dim]\n")
        raise click.Abort()
    console.print("[green]✓ Connected to Slack[/green]\n")

    # Initialize event handler
    event_handler = SlackEventHandler(
        slack_client=slack_client,
        task_queue=ctx.obj['task_queue'],
        task_planner=ctx.obj['task_planner'],
        agent_manager=ctx.obj['agent_manager'],
        slack_metadata=slack_metadata,
        logger=ctx.obj['logger']
    )

    # Setup Flask app
    setup_server(event_handler, config.slack_signing_secret)

    # Update agent manager's notifier to include Slack
    ctx.obj['agent_manager'].notifier.slack_client = slack_client
    ctx.obj['agent_manager'].notifier.slack_metadata = slack_metadata

    console.print(f"[bold green]✓ Server starting on {host}:{port}[/bold green]")
    console.print(f"\n[dim]Webhook endpoints:[/dim]")
    console.print(f"  • POST http://{host}:{port}/slack/commands")
    console.print(f"  • POST http://{host}:{port}/slack/interactions")
    console.print(f"  • GET  http://{host}:{port}/health")
    console.print(f"\n[yellow]Press Ctrl+C to stop the server[/yellow]\n")

    # Run Flask app
    try:
        app.run(host=host, port=port, debug=False)
    except KeyboardInterrupt:
        console.print("\n\n[dim]Server stopped[/dim]\n")


@cli.command()
@click.pass_context
def slack_setup(ctx):
    """Interactive Slack integration setup"""
    config = ctx.obj['config']

    console.print("\n[bold blue]NightShift Slack Integration Setup[/bold blue]\n")

    # Prompt for credentials
    console.print("[dim]Get these values from your Slack App settings at https://api.slack.com/apps[/dim]\n")

    bot_token = click.prompt("Slack Bot Token (xoxb-...)", type=str)
    if not bot_token.startswith('xoxb-'):
        console.print("\n[red]✗ Invalid bot token format (should start with 'xoxb-')[/red]\n")
        raise click.Abort()

    signing_secret = click.prompt("Slack Signing Secret", type=str)

    # Optional app token
    app_token = click.prompt(
        "Slack App Token (optional, press Enter to skip)",
        type=str,
        default='',
        show_default=False
    )

    # Save to config
    config.set_slack_config(
        bot_token=bot_token,
        signing_secret=signing_secret,
        app_token=app_token if app_token else None
    )

    console.print("\n[bold green]✓ Slack configuration saved![/bold green]\n")
    console.print("[dim]Next steps:[/dim]")
    console.print("  1. Run [bold]nightshift slack-server[/bold] to start the webhook server")
    console.print("  2. Use [bold]ngrok http 5000[/bold] to expose your local server")
    console.print("  3. Configure Slack App webhook URLs to point to your ngrok URL")
    console.print("  4. Test with [bold]/nightshift submit[/bold] in Slack\n")


@cli.command()
@click.pass_context
def slack_config(ctx):
    """Show current Slack configuration"""
    config = ctx.obj['config']

    console.print("\n[bold blue]Slack Configuration[/bold blue]\n")

    slack_config = config.get_slack_config()

    if not slack_config['enabled']:
        console.print("[yellow]Slack integration not configured[/yellow]")
        console.print("\nRun [bold]nightshift slack-setup[/bold] to configure\n")
        return

    # Display config
    table = Table(show_header=True, header_style="bold")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Enabled", "✓ Yes" if slack_config['enabled'] else "✗ No")
    table.add_row("Bot Token", slack_config['bot_token'] or "Not set")
    table.add_row("Signing Secret", slack_config['signing_secret'] or "Not set")
    if slack_config['app_token']:
        table.add_row("App Token", slack_config['app_token'])
    table.add_row("Webhook Host", slack_config['webhook_host'])
    table.add_row("Webhook Port", str(slack_config['webhook_port']))
    table.add_row("Enable Threads", "✓" if slack_config['enable_threads'] else "✗")

    console.print(table)
    console.print()


@cli.command()
@click.option('--confirm', is_flag=True, help='Skip confirmation prompt')
@click.pass_context
def clear(ctx, confirm):
    """Clear all NightShift data (database, logs, outputs)"""
    config = ctx.obj['config']

    if not confirm:
        console.print(f"\n[bold yellow]⚠️  Warning:[/bold yellow] This will delete all NightShift data:")
        console.print(f"  • Database: {config.get_database_path()}")
        console.print(f"  • Logs: {config.get_log_dir()}")
        console.print(f"  • Outputs: {config.get_output_dir()}")
        console.print(f"  • Notifications: {config.get_notifications_dir()}")

        response = click.confirm("\nAre you sure you want to continue?", default=False)
        if not response:
            console.print("\n[dim]Cancelled[/dim]\n")
            return

    # Remove the entire base directory
    import shutil
    if config.base_dir.exists():
        shutil.rmtree(config.base_dir)
        console.print(f"\n[bold green]✓ Cleared all NightShift data[/bold green]\n")
    else:
        console.print(f"\n[dim]Nothing to clear[/dim]\n")


def main():
    """Entry point"""
    cli(obj={})


if __name__ == '__main__':
    main()
