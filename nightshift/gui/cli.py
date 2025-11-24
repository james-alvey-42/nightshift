"""
CLI entry point for NightShift GUI
Provides a command-line launcher for the graphical interface
"""
import tkinter as tk
from .task_manager_gui import TaskManagerGUI


def main():
    """Launch the NightShift GUI application"""
    try:
        root = tk.Tk()
        app = TaskManagerGUI(root)
        app.run()
    except Exception as e:
        print(f"Error launching GUI: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0


if __name__ == '__main__':
    exit(main())
