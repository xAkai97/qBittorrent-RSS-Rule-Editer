"""
Main window setup and GUI initialization.

This module contains functions for setting up the main application window,
including window geometry, styling, menu bar, and event handlers.

Session 4A: Window & Menu Bar Extraction (COMPLETED ✅)
Session 4B: Season Controls & Library Panel (COMPLETED ✅)
Session 4C: Editor Panel (COMPLETED ✅)
Session 4D: Event Handlers (COMPLETED ✅ - implicit)
Session 4E: Final Integration (COMPLETED ✅)

Progress: GUI MODULE 100% COMPLETE - Fully Modular!
- ✅ Window initialization and styling
- ✅ Menu bar setup (File, Edit, Settings, Info)
- ✅ Status bar and auto-connect handling
- ✅ Keyboard shortcuts
- ✅ Season controls & library panel
- ✅ Editor panel with SubsPlease integration
- ✅ Context menu (Copy, Edit, Delete)
- ✅ All event handlers integrated
- ✅ Final setup_gui() integration
"""
# Standard library imports
import logging
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Tuple

# Local application imports
import src.qbittorrent_api as qbt_api
from src.config import config
from src.gui.app_state import AppState
from src.gui.dialogs import open_settings_window
from src.gui.file_operations import (
    clear_all_titles,
    import_titles_from_clipboard,
    import_titles_from_file,
    import_titles_from_text,
    update_treeview_with_titles,
)
from src.utils import (
    get_current_anime_season,
    get_display_title,
    get_rule_name,
)

logger = logging.getLogger(__name__)


def create_tooltip(widget: tk.Widget, text: str) -> None:
    """
    Creates a tooltip for a widget that appears on hover.
    
    Args:
        widget: The tkinter widget to attach the tooltip to
        text: The tooltip text to display
    """
    tooltip_window = None
    
    def on_enter(event):
        nonlocal tooltip_window
        try:
            x, y, _, _ = widget.bbox("insert")
        except:
            x = y = 0
        x += widget.winfo_rootx() + 25
        y += widget.winfo_rooty() + 25
        
        tooltip_window = tk.Toplevel(widget)
        tooltip_window.wm_overrideredirect(True)
        tooltip_window.wm_geometry(f"+{x}+{y}")
        
        tk.Label(
            tooltip_window, 
            text=text, 
            justify='left',
            background='#ffffe0', 
            relief='solid', 
            borderwidth=1,
            font=('Segoe UI', 9), 
            padx=5, 
            pady=3
        ).pack()
    
    def on_leave(event):
        nonlocal tooltip_window
        if tooltip_window:
            tooltip_window.destroy()
            tooltip_window = None
    
    widget.bind('<Enter>', on_enter)
    widget.bind('<Leave>', on_leave)


def setup_window_and_styles(root: tk.Tk) -> Tuple[ttk.Style, tk.StringVar, tk.StringVar]:
    """
    Configures the main window geometry, theme, and styles.
    
    Sets up window size, position, minimum size, background color,
    and configures all ttk widget styles with a modern look.
    
    Args:
        root: Tkinter root window
        
    Returns:
        Tuple of (style, season_var, year_var):
            - style: Configured ttk.Style object
            - season_var: StringVar for season selection
            - year_var: StringVar for year selection
    """
    root.title("qBittorrent RSS Rules Editor")
    
    # Position window away from taskbar
    from src.constants import UIConfig
    try:
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = UIConfig.DEFAULT_WINDOW_WIDTH
        window_height = UIConfig.DEFAULT_WINDOW_HEIGHT
        # Position at top-center with some margin from top
        x = (screen_width - window_width) // 2
        y = UIConfig.WINDOW_TOP_MARGIN
        root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    except Exception:
        root.geometry(f"{UIConfig.DEFAULT_WINDOW_WIDTH}x{UIConfig.DEFAULT_WINDOW_HEIGHT}")
    
    root.minsize(UIConfig.MIN_WINDOW_WIDTH, UIConfig.MIN_WINDOW_HEIGHT)

    style = ttk.Style()
    style.theme_use('clam')
    
    # Modern color scheme
    bg_color = '#f5f5f5'
    frame_bg = '#ffffff'
    accent_color = '#0078D4'
    accent_hover = '#005a9e'
    text_color = '#333333'
    border_color = '#e0e0e0'
    
    root.configure(bg=bg_color)
    
    # Configure styles with modern look
    style.configure('.', background=frame_bg, foreground=text_color)
    style.configure('TFrame', background=frame_bg)
    style.configure('TLabelFrame', background=frame_bg, bordercolor=border_color, relief='flat')
    style.configure('TLabelFrame.Label', background=frame_bg, foreground=text_color, font=('Segoe UI', 9, 'bold'))
    style.configure('TLabel', background=frame_bg, foreground=text_color, font=('Segoe UI', 9))
    style.configure('TCheckbutton', background=frame_bg, foreground=text_color, focuscolor=accent_color)
    style.configure('TButton', padding=6, relief='flat', font=('Segoe UI', 9))
    style.configure('Accent.TButton', foreground='white', background=accent_color, font=('Segoe UI', 9, 'bold'))
    style.map('Accent.TButton', background=[('active', accent_hover)])
    style.configure('RefreshButton.TButton', font=('Segoe UI', 18), padding=0)
    style.configure('TCombobox', padding=5)
    style.configure('TEntry', padding=5)
    
    # Add Secondary button style for sync button
    style.configure('Secondary.TButton', foreground='white', background='#5c636a', font=('Segoe UI', 9))
    style.map('Secondary.TButton', background=[('active', '#4a5056')])
    
    # Configure treeview scrollbar colors
    style.configure('TScrollbar', background=frame_bg, troughcolor=bg_color)
    
    # Configure treeview styles
    style.configure('Treeview', 
                   background='#ffffff',
                   foreground='#333333',
                   fieldbackground='#ffffff',
                   font=('Segoe UI', 9))
    style.configure('Treeview.Heading',
                   background='#f0f0f0',
                   foreground='#333333',
                   font=('Segoe UI', 9, 'bold'))
    style.map('Treeview', 
             background=[('selected', '#0078D4')],
             foreground=[('selected', '#ffffff')])

    # Get current anime season
    current_season, current_year = get_current_anime_season()
    season_var = tk.StringVar(value=current_season)
    year_var = tk.StringVar(value=current_year)

    return style, season_var, year_var


def setup_status_and_autoconnect(root: tk.Tk, status_var: tk.StringVar, config_set: bool) -> None:
    """
    Initializes status variable and handles auto-connection to qBittorrent.
    
    Sets up initial connection status message, checks if config exists,
    and optionally auto-connects to qBittorrent based on connection mode.
    
    Args:
        root: Tkinter root window
        status_var: StringVar for status bar
        config_set: Whether configuration was successfully loaded
    """
    def _get_connection_status():
        """Generates a status message describing the current connection mode."""
        mode = (getattr(config, 'CONNECTION_MODE', '') or '').lower()
        if mode == 'online':
            return f"Online: {config.QBT_PROTOCOL}://{config.QBT_HOST}:{config.QBT_PORT}"
        if mode == 'offline':
            return 'Offline'
        if mode == 'auto':
            return 'Auto (will try online if available)'
        return f"Mode: {mode or 'unknown'}"

    status_var.set(_get_connection_status())

    # Check if config file is missing
    config_file_missing = not os.path.exists(getattr(config, 'CONFIG_FILE', 'config.ini'))

    if not config_set and config_file_missing:
        status_var.set("🚨 CRITICAL: Please set qBittorrent credentials in Settings.")
        root.after(100, lambda: open_settings_window(root, status_var))

    def _start_auto_connect_thread():
        """Starts a background thread to automatically connect to qBittorrent."""
        def worker():
            attempts = 0
            while attempts < 3:
                attempts += 1
                try:
                    status_var.set('Auto: attempting qBittorrent connection...')
                    ok, msg = qbt_api.ping_qbittorrent(
                        config.QBT_PROTOCOL, 
                        config.QBT_HOST, 
                        str(config.QBT_PORT), 
                        config.QBT_USER or '', 
                        config.QBT_PASS or '', 
                        bool(config.QBT_VERIFY_SSL), 
                        getattr(config, 'QBT_CA_CERT', None)
                    )
                    if ok:
                        status_var.set(f'Connected to qBittorrent ({msg})')
                        return
                    else:
                        status_var.set(f'Auto: not connected ({msg})')
                except Exception:
                    status_var.set('Auto: connection attempt failed')
                time.sleep(2)
        try:
            t = threading.Thread(target=worker, daemon=True)
            t.start()
        except Exception:
            pass

    # Handle auto-connection based on mode
    try:
        if (getattr(config, 'CONNECTION_MODE', '') or '').lower() == 'auto':
            _start_auto_connect_thread()
        elif (getattr(config, 'CONNECTION_MODE', '') or '').lower() == 'online':
            # Auto-test connection for online mode if settings are filled
            def _auto_test_online():
                def worker():
                    try:
                        # Check if required settings are filled
                        host = getattr(config, 'QBT_HOST', '') or ''
                        port = getattr(config, 'QBT_PORT', '') or ''
                        if isinstance(host, str):
                            host = host.strip()
                        if port:
                            port = str(port).strip()
                        if host and port:
                            status_var.set('Testing connection to qBittorrent...')
                            ok, msg = qbt_api.ping_qbittorrent(
                                config.QBT_PROTOCOL, 
                                config.QBT_HOST, 
                                str(config.QBT_PORT), 
                                config.QBT_USER or '', 
                                config.QBT_PASS or '', 
                                bool(config.QBT_VERIFY_SSL), 
                                getattr(config, 'QBT_CA_CERT', None)
                            )
                            if ok:
                                status_var.set(f'✅ Connected: {msg}')
                            else:
                                status_var.set(f'❌ Connection failed: {msg}')
                        else:
                            status_var.set('Online mode: Connection not tested (missing host/port)')
                    except Exception as e:
                        status_var.set(f'Connection test failed: {e}')
                try:
                    t = threading.Thread(target=worker, daemon=True)
                    t.start()
                except Exception:
                    pass
            # Delay test slightly to let UI load
            root.after(500, _auto_test_online)
    except Exception:
        pass


def refresh_treeview_display() -> None:
    """
    Refresh the treeview display with current data from config.ALL_TITLES.
    Useful to fix display issues or synchronize the view with data.
    """
    from src.gui.file_operations import refresh_treeview_display_safe
    refresh_treeview_display_safe()


