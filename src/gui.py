"""
GUI module - Main application interface.

Phase 3: GUI Modularization in Progress
========================================

The GUI is being refactored from the monolithic qbt_editor.py into organized modules:

Structure:
----------
src/gui/
├── __init__.py          - Package initialization
├── main_window.py       - Main window setup (🔄 transitioning)
├── dialogs.py           - Dialog windows (🔄 transitioning)
└── widgets.py           - Custom widgets (✅ complete)

Status:
-------
- ✅ Widgets module complete with reusable components
- 🔄 Main window and dialogs still import from legacy during transition
- ⏳ Full refactoring in progress

Usage:
------
from src.gui import setup_gui, exit_handler

root = setup_gui()
root.mainloop()
"""
from src.gui.main_window import setup_gui, exit_handler
from src.gui.dialogs import open_settings_window

__all__ = ["setup_gui", "exit_handler", "open_settings_window"]

