"""
Dialog windows for the application.

Contains settings dialog, import/export dialogs, and other modal windows.
"""
# Standard library imports
import json
import logging
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

# Local application imports
import src.qbittorrent_api as qbt_api
from src.config import config
from src.gui.app_state import AppState
from src.gui.file_operations import import_titles_from_file, update_treeview_with_titles
from src.gui.helpers import center_window

logger = logging.getLogger(__name__)


def open_settings_window(root: tk.Tk, status_var: tk.StringVar) -> None:
    """
    Opens the settings dialog window for qBittorrent connection configuration.
    
    Creates a modal dialog allowing users to configure qBittorrent WebUI connection
    parameters including host, port, credentials, and SSL settings.
    
    Args:
        root: Parent Tkinter window
        status_var: Status bar variable for displaying connection status
    """
    settings_win = tk.Toplevel(root)
    settings_win.title("⚙️ Settings - Configuration")
    
    # Try to fit full settings on screen
    from src.constants import UIConfig
    screen_height = root.winfo_screenheight()
    optimal_height = min(900, screen_height - 100)  # Leave 100px for taskbar
    settings_win.geometry(f"{UIConfig.SETTINGS_WINDOW_WIDTH}x{optimal_height}")
    settings_win.minsize(UIConfig.SETTINGS_WINDOW_WIDTH, UIConfig.SETTINGS_WINDOW_MIN_HEIGHT)
    settings_win.transient(root)
    settings_win.grab_set()
    settings_win.configure(bg='#f5f5f5')

    # Initialize StringVars with config values
    qbt_protocol_temp = tk.StringVar(value=config.QBT_PROTOCOL or 'http')
    qbt_host_temp = tk.StringVar(value=config.QBT_HOST or 'localhost')
    qbt_port_temp = tk.StringVar(value=config.QBT_PORT or '8080')
    qbt_user_temp = tk.StringVar(value=config.QBT_USER or '')
    qbt_pass_temp = tk.StringVar(value=config.QBT_PASS or '')
    mode_temp = tk.StringVar(value=config.CONNECTION_MODE or 'online')
    verify_ssl_temp = tk.BooleanVar(value=bool(config.QBT_VERIFY_SSL))
    ca_cert_temp = tk.StringVar(value=config.QBT_CA_CERT or '')
    default_save_path_temp = tk.StringVar(value=config.DEFAULT_SAVE_PATH or '')
    default_category_temp = tk.StringVar(value=config.DEFAULT_CATEGORY or '')
    default_affected_feeds_temp = tk.StringVar(value=', '.join(config.DEFAULT_AFFECTED_FEEDS) if config.DEFAULT_AFFECTED_FEEDS else '')

    def save_and_close():
        """Saves connection settings and closes the settings dialog."""
        # Get and validate inputs
        new_qbt_host = qbt_host_temp.get().strip()
        new_qbt_port = qbt_port_temp.get().strip()
        
        if not new_qbt_host or not new_qbt_port:
            messagebox.showwarning("Warning", "Host and Port are required.")
            return

        # Parse feeds
        feeds_str = default_affected_feeds_temp.get().strip()
        new_default_affected_feeds = [f.strip() for f in feeds_str.split(',') if f.strip()] if feeds_str else []

        # Update config
        config.QBT_CA_CERT = ca_cert_temp.get().strip() or None
        config.DEFAULT_DOWNLOAD_PATH = default_download_path_temp.get().strip()
        
        # Save to file
        config.save_config(
            qbt_protocol_temp.get().strip(),
            new_qbt_host,
            new_qbt_port,
            qbt_user_temp.get().strip(),
            qbt_pass_temp.get().strip(),
            mode_temp.get(),
            verify_ssl_temp.get(),
            default_save_path_temp.get().strip(),
            default_category_temp.get().strip(),
            new_default_affected_feeds
        )
        settings_win.destroy()

    # Create canvas with scrollbar for main content
    canvas_frame = ttk.Frame(settings_win)
    canvas_frame.pack(fill='both', expand=True, padx=0, pady=0)
    
    canvas = tk.Canvas(canvas_frame, bg='#f5f5f5', highlightthickness=0)
    scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
    main_container = ttk.Frame(canvas)
    
    def _update_settings_scrollregion(event=None):
        """Update canvas scroll region and show/hide scrollbar as needed."""
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Auto-hide scrollbar if content fits
            bbox = canvas.bbox("all")
            if bbox:
                content_height = bbox[3] - bbox[1]
                canvas_height = canvas.winfo_height()
                if content_height > canvas_height:
                    scrollbar.pack(side="right", fill="y")
                else:
                    scrollbar.pack_forget()
        except Exception:
            pass
    
    main_container.bind("<Configure>", _update_settings_scrollregion)
    
    canvas_window = canvas.create_window((0, 0), window=main_container, anchor="nw", width=680)
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Resize canvas window when canvas size changes
    def _on_canvas_configure(event):
        canvas.itemconfig(canvas_window, width=event.width - 5)
    canvas.bind('<Configure>', _on_canvas_configure)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Mouse wheel scrolling
    def _on_mousewheel(event):
        """Handle mouse wheel scrolling."""
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _bind_mousewheel(event):
        """Bind mouse wheel when entering canvas area."""
        canvas.bind("<MouseWheel>", _on_mousewheel)
    
    def _unbind_mousewheel(event):
        """Unbind mouse wheel when leaving canvas area."""
        canvas.unbind("<MouseWheel>")
    
    # Bind to both canvas and container for better coverage
    for widget in (canvas, main_container):
        widget.bind("<Enter>", _bind_mousewheel)
        widget.bind("<Leave>", _unbind_mousewheel)
    
    # Cleanup on close
    def _cleanup_settings():
        """Cleanup event bindings and close window."""
        for widget in (canvas, main_container):
            for event in ("<Enter>", "<Leave>", "<MouseWheel>"):
                try:
                    widget.unbind(event)
                except Exception:
                    pass
        settings_win.destroy()
    
    settings_win.protocol("WM_DELETE_WINDOW", _cleanup_settings)

    mode_frame = ttk.LabelFrame(main_container, text="🔌 Connection Mode", padding=12)
    mode_frame.pack(fill='x', pady=(0, 10), padx=10)
    
    ttk.Label(mode_frame, text="Select how the application connects to qBittorrent:", 
              font=('Segoe UI', 9)).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))
    ttk.Radiobutton(mode_frame, text="🌐 Online - Direct API connection", 
                    variable=mode_temp, value='online').grid(row=1, column=0, sticky='w', padx=5, pady=3)
    ttk.Radiobutton(mode_frame, text="📁 Offline - Generate JSON file only", 
                    variable=mode_temp, value='offline').grid(row=1, column=1, sticky='w', padx=5, pady=3)

    qbt_frame = ttk.LabelFrame(main_container, text="🔧 qBittorrent Web UI Configuration", padding=15)
    qbt_frame.pack(fill='x', pady=(0, 10), padx=10)
    
    # Grid configuration for better layout
    ttk.Label(qbt_frame, text="Protocol:", font=('Segoe UI', 9, 'bold')).grid(row=0, column=0, sticky='w', padx=5, pady=8)
    protocol_dropdown = ttk.Combobox(qbt_frame, textvariable=qbt_protocol_temp, values=['http', 'https'], state='readonly', width=10)
    protocol_dropdown.grid(row=0, column=1, sticky='w', padx=5, pady=8)

    ttk.Label(qbt_frame, text="Host:", font=('Segoe UI', 9, 'bold')).grid(row=0, column=2, sticky='w', padx=(20, 5), pady=8)
    ttk.Entry(qbt_frame, textvariable=qbt_host_temp, width=20).grid(row=0, column=3, sticky='w', padx=5, pady=8)

    ttk.Label(qbt_frame, text="Port:", font=('Segoe UI', 9, 'bold')).grid(row=1, column=0, sticky='w', padx=5, pady=8)
    ttk.Entry(qbt_frame, textvariable=qbt_port_temp, width=10).grid(row=1, column=1, sticky='w', padx=5, pady=8)

    ttk.Label(qbt_frame, text="Username:", font=('Segoe UI', 9, 'bold')).grid(row=1, column=2, sticky='w', padx=(20, 5), pady=8)
    ttk.Entry(qbt_frame, textvariable=qbt_user_temp, width=20).grid(row=1, column=3, sticky='w', padx=5, pady=8)

    ttk.Label(qbt_frame, text="Password:", font=('Segoe UI', 9, 'bold')).grid(row=2, column=0, sticky='w', padx=5, pady=8)
    ttk.Entry(qbt_frame, textvariable=qbt_pass_temp, show='●', width=20).grid(row=2, column=1, columnspan=3, sticky='w', padx=5, pady=8)

    ttk.Checkbutton(qbt_frame, text="🔒 Verify SSL Certificate (uncheck for self-signed)", 
                    variable=verify_ssl_temp).grid(row=3, column=0, columnspan=4, sticky='w', padx=5, pady=10)

    ttk.Label(qbt_frame, text="CA Certificate (optional):", font=('Segoe UI', 9, 'bold')).grid(row=4, column=0, columnspan=4, sticky='w', padx=5, pady=(10, 5))
    
    def browse_ca():
        """
        Opens file dialog to browse for CA certificate file.
        """
        path = filedialog.askopenfilename(title='Select CA certificate (PEM)', filetypes=[('PEM files','*.pem;*.crt;*.cer'), ('All files','*.*')])
        if path:
            ca_cert_temp.set(path)
    
    ca_entry = ttk.Entry(qbt_frame, textvariable=ca_cert_temp, width=50)
    ca_entry.grid(row=5, column=0, columnspan=3, sticky='ew', padx=5, pady=5)
    ttk.Button(qbt_frame, text='📁 Browse...', command=browse_ca).grid(row=5, column=3, sticky='w', padx=5, pady=5)
    
    qbt_frame.grid_columnconfigure(3, weight=1)
    
    # Status and test section - use grid for better control
    test_btn_frame = ttk.Frame(qbt_frame)
    test_btn_frame.grid(row=6, column=0, columnspan=4, sticky='ew', padx=5, pady=(15, 5))
    
    test_btn = ttk.Button(test_btn_frame, text="🔍 Test Connection", style='Accent.TButton')
    test_btn.pack(side='left', padx=5)
    
    # Status label with wrapping - separate row for full width
    status_frame = ttk.Frame(qbt_frame)
    status_frame.grid(row=7, column=0, columnspan=4, sticky='ew', padx=5, pady=(5, 5))
    
    settings_conn_status = tk.StringVar(value='⚪ Not tested')
    status_label = tk.Label(status_frame, textvariable=settings_conn_status, 
                           font=('Segoe UI', 9), anchor='w', justify='left',
                           wraplength=620, bg='#f5f5f5')
    status_label.pack(side='left', fill='both', expand=True, padx=5)
    
    ttk.Label(qbt_frame, text="💡 Tip: Ensure WebUI is enabled in qBittorrent settings",
              font=('Segoe UI', 8), foreground='#666').grid(row=8, column=0, columnspan=4, sticky='w', padx=5, pady=(5, 0))

    # Default Rule Settings Frame
    defaults_frame = ttk.LabelFrame(main_container, text="📝 Default Rule Settings", padding=15)
    defaults_frame.pack(fill='x', pady=(0, 10), padx=10)
    
    ttk.Label(defaults_frame, text="These defaults will be used when creating new rules:", 
              font=('Segoe UI', 9)).grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 10))
    
    # Default Category (moved above save path)
    ttk.Label(defaults_frame, text="Default Category:", font=('Segoe UI', 9, 'bold')).grid(row=1, column=0, sticky='w', padx=5, pady=8)
    
    # Create combobox for category selection from cache
    from tkinter import ttk as tkinter_ttk
    default_category_combo = tkinter_ttk.Combobox(defaults_frame, textvariable=default_category_temp, width=28)
    default_category_combo.grid(row=1, column=1, sticky='w', padx=5, pady=8)
    
    # Default Save Path (moved below category)
    ttk.Label(defaults_frame, text="Default Save Path:", font=('Segoe UI', 9, 'bold')).grid(row=2, column=0, sticky='w', padx=5, pady=8)
    default_save_path_entry = ttk.Entry(defaults_frame, textvariable=default_save_path_temp, width=50)
    default_save_path_entry.grid(row=2, column=1, columnspan=3, sticky='ew', padx=5, pady=8)
    
    # Default Download Path from qBittorrent
    default_download_path_temp = tk.StringVar(value=getattr(config, 'DEFAULT_DOWNLOAD_PATH', '') or "")
    
    ttk.Label(defaults_frame, text="qBittorrent Download Path:", font=('Segoe UI', 9, 'bold')).grid(row=3, column=0, sticky='w', padx=5, pady=8)
    default_download_path_entry = ttk.Entry(defaults_frame, textvariable=default_download_path_temp, width=50, state='readonly')
    default_download_path_entry.grid(row=3, column=1, columnspan=2, sticky='ew', padx=5, pady=8)
    ttk.Label(defaults_frame, text="💡 Used as base path for auto-generated save paths (Season/Title structure)",
              font=('Segoe UI', 8), foreground='#666').grid(row=4, column=0, columnspan=4, sticky='w', padx=5, pady=(0, 8))
    
    def fetch_download_path():
        """Fetch default download path from qBittorrent."""
        try:
            # Use current settings to connect
            from src.qbittorrent_api import QBittorrentClient
            api = QBittorrentClient(
                protocol=qbt_protocol_temp.get(),
                host=qbt_host_temp.get(),
                port=qbt_port_temp.get(),
                username=qbt_user_temp.get(),
                password=qbt_pass_temp.get(),
                verify_ssl=verify_ssl_temp.get(),
                ca_cert=ca_cert_temp.get().strip() or None
            )
            
            if api.connect():
                prefs = api.get_preferences()
                save_path = prefs.get('save_path', '')
                if save_path:
                    default_download_path_temp.set(save_path)
                    messagebox.showinfo('Success', f'Fetched default download path:\n{save_path}')
                else:
                    messagebox.showwarning('No Path', 'Could not retrieve default download path from qBittorrent.')
                api.close()
            else:
                messagebox.showerror('Connection Failed', 'Could not connect to qBittorrent.')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to fetch download path:\n{e}')
    
    ttk.Button(defaults_frame, text='🔄 Fetch from qBittorrent', command=fetch_download_path).grid(row=3, column=3, sticky='w', padx=5, pady=8)
    
    # Load cached categories into combobox
    def _update_category_combobox():
        try:
            config.load_cached_categories()
            cats = getattr(config, 'CACHED_CATEGORIES', {}) or {}
            if isinstance(cats, dict):
                category_names = list(cats.keys())
            elif isinstance(cats, list):
                category_names = cats
            else:
                category_names = []
            default_category_combo['values'] = [''] + sorted(category_names)  # Empty option first
        except Exception as e:
            logger.error(f"Error loading categories for combobox: {e}")
            default_category_combo['values'] = ['']
    
    # Initial load
    _update_category_combobox()
    
    # Auto-fill save path when category is selected
    def _on_category_selected(event=None):
        try:
            selected_cat = default_category_temp.get().strip()
            if selected_cat:
                cats = getattr(config, 'CACHED_CATEGORIES', {}) or {}
                if isinstance(cats, dict) and selected_cat in cats:
                    cat_data = cats[selected_cat]
                    # Handle both string save paths and dict with 'savePath' key
                    if isinstance(cat_data, dict):
                        save_path = cat_data.get('savePath', '')
                    else:
                        save_path = str(cat_data)
                    default_save_path_temp.set(save_path)
                    logger.debug(f"Auto-filled save path from category '{selected_cat}': {save_path}")
        except Exception as e:
            logger.error(f"Error auto-filling save path: {e}")
    
    default_category_combo.bind('<<ComboboxSelected>>', _on_category_selected)
    
    # Default Affected Feeds - with listbox for cached feeds
    ttk.Label(defaults_frame, text="Default Affected Feeds:", font=('Segoe UI', 9, 'bold')).grid(row=5, column=0, sticky='nw', padx=5, pady=8)
    
    # Create frame for feeds listbox and buttons
    feeds_container = ttk.Frame(defaults_frame)
    feeds_container.grid(row=5, column=1, columnspan=3, sticky='ew', padx=5, pady=8)
    
    # Manual entry field
    manual_feed_entry_frame = ttk.Frame(feeds_container)
    manual_feed_entry_frame.pack(fill='x', pady=(0, 5))
    
    ttk.Label(manual_feed_entry_frame, text="Manual Entry:", font=('Segoe UI', 8)).pack(side='left', padx=(0, 5))
    default_feeds_entry = ttk.Entry(manual_feed_entry_frame, textvariable=default_affected_feeds_temp, width=45)
    default_feeds_entry.pack(side='left', fill='x', expand=True)
    
    # Listbox for cached feeds
    feeds_list_frame = ttk.LabelFrame(feeds_container, text="Cached Feeds (click to add)", padding=5)
    feeds_list_frame.pack(fill='both', expand=True)
    
    # Create inner frame for listbox and scrollbar
    feeds_inner_frame = ttk.Frame(feeds_list_frame)
    feeds_inner_frame.pack(fill='both', expand=True)
    
    feeds_listbox = tk.Listbox(feeds_inner_frame, height=4, font=('Segoe UI', 9),
                               bg='#ffffff', fg='#333333',
                               selectbackground='#0078D4', selectforeground='#ffffff',
                               highlightthickness=0, bd=0, relief='flat')
    feeds_listbox.pack(side='left', fill='both', expand=True)
    
    feeds_scroll = ttk.Scrollbar(feeds_inner_frame, orient='vertical', command=feeds_listbox.yview)
    feeds_scroll.pack(side='right', fill='y')
    feeds_listbox.configure(yscrollcommand=feeds_scroll.set)
    
    # Prevent feeds listbox scroll from affecting main canvas
    def _on_feeds_mousewheel(event):
        try:
            feeds_listbox.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        except Exception:
            pass
    
    feeds_listbox.bind("<MouseWheel>", _on_feeds_mousewheel)
    
    # Load cached feeds into listbox
    def _load_cached_feeds_into_listbox():
        """Load cached RSS feeds from config and populate listbox."""
        try:
            config.load_cached_feeds()
            feeds = getattr(config, 'CACHED_FEEDS', {}) or {}
            feeds_listbox.delete(0, 'end')
            
            # Extract feed URLs from the feeds structure
            feed_urls = set()  # Use set to automatically handle duplicates
            
            def extract_urls(obj):
                """Recursively extract URLs from nested feed structure."""
                if isinstance(obj, dict):
                    # Check for 'url' key
                    if 'url' in obj and obj['url'] and isinstance(obj['url'], str):
                        feed_urls.add(obj['url'].strip())
                    # Recurse into all values
                    for value in obj.values():
                        extract_urls(value)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_urls(item)
            
            extract_urls(feeds)
            
            # Add sorted URLs to listbox
            for url in sorted(feed_urls):
                feeds_listbox.insert('end', url)
                
            logger.debug(f"Loaded {len(feed_urls)} cached feed(s) into listbox")
        except Exception as e:
            logger.error(f"Error loading cached feeds into listbox: {e}")
    
    def _on_feed_select(event):
        """Add selected feed from listbox to manual entry field."""
        try:
            selection = feeds_listbox.curselection()
            if not selection:
                return
                
            selected_url = feeds_listbox.get(selection[0]).strip()
            current = default_affected_feeds_temp.get().strip()
            
            # Parse current feeds
            current_feeds = [f.strip() for f in current.split(',') if f.strip()] if current else []
            
            # Add if not already present
            if selected_url not in current_feeds:
                current_feeds.append(selected_url)
                default_affected_feeds_temp.set(', '.join(current_feeds))
                logger.debug(f"Added feed to defaults: {selected_url}")
        except Exception as e:
            logger.error(f"Error adding selected feed: {e}")
    
    feeds_listbox.bind('<<ListboxSelect>>', _on_feed_select)
    
    # Refresh button for feeds
    refresh_feeds_btn = ttk.Button(feeds_list_frame, text='🔄 Refresh', command=_load_cached_feeds_into_listbox)
    refresh_feeds_btn.pack(pady=(5, 0))
    
    # Initial load of cached feeds
    _load_cached_feeds_into_listbox()
    
    ttk.Label(defaults_frame, text="💡 Click feeds from cache to add them, or manually enter comma-separated URLs.",
              font=('Segoe UI', 8), foreground='#666').grid(row=6, column=0, columnspan=4, sticky='w', padx=5, pady=(5, 0))
    
    defaults_frame.grid_columnconfigure(1, weight=1)

    def _run_test_and_update():
        """Runs connection test in background thread and updates status."""
        def _worker():
            settings_conn_status.set('⏳ Testing connection...')
            try:
                ca_cert = ca_cert_temp.get().strip() or None
                ok, msg = qbt_api.ping_qbittorrent(
                    qbt_protocol_temp.get(),
                    qbt_host_temp.get(),
                    qbt_port_temp.get(),
                    qbt_user_temp.get(),
                    qbt_pass_temp.get(),
                    verify_ssl_temp.get(),
                    ca_cert
                )
                status_icon = '✅ Connected: ' if ok else '❌ Failed: '
                settings_conn_status.set(status_icon + msg)
            except Exception as e:
                settings_conn_status.set(f'❌ Error: {e}')
        
        threading.Thread(target=_worker, daemon=True).start()

    test_btn.configure(command=_run_test_and_update)

    try:
        cat_frame = ttk.LabelFrame(main_container, text='📂 Cached Categories', padding=10)
        cat_frame.pack(fill='both', expand=True, pady=(0, 10), padx=10)
        
        cat_listbox = tk.Listbox(cat_frame, height=5, font=('Segoe UI', 9),
                                 bg='#ffffff', fg='#333333',
                                 selectbackground='#0078D4', selectforeground='#ffffff',
                                 highlightthickness=0, bd=0, relief='flat')
        cat_listbox.pack(side='left', fill='both', expand=True, padx=(0, 5), pady=5)
        cat_scroll = ttk.Scrollbar(cat_frame, orient='vertical', command=cat_listbox.yview)
        cat_scroll.pack(side='left', fill='y', pady=5)
        cat_listbox.configure(yscrollcommand=cat_scroll.set)
        
        # Prevent category listbox scroll from affecting main canvas
        def _on_cat_mousewheel(event):
            """Handle mousewheel for category listbox."""
            cat_listbox.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"  # Prevent event propagation
        
        cat_listbox.bind("<MouseWheel>", _on_cat_mousewheel)

        def _load_cached_categories_into_listbox():
            """Load categories from cache into listbox and combobox."""
            config.load_cached_categories()
            cats = config.CACHED_CATEGORIES or {}
            cat_listbox.delete(0, 'end')
            
            # Extract category names
            if isinstance(cats, dict):
                keys = list(cats.keys())
            elif isinstance(cats, list):
                keys = cats
            else:
                keys = []
            
            # Populate listbox
            for k in keys:
                cat_listbox.insert('end', str(k))
            
            # Update combobox
            _update_category_combobox()

        def _clear_cached_categories():
            """Clear all cached categories after confirmation."""
            if messagebox.askyesno('Confirm', 'Clear cached categories? This cannot be undone.'):
                config.save_cached_categories({})
                _load_cached_categories_into_listbox()
                status_var.set('Cached categories cleared.')

        def _refresh_categories_from_server():
            """Refresh categories from qBittorrent server."""
            def _worker():
                settings_conn_status.set('⏳ Refreshing categories...')
                try:
                    ca_cert = ca_cert_temp.get().strip() or None
                    ok, data = qbt_api.fetch_categories(
                        qbt_protocol_temp.get(),
                        qbt_host_temp.get(),
                        qbt_port_temp.get(),
                        qbt_user_temp.get(),
                        qbt_pass_temp.get(),
                        verify_ssl_temp.get(),
                        ca_cert
                    )
                    
                    if ok:
                        config.save_cached_categories(data)
                        _load_cached_categories_into_listbox()
                        settings_conn_status.set('✅ Categories refreshed.')
                        status_var.set('Categories updated from server.')
                    else:
                        settings_conn_status.set(f'❌ Refresh failed: {data}')
                        status_var.set('Failed to refresh categories.')
                except Exception as e:
                    settings_conn_status.set(f'❌ Refresh error: {e}')
            
            threading.Thread(target=_worker, daemon=True).start()

        btns_frame = ttk.Frame(cat_frame)
        btns_frame.pack(side='left', fill='y', padx=(10, 0), pady=5)
        ttk.Button(btns_frame, text='🔄 Refresh', command=_refresh_categories_from_server, width=15).pack(fill='x', pady=(0, 5))
        ttk.Button(btns_frame, text='🗑️ Clear', command=_clear_cached_categories, width=15).pack(fill='x')
        _load_cached_categories_into_listbox()
    except Exception:
        pass

    try:
        feeds_frame = ttk.LabelFrame(main_container, text='📡 Cached RSS Feeds', padding=10)
        feeds_frame.pack(fill='both', expand=True, pady=(0, 10), padx=10)
        
        feeds_listbox = tk.Listbox(feeds_frame, height=5, font=('Segoe UI', 9),
                                   bg='#ffffff', fg='#333333',
                                   selectbackground='#0078D4', selectforeground='#ffffff',
                                   highlightthickness=0, bd=0, relief='flat')
        feeds_listbox.pack(side='left', fill='both', expand=True, padx=(0, 5), pady=5)
        feeds_scroll = ttk.Scrollbar(feeds_frame, orient='vertical', command=feeds_listbox.yview)
        feeds_scroll.pack(side='left', fill='y', pady=5)
        feeds_listbox.configure(yscrollcommand=feeds_scroll.set)
        
        # Prevent feeds listbox scroll from affecting main canvas
        def _on_feeds_mousewheel(event):
            try:
                feeds_listbox.yview_scroll(int(-1*(event.delta/120)), "units")
                return "break"  # Prevent event propagation
            except Exception:
                pass
        
        feeds_listbox.bind("<MouseWheel>", _on_feeds_mousewheel)

        def _load_cached_feeds_into_listbox():
            try:
                config.load_cached_feeds()
                f = getattr(config, 'CACHED_FEEDS', {}) or {}
                feeds_listbox.delete(0, 'end')
                if isinstance(f, dict):
                    if not f:
                        feeds_listbox.insert('end', '(No cached feeds - click Refresh to load)')
                    else:
                        for k, v in f.items():
                            if isinstance(v, dict) and v.get('url'):
                                feeds_listbox.insert('end', f"{k} -> {v.get('url')}")
                            else:
                                feeds_listbox.insert('end', str(k))
                elif isinstance(f, list):
                    if not f:
                        feeds_listbox.insert('end', '(No cached feeds - click Refresh to load)')
                    else:
                        for item in f:
                            if isinstance(item, dict) and item.get('url'):
                                feeds_listbox.insert('end', item.get('url'))
                            else:
                                feeds_listbox.insert('end', str(item))
                else:
                    feeds_listbox.insert('end', '(No cached feeds - click Refresh to load)')
            except Exception as e:
                feeds_listbox.delete(0, 'end')
                feeds_listbox.insert('end', f'(Error loading feeds: {e})')

        def _clear_cached_feeds():
            try:
                if not messagebox.askyesno('Confirm', 'Clear cached feeds? This cannot be undone.'):
                    return
                config.save_cached_feeds({})
                _load_cached_feeds_into_listbox()
                status_var.set('Cached feeds cleared.')
            except Exception:
                status_var.set('Failed to clear cached feeds.')

        def _refresh_feeds_from_server():
            def _worker():
                try:
                    settings_conn_status.set('Refreshing feeds...')
                    ok, data = qbt_api.fetch_feeds(qbt_protocol_temp.get(), qbt_host_temp.get(), qbt_port_temp.get(), qbt_user_temp.get(), qbt_pass_temp.get(), bool(verify_ssl_temp.get()), ca_cert_temp.get() if ca_cert_temp.get().strip() else None)
                    if ok:
                        try:
                            config.save_cached_feeds(data)
                        except Exception:
                            pass
                        settings_conn_status.set('Feeds refreshed.')
                        status_var.set('Feeds updated from server.')
                        _load_cached_feeds_into_listbox()
                    else:
                        settings_conn_status.set('Refresh failed: ' + str(data))
                        status_var.set('Failed to refresh feeds.')
                except Exception as e:
                    settings_conn_status.set('Refresh error: ' + str(e))
            try:
                threading.Thread(target=_worker, daemon=True).start()
            except Exception:
                settings_conn_status.set('Failed to start refresh thread')

        fbtns_frame = ttk.Frame(feeds_frame)
        fbtns_frame.pack(side='left', fill='y', padx=(10, 0), pady=5)
        ttk.Button(fbtns_frame, text='🔄 Refresh', command=_refresh_feeds_from_server, width=15).pack(fill='x', pady=(0, 5))
        ttk.Button(fbtns_frame, text='🗑️ Clear', command=_clear_cached_feeds, width=15).pack(fill='x')
        _load_cached_feeds_into_listbox()
    except Exception:
        pass

    # Import/Export Settings
    try:
        import_frame = ttk.LabelFrame(main_container, text='📥 Import/Export Settings', padding=10)
        import_frame.pack(fill='x', pady=(0, 10), padx=10)
        
        try:
            pref_prefix = config.get_pref('prefix_imports', True)
        except Exception:
            pref_prefix = True
        prefix_imports_setting_var = tk.BooleanVar(value=bool(pref_prefix))
        
        ttk.Checkbutton(import_frame, text='✓ Automatically prefix imported titles with Season/Year', 
                       variable=prefix_imports_setting_var,
                       command=lambda: config.set_pref('prefix_imports', bool(prefix_imports_setting_var.get()))).pack(anchor='w', pady=5)
        
        try:
            pref_auto_sanitize = config.get_pref('auto_sanitize_imports', True)
        except Exception:
            pref_auto_sanitize = True
        auto_sanitize_var = tk.BooleanVar(value=bool(pref_auto_sanitize))
        
        ttk.Checkbutton(import_frame, text='✓ Automatically sanitize titles with invalid folder names',
                       variable=auto_sanitize_var,
                       command=lambda: config.set_pref('auto_sanitize_imports', bool(auto_sanitize_var.get()))).pack(anchor='w', pady=5)
    except Exception:
        pass

    # Time Format Settings
    try:
        time_frame = ttk.LabelFrame(main_container, text='🕐 Time Format', padding=10)
        time_frame.pack(fill='x', pady=(0, 10), padx=10)
        
        try:
            pref_time_24 = config.get_pref('time_24', True)
        except Exception:
            pref_time_24 = True
        time_format_var = tk.BooleanVar(value=bool(pref_time_24))
        
        ttk.Radiobutton(time_frame, text='24-hour format (default)', 
                       variable=time_format_var, value=True,
                       command=lambda: config.set_pref('time_24', True)).pack(anchor='w', pady=2)
        ttk.Radiobutton(time_frame, text='12-hour format (AM/PM)', 
                       variable=time_format_var, value=False,
                       command=lambda: config.set_pref('time_24', False)).pack(anchor='w', pady=2)
    except Exception:
        pass

    # Filesystem Type Settings
    try:
        fs_frame = ttk.LabelFrame(main_container, text='💾 Target Filesystem Type', padding=10)
        fs_frame.pack(fill='x', pady=(0, 10), padx=10)
        
        ttk.Label(fs_frame, text='Select the target filesystem for folder validation:', 
                  font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 8))
        
        try:
            pref_fs_type = config.get_pref('filesystem_type', 'linux')
        except Exception:
            pref_fs_type = 'linux'
        fs_type_var = tk.StringVar(value=pref_fs_type)
        
        ttk.Radiobutton(fs_frame, text='🐧 Linux/Unix/Unraid (default) - Only blocks forward slashes (/)', 
                       variable=fs_type_var, value='linux',
                       command=lambda: config.set_pref('filesystem_type', 'linux')).pack(anchor='w', pady=2)
        ttk.Radiobutton(fs_frame, text='🪟 Windows - Strict validation (colons, quotes, etc. not allowed)', 
                       variable=fs_type_var, value='windows',
                       command=lambda: config.set_pref('filesystem_type', 'windows')).pack(anchor='w', pady=2)
        
        ttk.Label(fs_frame, text='💡 This affects validation when syncing rules from qBittorrent', 
                  font=('Segoe UI', 8), foreground='#666').pack(anchor='w', pady=(8, 2))
        ttk.Label(fs_frame, text='⚠️ Note: Linux folders with colons (:) will appear without colons', 
                  font=('Segoe UI', 8), foreground='#d32f2f').pack(anchor='w', pady=(0, 0))
        ttk.Label(fs_frame, text='    when accessed from Windows via SMB shares', 
                  font=('Segoe UI', 8), foreground='#d32f2f').pack(anchor='w', pady=(0, 0))
        
        # Auto-sanitize option
        ttk.Separator(fs_frame, orient='horizontal').pack(fill='x', pady=(10, 10))
        
        try:
            pref_auto_sanitize = config.get_pref('auto_sanitize_paths', True)
        except Exception:
            pref_auto_sanitize = True
        auto_sanitize_var = tk.BooleanVar(value=bool(pref_auto_sanitize))
        
        ttk.Checkbutton(fs_frame, text='✨ Auto-sanitize invalid folder names when syncing', 
                       variable=auto_sanitize_var,
                       command=lambda: config.set_pref('auto_sanitize_paths', auto_sanitize_var.get())).pack(anchor='w', pady=2)
        ttk.Label(fs_frame, text='💡 Automatically fixes invalid characters in folder paths (e.g., "Title: Name" → "Title Name")', 
                  font=('Segoe UI', 8), foreground='#666').pack(anchor='w', pady=(2, 0))
    except Exception:
        pass

    # Footer with buttons - outside scrollable area
    footer_frame = ttk.Frame(settings_win, padding=10)
    footer_frame.pack(fill='x', side='bottom')
    
    save_btn = ttk.Button(footer_frame, text="💾 Save & Close", command=save_and_close, style='Accent.TButton', width=20)
    save_btn.pack(side='right', padx=5)
    
    cancel_btn = ttk.Button(footer_frame, text="✕ Cancel", command=settings_win.destroy, width=15)
    cancel_btn.pack(side='right')