def setup_menu_bar(
    root: tk.Tk, 
    status_var: tk.StringVar, 
    season_var: tk.StringVar, 
    year_var: tk.StringVar
) -> Tuple[tk.Menu, tk.Menu, tk.Menu]:
    """
    Creates and configures the main menu bar.
    
    Sets up File, Edit, Settings, and Info menus with all commands,
    keyboard shortcuts, and recent files menu.
    
    Args:
        root: Tkinter root window
        status_var: StringVar for status bar updates
        season_var: StringVar for current season selection
        year_var: StringVar for current year selection
        
    Returns:
        Tuple of (menubar, recent_menu, edit_menu) for external updates
    """
    menubar = tk.Menu(root)
    file_menu = tk.Menu(menubar, tearoff=0)
    edit_menu = tk.Menu(menubar, tearoff=0)
    
    # File menu
    def _import_file_and_refresh():
        """Import from file and refresh recent menu."""
        result = import_titles_from_file(
            root, status_var, season_var, year_var,
            prefix_imports=config.get_pref('prefix_imports', True)
        )
        if result:
            refresh_recent_menu()
    
    file_menu.add_command(
        label='Open JSON File...', 
        accelerator='Ctrl+O', 
        command=_import_file_and_refresh
    )
    file_menu.add_command(
        label='Paste from Clipboard', 
        command=lambda: import_titles_from_clipboard(
            root, status_var, season_var, year_var,
            prefix_imports=config.get_pref('prefix_imports', True)
        )
    )
    recent_menu = tk.Menu(file_menu, tearoff=0)
    file_menu.add_cascade(label='Recent Files', menu=recent_menu)
    file_menu.add_separator()
    file_menu.add_command(
        label='Export to Sonarr...', 
        accelerator='Ctrl+Shift+S',
        command=lambda: None  # Will be set up later in setup_library_panel
    )
    file_menu.add_separator()
    file_menu.add_command(label='Exit', command=root.quit)
    menubar.add_cascade(label='📁 File', menu=file_menu)
    
    # Edit menu
    from src.gui.file_operations import (export_selected_titles, export_all_titles,
                                         clear_all_titles)
    from src.gui.dialogs import view_trash_dialog
    
    # Note: Toggle command will be set up after treeview is created
    # It is a placeholder here and will be configured in setup_library_panel
    edit_menu.add_command(label='🔄 Toggle Enable/Disable', accelerator='Space')
    edit_menu.add_separator()
    edit_menu.add_command(
        label='↶ Undo', 
        accelerator='Ctrl+Z', 
        command=lambda: None  # Will be configured after setup
    )
    edit_menu.add_separator()
    edit_menu.add_command(
        label='📝 Bulk Edit Selected...', 
        accelerator='Ctrl+B', 
        command=lambda: None  # Will be configured after setup
    )
    edit_menu.add_separator()
    edit_menu.add_command(
        label='Clear All Titles', 
        accelerator='Ctrl+Shift+C', 
        command=lambda: clear_all_titles(root, status_var)
    )
    edit_menu.add_command(
        label='Export Selected Titles...', 
        accelerator='Ctrl+E', 
        command=export_selected_titles
    )
    edit_menu.add_command(
        label='Export All Titles...', 
        accelerator='Ctrl+Shift+E', 
        command=lambda: export_all_titles()
    )
    edit_menu.add_separator()
    edit_menu.add_command(
        label='Refresh Treeview', 
        accelerator='F5', 
        command=lambda: refresh_treeview_display()
    )
    edit_menu.add_separator()
    edit_menu.add_command(
        label='View Trash...', 
        command=lambda: view_trash_dialog(root)
    )
    menubar.add_cascade(label='✏️ Edit', menu=edit_menu)

    # Templates menu
    templates_menu = tk.Menu(menubar, tearoff=0)
    templates_menu.add_command(
        label='📋 Apply Template...', 
        accelerator='Ctrl+Shift+T',
        command=lambda: _open_template_dialog()
    )
    templates_menu.add_command(
        label='💾 Save as Template...', 
        accelerator='Ctrl+T',
        command=lambda: _save_as_template()
    )
    templates_menu.add_separator()
    templates_menu.add_command(
        label='📚 Manage Templates...', 
        command=lambda: _manage_templates()
    )
    menubar.add_cascade(label='📋 Templates', menu=templates_menu)

    def refresh_recent_menu():
        """Refreshes the Recent Files menu with current file history."""
        try:
            recent_menu.delete(0, 'end')
        except Exception:
            pass
        try:
            config.load_recent_files()
            recent_files = getattr(config, 'RECENT_FILES', []) or []
            
            # Filter out non-existent files
            valid_files = [p for p in recent_files if os.path.isfile(p)]
            
            # Update config if files were removed
            if len(valid_files) != len(recent_files):
                config.RECENT_FILES = valid_files
                from src.cache import save_recent_files
                save_recent_files(valid_files)
            
            for path in valid_files:
                def _open_path(p=path):
                    try:
                        # Use import_titles_from_file to get proper merge behavior
                        result = import_titles_from_file(
                            root, status_var, season_var, year_var,
                            prefix_imports=config.get_pref('prefix_imports', True),
                            path=p
                        )
                        if result:
                            from src.gui.file_operations import refresh_treeview_display_safe
                            refresh_treeview_display_safe()
                    except Exception as e:
                        messagebox.showerror(
                            'Open Recent', 
                            f'Failed to open {os.path.basename(p)}: {e}\n\n'
                            'Action: Check if the file still exists and is not corrupted.'
                        )
                
                # Show filename with full path as tooltip-like info
                display_name = os.path.basename(path)
                if len(display_name) > 40:
                    display_name = display_name[:37] + '...'
                label = f"{display_name} ({os.path.dirname(path)})" if len(os.path.dirname(path)) < 50 else display_name
                
                recent_menu.add_command(label=label, command=_open_path)
            
            if valid_files:
                recent_menu.add_separator()
                recent_menu.add_command(
                    label='Clear Recent Files', 
                    command=lambda: (config.clear_recent_files(), refresh_recent_menu())
                )
            else:
                recent_menu.add_command(label='(No recent files)', state='disabled')
        except Exception:
            pass

    refresh_recent_menu()

    # Settings menu
    settings_menu = tk.Menu(menubar, tearoff=0)
    settings_menu.add_command(
        label='Settings...', 
        accelerator='Ctrl+,', 
        command=lambda: open_settings_window(root, status_var)
    )
    menubar.add_cascade(label='⚙️ Settings', menu=settings_menu)
    
    # Validate menu
    validate_menu = tk.Menu(menubar, tearoff=0)
    
    def _validate_all_titles():
        """Validates all titles and shows issues in a dialog."""
        try:
            import json
            from src.constants import FileSystem
            from src.gui.app_state import get_app_state
            
            app_state = get_app_state()
            listbox_items = app_state.listbox_items
            
            if not listbox_items:
                messagebox.showinfo('Validation', 'No titles to validate.')
                return
            
            # Use centralized validation function
            from src.utils import validate_folder_name_by_filesystem
            _is_valid_folder_name = validate_folder_name_by_filesystem
            
            # Validate all items
            problems = []
            
            for title_text, entry in listbox_items:
                e = entry if isinstance(entry, dict) else {'node': {'title': str(entry)}}
                
                try:
                    node = e.get('node') or {}
                    node_title = node.get('title') or e.get('mustContain') or title_text
                except Exception:
                    node_title = title_text
                    
                if not node_title or not str(node_title).strip():
                    problems.append(f'❌ Missing title for item: {title_text}')
                
                # Validate lastMatch JSON
                try:
                    lm = e.get('lastMatch', '')
                    if isinstance(lm, str):
                        s = lm.strip()
                        if s and (s.startswith('{') or s.startswith('[') or s.startswith('"')):
                            try:
                                json.loads(s)
                            except Exception as ex:
                                problems.append(f'❌ Invalid JSON lastMatch for "{title_text}": {ex}')
                except Exception:
                    pass
                
                # Validate folder names in save path
                try:
                    # Get the save path
                    save_path = e.get('savePath') or e.get('save_path') or ''
                    if not save_path:
                        tp = e.get('torrentParams') or e.get('torrent_params') or {}
                        save_path = tp.get('save_path') or tp.get('savePath') or ''
                    
                    if save_path:
                        # Validate each folder component in the path
                        path_str = str(save_path).replace('\\', '/')
                        folders = [f for f in path_str.split('/') if f.strip()]
                        
                        for folder in folders:
                            valid, reason = _is_valid_folder_name(folder)
                            if not valid:
                                problems.append(f'❌ Invalid folder in path for "{title_text}": "{folder}" - {reason}')
                                break
                except Exception:
                    pass
            
            # Show results dialog
            result_dlg = tk.Toplevel(root)
            result_dlg.title('Validation Results')
            result_dlg.geometry('700x500')
            result_dlg.transient(root)
            result_dlg.grab_set()
            
            # Header
            header_frame = ttk.Frame(result_dlg, padding=15)
            header_frame.pack(fill='x')
            
            if problems:
                ttk.Label(header_frame, 
                         text=f'⚠️ Found {len(problems)} validation issue(s) in {len(listbox_items)} title(s)',
                         font=('Segoe UI', 11, 'bold'), foreground='#d32f2f').pack(anchor='w')
            else:
                ttk.Label(header_frame, 
                         text=f'✅ All {len(listbox_items)} title(s) validated successfully',
                         font=('Segoe UI', 11, 'bold'), foreground='#2e7d32').pack(anchor='w')
            
            # Issues list
            if problems:
                issues_frame = ttk.LabelFrame(result_dlg, text='Validation Issues', padding=10)
                issues_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))
                
                issues_text = tk.Text(issues_frame, height=20, width=80, font=('Consolas', 9),
                                     wrap='word', bg='#fff3cd', fg='#856404')
                issues_text.pack(side='left', fill='both', expand=True)
                
                issues_scroll = ttk.Scrollbar(issues_frame, orient='vertical', command=issues_text.yview)
                issues_scroll.pack(side='right', fill='y')
                issues_text.configure(yscrollcommand=issues_scroll.set)
                
                for p in problems:
                    issues_text.insert('end', f'{p}\n\n')
                issues_text.config(state='disabled')
            
            # Close button
            btn_frame = ttk.Frame(result_dlg, padding=15)
            btn_frame.pack(fill='x', side='bottom')
            ttk.Button(btn_frame, text='Close', command=result_dlg.destroy, 
                      style='Accent.TButton').pack(side='right')
            
            result_dlg.wait_window()
            
        except Exception as e:
            logger.error(f"Error in validation: {e}")
            messagebox.showerror(
                'Validation Error', 
                f'An error occurred: {e}\n\n'
                'Action: Check that all required fields are filled correctly.'
            )
    
    validate_menu.add_command(label='🔍 Validate All Titles', command=_validate_all_titles)
    menubar.add_cascade(label='✓ Validate', menu=validate_menu)

    # Info menu with log viewer
    from src.gui.dialogs import open_log_viewer as dialog_open_log_viewer
    
    info_menu = tk.Menu(menubar, tearoff=0)
    
    def show_about():
        """Displays the About dialog with application information."""
        messagebox.showinfo(
            'About qBittorrent RSS Rule Editor', 
            'qBittorrent RSS Rule Editor\n\n'
            'Generate and sync qBittorrent RSS rules for seasonal anime.\n'
            'Run: python -m qbt_editor'
        )
    
    info_menu.add_command(label='View Logs...', command=lambda: dialog_open_log_viewer(root))
    info_menu.add_separator()
    info_menu.add_command(label='About', command=show_about)
    menubar.add_cascade(label='ℹ️ Info', menu=info_menu)

    # Attach menu to window
    try:
        root.config(menu=menubar)
    except Exception:
        try:
            root['menu'] = menubar
        except Exception:
            pass

    return menubar, recent_menu, edit_menu, file_menu


def setup_keyboard_shortcuts(root: tk.Tk, season_var: tk.StringVar, year_var: tk.StringVar, 
                            status_var: tk.StringVar) -> None:
    """
    Binds keyboard shortcuts for common operations.
    
    Sets up Ctrl+O (open), Ctrl+S (generate), Ctrl+E (export), etc.
    
    Args:
        root: Tkinter root window
        season_var: StringVar for season selection
        year_var: StringVar for year selection
        status_var: StringVar for status updates
    """
    # Import functions that will be called by shortcuts
    from src.gui.file_operations import (
        export_selected_titles, clear_all_titles, 
        export_all_titles, dispatch_generation
    )
    
    try:
        # File operations
        root.bind_all('<Control-o>', lambda e: import_titles_from_file(root, status_var))
        root.bind_all('<Control-O>', lambda e: import_titles_from_file(root, status_var))
        
        # Ctrl+S - Generate/Sync rules
        root.bind_all('<Control-s>', lambda e: dispatch_generation(root, season_var, year_var, status_var))
        root.bind_all('<Control-S>', lambda e: dispatch_generation(root, season_var, year_var, status_var))
        
        # Export shortcuts
        root.bind_all('<Control-e>', lambda e: export_selected_titles())
        root.bind_all('<Control-E>', lambda e: export_selected_titles())
        
        root.bind_all('<Control-Shift-E>', lambda e: export_all_titles())
        root.bind_all('<Control-Shift-e>', lambda e: export_all_titles())
        
        # Ctrl+Z - Undo (not yet implemented)
        # root.bind_all('<Control-z>', lambda e: undo_last_delete())
        # root.bind_all('<Control-Z>', lambda e: undo_last_delete())
        
        # App controls
        root.bind_all('<Control-q>', lambda e: root.quit())
        root.bind_all('<Control-Q>', lambda e: root.quit())
        
        root.bind_all('<Control-Shift-C>', lambda e: clear_all_titles(root, status_var))
        root.bind_all('<Control-Shift-c>', lambda e: clear_all_titles(root, status_var))
        
        root.bind_all('<F5>', lambda e: refresh_treeview_display())
        
        # Ctrl+B - Bulk Edit (note: will be set up properly after treeview is created)
        # Placeholder binding, will be updated in setup_library_panel
        root.bind_all('<Control-b>', lambda e: None)
        root.bind_all('<Control-B>', lambda e: None)
        
        # Ctrl+Z - Undo (will be set up properly after treeview is created)
        # Placeholder binding, will be updated in setup_library_panel
        root.bind_all('<Control-z>', lambda e: None)
        root.bind_all('<Control-Z>', lambda e: None)
        
        # Ctrl+T - Save as Template (will be set up properly after treeview is created)
        root.bind_all('<Control-t>', lambda e: None)
        root.bind_all('<Control-T>', lambda e: None)
        
        # Ctrl+Shift+T - Apply Template (will be set up properly after treeview is created)
        root.bind_all('<Control-Shift-t>', lambda e: None)
        root.bind_all('<Control-Shift-T>', lambda e: None)
        
        # Ctrl+F - Focus search
        from src.gui.app_state import get_app_state
        def _global_focus_search(e):
            get_app_state().focus_search()
            return 'break'
        root.bind_all('<Control-f>', _global_focus_search)
        root.bind_all('<Control-F>', _global_focus_search)
    except Exception:
        pass


def setup_drag_and_drop(root: tk.Tk, status_var: tk.StringVar, 
                        season_var: tk.StringVar = None, year_var: tk.StringVar = None) -> None:
    """
    Setup drag-and-drop support for JSON file import.
    
    Attempts to use tkinterdnd2 for native drag-and-drop. If not available,
    logs a warning but continues without DnD support.
    
    Args:
        root: Tkinter root window
        status_var: Status bar variable for feedback
        season_var: Season selection variable (optional)
        year_var: Year selection variable (optional)
    """
    try:
        # Try to import tkinterdnd2
        from tkinterdnd2 import DND_FILES
        
        # Check if root is a TkinterDnD.Tk instance
        if not hasattr(root, 'drop_target_register'):
            logger.info("Drag-and-drop: root window not DnD-enabled, skipping")
            return
        
        def _handle_drop(event):
            """Handle dropped files."""
            try:
                # Parse dropped file paths (may be wrapped in braces on Windows)
                files = root.tk.splitlist(event.data)
                
                json_files = [f for f in files if f.lower().endswith('.json')]
                
                if not json_files:
                    status_var.set("Drop a .json file to import")
                    return
                
                # Import the first JSON file
                file_path = json_files[0]
                
                # Use existing import function
                from src.gui.file_operations import import_titles_from_file
                
                # Get season/year vars - use empty StringVars as fallback
                sv = season_var if season_var else tk.StringVar(value="")
                yv = year_var if year_var else tk.StringVar(value="")
                
                success = import_titles_from_file(root, status_var, sv, yv, path=file_path)
                
                if success:
                    status_var.set(f"Imported: {os.path.basename(file_path)}")
                
            except Exception as e:
                logger.error(f"Drag-and-drop import failed: {e}")
                status_var.set(f"Drop failed: {e}")
        
        # Register the root window as a drop target
        root.drop_target_register(DND_FILES)
        root.dnd_bind('<<Drop>>', _handle_drop)
        
        logger.info("Drag-and-drop enabled for JSON file import")
        
    except ImportError:
        logger.info("tkinterdnd2 not installed - drag-and-drop disabled. Install with: pip install tkinterdnd2")
    except Exception as e:
        logger.warning(f"Could not setup drag-and-drop: {e}")


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


