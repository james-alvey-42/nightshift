"""
NightShift Task Manager GUI
A tkinter-based graphical interface for managing NightShift tasks
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import json
import threading
from typing import Optional, List, Dict
from datetime import datetime


class TaskManagerGUI:
    """Main GUI application for NightShift task management"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("NightShift Task Manager")
        self.root.geometry("1200x700")

        # Status color mapping
        self.status_colors = {
            'staged': '#FFA500',      # Orange
            'committed': '#1E90FF',   # Blue
            'running': '#00CED1',     # Cyan
            'completed': '#32CD32',   # Green
            'failed': '#DC143C',      # Red
            'cancelled': '#808080'    # Gray
        }

        # Configure styles
        self._configure_styles()

        # Create UI components
        self._create_widgets()

        # Auto-refresh timer
        self.refresh_timer = None
        self.auto_refresh_enabled = True

        # Load initial data
        self.refresh_task_list()

    def _configure_styles(self):
        """Configure ttk styles for the application"""
        style = ttk.Style()
        style.theme_use('clam')

        # Configure Treeview
        style.configure("Treeview",
                       background="#F5F5F5",
                       foreground="black",
                       rowheight=25,
                       fieldbackground="#F5F5F5")
        style.map('Treeview', background=[('selected', '#0078D7')])

        # Configure heading
        style.configure("Treeview.Heading",
                       background="#0078D7",
                       foreground="white",
                       relief="flat")
        style.map("Treeview.Heading",
                 background=[('active', '#005A9E')])

    def _create_widgets(self):
        """Create all GUI widgets"""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Top section: Task submission
        self._create_submission_section(main_frame)

        # Middle section: Task queue
        self._create_queue_section(main_frame)

        # Bottom section: Task details and actions
        self._create_details_section(main_frame)

    def _create_submission_section(self, parent):
        """Create task submission section"""
        submit_frame = ttk.LabelFrame(parent, text="Submit New Task", padding="10")
        submit_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        submit_frame.columnconfigure(1, weight=1)

        # Task description label and entry
        ttk.Label(submit_frame, text="Description:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))

        self.task_entry = ttk.Entry(submit_frame, width=80)
        self.task_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.task_entry.bind('<Return>', lambda e: self.submit_task())

        # Submit buttons
        button_frame = ttk.Frame(submit_frame)
        button_frame.grid(row=0, column=2, padx=(5, 0))

        self.submit_btn = ttk.Button(button_frame, text="Submit",
                                     command=self.submit_task, width=12)
        self.submit_btn.pack(side=tk.LEFT, padx=2)

        self.submit_auto_btn = ttk.Button(button_frame, text="Submit & Auto-Approve",
                                         command=self.submit_task_auto_approve, width=18)
        self.submit_auto_btn.pack(side=tk.LEFT, padx=2)

    def _create_queue_section(self, parent):
        """Create task queue section with treeview"""
        queue_frame = ttk.LabelFrame(parent, text="Task Queue", padding="10")
        queue_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        queue_frame.columnconfigure(0, weight=1)
        queue_frame.rowconfigure(1, weight=1)

        # Control bar
        control_frame = ttk.Frame(queue_frame)
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))

        # Filter dropdown
        ttk.Label(control_frame, text="Filter:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar(value="all")
        filter_combo = ttk.Combobox(control_frame, textvariable=self.filter_var,
                                    values=["all", "staged", "committed", "running",
                                           "completed", "failed", "cancelled"],
                                    state="readonly", width=12)
        filter_combo.pack(side=tk.LEFT, padx=5)
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self.refresh_task_list())

        # Refresh button
        self.refresh_btn = ttk.Button(control_frame, text="🔄 Refresh",
                                      command=self.refresh_task_list, width=12)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)

        # Auto-refresh checkbox
        self.auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="Auto-refresh (10s)",
                       variable=self.auto_refresh_var,
                       command=self.toggle_auto_refresh).pack(side=tk.LEFT, padx=5)

        # Task count label
        self.task_count_label = ttk.Label(control_frame, text="Tasks: 0")
        self.task_count_label.pack(side=tk.RIGHT, padx=5)

        # Treeview with scrollbar
        tree_frame = ttk.Frame(queue_frame)
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        # Create treeview
        columns = ("task_id", "status", "description", "tools", "est_time", "created")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                selectmode="browse")

        # Configure columns
        self.tree.heading("task_id", text="Task ID")
        self.tree.heading("status", text="Status")
        self.tree.heading("description", text="Description")
        self.tree.heading("tools", text="Tools")
        self.tree.heading("est_time", text="Est. Time")
        self.tree.heading("created", text="Created")

        self.tree.column("task_id", width=120, anchor=tk.W)
        self.tree.column("status", width=100, anchor=tk.CENTER)
        self.tree.column("description", width=400, anchor=tk.W)
        self.tree.column("tools", width=150, anchor=tk.W)
        self.tree.column("est_time", width=80, anchor=tk.CENTER)
        self.tree.column("created", width=100, anchor=tk.CENTER)

        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.W, tk.E))

        # Bind selection event
        self.tree.bind('<<TreeviewSelect>>', self.on_task_selected)

        # Bind double-click to show details
        self.tree.bind('<Double-Button-1>', lambda e: self.show_task_details())

    def _create_details_section(self, parent):
        """Create task details and action buttons section"""
        details_frame = ttk.LabelFrame(parent, text="Task Details & Actions", padding="10")
        details_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 0))
        details_frame.columnconfigure(0, weight=1)

        # Details text area
        self.details_text = scrolledtext.ScrolledText(details_frame, height=8,
                                                       wrap=tk.WORD, state='disabled')
        self.details_text.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Action buttons
        action_frame = ttk.Frame(details_frame)
        action_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))

        self.approve_btn = ttk.Button(action_frame, text="✓ Approve & Execute",
                                     command=self.approve_task, width=18, state='disabled')
        self.approve_btn.pack(side=tk.LEFT, padx=5)

        self.cancel_btn = ttk.Button(action_frame, text="✗ Cancel",
                                    command=self.cancel_task, width=12, state='disabled')
        self.cancel_btn.pack(side=tk.LEFT, padx=5)

        self.results_btn = ttk.Button(action_frame, text="📄 View Results",
                                     command=self.show_task_details, width=15, state='disabled')
        self.results_btn.pack(side=tk.LEFT, padx=5)

        self.logs_btn = ttk.Button(action_frame, text="📋 View Full Output",
                                   command=self.view_full_output, width=18, state='disabled')
        self.logs_btn.pack(side=tk.LEFT, padx=5)

    def submit_task(self, auto_approve: bool = False):
        """Submit a new task"""
        description = self.task_entry.get().strip()
        if not description:
            messagebox.showwarning("Input Required", "Please enter a task description.")
            return

        # Disable submit button and show processing
        self.submit_btn.config(state='disabled')
        self.submit_auto_btn.config(state='disabled')
        self.task_entry.config(state='disabled')

        def run_submit():
            try:
                cmd = ["nightshift", "submit", description]
                if auto_approve:
                    cmd.append("--auto-approve")

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

                # Schedule UI update on main thread
                self.root.after(0, lambda: self._on_submit_complete(result, auto_approve))

            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: self._on_submit_error("Task submission timed out (5 minutes)"))
            except Exception as e:
                self.root.after(0, lambda: self._on_submit_error(str(e)))

        # Run in background thread
        thread = threading.Thread(target=run_submit, daemon=True)
        thread.start()

    def _on_submit_complete(self, result, auto_approve: bool):
        """Handle submission completion"""
        # Re-enable submit controls
        self.submit_btn.config(state='normal')
        self.submit_auto_btn.config(state='normal')
        self.task_entry.config(state='normal')

        if result.returncode == 0:
            self.task_entry.delete(0, tk.END)
            if auto_approve:
                messagebox.showinfo("Success", "Task submitted and executed!")
            else:
                messagebox.showinfo("Success", "Task submitted successfully!")
            self.refresh_task_list()
        else:
            messagebox.showerror("Error", f"Failed to submit task:\n{result.stderr}")

    def _on_submit_error(self, error_msg: str):
        """Handle submission error"""
        self.submit_btn.config(state='normal')
        self.submit_auto_btn.config(state='normal')
        self.task_entry.config(state='normal')
        messagebox.showerror("Error", f"Failed to submit task:\n{error_msg}")

    def submit_task_auto_approve(self):
        """Submit task with auto-approve"""
        self.submit_task(auto_approve=True)

    def refresh_task_list(self):
        """Refresh the task queue display"""
        # Cancel pending auto-refresh
        if self.refresh_timer:
            self.root.after_cancel(self.refresh_timer)
            self.refresh_timer = None

        try:
            # Get filter value
            filter_status = self.filter_var.get()

            # Build command with JSON output
            cmd = ["nightshift", "queue", "--json"]
            if filter_status != "all":
                cmd.extend(["--status", filter_status])

            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                # Parse JSON output and update tree
                self._update_tree_from_json(result.stdout)
            else:
                # Show error in details
                self._show_error(f"Failed to fetch tasks:\n{result.stderr}")

        except subprocess.TimeoutExpired:
            self._show_error("Task queue refresh timed out")
        except Exception as e:
            self._show_error(f"Error refreshing task queue: {str(e)}")

        # Schedule next auto-refresh if enabled
        if self.auto_refresh_enabled and self.auto_refresh_var.get():
            self.refresh_timer = self.root.after(10000, self.refresh_task_list)

    def _update_tree_from_json(self, json_output: str):
        """Parse JSON output and update treeview"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            # Parse JSON
            tasks = json.loads(json_output)

            if not tasks:
                self.task_count_label.config(text="Tasks: 0")
                return

            # Add tasks to tree
            for task in tasks:
                # Extract data
                task_id = task['task_id']
                status = task['status'].lower()
                description = task['description']
                tools = ", ".join((task.get('allowed_tools', []) or [])[:3])  # Show first 3 tools
                est_time = f"{task['estimated_time']}s" if task.get('estimated_time') else "N/A"
                created = task['created_at'].split('T')[0] if task.get('created_at') else "N/A"

                # Truncate description
                if len(description) > 60:
                    description = description[:60] + "..."

                # Determine status color tag
                tag = f"status_{status}"

                # Insert into tree
                self.tree.insert('', tk.END, values=(
                    task_id,
                    status.upper(),
                    description,
                    tools,
                    est_time,
                    created
                ), tags=(tag,))

                # Configure tag color
                if status in self.status_colors:
                    self.tree.tag_configure(tag, foreground=self.status_colors[status])

            # Update task count
            self.task_count_label.config(text=f"Tasks: {len(tasks)}")

        except json.JSONDecodeError as e:
            self._show_error(f"Error parsing task JSON: {str(e)}")
        except Exception as e:
            self._show_error(f"Error updating task list: {str(e)}")

    def _get_task_details_raw(self, task_id: str) -> Optional[Dict]:
        """Get raw task details from CLI"""
        try:
            result = subprocess.run(
                ["nightshift", "results", task_id],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Parse the output
                details = {}
                lines = result.stdout.split('\n')
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip()
                        details[key] = value

                # Try to extract tools from allowed_tools field
                # This would need actual implementation based on output format
                return details

        except Exception:
            pass

        return None

    def on_task_selected(self, event):
        """Handle task selection in treeview"""
        selection = self.tree.selection()
        if not selection:
            self._clear_details()
            return

        # Get selected task
        item = self.tree.item(selection[0])
        task_id = item['values'][0]
        status = item['values'][1].lower()

        # Update details
        self._load_task_details(task_id)

        # Update button states based on status
        if status == 'staged':
            self.approve_btn.config(state='normal')
            self.cancel_btn.config(state='normal')
            self.results_btn.config(state='normal')
            self.logs_btn.config(state='disabled')
        elif status in ['committed', 'running']:
            self.approve_btn.config(state='disabled')
            self.cancel_btn.config(state='normal')
            self.results_btn.config(state='normal')
            self.logs_btn.config(state='disabled')
        elif status in ['completed', 'failed']:
            self.approve_btn.config(state='disabled')
            self.cancel_btn.config(state='disabled')
            self.results_btn.config(state='normal')
            self.logs_btn.config(state='normal')
        else:
            self.approve_btn.config(state='disabled')
            self.cancel_btn.config(state='disabled')
            self.results_btn.config(state='normal')
            self.logs_btn.config(state='disabled')

    def _load_task_details(self, task_id: str):
        """Load and display task details"""
        try:
            result = subprocess.run(
                ["nightshift", "results", task_id],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                self._update_details(result.stdout)
            else:
                self._update_details(f"Error loading task details:\n{result.stderr}")

        except Exception as e:
            self._update_details(f"Error loading task details: {str(e)}")

    def _update_details(self, text: str):
        """Update the details text area"""
        self.details_text.config(state='normal')
        self.details_text.delete('1.0', tk.END)
        self.details_text.insert('1.0', text)
        self.details_text.config(state='disabled')

    def _clear_details(self):
        """Clear details and disable buttons"""
        self._update_details("Select a task to view details")
        self.approve_btn.config(state='disabled')
        self.cancel_btn.config(state='disabled')
        self.results_btn.config(state='disabled')
        self.logs_btn.config(state='disabled')

    def _show_error(self, message: str):
        """Show error in details area"""
        self._update_details(f"ERROR: {message}")

    def approve_task(self):
        """Approve and execute selected task"""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        task_id = item['values'][0]

        # Confirm approval
        response = messagebox.askyesno(
            "Confirm Approval",
            f"Approve and execute task {task_id}?\n\nThis will start task execution immediately."
        )

        if not response:
            return

        # Disable button during execution
        self.approve_btn.config(state='disabled')

        def run_approve():
            try:
                result = subprocess.run(
                    ["nightshift", "approve", task_id],
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout for execution
                )

                self.root.after(0, lambda: self._on_approve_complete(result, task_id))

            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: self._on_approve_error(task_id, "Task execution timed out"))
            except Exception as e:
                self.root.after(0, lambda: self._on_approve_error(task_id, str(e)))

        # Run in background thread
        thread = threading.Thread(target=run_approve, daemon=True)
        thread.start()

        # Show progress message
        self._update_details(f"Executing task {task_id}...\nPlease wait, this may take several minutes.")

    def _on_approve_complete(self, result, task_id: str):
        """Handle approval completion"""
        if result.returncode == 0:
            messagebox.showinfo("Success", f"Task {task_id} completed successfully!")
            self.refresh_task_list()
        else:
            messagebox.showerror("Error", f"Task execution failed:\n{result.stderr}")
            self.refresh_task_list()

    def _on_approve_error(self, task_id: str, error_msg: str):
        """Handle approval error"""
        messagebox.showerror("Error", f"Failed to execute task {task_id}:\n{error_msg}")
        self.refresh_task_list()

    def cancel_task(self):
        """Cancel selected task"""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        task_id = item['values'][0]

        # Confirm cancellation
        response = messagebox.askyesno(
            "Confirm Cancellation",
            f"Cancel task {task_id}?"
        )

        if not response:
            return

        try:
            result = subprocess.run(
                ["nightshift", "cancel", task_id],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                messagebox.showinfo("Success", f"Task {task_id} cancelled.")
                self.refresh_task_list()
            else:
                messagebox.showerror("Error", f"Failed to cancel task:\n{result.stderr}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to cancel task: {str(e)}")

    def show_task_details(self):
        """Show detailed task information in a new window"""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        task_id = item['values'][0]

        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Task Details - {task_id}")
        details_window.geometry("800x600")

        # Add text widget with scrollbar
        frame = ttk.Frame(details_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True)

        # Load and display details
        try:
            result = subprocess.run(
                ["nightshift", "results", task_id],
                capture_output=True,
                text=True,
                timeout=5
            )

            text_widget.insert('1.0', result.stdout)
            text_widget.config(state='disabled')

        except Exception as e:
            text_widget.insert('1.0', f"Error loading details: {str(e)}")
            text_widget.config(state='disabled')

    def view_full_output(self):
        """View full task output including JSON results"""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        task_id = item['values'][0]

        # Create output window
        output_window = tk.Toplevel(self.root)
        output_window.title(f"Full Output - {task_id}")
        output_window.geometry("900x700")

        # Add text widget with scrollbar
        frame = ttk.Frame(output_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, font=('Courier', 9))
        text_widget.pack(fill=tk.BOTH, expand=True)

        # Load and display full output
        try:
            result = subprocess.run(
                ["nightshift", "results", task_id, "--show-output"],
                capture_output=True,
                text=True,
                timeout=10
            )

            text_widget.insert('1.0', result.stdout)
            text_widget.config(state='disabled')

        except Exception as e:
            text_widget.insert('1.0', f"Error loading output: {str(e)}")
            text_widget.config(state='disabled')

    def toggle_auto_refresh(self):
        """Toggle auto-refresh on/off"""
        if self.auto_refresh_var.get():
            self.refresh_task_list()  # Start refreshing
        else:
            # Cancel pending refresh
            if self.refresh_timer:
                self.root.after_cancel(self.refresh_timer)
                self.refresh_timer = None

    def run(self):
        """Start the GUI application"""
        self.root.mainloop()


def main():
    """Entry point for the GUI application"""
    root = tk.Tk()
    app = TaskManagerGUI(root)
    app.run()


if __name__ == '__main__':
    main()
