#!/usr/bin/env python3
"""
Test script for NightShift GUI
Run this to test the GUI without installing
"""
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run GUI
from nightshift.gui.task_manager_gui import main

if __name__ == '__main__':
    print("Launching NightShift GUI...")
    print("Note: Make sure you have nightshift CLI installed and configured.")
    main()