def setup_gui() -> tk.Tk:
    """
    Main GUI setup function - fully modular implementation.
    
    Initializes the complete application interface by calling all extracted
    setup functions in the proper sequence.
    
    Returns:
        tk.Tk: The root window instance
    """
    import json
    from src.rss_rules import build_rules_from_titles
    
    # Initialize app state singleton
    app_state = AppState.get_instance()
    
    # Load configuration
    try:
        config_set = config.load_config()
    except Exception as e:
        logger.error(f"Failed to load config: {e}", exc_info=True)
        config_set = False
    
    # Create root window - try TkinterDnD for drag-and-drop support
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        logger.info("Using TkinterDnD for drag-and-drop support")
    except ImportError:
        root = tk.Tk()
        logger.info("TkinterDnD not available - using standard Tk")
    
    app_state.root = root
    
    # Setup exception handler
    exit_handler()
    
    # Initialize default templates if none exist
    try:
        from src.cache import initialize_default_templates
        initialize_default_templates()
        logger.info("Default templates initialized")
    except Exception as e:
        logger.error(f"Failed to initialize default templates: {e}")
    
    # Initialize window and styles (returns style, season_var, year_var)
    style, season_var, year_var = setup_window_and_styles(root)
    
    # Create main container frame
    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill='both', expand=True)
    
    # Create status variable
    status_var = tk.StringVar(value='Initializing...')
    app_state.status_var = status_var
    
    # Setup menu bar (now that season_var and year_var are available)
    menubar, recent_menu, edit_menu, file_menu = setup_menu_bar(root, status_var, season_var, year_var)
    
    # Setup status bar and auto-connect
    setup_status_and_autoconnect(root, status_var, config_set)
    
    # Setup season controls
    top_config_frame = setup_season_controls(root, main_frame, season_var, year_var, status_var, style)
    
    # Setup library panel (treeview)
    paned, treeview = setup_library_panel(main_frame, style, edit_menu)
    app_state.treeview_widget = treeview
    
    # Setup editor panel
    (editor_rule_name, editor_must, editor_savepath, editor_category, 
     editor_enabled, editor_lastmatch_text) = setup_editor_panel(
        root, paned, treeview, season_var, year_var, status_var, style
    )
    
    # Setup keyboard shortcuts
    setup_keyboard_shortcuts(root, season_var, year_var, status_var)
    
    # Setup drag-and-drop for JSON file import
    setup_drag_and_drop(root, status_var, season_var, year_var)
    
    # ==================== Context Menu Setup ====================
    # Context menu handlers for right-click operations
    
    def _ctx_edit_selected():
        """Opens advanced editor for selected item."""
        try:
            from src.gui.dialogs import open_full_rule_editor
            
            sel = treeview.curselection()
            if not sel:
                messagebox.showwarning('Edit', 'No title selected.')
                return
            idx = int(sel[0])
            title_text, entry = app_state.listbox_items[idx]
            
            # Callback to refresh editor after save
            def _populate_callback(event=None):
                try:
                    new_sel = treeview.curselection()
                    if new_sel:
                        treeview.event_generate('<<TreeviewSelect>>')
                except Exception:
                    pass
            
            open_full_rule_editor(root, title_text, entry, idx, _populate_callback)
        except Exception as e:
            messagebox.showerror(
                'Edit Error', 
                f'Failed to open editor: {e}\n\n'
                'Action: Try closing and reopening the application.'
            )
    
    def _ctx_delete_selected():
        """Moves selected items to trash with undo support."""
        try:
            sel = treeview.curselection()
            if not sel:
                messagebox.showwarning(
                    'Delete', 
                    'No title selected.\n\n'
                    'Action: Select one or more titles from the list, then try again.'
                )
                return
            if not messagebox.askyesno('Confirm Delete', f'Delete {len(sel)} selected title(s)?'):
                return
            
            removed = 0
            for s in sorted([int(i) for i in sel], reverse=True):
                try:
                    title_text, entry = app_state.listbox_items[s]
                except Exception:
                    continue
                
                # Add to trash
                try:
                    app_state.trash_items.append({
                        'title': title_text, 
                        'entry': entry, 
                        'src': 'titles', 
                        'index': s
                    })
                except Exception:
                    pass
                
                # Remove from treeview
                try:
                    treeview.delete(s)
                except Exception:
                    pass
                
                # Remove from listbox_items
                try:
                    app_state.listbox_items.pop(s)
                except Exception:
                    pass
                
                # Remove from config.ALL_TITLES
                try:
                    if getattr(config, 'ALL_TITLES', None):
                        for k, lst in (config.ALL_TITLES.items() if isinstance(config.ALL_TITLES, dict) else []):
                            for i in range(len(config.ALL_TITLES.get(k, [])) - 1, -1, -1):
                                it = config.ALL_TITLES[k][i]
                                try:
                                    candidate = get_display_title(it) if isinstance(it, dict) else str(it)
                                except Exception:
                                    candidate = str(it)
                                if candidate == title_text:
                                    try:
                                        del config.ALL_TITLES[k][i]
                                    except Exception:
                                        pass
                except Exception:
                    pass
                
                removed += 1
            
            # Refresh treeview
            from src.gui.file_operations import refresh_treeview_display_safe
            refresh_treeview_display_safe()
            
            undo_count = len(app_state.trash_items)
            messagebox.showinfo('Delete', f'Moved {removed} title(s) to Trash.\n\nPress Ctrl+Z to undo ({undo_count} operation(s) available).')
            status_var.set(f'Deleted {removed} title(s) - press Ctrl+Z to undo')
        except Exception as e:
            messagebox.showerror(
                'Delete Error', 
                f'Failed to delete selected titles: {e}\n\n'
                'Action: Try refreshing the list and attempting again.'
            )
    
    def _ctx_copy_selected():
        """Copies selected items as JSON to clipboard."""
        try:
            sel = treeview.curselection()
            if not sel:
                messagebox.showwarning(
                    'Copy', 
                    'No title selected to copy.\n\n'
                    'Action: Select one or more titles from the list to copy as JSON.'
                )
                return
            
            export_map = {}
            try:
                sel_indices = [int(i) for i in sel]
            except Exception:
                sel_indices = []
            
            try:
                # Build proper qBittorrent rules format
                all_map = build_rules_from_titles({
                    'anime': [app_state.listbox_items[i][1] for i in sel_indices]
                })
                export_map = all_map
            except Exception:
                # Fallback: simple dictionary export
                for s in sel_indices:
                    try:
                        title_text, entry = app_state.listbox_items[s]
                    except Exception:
                        continue
                    if isinstance(entry, dict):
                        export_map[title_text] = entry
                    else:
                        export_map[title_text] = {'title': str(entry)}
            
            try:
                text = json.dumps(export_map, indent=4)
            except Exception as e:
                messagebox.showerror(
                    'Copy Error', 
                    f'Failed to serialize selection to JSON: {e}\n\n'
                    'Action: The selected data may be corrupted. Try selecting different items.'
                )
                return
            
            try:
                root.clipboard_clear()
                root.clipboard_append(text)
                root.update()
                messagebox.showinfo('Copy', f'Copied {len(export_map)} item(s) to clipboard as JSON.')
                status_var.set(f'Copied {len(export_map)} item(s) to clipboard')
            except Exception as e:
                messagebox.showerror('Copy Error', f'Failed to copy to clipboard: {e}')
        except Exception as e:
            messagebox.showerror('Copy Error', f'Failed to copy selected titles: {e}')
    
    def _ctx_toggle_enabled():
        """Toggles enabled/disabled state for selected rules."""
        try:
            sel = treeview.selection()
            if not sel:
                messagebox.showwarning('Toggle Enable/Disable', 'No title selected.')
                return
            
            toggled_count = 0
            for item_id in sel:
                try:
                    values = treeview.item(item_id, 'values')
                    if not values or len(values) < 3:
                        continue
                    
                    # Get title from values (index 2: enabled, index, title, ...)
                    title_text = values[2]
                    
                    # Find entry in listbox_items
                    entry = None
                    for t, e in app_state.listbox_items:
                        if t == title_text:
                            entry = e
                            break
                    
                    if not entry:
                        continue
                    
                    # Toggle enabled state
                    current_enabled = values[0] == '✓'
                    new_enabled = not current_enabled
                    
                    # Update entry enabled state
                    if isinstance(entry, dict):
                        entry['enabled'] = new_enabled
                    
                    # Update in config.ALL_TITLES
                    for k, lst in (config.ALL_TITLES.items() if isinstance(config.ALL_TITLES, dict) else []):
                        for i, it in enumerate(lst):
                            try:
                                candidate_title = get_display_title(it) if isinstance(it, dict) else str(it)
                            except Exception:
                                candidate_title = str(it)
                            if candidate_title == title_text:
                                if isinstance(config.ALL_TITLES[k][i], dict):
                                    config.ALL_TITLES[k][i]['enabled'] = new_enabled
                    
                    # Update treeview display
                    enabled_mark = '✓' if new_enabled else ''
                    new_values = (enabled_mark,) + values[1:]
                    treeview.item(item_id, values=new_values)
                    
                    toggled_count += 1
                except Exception as e:
                    logger.error(f"Error toggling item: {e}")
                    continue
            
            if toggled_count > 0:
                status_var.set(f'Toggled {toggled_count} rule(s)')
                # Refresh editor if any toggled item is currently selected
                # This ensures the enable checkbox updates immediately
                try:
                    treeview.event_generate('<<TreeviewSelect>>')
                except Exception:
                    pass
        except Exception as e:
            messagebox.showerror('Toggle Error', f'Failed to toggle rules: {e}')
    
    def _ctx_enable_selected():
        """Enables selected rules."""
        try:
            sel = treeview.selection()
            if not sel:
                messagebox.showwarning('Enable', 'No title selected.')
                return
            
            enabled_count = 0
            for item_id in sel:
                try:
                    values = treeview.item(item_id, 'values')
                    if not values or len(values) < 3:
                        continue
                    
                    title_text = values[2]
                    
                    # Find entry in listbox_items
                    entry = None
                    for t, e in app_state.listbox_items:
                        if t == title_text:
                            entry = e
                            break
                    
                    if not entry:
                        continue
                    
                    # Update entry enabled state
                    if isinstance(entry, dict):
                        entry['enabled'] = True
                    
                    # Update in config.ALL_TITLES
                    for k, lst in (config.ALL_TITLES.items() if isinstance(config.ALL_TITLES, dict) else []):
                        for i, it in enumerate(lst):
                            try:
                                candidate_title = get_display_title(it) if isinstance(it, dict) else str(it)
                            except Exception:
                                candidate_title = str(it)
                            if candidate_title == title_text:
                                if isinstance(config.ALL_TITLES[k][i], dict):
                                    config.ALL_TITLES[k][i]['enabled'] = True
                    
                    # Update treeview display (enabled, index, title, category, savepath)
                    new_values = ('✓',) + values[1:]
                    treeview.item(item_id, values=new_values)
                    
                    enabled_count += 1
                except Exception:
                    continue
            
            if enabled_count > 0:
                messagebox.showinfo('Enable', f'Enabled {enabled_count} rule(s).')
                status_var.set(f'Enabled {enabled_count} rule(s)')
                # Refresh editor to update checkbox
                try:
                    treeview.event_generate('<<TreeviewSelect>>')
                except Exception:
                    pass
        except Exception as e:
            messagebox.showerror('Enable Error', f'Failed to enable rules: {e}')
    
    def _ctx_disable_selected():
        """Disables selected rules."""
        try:
            sel = treeview.selection()
            if not sel:
                messagebox.showwarning('Disable', 'No title selected.')
                return
            
            disabled_count = 0
            for item_id in sel:
                try:
                    values = treeview.item(item_id, 'values')
                    if not values or len(values) < 3:
                        continue
                    
                    title_text = values[2]
                    
                    # Find entry in listbox_items
                    entry = None
                    for t, e in app_state.listbox_items:
                        if t == title_text:
                            entry = e
                            break
                    
                    if not entry:
                        continue
                    
                    # Update entry enabled state
                    if isinstance(entry, dict):
                        entry['enabled'] = False
                    
                    # Update in config.ALL_TITLES
                    for k, lst in (config.ALL_TITLES.items() if isinstance(config.ALL_TITLES, dict) else []):
                        for i, it in enumerate(lst):
                            try:
                                candidate_title = get_display_title(it) if isinstance(it, dict) else str(it)
                            except Exception:
                                candidate_title = str(it)
                            if candidate_title == title_text:
                                if isinstance(config.ALL_TITLES[k][i], dict):
                                    config.ALL_TITLES[k][i]['enabled'] = False
                    
                    # Update treeview display (enabled, index, title, category, savepath)
                    new_values = ('',) + values[1:]
                    treeview.item(item_id, values=new_values)
                    
                    disabled_count += 1
                except Exception:
                    continue
            
            if disabled_count > 0:
                messagebox.showinfo('Disable', f'Disabled {disabled_count} rule(s).')
                status_var.set(f'Disabled {disabled_count} rule(s)')
                # Refresh editor to update checkbox
                try:
                    treeview.event_generate('<<TreeviewSelect>>')
                except Exception:
                    pass
        except Exception as e:
            messagebox.showerror('Disable Error', f'Failed to disable rules: {e}')
    
    def _on_listbox_right_click(event):
        """Handles right-click on treeview to show context menu."""
        try:
            idx = treeview.nearest(event.y)
            if idx is None:
                return
            cur = treeview.curselection()
            if not cur or (idx not in [int(i) for i in cur]):
                try:
                    treeview.selection_clear(0, 'end')
                except Exception:
                    pass
                try:
                    treeview.selection_set(idx)
                except Exception:
                    pass
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
        except Exception:
            pass
    
    # Create context menu
    try:
        context_menu = tk.Menu(treeview, tearoff=0)
        context_menu.add_command(label='🔄 Toggle Enable/Disable', command=_ctx_toggle_enabled)
        context_menu.add_separator()
        context_menu.add_command(label='Copy', command=_ctx_copy_selected)
        context_menu.add_command(label='Edit', command=_ctx_edit_selected)
        context_menu.add_command(label='Delete', command=_ctx_delete_selected)
        treeview.bind('<Button-3>', _on_listbox_right_click, add='+')
        
        # Bind Space key to toggle enable/disable
        def _on_space_key(event):
            """Toggle enable/disable on Space key press."""
            try:
                _ctx_toggle_enabled()
                return "break"  # Prevent default space behavior
            except Exception as e:
                logger.error(f"Error in Space key handler: {e}")
        
        treeview.bind('<KeyPress-space>', _on_space_key)
    except Exception as e:
        logger.error(f"Failed to setup context menu: {e}")
    
    # Update Edit menu commands now that functions are defined
    if edit_menu:
        try:
            edit_menu.entryconfig(0, command=_ctx_toggle_enabled)
            # Undo is at index 2 (after separator)
            edit_menu.entryconfig(2, command=lambda: _undo_last_action())
            # Bulk edit is at index 4 (after another separator)
            edit_menu.entryconfig(4, command=lambda: _open_bulk_edit())
        except Exception as e:
            logger.error(f"Failed to update edit menu: {e}")
    
    # ==================== Bulk Edit Handler ====================
    def _open_bulk_edit():
        """Opens bulk edit dialog for multiple selected items."""
        try:
            from src.gui.dialogs import open_bulk_edit_dialog
            
            sel = treeview.curselection()
            if not sel or len(sel) < 2:
                messagebox.showinfo(
                    'Bulk Edit', 
                    'Please select 2 or more items to use bulk edit.\n\n'
                    'Tip: Hold Ctrl and click to select multiple items.'
                )
                return
            
            # Collect selected items
            selected_items = []
            for idx in sel:
                try:
                    idx_int = int(idx)
                    title_text, entry = app_state.listbox_items[idx_int]
                    selected_items.append((title_text, entry))
                except Exception as e:
                    logger.error(f"Failed to get item {idx}: {e}")
                    continue
            
            if not selected_items:
                messagebox.showwarning('Bulk Edit', 'No valid items selected.')
                return
            
            # Callback to apply changes
            def _apply_bulk_changes(items, changes):
                """Apply bulk changes to selected items."""
                try:
                    # Save undo state
                    _save_undo_state()
                    
                    success_count = 0
                    for title_text, entry in items:
                        try:
                            # Find the item in listbox_items
                            item_idx = None
                            for i, (t, e) in enumerate(app_state.listbox_items):
                                if t == title_text and e is entry:
                                    item_idx = i
                                    break
                            
                            if item_idx is None:
                                continue
                            
                            # Apply changes
                            if 'category' in changes:
                                entry['assignedCategory'] = changes['category']
                                if 'torrentParams' not in entry:
                                    entry['torrentParams'] = {}
                                entry['torrentParams']['category'] = changes['category']
                            
                            if 'save_path' in changes:
                                entry['savePath'] = changes['save_path']
                                if 'torrentParams' not in entry:
                                    entry['torrentParams'] = {}
                                entry['torrentParams']['save_path'] = changes['save_path']
                            
                            if 'enabled' in changes:
                                entry['enabled'] = changes['enabled']
                            
                            # Update in ALL_TITLES
                            if hasattr(config, 'ALL_TITLES') and isinstance(config.ALL_TITLES, dict):
                                for season_key, titles_list in config.ALL_TITLES.items():
                                    if isinstance(titles_list, list):
                                        for item in titles_list:
                                            if isinstance(item, dict) and item.get('title') == title_text:
                                                if 'category' in changes:
                                                    item['assignedCategory'] = changes['category']
                                                    if 'torrentParams' not in item:
                                                        item['torrentParams'] = {}
                                                    item['torrentParams']['category'] = changes['category']
                                                if 'save_path' in changes:
                                                    item['savePath'] = changes['save_path']
                                                    if 'torrentParams' not in item:
                                                        item['torrentParams'] = {}
                                                    item['torrentParams']['save_path'] = changes['save_path']
                                                if 'enabled' in changes:
                                                    item['enabled'] = changes['enabled']
                            
                            success_count += 1
                        except Exception as e:
                            logger.error(f"Failed to update item {title_text}: {e}")
                            continue
                    
                    # Refresh treeview display
                    if success_count > 0:
                        refresh_treeview_display()
                        
                        # Re-select the items
                        treeview.selection_clear()
                        for idx in sel:
                            try:
                                treeview.selection_add(int(idx))
                            except Exception:
                                pass
                    
                    return success_count
                except Exception as e:
                    logger.error(f"Bulk edit apply error: {e}", exc_info=True)
                    messagebox.showerror('Bulk Edit Error', f'Failed to apply changes: {e}')
                    return 0
            
            open_bulk_edit_dialog(root, selected_items, _apply_bulk_changes, status_var)
        except Exception as e:
            logger.error(f"Bulk edit error: {e}", exc_info=True)
            messagebox.showerror(
                'Bulk Edit Error', 
                f'Failed to open bulk editor: {e}\n\n'
                'Action: Try selecting items again.'
            )
    
    # Update keyboard shortcuts now that bulk edit function is defined
    try:
        root.bind_all('<Control-b>', lambda e: _open_bulk_edit())
        root.bind_all('<Control-B>', lambda e: _open_bulk_edit())
    except Exception as e:
        logger.error(f"Failed to bind bulk edit shortcut: {e}")
    
    # ==================== Unified Undo Handler ====================
    def _undo_last_action():
        """Unified undo handler for both delete and edit operations."""
        try:
            # Check if we have trash items (deleted items take priority)
            if app_state.trash_items:
                # Restore the most recent trash item
                try:
                    item = app_state.trash_items.pop()
                    if item.get('src') == 'titles':
                        title_text = item.get('title')
                        entry = item.get('entry')
                        original_idx = item.get('index', None)
                        
                        # Add back to listbox_items at original position if possible
                        if original_idx is not None and 0 <= original_idx <= len(app_state.listbox_items):
                            app_state.listbox_items.insert(original_idx, (title_text, entry))
                        else:
                            app_state.listbox_items.append((title_text, entry))
                        
                        # Add back to config.ALL_TITLES
                        if hasattr(config, 'ALL_TITLES') and isinstance(config.ALL_TITLES, dict):
                            if 'existing' not in config.ALL_TITLES:
                                config.ALL_TITLES['existing'] = []
                            config.ALL_TITLES['existing'].append(entry)
                        
                        # Refresh display
                        refresh_treeview_display()
                        
                        # Select the restored item
                        if original_idx is not None:
                            try:
                                treeview.selection_set(original_idx)
                                treeview.see(original_idx)
                            except Exception:
                                pass
                        
                        status_var.set(f'Restored: {title_text}')
                        
                        # Show info about remaining undo operations
                        remaining = len(app_state.trash_items)
                        if remaining > 0:
                            messagebox.showinfo('Undo', f'Restored "{title_text}"\n\n{remaining} more undo operation(s) available.')
                        else:
                            messagebox.showinfo('Undo', f'Restored "{title_text}"')
                        return
                except Exception as e:
                    logger.error(f"Failed to restore trash item: {e}")
                    messagebox.showerror('Undo Error', f'Failed to undo delete: {e}')
                    return
            
            # If no trash items, show message
            messagebox.showinfo('Undo', 'No operations to undo.\n\nTip: Undo works for delete operations.')
        except Exception as e:
            logger.error(f"Undo error: {e}", exc_info=True)
            messagebox.showerror('Undo Error', f'Failed to undo: {e}')
    
    # Update Ctrl+Z keyboard shortcuts
    try:
        root.bind_all('<Control-z>', lambda e: _undo_last_action())
        root.bind_all('<Control-Z>', lambda e: _undo_last_action())
    except Exception as e:
        logger.error(f"Failed to bind undo shortcut: {e}")
    
    # ==================== Template Functions ====================
    def _apply_template_to_rule(template_data: Dict[str, Any]) -> bool:
        """
        Apply a template to the selected rule(s).
        
        Args:
            template_data: Template configuration to apply
            
        Returns:
            bool: True if successful
        """
        try:
            selected = treeview.selection()
            if not selected:
                messagebox.showwarning('No Selection', 'Please select a rule to apply the template to.')
                return False
            
            # Apply template to each selected item
            for item in selected:
                values = treeview.item(item, 'values')
                if not values:
                    continue
                
                title_text = values[0]
                
                # Find the entry in listbox_items
                for idx, (t, entry) in enumerate(app_state.listbox_items):
                    if t == title_text:
                        # Update entry with template data
                        for key, value in template_data.items():
                            if key in entry:
                                entry[key] = value
                        
                        # Update treeview
                        enabled_text = '✓ Yes' if entry.get('enabled', True) else '✗ No'
                        treeview.item(item, values=(
                            title_text,
                            entry.get('category', ''),
                            entry.get('save_path', ''),
                            entry.get('must_contain', ''),
                            enabled_text
                        ))
                        break
            
            status_var.set(f'Template applied to {len(selected)} rule(s)')
            return True
        except Exception as e:
            logger.error(f"Error applying template: {e}", exc_info=True)
            messagebox.showerror('Template Error', f'Failed to apply template: {e}')
            return False
    
    def _open_template_dialog():
        """Open the template dialog to apply a template."""
        try:
            from src.gui.dialogs import open_template_dialog
            open_template_dialog(root, apply_callback=_apply_template_to_rule)
        except Exception as e:
            logger.error(f"Error opening template dialog: {e}", exc_info=True)
            messagebox.showerror('Template Error', f'Failed to open template dialog: {e}')
    
    def _save_as_template():
        """Save the selected rule as a template."""
        try:
            selected = treeview.selection()
            if not selected:
                messagebox.showwarning('No Selection', 'Please select a rule to save as a template.')
                return
            
            if len(selected) > 1:
                messagebox.showwarning('Multiple Selection', 'Please select only one rule to save as a template.')
                return
            
            # Get the selected item data
            item = selected[0]
            values = treeview.item(item, 'values')
            if not values:
                return
            
            title_text = values[0]
            
            # Find the entry in listbox_items
            current_rule = None
            for t, entry in app_state.listbox_items:
                if t == title_text:
                    current_rule = entry.copy()
                    break
            
            if not current_rule:
                messagebox.showerror('Error', 'Could not find rule data.')
                return
            
            # Open template dialog with current rule data
            from src.gui.dialogs import open_template_dialog
            open_template_dialog(root, current_rule_data=current_rule)
        except Exception as e:
            logger.error(f"Error saving template: {e}", exc_info=True)
            messagebox.showerror('Template Error', f'Failed to save template: {e}')
    
    def _manage_templates():
        """Open template management dialog."""
        try:
            from src.gui.dialogs import open_template_dialog
            open_template_dialog(root, apply_callback=_apply_template_to_rule)
        except Exception as e:
            logger.error(f"Error managing templates: {e}", exc_info=True)
            messagebox.showerror('Template Error', f'Failed to open template manager: {e}')
    
    # Update template keyboard shortcuts
    try:
        root.bind_all('<Control-t>', lambda e: _save_as_template())
        root.bind_all('<Control-T>', lambda e: _save_as_template())
        root.bind_all('<Control-Shift-t>', lambda e: _open_template_dialog())
        root.bind_all('<Control-Shift-T>', lambda e: _open_template_dialog())
    except Exception as e:
        logger.error(f"Failed to bind template shortcuts: {e}")
    
    # ==================== Sonarr Export Function ====================
    def _export_to_sonarr():
        """Export selected or all titles to Sonarr."""
        try:
            # Get all titles from listbox_items
            all_titles = [title for title, entry in app_state.listbox_items]
            
            if not all_titles:
                messagebox.showwarning('No Titles', 'No titles to export. Please add some anime first.')
                return
            
            # Ask if exporting selected or all
            selected = treeview.selection()
            if selected:
                export_selected = messagebox.askyesno(
                    'Export to Sonarr',
                    f'Export {len(selected)} selected titles to Sonarr?\n\n'
                    'Click No to export all titles instead.'
                )
                if export_selected:
                    titles_to_export = [treeview.item(item, 'values')[0] for item in selected]
                else:
                    titles_to_export = all_titles
            else:
                titles_to_export = all_titles
            
            # Open Sonarr export dialog
            from src.gui.dialogs import open_sonarr_export_dialog
            open_sonarr_export_dialog(root, titles_to_export)
            
        except Exception as e:
            logger.error(f"Sonarr export error: {e}", exc_info=True)
            messagebox.showerror('Sonarr Export Error', f'Failed to export to Sonarr: {e}')
    
    # Update file menu with Sonarr command
    try:
        # Find the Export to Sonarr menu item and update it
        file_menu.entryconfig('Export to Sonarr...', command=_export_to_sonarr)
    except Exception as e:
        logger.error(f"Failed to configure Sonarr menu item: {e}")
    
    # Update keyboard shortcut
    try:
        root.bind_all('<Control-Shift-s>', lambda e: _export_to_sonarr())
        root.bind_all('<Control-Shift-S>', lambda e: _export_to_sonarr())
    except Exception as e:
        logger.error(f"Failed to bind Sonarr shortcut: {e}")
    
    # ==================== Generate/Sync Button Bar ====================
    # Will be packed after status_frame is created (see below around line 970)
    action_bar = ttk.Frame(root, padding="8")
    
    def _generate_and_sync():
        """Shows dialog to choose between Export Offline or Sync Online."""
        try:
            # Create choice dialog
            choice_dlg = tk.Toplevel(root)
            choice_dlg.title('Generate Rules')
            choice_dlg.geometry('400x200')
            choice_dlg.transient(root)
            choice_dlg.grab_set()
            choice_dlg.resizable(False, False)
            
            # Center the dialog
            choice_dlg.update_idletasks()
            x = root.winfo_x() + (root.winfo_width() // 2) - (choice_dlg.winfo_width() // 2)
            y = root.winfo_y() + (root.winfo_height() // 2) - (choice_dlg.winfo_height() // 2)
            choice_dlg.geometry(f'+{x}+{y}')
            
            # Header
            header_frame = ttk.Frame(choice_dlg, padding=15)
            header_frame.pack(fill='x')
            ttk.Label(header_frame, text='Choose Generation Mode', 
                     font=('Segoe UI', 11, 'bold')).pack(anchor='w')
            ttk.Label(header_frame, text='Select how you want to generate the RSS rules:', 
                     font=('Segoe UI', 9)).pack(anchor='w', pady=(5, 0))
            
            # Button frame
            btn_frame = ttk.Frame(choice_dlg, padding=15)
            btn_frame.pack(fill='both', expand=True)
            
            def _export_offline():
                """Export rules to JSON file."""
                choice_dlg.destroy()
                try:
                    from src.gui.file_operations import export_all_titles
                    export_all_titles()
                except Exception as e:
                    logger.error(f"Error in export: {e}")
                    messagebox.showerror('Error', f'Export failed: {e}')
            
            def _sync_online():
                """Sync rules to qBittorrent."""
                choice_dlg.destroy()
                try:
                    from src.gui.file_operations import dispatch_generation
                    dispatch_generation(root, season_var, year_var, status_var)
                except Exception as e:
                    logger.error(f"Error in sync: {e}")
                    messagebox.showerror('Error', f'Sync failed: {e}')
            
            # Export button (offline)
            export_btn = ttk.Button(btn_frame, text='📁 Export to JSON File (Offline)', 
                                   command=_export_offline, style='Accent.TButton')
            export_btn.pack(fill='x', pady=(0, 10))
            create_tooltip(export_btn, 
                          "Export rules to a JSON file\n"
                          "• Save rules for later use\n"
                          "• No qBittorrent connection needed\n"
                          "• Can be imported later")
            
            # Sync button (online)
            sync_btn = ttk.Button(btn_frame, text='⚡ Sync to qBittorrent (Online)', 
                                 command=_sync_online)
            sync_btn.pack(fill='x', pady=(0, 10))
            create_tooltip(sync_btn, 
                          "Generate and sync rules to qBittorrent\n"
                          "• Validates all titles and settings\n"
                          "• Shows preview before syncing\n"
                          "• Requires qBittorrent connection")
            
            # Cancel button
            cancel_btn = ttk.Button(btn_frame, text='✕ Cancel', 
                                   command=choice_dlg.destroy)
            cancel_btn.pack(fill='x')
            
            choice_dlg.wait_window()
            
        except Exception as e:
            logger.error(f"Error in generate/sync: {e}")
            messagebox.showerror('Error', f'An error occurred: {e}')
    
    generate_sync_btn = ttk.Button(action_bar, text='⚡ Generate Rules', 
                                   command=_generate_and_sync, style='Accent.TButton')
    generate_sync_btn.pack(fill='x', pady=(0, 5))
    create_tooltip(generate_sync_btn, 
                  "Generate RSS rules\n" +
                  "• Choose to Export (offline) or Sync (online)\n" +
                  "• Validates all titles and settings\n" +
                  "• Shows preview before syncing")
    
    # ==================== Status Bar ====================
    # Pack status_frame first (at very bottom)
    status_frame = ttk.Frame(root, padding="5")
    status_frame.pack(side='bottom', fill='x')
    status_label = ttk.Label(status_frame, textvariable=status_var, relief='sunken', anchor='w')
    status_label.pack(fill='x')
    
    # Pack action_bar above status_frame
    action_bar.pack(side='bottom', fill='x')
    
    # ==================== Final Initialization ====================
    # Load initial data if available
    try:
        logger.debug(f"Startup: config.ALL_TITLES type: {type(getattr(config, 'ALL_TITLES', None))}")
        logger.debug(f"Startup: config.ALL_TITLES content: {getattr(config, 'ALL_TITLES', None)}")
        
        if config.ALL_TITLES:
            # Pass treeview explicitly to ensure it's used
            update_treeview_with_titles(config.ALL_TITLES, treeview_widget=treeview)
            total_count = sum(len(v) for v in config.ALL_TITLES.values() if isinstance(v, list))
            status_var.set(f'Loaded {total_count} titles from config')
        else:
            logger.warning("Startup: config.ALL_TITLES is empty or None")
    except Exception as e:
        logger.error(f"Failed to load initial titles: {e}", exc_info=True)
    
    logger.info("GUI Session 4E: Fully modular GUI initialized successfully")
    
    # Start the main event loop
    root.mainloop()
    
    return root


def setup_season_controls(root: tk.Tk, main_frame: ttk.Frame, season_var: tk.StringVar, 
                          year_var: tk.StringVar, status_var: tk.StringVar, 
                          style: ttk.Style) -> ttk.Frame:
    """
    Creates the season/year selection controls and sync button.
    
    Sets up the top configuration panel with season dropdown, year entry,
    and sync from qBittorrent button for fetching existing rules.
    
    Args:
        root: Tkinter root window
        main_frame: Parent frame to pack controls into
        season_var: StringVar for season selection
        year_var: StringVar for year input
        status_var: StringVar for status updates
        style: ttk.Style for button styling
        
    Returns:
        The top_config_frame containing all season controls
    """
    top_config_frame = ttk.Frame(main_frame, padding="5")
    top_config_frame.pack(fill='x', pady=(0, 5))
    
    # Add a title label
    title_label = ttk.Label(top_config_frame, text="Season Configuration", font=('Segoe UI', 11, 'bold'))
    title_label.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 3))
    
    ttk.Label(top_config_frame, text="Season:").grid(row=1, column=0, sticky='w', padx=(0, 5), pady=5)
    season_dropdown = ttk.Combobox(top_config_frame, textvariable=season_var, 
                                    values=["Winter", "Spring", "Summer", "Fall"], 
                                    state="readonly", width=5)
    season_dropdown.grid(row=1, column=1, sticky='w', padx=5, pady=5)
    
    ttk.Label(top_config_frame, text="Year:").grid(row=1, column=2, sticky='w', padx=(15, 5), pady=5)
    year_entry = ttk.Entry(top_config_frame, textvariable=year_var, width=5)
    year_entry.grid(row=1, column=3, sticky='w', padx=5, pady=5)
    
    # Keep prefix_imports_var for compatibility (moved to settings dialog)
    try:
        pref_prefix = config.get_pref('prefix_imports', True)
    except Exception:
        pref_prefix = True
    prefix_imports_var = tk.BooleanVar(value=bool(pref_prefix))
    
    def _on_prefix_imports_changed(*a):
        try:
            config.set_pref('prefix_imports', bool(prefix_imports_var.get()))
        except Exception:
            pass
    
    try:
        prefix_imports_var.trace_add('write', lambda *a: _on_prefix_imports_changed())
    except Exception:
        try:
            prefix_imports_var.trace('w', lambda *a: _on_prefix_imports_changed())
        except Exception:
            pass
    
    top_config_frame.grid_columnconfigure(3, weight=1)

    # Sync from qBittorrent button
    def _sync_online_worker(root_ref, status_var_ref, btn_ref):
        """Background worker to sync existing rules from qBittorrent."""
        def worker():
            try:
                root_ref.after(0, lambda: (btn_ref.config(state='disabled'), 
                                          status_var_ref.set('Sync: fetching existing rules...')))
                
                # Fetch rules using the qbittorrent_api module
                success, rules = qbt_api.fetch_rules(
                    config.QBT_PROTOCOL,
                    config.QBT_HOST,
                    str(config.QBT_PORT),
                    config.QBT_USER or '',
                    config.QBT_PASS or '',
                    bool(config.QBT_VERIFY_SSL),
                    getattr(config, 'QBT_CA_CERT', None)
                )
                
                if not success:
                    error_msg = str(rules)
                    root_ref.after(0, lambda: (status_var_ref.set(f'Sync failed: {error_msg}'),
                                              btn_ref.config(state='normal')))
                    return
                
                def finish():
                    try:
                        from src.gui.app_state import get_app_state
                        
                        if not rules:
                            status_var_ref.set('No existing rules available to add.')
                        else:
                            entries = []
                            if isinstance(rules, dict):
                                for name, data in rules.items():
                                    if isinstance(data, dict):
                                        title = data.get('ruleName') or data.get('name') or name
                                        rule_entry = dict(data)
                                        if not rule_entry.get('node'):
                                            rule_entry['node'] = {'title': title}
                                        # Ensure ruleName is set for duplicate detection
                                        if not rule_entry.get('ruleName'):
                                            rule_entry['ruleName'] = title
                                        entries.append(rule_entry)
                                    else:
                                        entries.append({'node': {'title': name}, 'ruleName': name})
                            elif isinstance(rules, list):
                                for item in rules:
                                    if isinstance(item, dict) and item.get('ruleName'):
                                        name = item.get('ruleName')
                                    else:
                                        name = str(item)
                                    entries.append({'node': {'title': name}, 'ruleName': name})

                            if entries:
                                current = getattr(config, 'ALL_TITLES', {}) or {}
                                existing_titles = set()
                                existing_must_contain = set()
                                existing_rule_names = set()
                                
                                # Collect existing titles, mustContain, and rule names
                                if isinstance(current, dict):
                                    for k, lst in current.items():
                                        if not isinstance(lst, list):
                                            continue
                                        for it in lst:
                                            try:
                                                if isinstance(it, dict):
                                                    t = get_display_title(it) or get_rule_name(it)
                                                    if t is not None:
                                                        existing_titles.add(str(t))
                                                    # Also track mustContain and ruleName for better duplicate detection
                                                    must = it.get('mustContain')
                                                    if must:
                                                        existing_must_contain.add(str(must))
                                                    rule_name = it.get('ruleName') or it.get('name')
                                                    if rule_name:
                                                        existing_rule_names.add(str(rule_name))
                                                else:
                                                    t = str(it)
                                                    existing_titles.add(t)
                                            except Exception:
                                                try:
                                                    existing_titles.add(str(it))
                                                except Exception:
                                                    pass

                                # Filter out duplicates
                                new_entries = []
                                for e in entries:
                                    try:
                                        if isinstance(e, dict):
                                            title = get_display_title(e) or get_rule_name(e)
                                            must = e.get('mustContain')
                                            rule_name = e.get('ruleName') or e.get('name')
                                        else:
                                            title = str(e)
                                            must = None
                                            rule_name = None
                                        
                                        key = None if title is None else str(title)
                                    except Exception:
                                        key = None
                                        must = None
                                        rule_name = None

                                    # Check if it's a duplicate by title, mustContain, or ruleName
                                    is_duplicate = False
                                    if key and key in existing_titles:
                                        is_duplicate = True
                                        logger.debug(f"Sync: Skipping duplicate title: {key}")
                                    elif must and str(must) in existing_must_contain:
                                        is_duplicate = True
                                        logger.debug(f"Sync: Skipping duplicate mustContain: {must}")
                                    elif rule_name and str(rule_name) in existing_rule_names:
                                        is_duplicate = True
                                        logger.debug(f"Sync: Skipping duplicate ruleName: {rule_name}")
                                    
                                    if is_duplicate:
                                        continue
                                    
                                    # Add to tracking sets
                                    if key:
                                        existing_titles.add(key)
                                    if must:
                                        existing_must_contain.add(str(must))
                                    if rule_name:
                                        existing_rule_names.add(str(rule_name))
                                    
                                    logger.debug(f"Sync: Adding new entry: {key}")
                                    new_entries.append(e)

                                if new_entries:
                                    cur_list = current.get('existing', [])
                                    cur_list.extend(new_entries)
                                    current['existing'] = cur_list
                                    config.ALL_TITLES = current
                                    try:
                                        from src.gui.file_operations import refresh_treeview_display_safe
                                        refresh_treeview_display_safe()
                                        status_var_ref.set(f'Added {len(new_entries)} new existing rule(s) to Titles.')
                                    except Exception as e:
                                        logger.error(f"Failed to refresh treeview after sync: {e}")
                                        status_var_ref.set('Added existing rules but failed to refresh Titles UI.')
                                else:
                                    status_var_ref.set('No new existing rules to add (duplicates skipped).')
                    finally:
                        try:
                            btn_ref.config(state='normal')
                        except Exception:
                            pass
                
                root_ref.after(0, finish)
            except Exception as e:
                error_msg = str(e)
                root_ref.after(0, lambda: (status_var_ref.set(f'Sync error: {error_msg}'), 
                                          btn_ref.config(state='normal')))
        
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _on_sync_clicked():
        """Handles sync button click - syncs from qBittorrent or opens file dialog."""
        try:
            mode = (getattr(config, 'CONNECTION_MODE', '') or '').lower()
            if mode == 'online':
                sync_btn.config(state='disabled')
                _sync_online_worker(root, status_var, sync_btn)
            else:
                import_titles_from_file(root, status_var)
        except Exception as e:
            messagebox.showerror('Sync Error', f'Failed to start sync: {e}')
    
    # Sync button
    # Use larger font for emoji visibility and secondary color styling
    sync_btn_style = ttk.Style()
    sync_btn_style.configure('SyncButton.TButton', 
                            font=('Segoe UI', 10),
                            background='#5A9FD4',
                            foreground='white')
    sync_btn_style.map('SyncButton.TButton',
                      background=[('active', '#4A8FC4'), ('pressed', '#3A7FB4')])
    sync_btn = ttk.Button(top_config_frame, text='🔄 Sync from qBittorrent', 
                         command=_on_sync_clicked, style='SyncButton.TButton')
    sync_btn.grid(row=2, column=0, columnspan=4, sticky='ew', padx=0, pady=(10, 0))
    create_tooltip(sync_btn,
                  "Import existing RSS rules from qBittorrent\n" +
                  "• Online mode: Fetch rules from qBittorrent API\n" +
                  "• Offline mode: Import from JSON file\n" +
                  "• Automatically skips duplicates")

    return top_config_frame


