"""
Dialog windows for the application.

Contains settings dialog, import/export dialogs, and other modal windows.
"""
import logging
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional
import sys
import os
import importlib.util

# Add parent directory to path for legacy imports during transition
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import config
from src.gui.widgets import ToolTip, center_window

logger = logging.getLogger(__name__)


def _load_legacy_module():
    """
    Load the legacy qbt_editor.py module dynamically.
    
    Returns:
        module: The loaded qbt_editor module
    """
    if 'qbt_editor' in sys.modules:
        return sys.modules['qbt_editor']
    
    # Calculate path to legacy qbt_editor.py
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    legacy_path = os.path.join(project_root, 'legacy', 'qbt_editor.py')
    
    if not os.path.exists(legacy_path):
        raise FileNotFoundError(f"Legacy qbt_editor.py not found at {legacy_path}")
    
    # Load legacy module dynamically
    spec = importlib.util.spec_from_file_location("qbt_editor", legacy_path)
    qbt_editor = importlib.util.module_from_spec(spec)
    sys.modules['qbt_editor'] = qbt_editor
    spec.loader.exec_module(qbt_editor)
    
    return qbt_editor


def open_settings_window(root: tk.Tk, status_var: tk.StringVar) -> None:
    """
    Opens the settings dialog for qBittorrent connection configuration.
    
    For now, this loads from the legacy qbt_editor.py file.
    TODO: Fully refactor this dialog in Phase 3.
    
    Args:
        root: Parent Tkinter window
        status_var: Status bar variable
    """
    try:
        legacy = _load_legacy_module()
        legacy.open_settings_window(root, status_var)
    except Exception as e:
        logger.error(f"Failed to open settings window: {e}", exc_info=True)
        messagebox.showerror("Error", f"Failed to open settings:\n{e}")


# TODO: Add more dialog functions as they are refactored:
# - open_import_dialog()
# - open_export_dialog()
# - open_full_rule_editor()
# - view_trash_dialog()
# - open_about_dialog()
