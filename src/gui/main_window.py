"""
Main application window and GUI setup.

This module contains the setup_gui() function and main window initialization.
"""
import logging
import sys
import os

# Add parent directory to path for legacy imports during transition
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


def setup_gui():
    """
    Setup and initialize the main GUI window.
    
    Phase 3 Transition Note:
    ----------------------
    This function currently loads from the legacy qbt_editor.py file.
    The GUI is being gradually refactored into modular components.
    
    Progress:
    - ✅ Widget components extracted (src/gui/widgets.py)
    - 🔄 Dialog windows being refactored (src/gui/dialogs.py)
    - ⏳ Main window setup (this file - in progress)
    - ⏳ Event handlers and business logic
    
    Returns:
        tk.Tk: The root window instance
    """
    import importlib.util
    import tkinter as tk
    from tkinter import messagebox
    
    # Calculate path to legacy qbt_editor.py
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    legacy_path = os.path.join(project_root, 'legacy', 'qbt_editor.py')
    
    if not os.path.exists(legacy_path):
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "GUI Import Error",
            f"Failed to load GUI components:\nNo module named 'qbt_editor'\n\n"
            f"The GUI is being modularized. Please ensure qbt_editor.py exists."
        )
        root.destroy()
        sys.exit(1)
    
    try:
        # Load legacy module dynamically
        spec = importlib.util.spec_from_file_location("qbt_editor", legacy_path)
        qbt_editor = importlib.util.module_from_spec(spec)
        sys.modules['qbt_editor'] = qbt_editor  # Add to sys.modules so other imports work
        spec.loader.exec_module(qbt_editor)
        
        logger.info("GUI Phase 3: Using legacy setup_gui during transition")
        return qbt_editor.setup_gui()
        
    except Exception as e:
        logger.error(f"Failed to load legacy GUI: {e}", exc_info=True)
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "GUI Import Error",
            f"Failed to load GUI components:\n{e}\n\n"
            "The GUI is being modularized. Please ensure qbt_editor.py exists."
        )
        root.destroy()
        sys.exit(1)


def exit_handler() -> None:
    """
    Setup custom exception handler for clean shutdown.
    
    Filters out non-critical exceptions during application shutdown.
    """
    def _custom_excepthook(exc_type, exc_value, exc_traceback):
        """
        Custom exception handler to suppress specific non-critical exceptions.
        
        Filters out AttributeErrors related to _http_session which can occur
        during shutdown without affecting functionality.
        
        Args:
            exc_type: Exception class
            exc_value: Exception instance
            exc_traceback: Traceback object
        """
        try:
            if exc_type is AttributeError and '_http_session' in str(exc_value):
                return
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _custom_excepthook


# Public API
__all__ = ["setup_gui", "exit_handler"]