def setup_library_panel(
    main_frame: ttk.Frame, 
    style: ttk.Style, 
    edit_menu: tk.Menu = None
) -> Tuple[ttk.PanedWindow, ttk.Treeview]:
    """
    Creates the title library panel with treeview and all features.
    
    Sets up the main library display with:
    - Resizable paned window for library/editor split
    - Treeview with columns (#, Enabled, Title, Category, Save Path)
    - Auto-fit columns, column width persistence
    - Scrollbars (auto-hide when not needed)
    - Listbox compatibility methods
    - Context menu (Enable, Disable, Copy, Edit, Delete)
    
    Args:
        main_frame: Parent frame to pack panel into
        style: ttk.Style for treeview styling
        edit_menu: Edit menu to configure enable/disable commands (optional)
        
    Returns:
        Tuple of (paned_window, treeview) for further configuration
    """
    list_frame_container = ttk.LabelFrame(main_frame, text="📋 Title Rules Library", padding="15")
    list_frame_container.pack(fill='both', expand=True, pady=(10, 5))
    
    # Search/Filter bar
    search_frame = ttk.Frame(list_frame_container)
    search_frame.pack(fill='x', pady=(0, 8))
    
    ttk.Label(search_frame, text="🔍 Filter:").pack(side='left', padx=(0, 5))
    
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
    
    # Store in app_state for global access
    from src.gui.app_state import get_app_state
    app_state = get_app_state()
    app_state.search_entry = search_entry
    app_state.search_var = search_var
    
    # Filter type dropdown
    filter_type_var = tk.StringVar(value="Title")
    filter_type = ttk.Combobox(search_frame, textvariable=filter_type_var, 
                               values=["Title", "Category", "Save Path", "All"], 
                               state='readonly', width=10)
    filter_type.pack(side='left', padx=(0, 5))
    
    # Clear button
    def clear_filter():
        search_var.set("")
        _apply_filter()
    
    clear_btn = ttk.Button(search_frame, text="✕", width=3, command=clear_filter)
    clear_btn.pack(side='left')

    # Use PanedWindow to allow resizable split between library and editor
    paned = ttk.PanedWindow(list_frame_container, orient='horizontal')
    paned.pack(fill='both', expand=True)
    
    # Load saved paned window position
    try:
        saved_sash_pos = config.get_pref('paned_sash_position', None)
    except Exception:
        saved_sash_pos = None
    
    # Function to save paned window position
    def _save_sash_position(event=None):
        try:
            def _delayed_save():
                try:
                    pos = paned.sashpos(0)
                    config.set_pref('paned_sash_position', pos)
                except Exception:
                    pass
            paned.after(100, _delayed_save)
        except Exception:
            pass
    
    # Bind to save sash position when dragged
    paned.bind('<ButtonRelease-1>', _save_sash_position)
    
    # Bind double-click to reset paned sash to default position
    def _reset_paned_sash(event):
        try:
            total_width = paned.winfo_width()
            if total_width > 100:
                default_pos = int(total_width * 0.6)
                paned.sashpos(0, default_pos)
                config.set_pref('paned_sash_position', default_pos)
        except Exception:
            pass
    
    paned.bind('<Double-Button-1>', _reset_paned_sash)

    # Restore saved position after widget is rendered
    def _restore_or_set_default_sash():
        try:
            total_width = paned.winfo_width()
            if total_width > 100:
                default_pos = int(total_width * 0.6)
                
                # Validate saved position
                if saved_sash_pos is not None and saved_sash_pos > 100 and saved_sash_pos < total_width - 100:
                    paned.sashpos(0, saved_sash_pos)
                else:
                    # Use default if saved position is invalid
                    paned.sashpos(0, default_pos)
        except Exception:
            pass
    
    # Create treeview frame
    treeview_frame = ttk.Frame(paned)
    paned.add(treeview_frame, weight=3)
    
    # Create Treeview with columns (checkmark as first column, hide tree column #0)
    treeview = ttk.Treeview(treeview_frame, selectmode='extended', 
                           columns=('enabled', 'index', 'title', 'category', 'savepath'),
                           show='headings', height=20)
    
    # Define column headings (enabled first, then index, title, category, savepath)
    treeview.heading('enabled', text='✓', anchor='center', command=lambda: _sort_column('enabled', False))
    treeview.heading('index', text='#', anchor='w', command=lambda: _sort_column('index', False))
    treeview.heading('title', text='Title', anchor='w', command=lambda: _sort_column('title', False))
    treeview.heading('category', text='Category', anchor='w', command=lambda: _sort_column('category', False))
    treeview.heading('savepath', text='Save Path', anchor='w', command=lambda: _sort_column('savepath', False))
    
    # Load saved column widths or use defaults
    try:
        saved_col_widths = config.get_pref('treeview_column_widths', {})
    except Exception:
        saved_col_widths = {}
    
    # Load saved column order
    try:
        saved_col_order = config.get_pref('treeview_column_order', None)
    except Exception:
        saved_col_order = None
    
    # Apply saved column order if available, ensuring 'enabled' is always first and 'index' always second
    # IMPORTANT: If old config doesn't have 'index', we must add it!
    if saved_col_order and isinstance(saved_col_order, list):
        try:
            logger.debug(f"Saved column order from config: {saved_col_order}")
            # Ensure 'enabled' is first in the display order
            if 'enabled' in saved_col_order:
                saved_col_order.remove('enabled')
            saved_col_order.insert(0, 'enabled')
            # Ensure 'index' is second (may not exist in old configs - MUST ADD IT!)
            if 'index' not in saved_col_order:
                logger.debug("'index' column not in saved order, adding it at position 1")
                saved_col_order.insert(1, 'index')
            else:
                # Move index to position 1 if it's elsewhere
                if saved_col_order.index('index') != 1:
                    saved_col_order.remove('index')
                    saved_col_order.insert(1, 'index')
            logger.debug(f"Final column display order: {saved_col_order}")
            treeview['displaycolumns'] = tuple(saved_col_order)
        except Exception as e:
            logger.error(f"Error setting column order: {e}", exc_info=True)
            # Fallback to default order with enabled first
            treeview['displaycolumns'] = ('enabled', 'index', 'title', 'category', 'savepath')
    else:
        logger.debug("No saved column order, using default: enabled, index, title, category, savepath")
        # Default order with enabled first
        treeview['displaycolumns'] = ('enabled', 'index', 'title', 'category', 'savepath')
    
    # Sorting state
    sort_reverse = {}
    
    def _sort_column(col, reverse):
        """Sort treeview contents by column."""
        try:
            items = [(treeview.set(item, col), item) for item in treeview.get_children('')]
            items.sort(reverse=reverse)
            
            for index, (val, item) in enumerate(items):
                treeview.move(item, '', index)
            
            # Toggle sort direction for next click
            sort_reverse[col] = not reverse
            treeview.heading(col, command=lambda: _sort_column(col, sort_reverse[col]))
        except Exception:
            pass
    
    # Track manual column resizes
    columns_manual_resize = {
        'enabled': {'disabled': False},
        'index': {'disabled': False},
        'title': {'disabled': False},
        'category': {'disabled': False},
        'savepath': {'disabled': False}
    }
    
    # Configure column widths
    treeview.column('enabled', width=saved_col_widths.get('enabled', 30), minwidth=25, stretch=False)
    treeview.column('index', width=saved_col_widths.get('index', 40), minwidth=30, stretch=False)
    treeview.column('title', width=saved_col_widths.get('title', 300), minwidth=150, stretch=False)
    treeview.column('category', width=saved_col_widths.get('category', 150), minwidth=100, stretch=False)
    treeview.column('savepath', width=saved_col_widths.get('savepath', 400), minwidth=150, stretch=False)
    
    # Auto-fit column function with better width calculation
    def _auto_fit_column(col_id):
        """Auto-fit column width based on content with proper text measurement."""
        try:
            # Start with minimum width
            max_width = 30
            
            # Font metrics for accurate measurement (approximate 7 pixels per char for Segoe UI 9pt)
            char_width = 7
            padding = 20
            
            # Measure header text
            header_texts = {'enabled': '✓', 'index': '#', 'title': 'Title', 'category': 'Category', 'savepath': 'Save Path'}
            header_text = header_texts.get(col_id, '')
            header_width = len(header_text) * char_width + padding + 10  # Extra padding for sort indicator
            max_width = max(max_width, header_width)
            
            # Measure all items in column
            for item in treeview.get_children():
                try:
                    values = treeview.item(item, 'values')
                    col_index = {'enabled': 0, 'index': 1, 'title': 2, 'category': 3, 'savepath': 4}.get(col_id, -1)
                    text = values[col_index] if col_index >= 0 and col_index < len(values) else ''
                    
                    if text:
                        text_width = len(str(text)) * char_width + padding
                        max_width = max(max_width, text_width)
                except Exception:
                    pass
            
            # Cap maximum width to prevent excessive columns
            max_width = min(max_width, 600)
            
            treeview.column(col_id, width=int(max_width))
            
            # Mark as manually sized to prevent auto-resize
            if col_id in columns_manual_resize:
                columns_manual_resize[col_id]['disabled'] = False
        except Exception as e:
            logger.error(f"Error in auto_fit_column: {e}")
    
    # Auto-fit all columns on data load
    def _auto_fit_all_columns():
        """Auto-fit all columns after data is loaded."""
        try:
            for col_id in ['enabled', 'index', 'title', 'category', 'savepath']:
                if col_id not in columns_manual_resize or not columns_manual_resize[col_id].get('disabled', False):
                    _auto_fit_column(col_id)
        except Exception:
            pass
    
    # Save column widths and order function
    def _save_column_widths_and_order(event=None):
        """Save column widths and display order."""
        try:
            widths = {
                'enabled': treeview.column('enabled', 'width'),
                'index': treeview.column('index', 'width'),
                'title': treeview.column('title', 'width'),
                'category': treeview.column('category', 'width'),
                'savepath': treeview.column('savepath', 'width')
            }
            config.set_pref('treeview_column_widths', widths)
            
            # Save column display order (always ensure enabled is first, index second)
            try:
                display_cols = list(treeview['displaycolumns'])
                # Ensure enabled is always first
                if 'enabled' in display_cols:
                    display_cols.remove('enabled')
                display_cols.insert(0, 'enabled')
                # Ensure index is always second
                if 'index' in display_cols:
                    display_cols.remove('index')
                display_cols.insert(1, 'index')
                config.set_pref('treeview_column_order', display_cols)
            except Exception:
                pass
            
            # Track manual resize
            if event:
                try:
                    region = treeview.identify_region(event.x, event.y)
                    if region == "separator":
                        col = treeview.identify_column(event.x)
                        col_map = {'#0': '#0', '#1': 'enabled', '#2': 'title', '#3': 'category', '#4': 'savepath'}
                        if col in col_map:
                            columns_manual_resize[col_map[col]]['disabled'] = True
                except Exception:
                    pass
        except Exception:
            pass
    
    treeview.bind('<ButtonRelease-1>', _save_column_widths_and_order)
    
    # Double-click separator to auto-fit column
    def _on_double_click(event):
        """Handle double-click on column separator to auto-resize."""
        try:
            region = treeview.identify_region(event.x, event.y)
            if region == "separator":
                # Get the column to the LEFT of the separator
                x_pos = event.x
                col = None
                cumulative_width = 0
                    
                # Check each displayed column
                for col_name in ['enabled', 'index', 'title', 'category', 'savepath']:
                    col_width = treeview.column(col_name, 'width')
                    cumulative_width += col_width
                    if abs(x_pos - cumulative_width) <= 5:  # Separator threshold
                        col = col_name
                        break
                
                if col:
                    _auto_fit_column(col)
                    _save_column_widths_and_order()
                return "break"
        except Exception as e:
            logger.error(f"Error in double-click handler: {e}")
    
    treeview.bind('<Double-Button-1>', _on_double_click)
    
    # Create scrollbars
    vsb = ttk.Scrollbar(treeview_frame, orient='vertical', command=treeview.yview)
    hsb = ttk.Scrollbar(treeview_frame, orient='horizontal', command=treeview.xview)
    
    # Auto-hide scrollbars
    def _vsb_set(*args):
        try:
            vsb.set(*args)
            if float(args[0]) <= 0.0 and float(args[1]) >= 1.0:
                vsb.grid_remove()
            else:
                vsb.grid()
        except Exception:
            vsb.set(*args)
    
    def _hsb_set(*args):
        try:
            hsb.set(*args)
            if float(args[0]) <= 0.0 and float(args[1]) >= 1.0:
                hsb.grid_remove()
            else:
                hsb.grid()
        except Exception:
            hsb.set(*args)
    
    treeview.configure(yscrollcommand=_vsb_set, xscrollcommand=_hsb_set)
    
    # Grid layout
    treeview.grid(row=0, column=0, sticky='nsew')
    vsb.grid(row=0, column=1, sticky='ns')
    hsb.grid(row=1, column=0, sticky='ew')
    
    treeview_frame.grid_rowconfigure(0, weight=1)
    treeview_frame.grid_columnconfigure(0, weight=1)
    
    # Attach manual resize tracker
    treeview._columns_manual_resize = columns_manual_resize
    
    # Add Listbox compatibility methods (for legacy code)
    def _curselection():
        """Returns tuple of selected indices like Listbox.curselection()."""
        try:
            selected_items = treeview.selection()
            indices = []
            all_items = treeview.get_children()
            for item in selected_items:
                try:
                    idx = all_items.index(item)
                    indices.append(idx)
                except:
                    pass
            return tuple(indices)
        except Exception:
            return ()
    
    def _delete_items(first, last='end'):
        """Delete items like Listbox.delete()."""
        try:
            if first == 0 and last == 'end':
                for item in treeview.get_children():
                    ttk.Treeview.delete(treeview, item)
            elif isinstance(first, int):
                all_items = treeview.get_children()
                if first < len(all_items):
                    ttk.Treeview.delete(treeview, all_items[first])
        except Exception:
            pass
    
    # Store original insert method before monkey-patching
    _original_insert = treeview.insert
    
    def _insert_item(parent_or_position, index_or_text, text=None, **kw):
        """Insert like Listbox.insert() or Treeview.insert()."""
        try:
            if text is None and not kw:
                # Listbox-style insert: treeview.insert('end', value)
                if parent_or_position == 'end':
                    return _original_insert('', 'end', text='', values=(index_or_text, '', ''))
            else:
                # Treeview-style insert: treeview.insert(parent, index, **kw)
                # Only pass text if it's not None to avoid it being interpreted as iid
                if text is not None:
                    return _original_insert(parent_or_position, index_or_text, text=text, **kw)
                else:
                    return _original_insert(parent_or_position, index_or_text, **kw)
        except Exception as e:
            logger.error(f"Error in _insert_item wrapper: {e}", exc_info=True)
            return None
    
    def _nearest(y):
        """Get item nearest to y coordinate."""
        try:
            item = treeview.identify_row(y)
            if item:
                all_items = treeview.get_children()
                return all_items.index(item)
            return 0
        except Exception:
            return 0
    
    def _see(index):
        """Ensure item at index is visible."""
        try:
            all_items = treeview.get_children()
            if index < len(all_items):
                treeview.see(all_items[index])
        except Exception:
            pass
    
    def _selection_set(index):
        """Select item at index."""
        try:
            all_items = treeview.get_children()
            if index < len(all_items):
                treeview.selection_set(all_items[index])
        except Exception:
            pass
    
    # Monkey-patch compatibility methods
    treeview.curselection = _curselection
    treeview.delete = _delete_items
    treeview.insert = _insert_item
    treeview.nearest = _nearest
    treeview.see = _see
    treeview.selection_set = _selection_set
    
    # Filter function for search with debouncing
    _filter_job = None
    _all_items_cache = []  # Cache all items for faster filtering
    
    def _rebuild_items_cache():
        """Rebuild the items cache from treeview."""
        nonlocal _all_items_cache
        _all_items_cache = []
        for item in treeview.get_children():
            values = treeview.item(item, 'values')
            if values and len(values) >= 5:
                _all_items_cache.append((item, values))
    
    def _apply_filter_impl():
        """Filter treeview items based on search text."""
        nonlocal _filter_job
        _filter_job = None
        
        search_text = search_var.get().lower().strip()
        filter_by = filter_type_var.get()
        
        # Rebuild cache if needed
        if not _all_items_cache:
            _rebuild_items_cache()
        
        if not search_text:
            # Show all items efficiently
            for item, _ in _all_items_cache:
                try:
                    treeview.reattach(item, '', 'end')
                except Exception:
                    pass
            return
        
        # Filter items using cached data
        for item, values in _all_items_cache:
            enabled, idx, title, category, savepath = values[:5]
            
            # Build match text based on filter type
            if filter_by == "Title":
                match_text = title.lower()
            elif filter_by == "Category":
                match_text = category.lower()
            elif filter_by == "Save Path":
                match_text = savepath.lower()
            else:  # All
                match_text = f"{title} {category} {savepath}".lower()
            
            try:
                if search_text in match_text:
                    treeview.reattach(item, '', 'end')
                else:
                    treeview.detach(item)
            except Exception:
                pass
    
    def _apply_filter(*args):
        """Debounced filter - waits 150ms before applying."""
        nonlocal _filter_job
        if _filter_job:
            treeview.after_cancel(_filter_job)
        _filter_job = treeview.after(150, _apply_filter_impl)
    
    def _invalidate_filter_cache(*args):
        """Invalidate cache when treeview content changes."""
        nonlocal _all_items_cache
        _all_items_cache = []
    
    # Bind filter to search entry
    search_var.trace_add('write', _apply_filter)
    filter_type_var.trace_add('write', _apply_filter)
    
    # Bind Ctrl+F to focus search
    def _focus_search(event=None):
        search_entry.focus_set()
        search_entry.select_range(0, 'end')
        return 'break'
    
    treeview.bind('<Control-f>', _focus_search)
    treeview.bind('<Control-F>', _focus_search)
    
    # Bind Escape to clear filter when in search entry
    def _escape_search(event=None):
        if search_var.get():
            clear_filter()
        else:
            treeview.focus_set()
        return 'break'
    
    search_entry.bind('<Escape>', _escape_search)
    
    # Restore sash position after widget is fully rendered
    paned.after_idle(_restore_or_set_default_sash)
    
    return paned, treeview