def open_log_viewer(root: tk.Tk) -> None:
    """
    Opens a window displaying the application log file.
    
    Shows the last 500 lines of the log file with auto-refresh capability
    and buttons to clear or open the full log file.
    
    Args:
        root: Parent Tkinter window
    """
    log_window = tk.Toplevel(root)
    log_window.title('Application Log Viewer')
    log_window.geometry('900x600')
    log_window.transient(root)
    
    # Create toolbar
    toolbar = ttk.Frame(log_window)
    toolbar.pack(side='top', fill='x', padx=5, pady=5)
    
    # Log level filter
    ttk.Label(toolbar, text='Filter:').pack(side='left', padx=5)
    filter_var = tk.StringVar(value='ALL')
    filter_combo = ttk.Combobox(toolbar, textvariable=filter_var, 
                                 values=['ALL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
                                 state='readonly', width=10)
    filter_combo.pack(side='left', padx=5)
    
    # Create text widget with scrollbar
    text_frame = ttk.Frame(log_window)
    text_frame.pack(fill='both', expand=True, padx=5, pady=5)
    
    log_text = tk.Text(text_frame, wrap='word', height=30, width=100)
    log_text.pack(side='left', fill='both', expand=True)
    
    scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=log_text.yview)
    scrollbar.pack(side='right', fill='y')
    log_text.configure(yscrollcommand=scrollbar.set)
    
    # Configure text tags for color coding
    log_text.tag_configure('ERROR', foreground='red')
    log_text.tag_configure('WARNING', foreground='orange')
    log_text.tag_configure('INFO', foreground='blue')
    log_text.tag_configure('DEBUG', foreground='gray')
    
    def load_log_content():
        """Load and display log file content with filtering."""
        try:
            log_text.configure(state='normal')
            log_text.delete('1.0', 'end')
            
            if not os.path.exists('qbt_editor.log'):
                log_text.insert('1.0', 'No log file found. Start using the application to generate logs.')
                log_text.configure(state='disabled')
                return
            
            # Read last 500 lines
            with open('qbt_editor.log', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                lines = lines[-500:] if len(lines) > 500 else lines
            
            filter_level = filter_var.get()
            
            for line in lines:
                # Apply filter
                if filter_level != 'ALL':
                    if f' - {filter_level} - ' not in line:
                        continue
                
                # Color code by log level
                if ' - ERROR - ' in line:
                    log_text.insert('end', line, 'ERROR')
                elif ' - WARNING - ' in line:
                    log_text.insert('end', line, 'WARNING')
                elif ' - INFO - ' in line:
                    log_text.insert('end', line, 'INFO')
                elif ' - DEBUG - ' in line:
                    log_text.insert('end', line, 'DEBUG')
                else:
                    log_text.insert('end', line)
            
            # Scroll to bottom
            log_text.see('end')
            log_text.configure(state='disabled')
            
        except Exception as e:
            log_text.insert('1.0', f'Error loading log file: {e}')
            log_text.configure(state='disabled')
    
    def refresh_log():
        """Refresh the log display."""
        load_log_content()
    
    def clear_log():
        """Clear the log file after confirmation."""
        if messagebox.askyesno('Clear Log', 'Are you sure you want to clear the log file?'):
            try:
                with open('qbt_editor.log', 'w', encoding='utf-8') as f:
                    f.write('')
                logger.info('Log file cleared by user')
                load_log_content()
                messagebox.showinfo('Success', 'Log file cleared successfully')
            except Exception as e:
                messagebox.showerror('Error', f'Failed to clear log: {e}')
    
    def open_log_file():
        """Open the log file in the default text editor."""
        try:
            if os.path.exists('qbt_editor.log'):
                if sys.platform == 'win32':
                    os.startfile('qbt_editor.log')
                elif sys.platform == 'darwin':
                    os.system('open qbt_editor.log')
                else:
                    os.system('xdg-open qbt_editor.log')
            else:
                messagebox.showwarning('Not Found', 'Log file does not exist yet.')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to open log file: {e}')
    
    # Buttons
    button_frame = ttk.Frame(log_window)
    button_frame.pack(side='bottom', fill='x', padx=5, pady=5)
    
    ttk.Button(button_frame, text='Refresh', command=refresh_log).pack(side='left', padx=5)
    ttk.Button(button_frame, text='Clear Log', command=clear_log).pack(side='left', padx=5)
    ttk.Button(button_frame, text='Open in Editor', command=open_log_file).pack(side='left', padx=5)
    ttk.Button(button_frame, text='Close', command=log_window.destroy).pack(side='right', padx=5)
    
    # Bind filter change
    filter_combo.bind('<<ComboboxSelected>>', lambda e: load_log_content())
    
    # Initial load
    load_log_content()


def view_trash_dialog(parent: tk.Tk) -> None:
    """
    Opens a dialog showing all deleted items in the trash.
    
    Args:
        parent: Parent Tkinter window
    """
    app_state = AppState.get_instance()
    trash_items = app_state.trash_items
    
    try:
        dlg = tk.Toplevel(parent)
        dlg.title('Trash')
        dlg.transient(parent)
        dlg.grab_set()

        lb = tk.Listbox(dlg, height=12, width=80)
        lb.pack(fill='both', expand=True, padx=10, pady=10)

        def refresh():
            try:
                lb.delete(0, 'end')
            except Exception:
                pass
            for it in trash_items:
                try:
                    lb.insert('end', f"{it.get('src')} - {it.get('title')}")
                except Exception:
                    pass

        def _restore_selected():
            try:
                sel = lb.curselection()
                if not sel:
                    messagebox.showwarning('Restore', 'No trash item selected.')
                    return
                restored_count = 0
                for i in sorted([int(x) for x in sel], reverse=True):
                    try:
                        item = trash_items.pop(i)
                    except Exception:
                        continue
                    if item.get('src') == 'titles':
                        title_text = item.get('title')
                        entry = item.get('entry')
                        try:
                            # Add back to listbox_items
                            app_state.listbox_items.append((title_text, entry))
                            
                            # Add back to config.ALL_TITLES
                            import src.config as config
                            if not hasattr(config, 'ALL_TITLES') or not isinstance(config.ALL_TITLES, dict):
                                config.ALL_TITLES = {}
                            if 'existing' not in config.ALL_TITLES:
                                config.ALL_TITLES['existing'] = []
                            config.ALL_TITLES['existing'].append(entry)
                            
                            restored_count += 1
                        except Exception:
                            pass
                
                # Refresh treeview to show restored items
                if restored_count > 0:
                    update_treeview_with_titles(config.ALL_TITLES)
                
                refresh()
                messagebox.showinfo('Restore', f'Restored {restored_count} item(s) to Titles.')
            except Exception as e:
                messagebox.showerror('Restore Error', f'Failed to restore: {e}')

        def _delete_permanent():
            try:
                sel = lb.curselection()
                if not sel:
                    messagebox.showwarning('Delete', 'No trash item selected.')
                    return
                if not messagebox.askyesno('Permanently Delete', f'Delete {len(sel)} item(s) permanently?'):
                    return
                for i in sorted([int(x) for x in sel], reverse=True):
                    try:
                        trash_items.pop(i)
                    except Exception:
                        pass
                refresh()
            except Exception as e:
                messagebox.showerror('Delete Error', f'Failed to permanently delete: {e}')

        def _empty_trash():
            try:
                if not trash_items:
                    return
                if not messagebox.askyesno('Empty Trash', 'Empty the trash permanently?'):
                    return
                trash_items.clear()
                refresh()
            except Exception as e:
                messagebox.showerror('Trash Error', f'Failed to empty trash: {e}')

        btns = ttk.Frame(dlg)
        btns.pack(fill='x', padx=10, pady=(0,10))
        ttk.Button(btns, text='Restore Selected', command=_restore_selected).pack(side='left')
        ttk.Button(btns, text='Delete Permanently', command=_delete_permanent).pack(side='left', padx=6)
        ttk.Button(btns, text='Empty Trash', command=_empty_trash).pack(side='right')

        refresh()
    except Exception:
        pass


def open_full_rule_editor(root: tk.Tk, title_text: str, entry: Dict[str, Any], idx: int, 
                          populate_editor_callback: Optional[callable] = None) -> None:
    """
    Opens a comprehensive editor dialog for all rule settings.
    
    Args:
        root: Parent Tkinter window
        title_text: Display name of the title being edited
        entry: Rule entry dictionary containing all configuration
        idx: Index of the item in listbox_items
        populate_editor_callback: Optional callback to refresh main editor after save
    """
    app_state = AppState.get_instance()
    listbox_items = app_state.listbox_items
    treeview_widget = app_state.treeview_widget
    
    dlg = tk.Toplevel(root)
    dlg.title(f'🔧 Advanced Rule Editor - {title_text}')
    
    # Auto-size to monitor height (use 85% of screen height), increased width to 1000px
    try:
        screen_height = dlg.winfo_screenheight()
        dialog_height = int(screen_height * 0.85)
        dialog_height = max(600, min(dialog_height, screen_height - 100))
        dlg.geometry(f'1000x{dialog_height}')
    except Exception:
        dlg.geometry('1000x700')
    
    dlg.transient(root)
    dlg.grab_set()
    dlg.configure(bg='#f5f5f5')

    def safe_get(d, *keys, default=''):
        try:
            v = d
            for k in keys:
                v = v.get(k) if isinstance(v, dict) else None
            return v if v is not None else default
        except Exception:
            return default

    def _get_field(k, default=''):
        try:
            if not isinstance(entry, dict):
                return default
            v = entry.get(k)
            return default if v is None else v
        except Exception:
            return default

    addPaused_val = _get_field('addPaused', None)
    if addPaused_val is None:
        addPaused_str = 'None'
    else:
        addPaused_str = 'True' if addPaused_val else 'False'
    addPaused_var = tk.StringVar(value=addPaused_str)
    assigned_var = tk.StringVar(value=_get_field('assignedCategory', ''))
    enabled_var = tk.BooleanVar(value=bool(_get_field('enabled', True)))
    episode_var = tk.StringVar(value=_get_field('episodeFilter', ''))
    ignore_var = tk.StringVar(value=str(_get_field('ignoreDays', 0)))
    lastmatch_var = tk.StringVar(value=_get_field('lastMatch', ''))
    must_var = tk.StringVar(value=_get_field('mustContain', title_text))
    mustnot_var = tk.StringVar(value=_get_field('mustNotContain', ''))
    priority_var = tk.StringVar(value=str(_get_field('priority', 0)))
    rule_title_var = tk.StringVar(value=title_text)

    smart_var = tk.BooleanVar(value=bool(_get_field('smartFilter', False)))
    tcl_val = _get_field('torrentContentLayout', '')
    tcl_var = tk.StringVar(value='' if tcl_val is None else tcl_val)
    useregex_var = tk.BooleanVar(value=bool(_get_field('useRegex', False)))

    tp = entry.get('torrentParams') if (isinstance(entry, dict) and entry.get('torrentParams') is not None) else {}
    try:
        sp_val = _get_field('savePath', '') or _get_field('save_path', '')
        if not sp_val and isinstance(tp, dict):
            sp_val = tp.get('save_path') or tp.get('download_path') or ''
        sp_disp = '' if sp_val is None else str(sp_val).replace('/', '\\')
    except Exception:
        sp_disp = ''

    savepath_var = tk.StringVar(value=sp_disp)
    tp_category = tk.StringVar(value=tp.get('category', ''))
    tp_download_limit = tk.StringVar(value=str(tp.get('download_limit', -1)))
    tp_download_path = tk.StringVar(value=tp.get('download_path', ''))
    tp_inactive_limit = tk.StringVar(value=str(tp.get('inactive_seeding_time_limit', -2)))
    tp_operating_mode = tk.StringVar(value=tp.get('operating_mode', 'AutoManaged'))
    tp_ratio_limit = tk.StringVar(value=str(tp.get('ratio_limit', -2)))
    tp_save_path = tk.StringVar(value=tp.get('save_path', '').replace('/', '\\'))
    tp_seeding_time = tk.StringVar(value=str(tp.get('seeding_time_limit', -2)))
    tp_skip = tk.BooleanVar(value=bool(tp.get('skip_checking', False)))
    tp_tags = tk.StringVar(value=(','.join(tp.get('tags')) if isinstance(tp.get('tags'), list) else ''))
    tp_upload_limit = tk.StringVar(value=str(tp.get('upload_limit', -1)))
    tp_auto_tmm = tk.BooleanVar(value=bool(tp.get('use_auto_tmm', False)))

    # Create scrollable frame
    canvas = tk.Canvas(dlg, bg='#f5f5f5', highlightthickness=0)
    scrollbar = ttk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas, padding=20)
    
    def _update_scrollregion(event=None):
        try:
            if canvas.winfo_exists():
                canvas.configure(scrollregion=canvas.bbox("all"))
                # Show/hide scrollbar based on content size
                try:
                    bbox = canvas.bbox("all")
                    if bbox:
                        content_height = bbox[3] - bbox[1]
                        canvas_height = canvas.winfo_height()
                        if content_height > canvas_height:
                            scrollbar.pack(side="right", fill="y")
                        else:
                            scrollbar.pack_forget()
                except Exception:
                    pass
        except Exception:
            pass
    
    scrollable_frame.bind("<Configure>", _update_scrollregion)
    
    canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Update canvas window width when canvas resizes to eliminate right space
    def _on_canvas_resize(event):
        try:
            canvas.itemconfig(canvas_window, width=event.width)
        except Exception:
            pass
    canvas.bind('<Configure>', _on_canvas_resize)
    
    # Enable mousewheel scrolling when hovering - use widget-specific binding
    def _on_mousewheel(event):
        try:
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except Exception:
            pass
    
    def _bind_mousewheel(event):
        try:
            canvas.bind("<MouseWheel>", _on_mousewheel)
        except Exception:
            pass
    
    def _unbind_mousewheel(event):
        try:
            canvas.unbind("<MouseWheel>")
        except Exception:
            pass
    
    canvas.bind("<Enter>", _bind_mousewheel)
    canvas.bind("<Leave>", _unbind_mousewheel)
    scrollable_frame.bind("<Enter>", _bind_mousewheel)
    scrollable_frame.bind("<Leave>", _unbind_mousewheel)
    
    # Create footer frame FIRST (pack at bottom before canvas)
    footer = ttk.Frame(dlg, padding=10)
    footer.pack(side='bottom', fill='x', pady=(0, 0), padx=10)
    
    # Add separator above footer for visual distinction
    footer_separator = ttk.Separator(dlg, orient='horizontal')
    footer_separator.pack(side='bottom', fill='x', pady=(0, 0))
    
    # Pack canvas and scrollbar - using pack for main layout
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Cleanup on dialog close
    def _on_close():
        try:
            canvas.unbind("<Enter>")
            canvas.unbind("<Leave>")
            canvas.unbind("<MouseWheel>")
            scrollable_frame.unbind("<Enter>")
            scrollable_frame.unbind("<Leave>")
        except Exception:
            pass
        dlg.destroy()
    
    dlg.protocol("WM_DELETE_WINDOW", _on_close)
    
    row = 0
    frm = scrollable_frame
    
    # Configure column 1 to expand with window resize
    frm.columnconfigure(1, weight=1)

    def grid_label(r, text=''):
        ttk.Label(frm, text=text, font=('Segoe UI', 9, 'bold')).grid(row=r, column=0, sticky='w', padx=5, pady=4)

    affected_frame = ttk.Frame(frm)
    affected_listbox_frame = ttk.Frame(affected_frame)
    affected_listbox = tk.Listbox(affected_listbox_frame, height=5, font=('Consolas', 9),
                                   bg='#fafafa', relief='flat', bd=1, selectmode='extended',
                                   highlightthickness=1, highlightbackground='#e0e0e0')
    affected_scrollbar = ttk.Scrollbar(affected_listbox_frame, orient='vertical', command=affected_listbox.yview)
    affected_listbox.configure(yscrollcommand=affected_scrollbar.set)

    prevmatches_frame = ttk.Frame(frm)
    prevmatches_text = tk.Text(prevmatches_frame, height=3, width=50, font=('Consolas', 9),
                               bg='#fafafa', relief='flat', bd=1,
                               highlightthickness=1, highlightbackground='#e0e0e0')
    
    # Title section
    ttk.Label(frm, text='📌 Basic Information', font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(0, 10))
    row += 1

    grid_label(row, 'Rule Title:')
    ttk.Entry(frm, textvariable=rule_title_var, width=60, font=('Segoe UI', 9)).grid(row=row, column=1, sticky='ew', padx=5, pady=4)
    row += 1
    
    ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=15)
    row += 1
    
    ttk.Label(frm, text='⚙️ Rule Configuration', font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(0, 10))
    row += 1

    grid_label(row, 'Add Paused:')
    ttk.Combobox(frm, textvariable=addPaused_var, values=['None', 'False', 'True'], 
                 state='readonly', width=15, font=('Segoe UI', 9)).grid(row=row, column=1, sticky='w', padx=5, pady=4)
    row += 1

    def _validate_full_lastmatch(*a):
        try:
            txt = lastmatch_var.get().strip()
            if lastmatch_full_status_label is None:
                return True
            try:
                lastmatch_full_status_label.config(text='', fg='green')
            except Exception:
                pass
            if not txt:
                return True
            if not (txt.startswith('{') or txt.startswith('[') or txt.startswith('"')):
                return True
            try:
                json.loads(txt)
                try:
                    lastmatch_full_status_label.config(text='Valid JSON', fg='green')
                except Exception:
                    pass
                return True
            except Exception as e:
                try:
                    msg = f'Invalid JSON: {str(e)}'
                    short = msg if len(msg) < 120 else msg[:116] + '...'
                    lastmatch_full_status_label.config(text=short, fg='red')
                except Exception:
                    pass
                return False
        except Exception:
            try:
                if lastmatch_full_status_label is not None:
                    lastmatch_full_status_label.config(text='Invalid JSON', fg='red')
            except Exception:
                pass
            return False

    try:
        lastmatch_var.trace_add('write', lambda *a: _validate_full_lastmatch())
    except Exception:
        try:
            lastmatch_var.trace('w', lambda *a: _validate_full_lastmatch())
        except Exception:
            pass

    grid_label(row, 'Affected Feeds:')
    row += 1
    
    # Place listbox and controls below the label in column 0-1 span
    affected_frame.grid(row=row, column=0, columnspan=2, sticky='ew', padx=5, pady=4)
    affected_frame.columnconfigure(0, weight=1)  # Make frame expand
    
    # Listbox frame with better height
    affected_listbox_frame.pack(side='top', fill='both', expand=False, pady=(0, 8))
    affected_listbox.pack(side='left', fill='both', expand=True)
    affected_scrollbar.pack(side='right', fill='y')
    
    # Set a reasonable height for the listbox
    affected_listbox.configure(height=6)
    
    try:
        af = entry.get('affectedFeeds') if isinstance(entry, dict) else []
        if isinstance(af, list):
            affected_listbox.delete(0, 'end')
            for feed in af:
                affected_listbox.insert('end', feed)
    except Exception:
        pass
    try:
        config.load_cached_feeds()
        cached_feeds = getattr(config, 'CACHED_FEEDS', {}) or {}
    except Exception:
        cached_feeds = {}
    try:
        feeds_choices = []
        if isinstance(cached_feeds, dict):
            for k, v in cached_feeds.items():
                if isinstance(v, dict) and v.get('url'):
                    feeds_choices.append(f"{k} -> {v.get('url')}")
                else:
                    feeds_choices.append(str(k))
        elif isinstance(cached_feeds, list):
            for it in cached_feeds:
                if isinstance(it, dict) and it.get('url'):
                    feeds_choices.append(it.get('url'))
                else:
                    feeds_choices.append(str(it))
        else:
            feeds_choices = []
    except Exception:
        feeds_choices = []
    try:
        # Control frame for add/delete buttons
        feeds_select_frame = ttk.Frame(affected_frame)
        feeds_select_frame.pack(side='top', fill='x', pady=(0, 8))
        
        ttk.Label(feeds_select_frame, text='Add from cached feeds:', font=('Segoe UI', 9)).pack(side='left', padx=(0, 5))
        
        feeds_combo = ttk.Combobox(feeds_select_frame, values=feeds_choices, state='readonly', width=50)
        feeds_combo.pack(side='left', padx=(0, 5))
        
        def _add_selected_feed():
            try:
                val = feeds_combo.get().strip()
                if not val:
                    return
                if '->' in val:
                    val = val.split('->',1)[1].strip()
                current_items = affected_listbox.get(0, 'end')
                if val not in current_items:
                    affected_listbox.insert('end', val)
                    feeds_combo.set('')  # Clear selection after adding
            except Exception:
                pass
        
        def _delete_selected_feeds():
            try:
                selected = affected_listbox.curselection()
                if not selected:
                    messagebox.showwarning('Remove Feed', 'Please select one or more feeds to remove from the list above.')
                    return
                for idx in reversed(selected):
                    affected_listbox.delete(idx)
            except Exception as e:
                messagebox.showerror('Remove Error', f'Failed to remove feeds: {e}')
        
        ttk.Button(feeds_select_frame, text='➕ Add', command=_add_selected_feed, width=10).pack(side='left', padx=2)
        ttk.Button(feeds_select_frame, text='🗑️ Remove', command=_delete_selected_feeds, width=14).pack(side='left', padx=2)
    except Exception:
        pass
    row += 1

    grid_label(row, 'Assigned Category:')
    # Use Combobox with cached categories and allow manual editing
    try:
        config.load_cached_categories()
        cached_cats = getattr(config, 'CACHED_CATEGORIES', {}) or {}
    except Exception:
        cached_cats = {}
    try:
        if isinstance(cached_cats, dict):
            cat_choices = list(cached_cats.keys())
        elif isinstance(cached_cats, list):
            cat_choices = cached_cats
        else:
            cat_choices = []
    except Exception:
        cat_choices = []
    
    # Add categories from current listbox items
    try:
        for title_text_item, entry_item in listbox_items:
            if isinstance(entry_item, dict):
                cat = entry_item.get('assignedCategory') or entry_item.get('assigned_category') or entry_item.get('category') or ''
                if cat and cat not in cat_choices:
                    cat_choices.append(str(cat))
    except Exception:
        pass
    
    assigned_combo = ttk.Combobox(frm, textvariable=assigned_var, values=sorted(cat_choices), width=48, font=('Segoe UI', 9))
    assigned_combo.grid(row=row, column=1, sticky='w', padx=5, pady=4)
    
    # Track if save path was manually edited in the full editor
    savepath_manually_edited_full = {'flag': False}
    
    # Sync assigned_var with tp_category when either changes
    def _sync_assigned_to_tp(*args):
        try:
            tp_category.set(assigned_var.get())
            # Auto-fill save path from category if not manually edited
            if not savepath_manually_edited_full['flag']:
                try:
                    selected_category = assigned_var.get().strip()
                    if selected_category:
                        # Get category info from cached categories
                        cached_cats = getattr(config, 'CACHED_CATEGORIES', {}) or {}
                        if isinstance(cached_cats, dict) and selected_category in cached_cats:
                            cat_info = cached_cats[selected_category]
                            if isinstance(cat_info, dict) and 'savePath' in cat_info:
                                cat_save_path = cat_info['savePath']
                                if cat_save_path:
                                    savepath_var.set(cat_save_path.replace('/', '\\'))
                                    tp_save_path.set(cat_save_path.replace('/', '\\'))
                except Exception:
                    pass
        except Exception:
            pass
    
    def _sync_tp_to_assigned(*args):
        try:
            assigned_var.set(tp_category.get())
        except Exception:
            pass
    
    try:
        assigned_var.trace_add('write', _sync_assigned_to_tp)
        tp_category.trace_add('write', _sync_tp_to_assigned)
    except Exception:
        try:
            assigned_var.trace('w', _sync_assigned_to_tp)
            tp_category.trace('w', _sync_tp_to_assigned)
        except Exception:
            pass
    
    row += 1

    grid_label(row, 'Enabled:')
    ttk.Checkbutton(frm, variable=enabled_var, text='Enable this rule').grid(row=row, column=1, sticky='w', padx=5, pady=4)
    row += 1

    grid_label(row, 'Episode Filter:')
    ttk.Entry(frm, textvariable=episode_var, font=('Segoe UI', 9)).grid(row=row, column=1, sticky='ew', padx=5, pady=4)
    row += 1

    grid_label(row, 'Ignore Days:')
    ttk.Entry(frm, textvariable=ignore_var, width=10, font=('Segoe UI', 9)).grid(row=row, column=1, sticky='w', padx=5, pady=4)
    row += 1

    grid_label(row, 'Last Match:')
    ttk.Entry(frm, textvariable=lastmatch_var, font=('Segoe UI', 9)).grid(row=row, column=1, sticky='ew', padx=5, pady=4)
    try:
        lastmatch_full_status_label = tk.Label(frm, text='', fg='green')
        lastmatch_full_status_label.grid(row=row, column=2, sticky='w', padx=(8,0))
    except Exception:
        lastmatch_full_status_label = None
    row += 1

    grid_label(row, 'Must Contain:')
    ttk.Entry(frm, textvariable=must_var, font=('Segoe UI', 9)).grid(row=row, column=1, sticky='ew', padx=5, pady=4)
    row += 1

    grid_label(row, 'Must Not Contain:')
    ttk.Entry(frm, textvariable=mustnot_var, font=('Segoe UI', 9)).grid(row=row, column=1, sticky='ew', padx=5, pady=4)
    row += 1

    grid_label(row, 'Previously Matched (one per line):')
    prevmatches_frame.grid(row=row, column=1, sticky='w')
    prevmatches_text.grid(row=0, column=0, sticky='w', padx=2, pady=6)
    try:
        pm = entry.get('previouslyMatchedEpisodes') if isinstance(entry, dict) else []
        if isinstance(pm, list):
            prevmatches_text.delete('1.0', 'end')
            prevmatches_text.insert('1.0', '\n'.join([str(x) for x in pm]))
    except Exception:
        pass
    row += 1

    grid_label(row, 'Priority:')
    ttk.Entry(frm, textvariable=priority_var, width=10, font=('Segoe UI', 9)).grid(row=row, column=1, sticky='w', padx=5, pady=4)
    row += 1

    grid_label(row, 'Save Path:')
    savepath_entry = ttk.Entry(frm, textvariable=savepath_var, font=('Segoe UI', 9))
    savepath_entry.grid(row=row, column=1, sticky='ew', padx=5, pady=4)
    
    # Detect manual edits to save path
    def _on_savepath_keyrelease(event):
        savepath_manually_edited_full['flag'] = True
    savepath_entry.bind('<KeyRelease>', _on_savepath_keyrelease)
    
    row += 1

    grid_label(row, 'Smart Filter:')
    ttk.Checkbutton(frm, variable=smart_var, text='Enable smart filtering').grid(row=row, column=1, sticky='w', padx=5, pady=4)
    row += 1

    grid_label(row, 'Torrent Content Layout:')
    ttk.Entry(frm, textvariable=tcl_var, font=('Segoe UI', 9)).grid(row=row, column=1, sticky='ew', padx=5, pady=4)
    row += 1

    ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=15)
    row += 1

    # torrentParams section with better styling
    ttk.Label(frm, text='🔧 Torrent Parameters', font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, columnspan=2, sticky='w', pady=(0, 10))
    
    tp_frame = ttk.LabelFrame(frm, text='', padding=10)
    tp_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=4)
    tp_frame.columnconfigure(1, weight=1)
    tp_row = 0
    
    ttk.Label(tp_frame, text='category:', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    tp_category_combo = ttk.Combobox(tp_frame, textvariable=tp_category, values=sorted(cat_choices), font=('Segoe UI', 9))
    tp_category_combo.grid(row=tp_row, column=1, sticky='ew', padx=5, pady=4)
    tp_row += 1

    ttk.Label(tp_frame, text='download_limit:', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    ttk.Entry(tp_frame, textvariable=tp_download_limit, width=10, font=('Segoe UI', 9)).grid(row=tp_row, column=1, sticky='w', padx=5, pady=4)
    tp_row += 1

    ttk.Label(tp_frame, text='download_path:', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    ttk.Entry(tp_frame, textvariable=tp_download_path, font=('Segoe UI', 9)).grid(row=tp_row, column=1, sticky='ew', padx=5, pady=4)
    tp_row += 1

    ttk.Label(tp_frame, text='inactive_seeding_time_limit:', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    ttk.Entry(tp_frame, textvariable=tp_inactive_limit, width=10, font=('Segoe UI', 9)).grid(row=tp_row, column=1, sticky='w', padx=5, pady=4)
    tp_row += 1

    ttk.Label(tp_frame, text='operating_mode:', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    ttk.Entry(tp_frame, textvariable=tp_operating_mode, font=('Segoe UI', 9)).grid(row=tp_row, column=1, sticky='ew', padx=5, pady=4)
    tp_row += 1

    ttk.Label(tp_frame, text='ratio_limit:', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    ttk.Entry(tp_frame, textvariable=tp_ratio_limit, width=10, font=('Segoe UI', 9)).grid(row=tp_row, column=1, sticky='w', padx=5, pady=4)
    tp_row += 1

    ttk.Label(tp_frame, text='save_path:', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    tp_save_path_entry = ttk.Entry(tp_frame, textvariable=tp_save_path, font=('Segoe UI', 9))
    tp_save_path_entry.grid(row=tp_row, column=1, sticky='ew', padx=5, pady=4)
    
    # Detect manual edits to tp_save_path
    def _on_tp_savepath_keyrelease(event):
        savepath_manually_edited_full['flag'] = True
    tp_save_path_entry.bind('<KeyRelease>', _on_tp_savepath_keyrelease)
    
    tp_row += 1

    ttk.Label(tp_frame, text='seeding_time_limit:', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    ttk.Entry(tp_frame, textvariable=tp_seeding_time, width=10, font=('Segoe UI', 9)).grid(row=tp_row, column=1, sticky='w', padx=5, pady=4)
    tp_row += 1

    ttk.Label(tp_frame, text='skip_checking:', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    ttk.Checkbutton(tp_frame, variable=tp_skip, text='Skip hash checking').grid(row=tp_row, column=1, sticky='w', padx=5, pady=4)
    tp_row += 1

    ttk.Label(tp_frame, text='tags (comma separated):', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    ttk.Entry(tp_frame, textvariable=tp_tags, font=('Segoe UI', 9)).grid(row=tp_row, column=1, sticky='ew', padx=5, pady=4)
    tp_row += 1

    ttk.Label(tp_frame, text='upload_limit:', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    ttk.Entry(tp_frame, textvariable=tp_upload_limit, width=10, font=('Segoe UI', 9)).grid(row=tp_row, column=1, sticky='w', padx=5, pady=4)
    tp_row += 1

    ttk.Label(tp_frame, text='use_auto_tmm:', font=('Segoe UI', 9, 'bold')).grid(row=tp_row, column=0, sticky='w', padx=5, pady=4)
    ttk.Checkbutton(tp_frame, variable=tp_auto_tmm, text='Use automatic torrent management').grid(row=tp_row, column=1, sticky='w', padx=5, pady=4)
    tp_row += 1

    row += 1

    ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=15)
    row += 1

    grid_label(row, 'Use Regex:')
    ttk.Checkbutton(frm, variable=useregex_var, text='Enable regex matching').grid(row=row, column=1, sticky='w', padx=5, pady=4)
    row += 1

    # Footer buttons are defined at the end after _apply_full function

    def _apply_full():
        try:
            new_rule = {}
            ap = addPaused_var.get()
            if ap == 'None':
                new_rule['addPaused'] = None
            elif ap == 'True':
                new_rule['addPaused'] = True
            else:
                new_rule['addPaused'] = False

            feeds_raw = affected_listbox.get(0, 'end')
            new_rule['affectedFeeds'] = [f.strip() for f in feeds_raw if f.strip()]
            new_rule['assignedCategory'] = assigned_var.get().strip()
            new_rule['enabled'] = bool(enabled_var.get())
            new_rule['episodeFilter'] = episode_var.get().strip()
            try:
                new_rule['ignoreDays'] = int(ignore_var.get())
            except Exception:
                new_rule['ignoreDays'] = 0
            try:
                lm_txt = lastmatch_var.get().strip()
                if lm_txt:
                    if lm_txt.startswith('{') or lm_txt.startswith('[') or lm_txt.startswith('"'):
                        try:
                            new_rule['lastMatch'] = json.loads(lm_txt)
                        except Exception as e:
                            try:
                                if not messagebox.askyesno('Invalid JSON', f'Last Match appears to be JSON but is invalid:\n{e}\n\nApply as raw text anyway?'):
                                    return
                            except Exception:
                                return
                            new_rule['lastMatch'] = lm_txt
                    else:
                        new_rule['lastMatch'] = lm_txt
                else:
                    new_rule['lastMatch'] = ''
            except Exception:
                try:
                    new_rule['lastMatch'] = lastmatch_var.get().strip()
                except Exception:
                    new_rule['lastMatch'] = ''
            new_rule['mustContain'] = must_var.get().strip()
            new_rule['mustNotContain'] = mustnot_var.get().strip()
            pm_raw = prevmatches_text.get('1.0', 'end').strip()
            new_rule['previouslyMatchedEpisodes'] = [l.strip() for l in pm_raw.splitlines() if l.strip()]
            try:
                new_rule['priority'] = int(priority_var.get())
            except Exception:
                new_rule['priority'] = 0

            sp = savepath_var.get().strip()
            if not sp:
                if not messagebox.askyesno('Validation', 'Save Path is empty. Do you want to continue without a save path?'):
                    return
            else:
                try:
                    if len(sp) > 260 and not messagebox.askyesno('Validation Warning', 'Save Path is unusually long. Continue?'):
                        return
                except Exception:
                    pass
            new_rule['savePath'] = sp.replace('/', '\\')
            new_rule['smartFilter'] = bool(smart_var.get())
            new_rule['torrentContentLayout'] = None if not tcl_var.get().strip() else tcl_var.get().strip()
            new_rule['useRegex'] = bool(useregex_var.get())

            tp_new = {}
            tp_new['category'] = tp_category.get().strip()
            try:
                tp_new['download_limit'] = int(tp_download_limit.get())
            except Exception:
                tp_new['download_limit'] = -1
            tp_new['download_path'] = tp_download_path.get().strip()
            try:
                tp_new['inactive_seeding_time_limit'] = int(tp_inactive_limit.get())
            except Exception:
                tp_new['inactive_seeding_time_limit'] = -2
            tp_new['operating_mode'] = tp_operating_mode.get().strip() or 'AutoManaged'
            try:
                tp_new['ratio_limit'] = int(tp_ratio_limit.get())
            except Exception:
                tp_new['ratio_limit'] = -2
            tp_new['save_path'] = tp_save_path.get().strip().replace('\\', '/')
            try:
                tp_new['seeding_time_limit'] = int(tp_seeding_time.get())
            except Exception:
                tp_new['seeding_time_limit'] = -2
            tp_new['skip_checking'] = bool(tp_skip.get())
            tags_val = [t.strip() for t in tp_tags.get().split(',') if t.strip()]
            tp_new['tags'] = tags_val
            try:
                tp_new['upload_limit'] = int(tp_upload_limit.get())
            except Exception:
                tp_new['upload_limit'] = -1
            tp_new['use_auto_tmm'] = bool(tp_auto_tmm.get())
            new_rule['torrentParams'] = tp_new

            # Get the new rule title
            new_title = rule_title_var.get().strip()
            if not new_title:
                messagebox.showerror('Validation Error', 'Rule Title cannot be empty.')
                return
            
            # Preserve or create node structure with the title
            node = entry.get('node') if isinstance(entry, dict) else {}
            if not isinstance(node, dict):
                node = {}
            node['title'] = new_title
            new_rule['node'] = node

            listbox_items[idx] = (new_title, new_rule)
            try:
                if getattr(config, 'ALL_TITLES', None):
                    for k, lst in (config.ALL_TITLES.items() if isinstance(config.ALL_TITLES, dict) else []):
                        for i, it in enumerate(lst):
                            try:
                                candidate_title = (it.get('node') or {}).get('title') if isinstance(it, dict) else str(it)
                            except Exception:
                                candidate_title = str(it)
                            if candidate_title == title_text:
                                config.ALL_TITLES[k][i] = new_rule
                                raise StopIteration
            except StopIteration:
                pass

            try:
                treeview_widget.delete(idx)
                treeview_widget.insert(idx, new_title)
                treeview_widget.selection_set(idx)
                treeview_widget.see(idx)
            except Exception:
                pass

            dlg.destroy()
            # Auto-refresh the editor to show updated values
            if populate_editor_callback:
                try:
                    populate_editor_callback()
                except Exception:
                    pass
            messagebox.showinfo('Edit', 'Full settings applied.')
        except Exception as e:
            messagebox.showerror('Apply Error', f'Failed to apply full settings: {e}')

    ttk.Button(footer, text='✓ Apply', command=_apply_full, style='Accent.TButton', width=12).pack(side='right', padx=5)
    ttk.Button(footer, text='✕ Cancel', command=dlg.destroy, width=12).pack(side='right')


def open_bulk_edit_dialog(root: tk.Tk, selected_items: List[tuple], 
                          apply_callback: callable, status_var: tk.StringVar) -> None:
    """
    Opens a bulk edit dialog for editing multiple selected rules at once.
    
    Args:
        root: Parent Tkinter window
        selected_items: List of (title, entry) tuples for selected items
        apply_callback: Callback function to apply changes
        status_var: Status bar variable for feedback
    """
    if not selected_items:
        messagebox.showwarning('Bulk Edit', 'No items selected.')
        return
    
    dlg = tk.Toplevel(root)
    dlg.title(f"📝 Bulk Edit - {len(selected_items)} items selected")
    dlg.geometry("600x400")
    dlg.minsize(500, 350)
    dlg.transient(root)
    dlg.grab_set()
    dlg.configure(bg='#f5f5f5')
    
    center_window(dlg)
    
    # Main frame
    main_frame = ttk.Frame(dlg, padding=20)
    main_frame.pack(fill='both', expand=True)
    
    # Info label
    ttk.Label(main_frame, text=f"Editing {len(selected_items)} selected rules", 
              font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 15))
    
    ttk.Label(main_frame, text="Check the fields you want to update for all selected items:",
              font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 10))
    
    # Fields frame
    fields_frame = ttk.Frame(main_frame)
    fields_frame.pack(fill='both', expand=True, pady=10)
    
    # Category field
    category_enabled = tk.BooleanVar(value=False)
    category_var = tk.StringVar(value='')
    
    category_frame = ttk.Frame(fields_frame)
    category_frame.pack(fill='x', pady=8)
    
    ttk.Checkbutton(category_frame, text="Category:", variable=category_enabled,
                   width=12).pack(side='left')
    category_combo = ttk.Combobox(category_frame, textvariable=category_var, 
                                 font=('Segoe UI', 9), state='normal')
    category_combo.pack(side='left', fill='x', expand=True, padx=(5, 0))
    
    # Populate category dropdown from cached categories
    try:
        cached_cats = getattr(config, 'CACHED_CATEGORIES', {}) or {}
        if isinstance(cached_cats, dict):
            category_combo['values'] = sorted(cached_cats.keys())
    except Exception:
        pass
    
    # Save Path field
    savepath_enabled = tk.BooleanVar(value=False)
    savepath_var = tk.StringVar(value='')
    
    savepath_frame = ttk.Frame(fields_frame)
    savepath_frame.pack(fill='x', pady=8)
    
    ttk.Checkbutton(savepath_frame, text="Save Path:", variable=savepath_enabled,
                   width=12).pack(side='left')
    savepath_entry = ttk.Entry(savepath_frame, textvariable=savepath_var,
                              font=('Segoe UI', 9))
    savepath_entry.pack(side='left', fill='x', expand=True, padx=(5, 0))
    
    # Auto-fill save path from category
    def _on_category_change(*args):
        if not category_enabled.get():
            return
        try:
            selected_cat = category_var.get().strip()
            if selected_cat:
                cached_cats = getattr(config, 'CACHED_CATEGORIES', {}) or {}
                if isinstance(cached_cats, dict) and selected_cat in cached_cats:
                    cat_info = cached_cats[selected_cat]
                    if isinstance(cat_info, dict) and 'savePath' in cat_info:
                        savepath_var.set(cat_info['savePath'])
                        savepath_enabled.set(True)  # Auto-enable save path field
        except Exception:
            pass
    
    category_var.trace_add('write', _on_category_change)
    
    # Enabled field
    enabled_enabled = tk.BooleanVar(value=False)
    enabled_var = tk.BooleanVar(value=True)
    
    enabled_frame = ttk.Frame(fields_frame)
    enabled_frame.pack(fill='x', pady=8)
    
    ttk.Checkbutton(enabled_frame, text="Enabled:", variable=enabled_enabled,
                   width=12).pack(side='left')
    ttk.Checkbutton(enabled_frame, text="Enable rules", variable=enabled_var).pack(side='left', padx=(5, 0))
    
    # Separator
    ttk.Separator(fields_frame, orient='horizontal').pack(fill='x', pady=15)
    
    # Summary frame
    summary_frame = ttk.Frame(fields_frame)
    summary_frame.pack(fill='x', pady=5)
    
    summary_label = ttk.Label(summary_frame, text="", 
                             font=('Segoe UI', 9), foreground='#666')
    summary_label.pack(anchor='w')
    
    def _update_summary(*args):
        changes = []
        if category_enabled.get():
            changes.append(f"Category → '{category_var.get()}'")
        if savepath_enabled.get():
            changes.append(f"Save Path → '{savepath_var.get()}'")
        if enabled_enabled.get():
            changes.append(f"Enabled → {'Yes' if enabled_var.get() else 'No'}")
        
        if changes:
            summary_label.config(text="Will update: " + ", ".join(changes))
        else:
            summary_label.config(text="No changes selected")
    
    category_enabled.trace_add('write', _update_summary)
    savepath_enabled.trace_add('write', _update_summary)
    enabled_enabled.trace_add('write', _update_summary)
    category_var.trace_add('write', _update_summary)
    savepath_var.trace_add('write', _update_summary)
    enabled_var.trace_add('write', _update_summary)
    
    _update_summary()
    
    # Footer with buttons
    footer = ttk.Frame(dlg, padding=(20, 10))
    footer.pack(fill='x', side='bottom')
    
    def _apply_bulk_changes():
        """Apply bulk changes to all selected items."""
        try:
            # Check if any fields are enabled
            if not (category_enabled.get() or savepath_enabled.get() or enabled_enabled.get()):
                messagebox.showwarning('Bulk Edit', 'No fields selected to update.')
                return
            
            # Confirm with user
            changes_text = []
            if category_enabled.get():
                changes_text.append(f"• Category: '{category_var.get()}'")
            if savepath_enabled.get():
                changes_text.append(f"• Save Path: '{savepath_var.get()}'")
            if enabled_enabled.get():
                changes_text.append(f"• Enabled: {'Yes' if enabled_var.get() else 'No'}")
            
            confirm_msg = f"Update {len(selected_items)} selected rules with:\n\n" + "\n".join(changes_text)
            
            if not messagebox.askyesno('Confirm Bulk Edit', confirm_msg):
                return
            
            # Prepare changes dict
            changes = {}
            if category_enabled.get():
                changes['category'] = category_var.get().strip()
            if savepath_enabled.get():
                changes['save_path'] = savepath_var.get().strip()
            if enabled_enabled.get():
                changes['enabled'] = enabled_var.get()
            
            # Apply changes via callback
            success_count = apply_callback(selected_items, changes)
            
            dlg.destroy()
            
            if success_count > 0:
                status_var.set(f'Bulk edit applied to {success_count} rules')
                messagebox.showinfo('Bulk Edit', f'Successfully updated {success_count} rules.')
            else:
                messagebox.showwarning('Bulk Edit', 'No rules were updated.')
                
        except Exception as e:
            logger.error(f"Bulk edit error: {e}", exc_info=True)
            messagebox.showerror('Bulk Edit Error', f'Failed to apply bulk changes: {e}')
    
    ttk.Button(footer, text='✓ Apply to All', command=_apply_bulk_changes, 
              style='Accent.TButton', width=15).pack(side='right', padx=5)
    ttk.Button(footer, text='✕ Cancel', command=dlg.destroy, width=12).pack(side='right')


def open_template_dialog(root: tk.Tk, apply_callback=None, current_rule_data: Dict[str, Any] = None) -> None:
    """
    Opens the template management dialog.
    
    Allows users to view, apply, create, edit, and delete rule templates.
    
    Args:
        root: Parent Tkinter window
        apply_callback: Function to call when applying a template, signature: callback(template_data) -> bool
        current_rule_data: Optional dict with current rule data for creating new templates
    """
    from src.cache import load_templates, save_templates, add_template, delete_template, initialize_default_templates
    
    # Initialize default templates if none exist
    initialize_default_templates()
    
    dlg = tk.Toplevel(root)
    dlg.title("📋 Rule Templates")
    dlg.geometry("900x650")
    dlg.minsize(700, 500)
    dlg.transient(root)
    dlg.grab_set()
    dlg.configure(bg='#f5f5f5')
    center_window(dlg, root)
    
    # Main container
    main_frame = ttk.Frame(dlg, padding=20)
    main_frame.pack(fill='both', expand=True)
    
    # Title
    title_label = ttk.Label(main_frame, text="Rule Templates", 
                           font=('Segoe UI', 16, 'bold'))
    title_label.pack(pady=(0, 15))
    
    # Content area (list + preview)
    content_frame = ttk.Frame(main_frame)
    content_frame.pack(fill='both', expand=True, pady=(0, 15))
    
    # Left side - Template list
    list_frame = ttk.LabelFrame(content_frame, text="Templates", padding=10)
    list_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
    
    # Listbox with scrollbar
    list_scroll = ttk.Scrollbar(list_frame, orient='vertical')
    template_listbox = tk.Listbox(list_frame, yscrollcommand=list_scroll.set,
                                  font=('Segoe UI', 10), height=20)
    list_scroll.config(command=template_listbox.yview)
    list_scroll.pack(side='right', fill='y')
    template_listbox.pack(side='left', fill='both', expand=True)
    
    # Right side - Preview pane
    preview_frame = ttk.LabelFrame(content_frame, text="Preview", padding=10)
    preview_frame.pack(side='right', fill='both', expand=True)
    
    # Preview text widget with scrollbar
    preview_scroll = ttk.Scrollbar(preview_frame, orient='vertical')
    preview_text = tk.Text(preview_frame, yscrollcommand=preview_scroll.set,
                          font=('Consolas', 9), wrap='word', height=20, width=40)
    preview_scroll.config(command=preview_text.yview)
    preview_scroll.pack(side='right', fill='y')
    preview_text.pack(side='left', fill='both', expand=True)
    preview_text.config(state='disabled')  # Read-only
    
    # Template data storage
    templates = {}
    
    def refresh_template_list():
        """Refresh the template list."""
        nonlocal templates
        templates = load_templates()
        
        template_listbox.delete(0, tk.END)
        for name in sorted(templates.keys()):
            template_listbox.insert(tk.END, name)
        
        if template_listbox.size() > 0:
            template_listbox.selection_set(0)
            update_preview()
    
    def update_preview(event=None):
        """Update the preview pane with selected template."""
        selection = template_listbox.curselection()
        if not selection:
            preview_text.config(state='normal')
            preview_text.delete('1.0', tk.END)
            preview_text.config(state='disabled')
            return
        
        template_name = template_listbox.get(selection[0])
        template_data = templates.get(template_name, {})
        
        # Format preview
        preview_content = f"Template: {template_name}\n"
        preview_content += "=" * 50 + "\n\n"
        
        if 'description' in template_data:
            preview_content += f"Description:\n  {template_data['description']}\n\n"
        
        preview_content += "Settings:\n"
        for key, value in template_data.items():
            if key == 'description':
                continue
            preview_content += f"  {key}: {value}\n"
        
        preview_text.config(state='normal')
        preview_text.delete('1.0', tk.END)
        preview_text.insert('1.0', preview_content)
        preview_text.config(state='disabled')
    
    template_listbox.bind('<<ListboxSelect>>', update_preview)
    
    def apply_template():
        """Apply the selected template."""
        selection = template_listbox.curselection()
        if not selection:
            messagebox.showwarning('No Selection', 'Please select a template to apply.')
            return
        
        template_name = template_listbox.get(selection[0])
        template_data = templates.get(template_name, {})
        
        if apply_callback:
            try:
                # Remove description from data passed to callback
                data_to_apply = {k: v for k, v in template_data.items() if k != 'description'}
                success = apply_callback(data_to_apply)
                if success:
                    messagebox.showinfo('Template Applied', f'Template "{template_name}" applied successfully.')
                    dlg.destroy()
                else:
                    messagebox.showerror('Apply Failed', 'Failed to apply template.')
            except Exception as e:
                logger.error(f"Error applying template: {e}", exc_info=True)
                messagebox.showerror('Error', f'Failed to apply template: {e}')
        else:
            messagebox.showinfo('Template Data', f'Template "{template_name}" selected.\n\nData:\n{template_data}')
    
    def create_new_template():
        """Create a new template."""
        create_win = tk.Toplevel(dlg)
        create_win.title("Create New Template")
        create_win.geometry("500x600")
        create_win.transient(dlg)
        create_win.grab_set()
        center_window(create_win, dlg)
        
        form_frame = ttk.Frame(create_win, padding=20)
        form_frame.pack(fill='both', expand=True)
        
        ttk.Label(form_frame, text="Create New Template", 
                 font=('Segoe UI', 14, 'bold')).pack(pady=(0, 20))
        
        # Template name
        ttk.Label(form_frame, text="Template Name:").pack(anchor='w', pady=(5, 2))
        name_entry = ttk.Entry(form_frame, width=50)
        name_entry.pack(fill='x', pady=(0, 10))
        
        # Description
        ttk.Label(form_frame, text="Description:").pack(anchor='w', pady=(5, 2))
        desc_entry = ttk.Entry(form_frame, width=50)
        desc_entry.pack(fill='x', pady=(0, 10))
        
        # Category
        ttk.Label(form_frame, text="Category:").pack(anchor='w', pady=(5, 2))
        category_entry = ttk.Entry(form_frame, width=50)
        category_entry.pack(fill='x', pady=(0, 10))
        
        # Save Path
        ttk.Label(form_frame, text="Save Path:").pack(anchor='w', pady=(5, 2))
        savepath_entry = ttk.Entry(form_frame, width=50)
        savepath_entry.pack(fill='x', pady=(0, 10))
        
        # Must Contain
        ttk.Label(form_frame, text="Must Contain:").pack(anchor='w', pady=(5, 2))
        must_contain_entry = ttk.Entry(form_frame, width=50)
        must_contain_entry.pack(fill='x', pady=(0, 10))
        
        # Must Not Contain
        ttk.Label(form_frame, text="Must Not Contain:").pack(anchor='w', pady=(5, 2))
        must_not_contain_entry = ttk.Entry(form_frame, width=50)
        must_not_contain_entry.pack(fill='x', pady=(0, 10))
        
        # Episode Filter
        ttk.Label(form_frame, text="Episode Filter:").pack(anchor='w', pady=(5, 2))
        episode_filter_entry = ttk.Entry(form_frame, width=50)
        episode_filter_entry.pack(fill='x', pady=(0, 10))
        
        # Enabled checkbox
        enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Enabled by default", 
                       variable=enabled_var).pack(anchor='w', pady=(5, 10))
        
        # Use Regex checkbox
        use_regex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Use Regular Expression", 
                       variable=use_regex_var).pack(anchor='w', pady=(0, 10))
        
        # Pre-fill with current rule data if provided
        if current_rule_data:
            category_entry.insert(0, current_rule_data.get('category', ''))
            savepath_entry.insert(0, current_rule_data.get('save_path', ''))
            must_contain_entry.insert(0, current_rule_data.get('must_contain', ''))
            must_not_contain_entry.insert(0, current_rule_data.get('must_not_contain', ''))
            episode_filter_entry.insert(0, current_rule_data.get('episode_filter', ''))
            enabled_var.set(current_rule_data.get('enabled', True))
            use_regex_var.set(current_rule_data.get('use_regex', False))
        
        def save_new_template():
            """Save the new template."""
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning('Invalid Name', 'Please enter a template name.')
                return
            
            if name in templates:
                if not messagebox.askyesno('Overwrite Template', 
                                          f'Template "{name}" already exists. Overwrite?'):
                    return
            
            template_data = {
                'description': desc_entry.get().strip(),
                'category': category_entry.get().strip(),
                'save_path': savepath_entry.get().strip(),
                'must_contain': must_contain_entry.get().strip(),
                'must_not_contain': must_not_contain_entry.get().strip(),
                'episode_filter': episode_filter_entry.get().strip(),
                'enabled': enabled_var.get(),
                'use_regex': use_regex_var.get(),
            }
            
            if add_template(name, template_data):
                messagebox.showinfo('Success', f'Template "{name}" saved successfully.')
                create_win.destroy()
                refresh_template_list()
            else:
                messagebox.showerror('Error', 'Failed to save template.')
        
        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.pack(fill='x', pady=(15, 0))
        
        ttk.Button(btn_frame, text='✓ Save Template', command=save_new_template,
                  style='Accent.TButton', width=15).pack(side='right', padx=5)
        ttk.Button(btn_frame, text='✕ Cancel', command=create_win.destroy,
                  width=12).pack(side='right')
    
    def edit_template():
        """Edit the selected template."""
        selection = template_listbox.curselection()
        if not selection:
            messagebox.showwarning('No Selection', 'Please select a template to edit.')
            return
        
        template_name = template_listbox.get(selection[0])
        template_data = templates.get(template_name, {})
        
        # Open create dialog pre-filled with template data
        create_new_template()  # This will be enhanced to handle editing
    
    def delete_selected_template():
        """Delete the selected template."""
        selection = template_listbox.curselection()
        if not selection:
            messagebox.showwarning('No Selection', 'Please select a template to delete.')
            return
        
        template_name = template_listbox.get(selection[0])
        
        if not messagebox.askyesno('Confirm Delete', 
                                   f'Delete template "{template_name}"?'):
            return
        
        if delete_template(template_name):
            messagebox.showinfo('Deleted', f'Template "{template_name}" deleted.')
            refresh_template_list()
        else:
            messagebox.showerror('Error', 'Failed to delete template.')
    
    # Button panel
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=(0, 0))
    
    ttk.Button(button_frame, text='✓ Apply Template', command=apply_template,
              style='Accent.TButton', width=15).pack(side='left', padx=5)
    ttk.Button(button_frame, text='+ New Template', command=create_new_template,
              width=15).pack(side='left', padx=5)
    ttk.Button(button_frame, text='✎ Edit Template', command=edit_template,
              width=15).pack(side='left', padx=5)
    ttk.Button(button_frame, text='🗑 Delete', command=delete_selected_template,
              width=12).pack(side='left', padx=5)
    ttk.Button(button_frame, text='✕ Close', command=dlg.destroy,
              width=12).pack(side='right', padx=5)
    
    # Load templates
    refresh_template_list()


def open_sonarr_export_dialog(root: tk.Tk, titles_to_export: List[str]) -> None:
    """
    Opens the Sonarr export dialog to bulk-add series.
    
    Args:
        root: Parent Tkinter window
        titles_to_export: List of anime titles to add to Sonarr
    """
    import src.sonarr_api as sonarr
    from src.config import config
    from src.gui.helpers import center_window
    
    dlg = tk.Toplevel(root)
    dlg.title("📺 Export to Sonarr")
    dlg.geometry("1000x700")
    dlg.minsize(800, 600)
    dlg.transient(root)
    dlg.grab_set()
    dlg.configure(bg='#f5f5f5')
    center_window(dlg, root)
    
    # Main container
    main_frame = ttk.Frame(dlg, padding=20)
    main_frame.pack(fill='both', expand=True)
    
    # Title
    title_label = ttk.Label(main_frame, text="Export to Sonarr", 
                           font=('Segoe UI', 16, 'bold'))
    title_label.pack(pady=(0, 10))
    
    # Status label
    status_var = tk.StringVar(value=f"Ready to export {len(titles_to_export)} titles")
    status_label = ttk.Label(main_frame, textvariable=status_var, 
                            font=('Segoe UI', 9))
    status_label.pack(pady=(0, 15))
    
    # Connection frame
    conn_frame = ttk.LabelFrame(main_frame, text="Sonarr Connection", padding=10)
    conn_frame.pack(fill='x', pady=(0, 15))
    
    # URL
    ttk.Label(conn_frame, text="Sonarr URL:").grid(row=0, column=0, sticky='w', padx=(0, 10))
    url_var = tk.StringVar(value=config.SONARR_URL or "http://localhost:8989")
    url_entry = ttk.Entry(conn_frame, textvariable=url_var, width=40)
    url_entry.grid(row=0, column=1, sticky='ew', padx=(0, 10))
    
    # API Key
    ttk.Label(conn_frame, text="API Key:").grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
    api_key_var = tk.StringVar(value=config.SONARR_API_KEY or "")
    api_key_entry = ttk.Entry(conn_frame, textvariable=api_key_var, width=40, show='*')
    api_key_entry.grid(row=1, column=1, sticky='ew', padx=(0, 10), pady=(5, 0))
    
    # Test button
    def test_connection():
        status_var.set("Testing connection...")
        dlg.update()
        try:
            result = sonarr.test_connection(url_var.get(), api_key_var.get())
            version = result.get('version', 'Unknown')
            status_var.set(f"✓ Connected to Sonarr v{version}")
            messagebox.showinfo('Connection Test', f'Successfully connected to Sonarr v{version}')
            
            # Save config
            config.save_sonarr_config(url_var.get(), api_key_var.get())
        except Exception as e:
            status_var.set(f"✗ Connection failed: {e}")
            messagebox.showerror('Connection Error', f'Failed to connect to Sonarr:\n\n{e}')
    
    test_btn = ttk.Button(conn_frame, text='Test Connection', command=test_connection)
    test_btn.grid(row=0, column=2, rowspan=2, padx=(5, 0))
    
    conn_frame.columnconfigure(1, weight=1)
    
    # Settings frame
    settings_frame = ttk.LabelFrame(main_frame, text="Import Settings", padding=10)
    settings_frame.pack(fill='x', pady=(0, 15))
    
    # Quality Profile
    ttk.Label(settings_frame, text="Quality Profile:").grid(row=0, column=0, sticky='w', padx=(0, 10))
    quality_var = tk.StringVar()
    quality_combo = ttk.Combobox(settings_frame, textvariable=quality_var, state='readonly', width=30)
    quality_combo.grid(row=0, column=1, sticky='w')
    
    # Root Folder
    ttk.Label(settings_frame, text="Root Folder:").grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
    root_folder_var = tk.StringVar()
    root_folder_combo = ttk.Combobox(settings_frame, textvariable=root_folder_var, state='readonly', width=50)
    root_folder_combo.grid(row=1, column=1, sticky='ew', pady=(5, 0))
    
    # Monitor Mode
    ttk.Label(settings_frame, text="Monitor:").grid(row=2, column=0, sticky='w', padx=(0, 10), pady=(5, 0))
    monitor_var = tk.StringVar(value="all")
    monitor_combo = ttk.Combobox(settings_frame, textvariable=monitor_var, state='readonly', width=20,
                                values=['all', 'future', 'missing', 'existing', 'none'])
    monitor_combo.grid(row=2, column=1, sticky='w', pady=(5, 0))
    
    # Search on add
    search_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(settings_frame, text="Search for missing episodes on add", 
                   variable=search_var).grid(row=3, column=0, columnspan=2, sticky='w', pady=(5, 0))
    
    settings_frame.columnconfigure(1, weight=1)
    
    # Load quality profiles and root folders
    quality_profiles = []
    root_folders = []
    
    def load_settings():
        nonlocal quality_profiles, root_folders
        try:
            status_var.set("Loading Sonarr settings...")
            dlg.update()
            
            # Get quality profiles
            quality_profiles = sonarr.get_quality_profiles(url_var.get(), api_key_var.get())
            profile_names = [p['name'] for p in quality_profiles]
            quality_combo['values'] = profile_names
            if profile_names:
                quality_combo.current(0)
            
            # Get root folders
            root_folders = sonarr.get_root_folders(url_var.get(), api_key_var.get())
            folder_paths = [f['path'] for f in root_folders]
            root_folder_combo['values'] = folder_paths
            if folder_paths:
                root_folder_combo.current(0)
            
            status_var.set(f"Loaded {len(quality_profiles)} profiles, {len(root_folders)} folders")
        except Exception as e:
            status_var.set(f"Failed to load settings: {e}")
            messagebox.showerror('Settings Error', f'Failed to load Sonarr settings:\n\n{e}')
    
    load_settings_btn = ttk.Button(settings_frame, text='↻ Load Settings', command=load_settings)
    load_settings_btn.grid(row=0, column=2, padx=(10, 0))
    
    # Series matching frame
    matching_frame = ttk.LabelFrame(main_frame, text="Series Matching", padding=10)
    matching_frame.pack(fill='both', expand=True, pady=(0, 15))
    
    # Treeview for series matching
    columns = ('title', 'status', 'match')
    tree = ttk.Treeview(matching_frame, columns=columns, show='headings', height=15)
    tree.heading('title', text='Title')
    tree.heading('status', text='Status')
    tree.heading('match', text='Sonarr Match')
    tree.column('title', width=250)
    tree.column('status', width=100)
    tree.column('match', width=400)
    
    # Scrollbar
    scrollbar = ttk.Scrollbar(matching_frame, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right', fill='y')
    tree.pack(side='left', fill='both', expand=True)
    
    # Store series matches
    series_matches = {}  # title -> sonarr series data
    
    # Populate tree
    for title in titles_to_export:
        tree.insert('', 'end', values=(title, 'Pending', ''))
    
    # Search for series
    def search_all_series():
        status_var.set("Searching for series in Sonarr...")
        dlg.update()
        
        matches_found = 0
        for item in tree.get_children():
            title = tree.item(item, 'values')[0]
            try:
                results = sonarr.search_series(url_var.get(), api_key_var.get(), title)
                if results:
                    # Use first match
                    match = results[0]
                    series_matches[title] = match
                    match_text = f"{match.get('title')} ({match.get('year', 'N/A')})"
                    tree.item(item, values=(title, '✓ Found', match_text))
                    tree.item(item, tags=('found',))
                    matches_found += 1
                else:
                    tree.item(item, values=(title, '✗ Not Found', 'No matches'))
                    tree.item(item, tags=('not_found',))
            except Exception as e:
                tree.item(item, values=(title, '✗ Error', str(e)))
                tree.item(item, tags=('error',))
            
            dlg.update()
        
        tree.tag_configure('found', foreground='green')
        tree.tag_configure('not_found', foreground='red')
        tree.tag_configure('error', foreground='orange')
        
        status_var.set(f"Found matches for {matches_found}/{len(titles_to_export)} series")
    
    # Button frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x')
    
    ttk.Button(button_frame, text='🔍 Search for Series', command=search_all_series).pack(side='left', padx=5)
    
    def add_to_sonarr():
        if not series_matches:
            messagebox.showwarning('No Matches', 'Please search for series first.')
            return
        
        # Get selected quality profile and root folder
        quality_name = quality_var.get()
        quality_id = next((p['id'] for p in quality_profiles if p['name'] == quality_name), None)
        
        root_folder = root_folder_var.get()
        
        if not quality_id or not root_folder:
            messagebox.showwarning('Settings Required', 'Please select quality profile and root folder.')
            return
        
        # Confirm
        if not messagebox.askyesno('Confirm Add', 
                                   f'Add {len(series_matches)} series to Sonarr?\n\n' +
                                   f'Quality: {quality_name}\n' +
                                   f'Folder: {root_folder}\n' +
                                   f'Monitor: {monitor_var.get()}'):
            return
        
        # Add series
        status_var.set("Adding series to Sonarr...")
        dlg.update()
        
        results = sonarr.bulk_add_series(
            url_var.get(), api_key_var.get(),
            list(series_matches.values()),
            quality_id, root_folder,
            monitor_var.get(), search_var.get()
        )
        
        # Update tree with results
        for item in tree.get_children():
            title = tree.item(item, 'values')[0]
            if title in results['success']:
                tree.item(item, values=(title, '✓ Added', tree.item(item, 'values')[2]))
                tree.item(item, tags=('added',))
            elif any(title in f for f in results['failed']):
                error = next(f for f in results['failed'] if title in f)
                tree.item(item, values=(title, '✗ Failed', error))
                tree.item(item, tags=('failed',))
        
        tree.tag_configure('added', foreground='blue')
        tree.tag_configure('failed', foreground='red')
        
        status_var.set(f"Added {len(results['success'])} series, {len(results['failed'])} failed")
        
        # Save settings
        config.save_sonarr_config(
            url_var.get(), api_key_var.get(),
            quality_id, root_folder,
            monitor_var.get(), search_var.get()
        )
        
        messagebox.showinfo('Sonarr Export Complete', 
                           f"Successfully added {len(results['success'])} series to Sonarr.\n\n" +
                           (f"Failed: {len(results['failed'])}" if results['failed'] else ""))
    
    ttk.Button(button_frame, text='✓ Add to Sonarr', command=add_to_sonarr,
              style='Accent.TButton').pack(side='left', padx=5)
    ttk.Button(button_frame, text='✕ Close', command=dlg.destroy).pack(side='right', padx=5)

