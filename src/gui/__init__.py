"""
GUI Package for qBittorrent RSS Rule Editor

This package contains all GUI-related modules organized by responsibility:
- widgets: Reusable widget components (ToolTip, ScrollableFrame, etc.)
- dialogs: Dialog windows (settings, import/export, etc.)
- main_window: Main application window setup and layout
- event_handlers: Business logic and event callbacks (TODO)

Phase 3: GUI Modularization Progress
====================================
✅ widgets.py - Complete (ToolTip, ScrollableFrame, helpers)
🔄 dialogs.py - Stub (imports legacy)
🔄 main_window.py - Stub (imports legacy)
⏳ event_handlers.py - TODO

Transition Strategy:
- New modules initially import from legacy qbt_editor.py
- Gradually refactor each component
- Maintain backward compatibility throughout
"""

# Import main window setup as primary GUI entry point
from .main_window import setup_gui, exit_handler

# Import dialogs for convenience
from .dialogs import open_settings_window

# Import widgets for external use
from .widgets import (
    ToolTip,
    ScrollableFrame,
    create_labeled_entry,
    create_labeled_text,
    center_window
)

__all__ = [
    # Main window
    'setup_gui',
    'exit_handler',
    
    # Dialogs
    'open_settings_window',
    
    # Widgets
    'ToolTip',
    'ScrollableFrame',
    'create_labeled_entry',
    'create_labeled_text',
    'center_window',
]

__version__ = "0.3.0-dev"  # Phase 3 in development