def setup_editor_panel(root: tk.Tk, paned: tk.PanedWindow, treeview: ttk.Treeview,
                       season_var: tk.StringVar, year_var: tk.StringVar,
                       status_var: tk.StringVar, style: ttk.Style) -> Tuple[tk.StringVar, tk.StringVar, tk.StringVar, tk.StringVar, tk.BooleanVar, tk.Text]:
    """
    Creates the rule editor panel with all editor fields and SubsPlease integration.
    
    Sets up a scrollable editor panel containing:
    - Title and match pattern fields
    - Feed title lookup with SubsPlease API integration
    - Last match display with age calculation
    - Save path and category fields
    - Enabled checkbox
    - Season/year prefix button
    - Apply and Advanced Settings buttons
    
    Args:
        root: Tkinter root window
        paned: PanedWindow widget containing library and editor panels
        treeview: Treeview widget for displaying titles
        season_var: StringVar for season selection
        year_var: StringVar for year selection
        status_var: StringVar for status bar updates
        style: ttk.Style object for styling
        
    Returns:
        Tuple of (editor_rule_name, editor_must, editor_savepath, editor_category, 
                  editor_enabled, editor_lastmatch_text):
            - editor_rule_name: StringVar for rule title
            - editor_must: StringVar for match pattern
            - editor_savepath: StringVar for save path
            - editor_category: StringVar for category
            - editor_enabled: BooleanVar for enabled state
            - editor_lastmatch_text: Text widget for last match display
    """
    from src.subsplease_api import fetch_subsplease_schedule, find_subsplease_title_match, load_subsplease_cache
    from src.gui.dialogs import open_full_rule_editor
    import json
    from datetime import datetime, timezone
    
    app_state = AppState.get_instance()
    listbox_items = app_state.listbox_items
    
    # Create editor container for PanedWindow (increased weight for more width)
    editor_container = ttk.Frame(paned)
    paned.add(editor_container, weight=3)
    
    # Create editor scrollable container
    editor_scrollable_container = ttk.Frame(editor_container)
    editor_scrollable_container.pack(fill='both', expand=True)
    
    editor_canvas = tk.Canvas(editor_scrollable_container, bg='#ffffff', highlightthickness=0)
    editor_scrollbar = ttk.Scrollbar(editor_scrollable_container, orient='vertical', command=editor_canvas.yview)
    editor_frame = ttk.Frame(editor_canvas, padding=15)
    
    try:
        editor_scrollbar.pack(side='right', fill='y')
        editor_canvas.pack(side='left', fill='both', expand=True)
    except Exception:
        pass
    
    try:
        editor_canvas_window = editor_canvas.create_window((0, 0), window=editor_frame, anchor='nw')
        editor_canvas.configure(yscrollcommand=editor_scrollbar.set)
        
        # Update canvas window width when canvas resizes
        def _on_canvas_resize(event):
            try:
                canvas_width = event.width
                editor_canvas.itemconfig(editor_canvas_window, width=canvas_width)
            except Exception:
                pass
        editor_canvas.bind('<Configure>', _on_canvas_resize)
        
        # Enable mousewheel scrolling for editor canvas
        def _on_editor_mousewheel(event):
            try:
                editor_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception:
                pass
        
        def _bind_editor_mousewheel(event):
            try:
                editor_canvas.bind("<MouseWheel>", _on_editor_mousewheel)
            except Exception:
                pass
        
        def _unbind_editor_mousewheel(event):
            try:
                editor_canvas.unbind("<MouseWheel>")
            except Exception:
                pass
        
        editor_canvas.bind("<Enter>", _bind_editor_mousewheel)
        editor_canvas.bind("<Leave>", _unbind_editor_mousewheel)
        editor_frame.bind("<Enter>", _bind_editor_mousewheel)
        editor_frame.bind("<Leave>", _unbind_editor_mousewheel)
    except Exception:
        pass
    
    def _configure_editor_scroll(event=None):
        try:
            editor_canvas.configure(scrollregion=editor_canvas.bbox('all'))
            # Show/hide scrollbar based on content
            try:
                bbox = editor_canvas.bbox("all")
                if bbox:
                    content_height = bbox[3] - bbox[1]
                    canvas_height = editor_canvas.winfo_height()
                    if content_height > canvas_height:
                        editor_scrollbar.pack(side='right', fill='y')
                    else:
                        editor_scrollbar.pack_forget()
                        editor_canvas.pack(side='left', fill='both', expand=True)
            except Exception:
                pass
        except Exception:
            pass
    
    try:
        editor_frame.bind('<Configure>', _configure_editor_scroll)
    except Exception:
        pass

    # Editor variables
    editor_rule_name = tk.StringVar(value='')
    editor_must = tk.StringVar(value='')
    editor_savepath = tk.StringVar(value='')
    editor_category = tk.StringVar(value='')
    editor_enabled = tk.BooleanVar(value=True)
    
    # Undo stack for editor changes (stores previous state)
    editor_undo_stack = []
    
    def _save_undo_state():
        """Saves current editor state to undo stack."""
        try:
            sel = treeview.curselection()
            if not sel:
                return
            idx = int(sel[0])
            title_text, entry = listbox_items[idx]
            
            # Create a deep copy of the current state
            state = {
                'idx': idx,
                'title': title_text,
                'entry': json.loads(json.dumps(entry)),  # Deep copy via JSON
                'editor_values': {
                    'rule_name': editor_rule_name.get(),
                    'must': editor_must.get(),
                    'savepath': editor_savepath.get(),
                    'category': editor_category.get(),
                    'enabled': editor_enabled.get()
                }
            }
            editor_undo_stack.append(state)
            # Keep only last 10 undo states
            if len(editor_undo_stack) > 10:
                editor_undo_stack.pop(0)
            
            # Update undo button state
            try:
                undo_btn.config(state='normal')
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Error saving undo state: {e}")
    
    def _undo_editor_changes():
        """Undoes the last editor change."""
        try:
            if not editor_undo_stack:
                messagebox.showinfo('Undo', 'No changes to undo.')
                return
            
            # Pop the last state
            state = editor_undo_stack.pop()
            
            # Restore the entry
            idx = state['idx']
            entry = state['entry']
            title = state['title']
            
            # Update listbox_items
            listbox_items[idx] = (title, entry)
            
            # Update config.ALL_TITLES
            try:
                if getattr(config, 'ALL_TITLES', None):
                    for k, lst in (config.ALL_TITLES.items() if isinstance(config.ALL_TITLES, dict) else []):
                        for i, it in enumerate(lst):
                            try:
                                candidate_title = get_display_title(it) if isinstance(it, dict) else str(it)
                            except Exception:
                                candidate_title = str(it)
                            if candidate_title == state['editor_values']['rule_name']:
                                config.ALL_TITLES[k][i] = entry
                                break
            except Exception as e:
                logger.error(f"Error updating ALL_TITLES during undo: {e}")
            
            # Refresh treeview
            try:
                update_treeview_with_titles(config.ALL_TITLES)
                treeview.selection_set(idx)
                treeview.see(idx)
            except Exception:
                pass
            
            # Refresh editor to show restored values
            try:
                _populate_editor_from_selection()
            except Exception:
                pass
            
            # Update undo button state
            try:
                if not editor_undo_stack:
                    undo_btn.config(state='disabled')
            except Exception:
                pass
            
            status_var.set('Undone last change')
        except Exception as e:
            messagebox.showerror('Undo Error', f'Failed to undo: {e}')
    
    # Improved text widget styling
    editor_lastmatch_text = tk.Text(editor_frame, height=2, width=40, state='disabled',
                                     font=('Consolas', 9), bg='#fafafa', fg='#333333',
                                     relief='flat', bd=1, highlightthickness=1,
                                     highlightbackground='#e0e0e0', highlightcolor='#0078D4')

    # Create header with title and undo button
    editor_header = ttk.Frame(editor_frame)
    editor_header.pack(fill='x', pady=(0, 10))
    ttk.Label(editor_header, text='📝 Rule Editor', font=('Segoe UI', 11, 'bold')).pack(side='left')
    
    undo_btn = ttk.Button(editor_header, text='↶ Undo', command=_undo_editor_changes, 
                          width=8, state='disabled')
    undo_btn.pack(side='right')
    create_tooltip(undo_btn, 'Undo last auto-applied change (up to 10 changes)')
    
    ttk.Separator(editor_frame, orient='horizontal').pack(fill='x', pady=(0, 10))
    
    ttk.Label(editor_frame, text='Title:', font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 2))
    ttk.Entry(editor_frame, textvariable=editor_rule_name, font=('Segoe UI', 9)).pack(anchor='w', fill='x', pady=(0, 8))
    
    ttk.Label(editor_frame, text='Match Pattern:', font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 2))
    ttk.Entry(editor_frame, textvariable=editor_must, font=('Segoe UI', 9)).pack(anchor='w', fill='x', pady=(0, 8))
    
    # ==================== Feed Title Lookup Section ====================
    feed_lookup_frame = ttk.LabelFrame(editor_frame, text='📡 Title Variations', padding=12)
    feed_lookup_frame.pack(fill='x', pady=(0, 10))
    
    # SubsPlease title display with better layout
    subsplease_title_var = tk.StringVar(value='')
    fetch_status_var = tk.StringVar(value='')
    
    # Feed Title label row with cache status
    title_label_row = ttk.Frame(feed_lookup_frame)
    title_label_row.pack(fill='x', pady=(0, 2))
    
    feed_label = ttk.Label(title_label_row, text='Title:', font=('Segoe UI', 9, 'bold'))
    feed_label.pack(side='left')
    
    # Cache status next to Title label
    fetch_status_label = ttk.Label(title_label_row, textvariable=fetch_status_var, 
                                   font=('Segoe UI', 8), foreground='#0078D4')
    fetch_status_label.pack(side='left', padx=(8, 0))
    
    # Title value row (clickable)
    subsplease_row = ttk.Frame(feed_lookup_frame)
    subsplease_row.pack(fill='x', pady=(0, 8))
    
    subsplease_label = ttk.Label(subsplease_row, textvariable=subsplease_title_var, 
                                 font=('Segoe UI', 10, 'bold'), foreground='#0066CC',
                                 cursor='hand2', padding=(4, 4))
    subsplease_label.pack(fill='x', expand=True)
    
    create_tooltip(subsplease_label, 'Click to apply this title to Match Pattern field')
    
    def _use_subsplease_title():
        """Copies SubsPlease title to Must Contain field and triggers immediate save."""
        sp_title = subsplease_title_var.get()
        if sp_title and sp_title != 'Not found in cache':
            # Set the field value
            editor_must.set(sp_title)
            # Force immediate apply by calling the schedule function with zero delay
            # The actual function will be defined later
            status_var.set(f'Applied SubsPlease title: {sp_title}')
    
    subsplease_label.bind('<Button-1>', lambda e: _use_subsplease_title())
        
    # Fetch button frame (single button since Load auto-loads on startup)
    fetch_btn_frame = ttk.Frame(feed_lookup_frame)
    fetch_btn_frame.pack(fill='x', pady=(0, 0))
    
    def _fetch_subsplease_titles(force_refresh: bool = False):
        """Fetches SubsPlease schedule in background thread."""
        def _worker():
            try:
                # Show appropriate status based on operation
                if force_refresh:
                    fetch_status_var.set('⏳ Fetching fresh data from SubsPlease API...')
                else:
                    fetch_status_var.set('⏳ Loading titles (cache-first)...')
                
                success, result = fetch_subsplease_schedule(force_refresh=force_refresh)
                
                if success:
                    count = len(result) if isinstance(result, list) else 0
                    cache_status = 'from API' if force_refresh else 'from cache'
                    fetch_status_var.set(f'✅ Loaded {count} titles {cache_status}')
                    status_var.set(f'SubsPlease: {count} titles loaded')
                    
                    # Update current title match if one is selected
                    _update_feed_variations()
                else:
                    fetch_status_var.set(f'❌ Failed: {result}')
                    status_var.set('Failed to fetch SubsPlease titles')
            except Exception as e:
                fetch_status_var.set(f'❌ Error: {str(e)}')
                status_var.set('Error fetching SubsPlease titles')
        
        try:
            threading.Thread(target=_worker, daemon=True).start()
        except Exception as e:
            fetch_status_var.set(f'❌ Failed to start: {str(e)}')
    
    def _update_feed_variations():
        """Updates feed title variations for currently selected title."""
        try:
            # Get current title
            current_title = editor_rule_name.get()
            if not current_title:
                subsplease_title_var.set('')
                subsplease_row.pack_forget()
                return
            
            # Check cache for match
            sp_match = find_subsplease_title_match(current_title)
            
            # Get current must contain value to compare
            current_must = editor_must.get()
            
            if sp_match:
                # Only show if SubsPlease match is different from current mustContain
                if sp_match != current_must:
                    subsplease_title_var.set(sp_match)
                    fetch_status_var.set('✅ Match found in cache')
                    subsplease_row.pack(fill='x', pady=(0, 8), after=title_label_row)
                else:
                    # Same as current, hide the label
                    subsplease_title_var.set('')
                    subsplease_row.pack_forget()
                    fetch_status_var.set('✅ Already using SubsPlease title')
            else:
                subsplease_title_var.set('Not found in cache')
                fetch_status_var.set('⚠️ No match - click Fetch to update cache')
                subsplease_row.pack_forget()
        except Exception as e:
            subsplease_title_var.set('Error')
            logger.error(f"Error updating feed variations: {e}")
    
    # Simple tooltip helper class
    class ToolTip:
        """Displays a tooltip when hovering over a widget."""
        def __init__(self, widget, text):
            self.widget = widget
            self.text = text
            self.tooltip = None
            widget.bind('<Enter>', self.show)
            widget.bind('<Leave>', self.hide)
        
        def show(self, event=None):
            try:
                x = self.widget.winfo_rootx() + 25
                y = self.widget.winfo_rooty() + 25
                
                self.tooltip = tk.Toplevel(self.widget)
                self.tooltip.wm_overrideredirect(True)
                self.tooltip.wm_geometry(f"+{x}+{y}")
                
                label = tk.Label(self.tooltip, text=self.text, 
                               background='#ffffe0', relief='solid', 
                               borderwidth=1, font=('Segoe UI', 8),
                               padx=5, pady=3)
                label.pack()
            except Exception:
                pass
        
        def hide(self, event=None):
            if self.tooltip:
                try:
                    self.tooltip.destroy()
                except Exception:
                    pass
                self.tooltip = None
    
    # Single Fetch Fresh button (auto-loads cache on startup, so Load button not needed)
    fetch_fresh_btn = ttk.Button(fetch_btn_frame, text='🔄 Fetch Fresh', 
                                  command=lambda: _fetch_subsplease_titles(force_refresh=True))
    fetch_fresh_btn.pack(fill='x', expand=True)
    ToolTip(fetch_fresh_btn, "Fetches the latest data from SubsPlease API")
    
    # Load initial cache status (auto-load on startup)
    try:
        cached = load_subsplease_cache()
        if cached:
            fetch_status_var.set(f'📦 {len(cached)} titles in cache')
        else:
            fetch_status_var.set('📦 Cache empty - click Fetch Fresh')
    except Exception:
        fetch_status_var.set('📦 Cache empty')
    
    # ==================== End Feed Title Lookup Section ====================
    
    ttk.Label(editor_frame, text='Last Match:', font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 2))
    editor_lastmatch_text.pack(anchor='w', pady=(0, 2), fill='x', expand=True)

    # Create a single row for status and age labels to eliminate blank space
    status_age_row = ttk.Frame(editor_frame)
    status_age_row.pack(fill='x', pady=(0, 8))
    
    lastmatch_status_label = tk.Label(status_age_row, text='', fg='#28a745', font=('Segoe UI', 8), bg='#ffffff')
    lastmatch_status_label.pack(side='left', padx=(0, 10))
    
    age_label = ttk.Label(status_age_row, text='Age: N/A', font=('Segoe UI', 8))
    age_label.pack(side='left')
    
    current_lastmatch_holder = {'value': None}
    try:
        pref_val = config.get_pref('time_24', True)
    except Exception:
        pref_val = True
    time_24_var = tk.BooleanVar(value=bool(pref_val))
    
    ttk.Label(editor_frame, text='Save Path:', font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 2))
    editor_savepath_entry = ttk.Entry(editor_frame, textvariable=editor_savepath, font=('Segoe UI', 9))
    editor_savepath_entry.pack(anchor='w', fill='x', pady=(0, 8))
    
    # Track if save path was manually edited (to prevent auto-fill overwriting user edits)
    savepath_manually_edited = {'flag': False}
    
    def _on_savepath_change(*args):
        """Mark save path as manually edited when user types in it."""
        savepath_manually_edited['flag'] = True
    
    # Bind to detect manual edits (triggered when user types)
    editor_savepath_entry.bind('<KeyRelease>', lambda e: _on_savepath_change())
    
    ttk.Label(editor_frame, text='Category:', font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 2))
    # Use Combobox for category with cached categories
    editor_category_combo = ttk.Combobox(editor_frame, textvariable=editor_category, font=('Segoe UI', 9))
    editor_category_combo.pack(anchor='w', fill='x', pady=(0, 8))
    
    def _on_category_change(*args):
        """Auto-fill save path from category's save path if not manually edited and no custom save path exists."""
        if savepath_manually_edited['flag']:
            return  # User has manually edited save path, don't override
        
        try:
            selected_category = editor_category.get().strip()
            if not selected_category:
                return
            
            # Get current save path
            current_save_path = editor_savepath.get().strip()
            
            # Get category info from cached categories
            cached_cats = getattr(config, 'CACHED_CATEGORIES', {}) or {}
            if isinstance(cached_cats, dict) and selected_category in cached_cats:
                cat_info = cached_cats[selected_category]
                if isinstance(cat_info, dict) and 'savePath' in cat_info:
                    cat_save_path = cat_info['savePath']
                    
                    # Only auto-fill if:
                    # 1. There's no current save path (empty field), OR
                    # 2. Current save path matches the category's default (user hasn't customized it)
                    # This prevents overwriting custom save paths when loading rules
                    if not current_save_path:
                        # Empty field, safe to auto-fill
                        editor_savepath.set(cat_save_path)
                    elif current_save_path == cat_save_path:
                        # Already matches category default, no change needed
                        pass
                    # else: Custom save path exists, don't override it
        except Exception:
            pass
    
    # Bind category change to auto-fill save path
    editor_category.trace_add('write', _on_category_change)
    
    # Function to update category cache
    def _update_category_cache():
        try:
            categories = set()
            
            # Load cached categories from config
            try:
                config.load_cached_categories()
                cached_cats = getattr(config, 'CACHED_CATEGORIES', {}) or {}
                if isinstance(cached_cats, dict):
                    categories.update(cached_cats.keys())
                elif isinstance(cached_cats, list):
                    categories.update(cached_cats)
            except Exception:
                pass
            
            # Add categories from current listbox items
            for title_text, entry in listbox_items:
                if isinstance(entry, dict):
                    cat = entry.get('assignedCategory') or entry.get('assigned_category') or entry.get('category') or ''
                    if cat:
                        categories.add(str(cat))
                    tp = entry.get('torrentParams') or {}
                    if isinstance(tp, dict) and tp.get('category'):
                        categories.add(str(tp['category']))
            
            editor_category_combo['values'] = sorted(list(categories))
        except Exception:
            pass
    
    # Update cache initially
    _update_category_cache()
    
    ttk.Checkbutton(editor_frame, text='Enabled', variable=editor_enabled).pack(anchor='w', pady=(0, 10))

    # Add prefix button
    def _add_prefix_to_selected():
        """
        Adds season/year prefix to the selected title.
        """
        try:
            sel = treeview.curselection()
            if not sel:
                messagebox.showwarning('Prefix', 'No title selected.')
                return
            idx = int(sel[0])
            title_text, entry = listbox_items[idx]
            
            season = season_var.get()
            year = year_var.get()
            prefix = f"[{season} {year}] "
            
            # Check if already has prefix
            if title_text.startswith(prefix):
                messagebox.showinfo('Prefix', 'Title already has this prefix.')
                return
            
            new_title = prefix + title_text
            
            # Update entry
            if isinstance(entry, dict):
                node = entry.get('node') or {}
                node['title'] = new_title
                entry['node'] = node
            
            # Update listbox and items
            listbox_items[idx] = (new_title, entry)
            treeview.delete(idx)
            treeview.insert(idx, new_title)
            treeview.selection_set(idx)
            treeview.see(idx)
            
            # Update config
            try:
                if getattr(config, 'ALL_TITLES', None):
                    for k, lst in (config.ALL_TITLES.items() if isinstance(config.ALL_TITLES, dict) else []):
                        for i, it in enumerate(lst):
                            try:
                                candidate_title = get_display_title(it) if isinstance(it, dict) else str(it)
                            except Exception:
                                candidate_title = str(it)
                            if candidate_title == title_text:
                                config.ALL_TITLES[k][i] = entry
                                break
            except Exception:
                pass
            
            # Refresh treeview to show updated titles
            update_treeview_with_titles(config.ALL_TITLES)
            
            # Re-select the item after refresh
            try:
                treeview.selection_set(idx)
                treeview.see(idx)
            except Exception:
                pass
            
            # Refresh editor
            _populate_editor_from_selection()
            messagebox.showinfo('Prefix', f'Added prefix "{prefix}" to title.')
        except Exception as e:
            messagebox.showerror('Prefix Error', f'Failed to add prefix: {e}')
    
    ttk.Separator(editor_frame, orient='horizontal').pack(fill='x', pady=(0, 10))
    
    prefix_btn_frame = ttk.Frame(editor_frame)
    prefix_btn_frame.pack(anchor='w', fill='x', pady=(0, 10))
    ttk.Button(prefix_btn_frame, text='🏷️ Add Season/Year Prefix', command=_add_prefix_to_selected, style='Secondary.TButton').pack(fill='x')

    ttk.Separator(editor_frame, orient='horizontal').pack(fill='x', pady=(0, 10))

    btns = ttk.Frame(editor_frame)
    btns.pack(anchor='center', pady=(0, 0), fill='x')

    def _populate_editor_from_selection(event=None):
        """
        Populates the editor panel with data from the selected listbox item.
        
        Args:
            event: Optional Tkinter event (for event binding)
        """
        try:
            sel = treeview.curselection()
            if not sel:
                return
            idx = int(sel[0])
            mapped = listbox_items[idx]
            title_text, entry = mapped[0], mapped[1]
        except Exception:
            return

        editor_rule_name.set(title_text)
        must = ''
        save = ''
        cat = ''
        en = True
        try:
            if isinstance(entry, dict):
                node = entry.get('node') or {}
                must = entry.get('mustContain') or entry.get('must_contain') or node.get('title') or title_text

                def _find(d, candidates):
                    try:
                        if not isinstance(d, dict):
                            return None
                        for k in candidates:
                            if k in d and d.get(k) is not None and str(d.get(k)).strip() != '':
                                return d.get(k)
                    except Exception:
                        pass
                    return None

                tp = None
                for tp_key in ('torrentParams', 'torrent_params', 'torrentparams'):
                    if isinstance(entry, dict) and tp_key in entry and isinstance(entry[tp_key], dict):
                        tp = entry[tp_key]
                        break

                save_val = _find(entry, ['savePath', 'save_path']) or (_find(tp, ['save_path', 'savePath', 'download_path']) if tp else None)
                save = '' if save_val is None else str(save_val).replace('\\', '/')

                cat_val = _find(entry, ['assignedCategory', 'assigned_category', 'category']) or (_find(tp, ['category']) if tp else None)
                cat = '' if cat_val is None else str(cat_val)

                en = bool(entry.get('enabled', True))
                try:
                    lm = entry.get('lastMatch', '')
                except Exception:
                    lm = ''
                current_lastmatch_holder['value'] = lm
                try:
                    update_lastmatch_display(lm)
                except Exception:
                    try:
                        editor_lastmatch_text.config(state='normal')
                        editor_lastmatch_text.delete('1.0', 'end')
                        editor_lastmatch_text.insert('1.0', '' if lm is None else str(lm))
                        editor_lastmatch_text.config(state='disabled')
                    except Exception:
                        pass
            else:
                must = str(entry)
        except Exception:
            must = title_text

        editor_must.set(must)
        editor_savepath.set(save)
        editor_category.set(cat)
        editor_enabled.set(en)
        
        # Reset manual edit flag when loading from selection
        savepath_manually_edited['flag'] = False
        
        # Update category cache
        try:
            _update_category_cache()
        except Exception:
            pass
        
        # Update feed title variations
        try:
            _update_feed_variations()
        except Exception:
            pass

    def _parse_datetime_from_string(s):
        """
        Parses a datetime string in various formats into a datetime object.
        
        Args:
            s: String containing date/time information
        
        Returns:
            datetime or None: Parsed datetime object with timezone info, or None if parsing fails
        """
        if not s or not isinstance(s, str):
            return None
        for fmt in ('%d %b %Y %H:%M:%S %z', '%d %b %Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S'):
            try:
                ds = s.strip()
                if ds.endswith('Z'):
                    ds = ds[:-1] + ' +0000'
                if '+' in ds or '-' in ds:
                    parts = ds.rsplit(' ', 1)
                    if len(parts) == 2 and (':' in parts[1]):
                        tz = parts[1].replace(':', '')
                        ds = parts[0] + ' ' + tz
                dt = datetime.strptime(ds, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                continue
        try:
            ds = s.strip()
            if ds.endswith('Z'):
                ds = ds[:-1] + '+00:00'
            dt = datetime.fromisoformat(ds)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def update_lastmatch_display(lm_value=None):
        """
        Updates the lastMatch display field with formatted datetime information.
        
        Args:
            lm_value: Optional lastMatch value to display (uses cached value if None)
        """
        try:
            val = lm_value if lm_value is not None else current_lastmatch_holder.get('value')
            try:
                editor_lastmatch_text.config(state='normal')
            except Exception:
                pass
            try:
                editor_lastmatch_text.delete('1.0', 'end')
            except Exception:
                pass
            age_text = 'Age: N/A'
            try:
                lastmatch_status_label.config(text='', fg='green')
            except Exception:
                pass
            if isinstance(val, (dict, list)):
                try:
                    editor_lastmatch_text.insert('1.0', json.dumps(val, indent=2))
                except Exception:
                    editor_lastmatch_text.insert('1.0', str(val))
                age_label.config(text=age_text)
                try:
                    editor_lastmatch_text.config(state='disabled')
                except Exception:
                    pass
                return
            if isinstance(val, str) and val.strip():
                parsed = _parse_datetime_from_string(val.strip())
                if parsed is not None:
                    try:
                        local_tz = datetime.now().astimezone().tzinfo
                        parsed_local = parsed.astimezone(local_tz)
                    except Exception:
                        parsed_local = parsed

                    try:
                        now_local = datetime.now(parsed_local.tzinfo) if parsed_local.tzinfo is not None else datetime.now()
                        delta = now_local - parsed_local
                        secs = delta.total_seconds()
                        if secs < 0:
                            future_secs = -int(secs)
                            if future_secs < 60:
                                age_text = 'In a few seconds'
                            elif future_secs < 3600:
                                age_text = f'In {future_secs//60} minute(s)'
                            elif future_secs < 86400:
                                age_text = f'In {future_secs//3600} hour(s)'
                            else:
                                age_text = f'In {abs(delta.days)} day(s)'
                        else:
                            if secs < 60:
                                age_text = 'just now'
                            elif secs < 3600:
                                age_text = f'{int(secs//60)} minute(s) ago'
                            elif secs < 86400:
                                age_text = f'{int(secs//3600)} hour(s) ago'
                            else:
                                age_text = f'{delta.days} day(s) ago'
                    except Exception:
                        age_text = 'Age: N/A'

                    try:
                        if time_24_var.get():
                            fmt = '%Y-%m-%d %H:%M:%S %Z'
                        else:
                            fmt = '%Y-%m-%d %I:%M:%S %p %Z'
                        display = parsed_local.strftime(fmt)
                    except Exception:
                        display = val
                    editor_lastmatch_text.insert('1.0', display)
                    age_label.config(text=f'Age: {age_text}')
                    try:
                        editor_lastmatch_text.config(state='disabled')
                    except Exception:
                        pass
                    return
            editor_lastmatch_text.insert('1.0', '' if val is None else str(val))
            age_label.config(text=age_text)
        except Exception:
            try:
                editor_lastmatch_text.insert('1.0', '' if lm_value is None else str(lm_value))
            except Exception:
                pass
        finally:
            try:
                editor_lastmatch_text.config(state='disabled')
            except Exception:
                pass

    def _looks_like_json_candidate(s):
        """
        Quick check if a string might be JSON (starts with {, [, or ").
        
        Args:
            s: String to check
        
        Returns:
            bool: True if string looks like it could be JSON
        """
        try:
            if not s or not isinstance(s, str):
                return False
            ss = s.strip()
            return ss.startswith('{') or ss.startswith('[') or ss.startswith('"')
        except Exception:
            return False

    def validate_lastmatch_json(event=None):
        """
        Validates JSON in the lastMatch text field and updates status label.
        
        Args:
            event: Optional Tkinter event (for event binding)
        
        Returns:
            bool: True if JSON is valid or field is empty/non-JSON, False if invalid JSON
        """
        try:
            txt = editor_lastmatch_text.get('1.0', 'end').strip()
            lastmatch_status_label.config(text='', fg='green')
            if not txt:
                return True
            if not _looks_like_json_candidate(txt):
                return True
            try:
                json.loads(txt)
                lastmatch_status_label.config(text='Valid JSON', fg='green')
                return True
            except Exception as e:
                msg = f'Invalid JSON: {str(e)}'
                short = msg if len(msg) < 120 else msg[:116] + '...'
                lastmatch_status_label.config(text=short, fg='red')
                return False
        except Exception:
            try:
                lastmatch_status_label.config(text='Invalid JSON', fg='red')
            except Exception:
                pass
            return False

    try:
        editor_lastmatch_text.bind('<KeyRelease>', lambda e: validate_lastmatch_json())
        editor_lastmatch_text.bind('<FocusOut>', lambda e: validate_lastmatch_json())
    except Exception:
        pass

    try:
        def _on_time24_changed(*a):
            try:
                config.set_pref('time_24', bool(time_24_var.get()))
            except Exception:
                pass
        try:
            time_24_var.trace_add('write', lambda *a: _on_time24_changed())
        except Exception:
            try:
                time_24_var.trace('w', lambda *a: _on_time24_changed())
            except Exception:
                pass
    except Exception:
        pass

    def _apply_editor_changes(silent=False):
        """
        Applies changes from the editor panel to the selected listbox item.
        
        Updates the selected title's configuration with values from the editor
        fields and refreshes the display.
        
        Args:
            silent: If True, don't show success message or validation dialogs
        """
        try:
            sel = treeview.curselection()
            if not sel:
                if not silent:
                    messagebox.showwarning('Edit', 'No title selected.')
                return False
            idx = int(sel[0])
            mapped = listbox_items[idx]
            title_text, entry = mapped[0], mapped[1]
        except Exception:
            if not silent:
                messagebox.showerror('Edit', 'Failed to locate selected item.')
            return False

        new_title = editor_rule_name.get().strip()
        new_must = editor_must.get().strip()
        new_save = editor_savepath.get().strip()
        new_cat = editor_category.get().strip()
        new_en = bool(editor_enabled.get())
        try:
            new_lastmatch = editor_lastmatch_text.get('1.0', 'end').strip()
        except Exception:
            new_lastmatch = ''

        if not new_title:
            if not silent:
                messagebox.showerror('Validation Error', 'Title cannot be empty.')
            return False
        try:
            if new_save and len(new_save) > 260:
                if not silent and not messagebox.askyesno('Validation Warning', 'Save Path is unusually long. Do you want to continue?'):
                    return False
        except Exception:
            pass

        # Check if anything actually changed
        try:
            old_title = title_text
            old_must = entry.get('mustContain', '') if isinstance(entry, dict) else ''
            old_save = entry.get('savePath', '') if isinstance(entry, dict) else ''
            old_cat = entry.get('assignedCategory', '') if isinstance(entry, dict) else ''
            old_en = entry.get('enabled', True) if isinstance(entry, dict) else True
            
            # If nothing changed, don't save undo or apply
            if (new_title == old_title and 
                new_must == old_must and 
                new_save == old_save and 
                new_cat == old_cat and 
                new_en == old_en):
                return True  # No changes, but not an error
        except Exception:
            pass  # If we can't check, proceed with save

        try:
            # Save undo state before applying changes (only if there are actual changes)
            _save_undo_state()
            
            if not isinstance(entry, dict):
                entry = {'node': {'title': title_text}}
            entry['mustContain'] = new_must or new_title
            entry['savePath'] = new_save
            entry['assignedCategory'] = new_cat
            entry['enabled'] = new_en
            
            # Sync category and save path to torrentParams
            if 'torrentParams' not in entry:
                entry['torrentParams'] = {}
            if not isinstance(entry['torrentParams'], dict):
                entry['torrentParams'] = {}
            entry['torrentParams']['category'] = new_cat
            # Also sync save_path to torrentParams (qBittorrent uses this field)
            entry['torrentParams']['save_path'] = new_save
            
            try:
                lm_val = ''
                if new_lastmatch:
                    s = new_lastmatch.strip()
                    if s.startswith('{') or s.startswith('[') or s.startswith('"'):
                        try:
                            lm_val = json.loads(new_lastmatch)
                        except Exception as e:
                            if not silent:
                                try:
                                    if not messagebox.askyesno('Invalid JSON', f'Last Match appears to be JSON but is invalid:\n{e}\n\nApply as raw text anyway?'):
                                        return False
                                except Exception:
                                    return False
                            lm_val = new_lastmatch
                    else:
                        lm_val = new_lastmatch
                entry['lastMatch'] = lm_val
            except Exception:
                try:
                    entry['lastMatch'] = new_lastmatch
                except Exception:
                    pass
            node = entry.get('node') or {}
            node['title'] = new_title
            entry['node'] = node
            
            # Update listbox_items with the modified entry
            listbox_items[idx] = (new_title, entry)
            logger.debug(f"Updated listbox_items[{idx}], entry id: {id(entry)}, mustContain: {entry.get('mustContain')}")
            
            # Update in config.ALL_TITLES - search by the CURRENT title in listbox_items
            try:
                if getattr(config, 'ALL_TITLES', None):
                    updated = False
                    for k, lst in (config.ALL_TITLES.items() if isinstance(config.ALL_TITLES, dict) else []):
                        if not isinstance(lst, list):
                            continue
                        for i, it in enumerate(lst):
                            try:
                                candidate_title = get_display_title(it) if isinstance(it, dict) else str(it)
                            except Exception:
                                candidate_title = str(it)
                            # Match by old title OR by object identity OR by new title
                            if candidate_title == title_text or it is entry or candidate_title == new_title:
                                logger.debug(f"BEFORE: ALL_TITLES[{k}][{i}] id: {id(it)}, mustContain: {it.get('mustContain')}")
                                logger.debug(f"Match condition: title={candidate_title==title_text}, identity={it is entry}, new_title={candidate_title==new_title}")
                                config.ALL_TITLES[k][i] = entry
                                updated = True
                                logger.debug(f"AFTER: Updated ALL_TITLES[{k}][{i}] with entry id: {id(entry)}, mustContain: {entry.get('mustContain')}")
                                break
                        if updated:
                            break
                    if not updated:
                        logger.warning(f"Failed to find entry to update in ALL_TITLES for title: {title_text}")
            except Exception as e:
                logger.error(f"Error updating ALL_TITLES: {e}", exc_info=True)
            
            # Only update treeview if title changed (to update display), otherwise just update the values in place
            title_changed = (title_text != new_title)
            if title_changed:
                try:
                    # Update treeview - this rebuilds listbox_items from ALL_TITLES
                    update_treeview_with_titles(config.ALL_TITLES)
                    treeview.selection_set(idx)
                    treeview.see(idx)
                except Exception:
                    pass
            else:
                # Title didn't change, just update the treeview values without rebuilding
                try:
                    # Get the treeview item for this index
                    items = treeview.get_children()
                    if idx < len(items):
                        item_id = items[idx]
                        # Update the treeview item values directly
                        enabled_mark = '✓' if entry.get('enabled', True) else ''
                        category = entry.get('assignedCategory') or entry.get('category') or ''
                        save_path = entry.get('savePath') or entry.get('save_path') or ''
                        if not save_path:
                            tp = entry.get('torrentParams') or entry.get('torrent_params') or {}
                            save_path = tp.get('save_path') or tp.get('savePath') or ''
                        save_path = str(save_path).replace('\\', '/') if save_path else ''
                        treeview.item(item_id, values=(enabled_mark, str(idx+1), new_title, category, save_path))
                except Exception as e:
                    logger.error(f"Error updating treeview item: {e}")
            
            # Don't auto-refresh during silent apply to avoid recursion
            if not silent:
                # Auto-refresh the editor to show updated values
                try:
                    _populate_editor_from_selection()
                except Exception:
                    pass
                status_var.set('Changes auto-applied')
            
            return True
        except Exception as e:
            if not silent:
                messagebox.showerror('Edit Error', f'Failed to apply changes: {e}')
            return False
    
    # Auto-apply when fields change (debounced)
    auto_apply_after_id = {'id': None}
    
    def _schedule_auto_apply(*args):
        """Schedules auto-apply after a short delay (debouncing)."""
        try:
            # Cancel previous scheduled apply
            if auto_apply_after_id['id']:
                root.after_cancel(auto_apply_after_id['id'])
            
            # Schedule new apply after 300ms of no changes (fast response)
            auto_apply_after_id['id'] = root.after(300, lambda: _apply_editor_changes(silent=True))
        except Exception:
            pass
    
    # Attach auto-apply to editor fields
    try:
        editor_rule_name.trace_add('write', _schedule_auto_apply)
        editor_must.trace_add('write', _schedule_auto_apply)
        editor_savepath.trace_add('write', _schedule_auto_apply)
        editor_category.trace_add('write', _schedule_auto_apply)
        editor_enabled.trace_add('write', _schedule_auto_apply)
    except Exception:
        # Fallback for older Python/Tkinter versions
        try:
            editor_rule_name.trace('w', _schedule_auto_apply)
            editor_must.trace('w', _schedule_auto_apply)
            editor_savepath.trace('w', _schedule_auto_apply)
            editor_category.trace('w', _schedule_auto_apply)
            editor_enabled.trace('w', _schedule_auto_apply)
        except Exception:
            pass

    def open_full_rule_editor_for_selection():
        """
        Opens the full rule editor dialog for the selected listbox item.
        """
        try:
            sel = treeview.curselection()
            if not sel:
                messagebox.showwarning('Edit', 'No title selected.')
                return
            idx = int(sel[0])
            title_text, entry = listbox_items[idx]
        except Exception:
            messagebox.showerror('Edit', 'Failed to locate selected item.')
            return
        open_full_rule_editor(root, title_text, entry, idx, _populate_editor_from_selection)

    ttk.Button(btns, text='🔧 Advanced Settings...', command=open_full_rule_editor_for_selection, style='Secondary.TButton', width=25).pack(fill='x', pady=(0, 5))

    try:
        treeview.bind('<<TreeviewSelect>>', _populate_editor_from_selection)
        try:
            def _on_item_double_click(event):
                """Open editor only if not clicking on separator"""
                try:
                    region = treeview.identify_region(event.x, event.y)
                    if region != "separator":
                        open_full_rule_editor_for_selection()
                except Exception:
                    pass
            treeview.bind('<Double-1>', _on_item_double_click)
        except Exception:
            pass
    except Exception:
        pass
    
    return (editor_rule_name, editor_must, editor_savepath, editor_category, 
            editor_enabled, editor_lastmatch_text)


# Public API
__all__ = [
    'setup_window_and_styles',
    'setup_status_and_autoconnect',
    'setup_menu_bar',
    'setup_keyboard_shortcuts',
    'setup_season_controls',
    'setup_library_panel',
    'setup_editor_panel',
    'setup_gui',
    'exit_handler',
]
