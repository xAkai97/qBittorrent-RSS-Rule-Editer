"""UI module containing the Tkinter application and related helpers.

This module implements the GUI previously contained in `core.py`.
"""
import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from . import config
from . import qbt_api
from .utils import get_current_anime_season, generate_offline_config, create_qbittorrent_rule_def

# Scrolling configuration
SCROLL_MODE = 'lines'
SCROLL_LINES = 3
SCROLL_PIXELS = 60

# Globals used by UI
LISTBOX_WIDGET = None
LISTBOX_ITEMS = []
_APP_ROOT = None
_APP_STATUS_VAR = None


def preview_and_edit_generated_rules(root, rules_dict, connection_mode, status_var):
    if not rules_dict:
        messagebox.showwarning('Preview', 'No generated rules to preview.')
        return

    preview_win = tk.Toplevel(root)
    preview_win.title('Preview Generated Rules')
    preview_win.transient(root)
    preview_win.grab_set()

    cols = ("enabled", "name", "match", "savepath")
    tree = ttk.Treeview(preview_win, columns=cols, show='headings', height=18)
    for c, h in [('enabled','Enabled'), ('name','Rule Name'), ('match','Match Pattern'), ('savepath','Save Path')]:
        tree.heading(c, text=h)
        tree.column(c, width=200 if c!='enabled' else 70, anchor='w')

    vsb = ttk.Scrollbar(preview_win, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky='nsew', padx=(10,0), pady=10)
    vsb.grid(row=0, column=1, sticky='ns', pady=10)

    for name, data in rules_dict.items():
        tree.insert('', 'end', iid=name, values=(str(bool(data.get('enabled', True))), name, data.get('mustContain', ''), data.get('savePath', '')))

    def edit_selected():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning('Edit', 'Please select a rule to edit.')
            return
        key = sel[0]
        entry = rules_dict.get(key, {})

        dlg = tk.Toplevel(preview_win)
        dlg.title(f'Edit Generated Rule - {key}')
        dlg.transient(preview_win)
        dlg.grab_set()

        enabled_var = tk.BooleanVar(value=bool(entry.get('enabled', True)))
        name_var = tk.StringVar(value=key)
        match_var = tk.StringVar(value=entry.get('mustContain', ''))
        save_var = tk.StringVar(value=entry.get('savePath', ''))

        ttk.Checkbutton(dlg, text='Enabled', variable=enabled_var).grid(row=0, column=0, sticky='w', padx=10, pady=5)
        ttk.Label(dlg, text='Rule Name:').grid(row=1, column=0, sticky='w', padx=10, pady=2)
        ttk.Entry(dlg, textvariable=name_var, width=60).grid(row=1, column=1, padx=10, pady=2)
        ttk.Label(dlg, text='Match Pattern:').grid(row=2, column=0, sticky='w', padx=10, pady=2)
        ttk.Entry(dlg, textvariable=match_var, width=60).grid(row=2, column=1, padx=10, pady=2)
        ttk.Label(dlg, text='Save Path:').grid(row=3, column=0, sticky='w', padx=10, pady=2)
        ttk.Entry(dlg, textvariable=save_var, width=60).grid(row=3, column=1, padx=10, pady=2)

        def apply_changes():
            new_name = name_var.get().strip()
            new_entry = dict(entry)
            new_entry['enabled'] = bool(enabled_var.get())
            new_entry['mustContain'] = match_var.get()
            new_entry['savePath'] = save_var.get()

            if new_name != key:
                rules_dict.pop(key, None)
                rules_dict[new_name] = new_entry
                tree.delete(key)
                tree.insert('', 'end', iid=new_name, values=(str(bool(new_entry['enabled'])), new_name, new_entry['mustContain'], new_entry['savePath']))
            else:
                rules_dict[key] = new_entry
                tree.item(key, values=(str(bool(new_entry['enabled'])), key, new_entry['mustContain'], new_entry['savePath']))
            dlg.destroy()

        ttk.Button(dlg, text='Apply', command=apply_changes).grid(row=4, column=0, padx=10, pady=10)
        ttk.Button(dlg, text='Cancel', command=dlg.destroy).grid(row=4, column=1, padx=10, pady=10)

    def export_rules():
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON','*.json')])
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(rules_dict, f, indent=2)
            messagebox.showinfo('Export', f'Rules exported to {path}')
        except Exception as e:
            messagebox.showerror('Export Error', f'Failed to export rules: {e}')

    def apply_now():
        if connection_mode == 'offline':
            export_rules()
            preview_win.destroy()
            status_var.set('Exported generated rules (offline).')
            return

        try:
            verify_arg = config.QBT_CA_CERT if (getattr(config, 'QBT_CA_CERT', None) and config.QBT_VERIFY_SSL) else config.QBT_VERIFY_SSL
            full_host = f"{config.QBT_PROTOCOL}://{config.QBT_HOST}:{config.QBT_PORT}"
            qbt = qbt_api.create_qbittorrent_client(host=full_host, username=config.QBT_USER, password=config.QBT_PASS, verify_ssl=verify_arg)
            qbt.auth_log_in()
            applied = 0
            for name, data in list(rules_dict.items()):
                rule_def = {
                    'affectedFeeds': data.get('affectedFeeds', [config.DEFAULT_RSS_FEED]),
                    'assignedCategory': data.get('assignedCategory', 'Anime/Seasonal'),
                    'enabled': data.get('enabled', True),
                    'mustContain': data.get('mustContain', ''),
                    'mustNotContain': data.get('mustNotContain', ''),
                    'useRegex': data.get('useRegex', False),
                    'savePath': data.get('savePath', ''),
                    'torrentParams': data.get('torrentParams', {})
                }
                try:
                    qbt.rss_set_rule(rule_name=name, rule_def=rule_def)
                    applied += 1
                except Exception:
                    try:
                        qbt.rss_remove_rule(rule_name=name)
                        qbt.rss_set_rule(rule_name=name, rule_def=rule_def)
                        applied += 1
                    except Exception:
                        pass

            messagebox.showinfo('Apply', f'Applied {applied}/{len(rules_dict)} generated rules to qBittorrent')
            status_var.set(f'Applied {applied} generated rules online.')
            preview_win.destroy()
        except Exception as e:
            messagebox.showerror('Apply Error', f'Failed to apply generated rules: {e}')

    btn_frame = ttk.Frame(preview_win)
    btn_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=(0,10))
    ttk.Button(btn_frame, text='Edit Selected', command=edit_selected).pack(side='left', padx=5)
    ttk.Button(btn_frame, text='Export (JSON)', command=export_rules).pack(side='left', padx=5)
    ttk.Button(btn_frame, text='Apply Now', command=apply_now).pack(side='right', padx=5)

    preview_win.columnconfigure(0, weight=1)


def display_rules(root, rules_dict, source_name):
    if not rules_dict:
        messagebox.showinfo("Info", f"No rules found from {source_name}.")
        return

    rules = rules_dict
    display_win = tk.Toplevel(root)
    display_win.title(f"Existing Rules - Source: {source_name}")
    display_win.transient(root)
    display_win.grab_set()

    cols = ("enabled", "name", "match", "savepath")
    tree = ttk.Treeview(display_win, columns=cols, show='headings', height=20)
    tree.heading('enabled', text='Enabled')
    tree.heading('name', text='Rule Name')
    tree.heading('match', text='Match Pattern')
    tree.heading('savepath', text='Save Path')

    tree.column('enabled', width=70, anchor='center')
    tree.column('name', width=220, anchor='w')
    tree.column('match', width=220, anchor='w')
    tree.column('savepath', width=300, anchor='w')

    vsb = ttk.Scrollbar(display_win, orient='vertical', command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky='nsew', padx=(10,0), pady=10)
    vsb.grid(row=0, column=1, sticky='ns', pady=10)

    for name, data in rules.items():
        en = data.get('enabled', True)
        must = data.get('mustContain', data.get('must_contain', ''))
        sp = data.get('savePath', data.get('save_path', ''))
        tree.insert('', 'end', iid=name, values=(str(bool(en)), name, must, sp))

    btn_frame = ttk.Frame(display_win)
    btn_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=(0,10))

    def edit_selected():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning('Edit Rule', 'Please select a rule to edit.')
            return
        key = sel[0]
        entry = rules.get(key, {})

        dlg = tk.Toplevel(display_win)
        dlg.title(f"Edit Rule - {key}")
        dlg.transient(display_win)
        dlg.grab_set()

        enabled_var = tk.BooleanVar(value=bool(entry.get('enabled', True)))
        name_var = tk.StringVar(value=key)
        match_var = tk.StringVar(value=entry.get('mustContain', entry.get('must_contain', '')))
        save_var = tk.StringVar(value=entry.get('savePath', entry.get('save_path', '')))

        ttk.Checkbutton(dlg, text='Enabled', variable=enabled_var).grid(row=0, column=0, sticky='w', padx=10, pady=5)
        ttk.Label(dlg, text='Rule Name:').grid(row=1, column=0, sticky='w', padx=10, pady=2)
        ttk.Entry(dlg, textvariable=name_var, width=50).grid(row=1, column=1, padx=10, pady=2)
        ttk.Label(dlg, text='Match Pattern:').grid(row=2, column=0, sticky='w', padx=10, pady=2)
        ttk.Entry(dlg, textvariable=match_var, width=50).grid(row=2, column=1, padx=10, pady=2)
        ttk.Label(dlg, text='Save Path:').grid(row=3, column=0, sticky='w', padx=10, pady=2)
        ttk.Entry(dlg, textvariable=save_var, width=50).grid(row=3, column=1, padx=10, pady=2)

        def apply_changes():
            new_name = name_var.get().strip()
            new_entry = dict(entry)
            new_entry['enabled'] = bool(enabled_var.get())
            new_entry['mustContain'] = match_var.get()
            new_entry['savePath'] = save_var.get()

            if new_name != key:
                rules.pop(key, None)
                rules[new_name] = new_entry
                tree.delete(key)
                tree.insert('', 'end', iid=new_name, values=(str(bool(new_entry['enabled'])), new_name, new_entry['mustContain'], new_entry['savePath']))
            else:
                rules[key] = new_entry
                tree.item(key, values=(str(bool(new_entry['enabled'])), key, new_entry['mustContain'], new_entry['savePath']))

            dlg.destroy()

        ttk.Button(dlg, text='Apply', command=apply_changes).grid(row=4, column=0, padx=10, pady=10)
        ttk.Button(dlg, text='Cancel', command=dlg.destroy).grid(row=4, column=1, padx=10, pady=10)

    def export_rules():
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON','*.json')])
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(rules, f, indent=2)
            messagebox.showinfo('Export', f'Rules exported to {path}')
        except Exception as e:
            messagebox.showerror('Export Error', f'Failed to export rules: {e}')

    def apply_online():
        if not rules:
            messagebox.showwarning('Apply', 'No rules to apply')
            return

        apply_list = [(name, data) for name, data in rules.items()]
        if not messagebox.askyesno('Apply Online', f'Apply {len(apply_list)} rules to qBittorrent now?'):
            return

        try:
            verify_arg = config.QBT_CA_CERT if (getattr(config, 'QBT_CA_CERT', None) and config.QBT_VERIFY_SSL) else config.QBT_VERIFY_SSL
            full_host = f"{config.QBT_PROTOCOL}://{config.QBT_HOST}:{config.QBT_PORT}"
            qbt = qbt_api.create_qbittorrent_client(host=full_host, username=config.QBT_USER, password=config.QBT_PASS, verify_ssl=verify_arg)
            qbt.auth_log_in()
            applied = 0
            for name, data in apply_list:
                rule_def = {
                    'affectedFeeds': data.get('affectedFeeds', [config.DEFAULT_RSS_FEED]),
                    'assignedCategory': data.get('assignedCategory', 'Anime/Seasonal'),
                    'enabled': data.get('enabled', True),
                    'mustContain': data.get('mustContain', ''),
                    'mustNotContain': data.get('mustNotContain', ''),
                    'useRegex': data.get('useRegex', False),
                    'savePath': data.get('savePath', ''),
                    'torrentParams': data.get('torrentParams', {})
                }
                try:
                    qbt.rss_set_rule(rule_name=name, rule_def=rule_def)
                    applied += 1
                except Exception:
                    try:
                        qbt.rss_remove_rule(rule_name=name)
                        qbt.rss_set_rule(rule_name=name, rule_def=rule_def)
                        applied += 1
                    except Exception:
                        pass

            messagebox.showinfo('Apply Online', f'Applied {applied}/{len(apply_list)} rules to qBittorrent')
        except Exception as e:
            messagebox.showerror('Apply Error', f'Failed to apply rules online: {e}')

    edit_btn = ttk.Button(btn_frame, text='Edit Selected', command=edit_selected)
    edit_btn.pack(side='left', padx=5)
    export_btn = ttk.Button(btn_frame, text='Export to JSON', command=export_rules)
    export_btn.pack(side='left', padx=5)
    apply_btn = ttk.Button(btn_frame, text='Apply to qBittorrent (Online)', command=apply_online)
    apply_btn.pack(side='right', padx=5)

    display_win.columnconfigure(0, weight=1)
    display_win.rowconfigure(0, weight=1)


def handle_load_rules(root, status_var):
    config.load_config()
    status_var.set("Loading existing rules...")
    rules_dict = None
    source_name = ""

    if config.CONNECTION_MODE == 'online':
        rules_dict = qbt_api.fetch_online_rules(root)
        source_name = f"Online ({config.QBT_PROTOCOL}://{config.QBT_HOST}:{config.QBT_PORT})"
    else:
        filepath = filedialog.askopenfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")], title="Open qBittorrent Rules File")
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    rules_dict = json.load(f)
            except Exception as e:
                messagebox.showerror("File Error", f"Error reading file: {e}")
        source_name = "Local JSON File"

    if rules_dict is not None:
        display_rules(root, rules_dict, source_name)
        status_var.set(f"Successfully loaded {len(rules_dict)} existing rules from {source_name}.")
    else:
        status_var.set(f"Failed to load existing rules in {config.CONNECTION_MODE} mode.")


def open_settings_window(root, status_var):
    settings_win = tk.Toplevel(root)
    settings_win.title("Settings - Configuration")
    settings_win.transient(root)
    settings_win.grab_set()

    qbt_protocol_temp = tk.StringVar(value=config.QBT_PROTOCOL)
    qbt_host_temp = tk.StringVar(value=config.QBT_HOST)
    qbt_port_temp = tk.StringVar(value=config.QBT_PORT)
    qbt_user_temp = tk.StringVar(value=config.QBT_USER)
    qbt_pass_temp = tk.StringVar(value=config.QBT_PASS)
    mode_temp = tk.StringVar(value=config.CONNECTION_MODE)
    verify_ssl_temp = tk.BooleanVar(value=config.QBT_VERIFY_SSL)
    ca_cert_temp = tk.StringVar(value=getattr(config, 'QBT_CA_CERT', '') or "")

    def save_and_close():
        new_qbt_protocol = qbt_protocol_temp.get().strip()
        new_qbt_host = qbt_host_temp.get().strip()
        new_qbt_port = qbt_port_temp.get().strip()
        new_qbt_user = qbt_user_temp.get().strip()
        new_qbt_pass = qbt_pass_temp.get().strip()
        new_mode = mode_temp.get()
        new_verify_ssl = verify_ssl_temp.get()
        new_ca_cert = ca_cert_temp.get().strip()

        if not new_qbt_host or not new_qbt_port:
            messagebox.showwarning("Warning", "Host and Port are required.")
            return

        config.QBT_CA_CERT = new_ca_cert or None
        config.save_config(new_qbt_protocol, new_qbt_host, new_qbt_port, new_qbt_user, new_qbt_pass, new_mode, new_verify_ssl)
        settings_win.destroy()

    mode_frame = ttk.LabelFrame(settings_win, text="Connection Mode", padding=10)
    mode_frame.pack(fill='x', padx=10, pady=10)
    ttk.Label(mode_frame, text="Choose how to apply the rules:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    ttk.Radiobutton(mode_frame, text="Online (Direct API Sync)", variable=mode_temp, value='online').grid(row=1, column=0, sticky='w', padx=5)
    ttk.Radiobutton(mode_frame, text="Offline (Generate JSON File)", variable=mode_temp, value='offline').grid(row=1, column=1, sticky='w', padx=5)

    qbt_frame = ttk.LabelFrame(settings_win, text="qBittorrent Web UI API", padding=10)
    qbt_frame.pack(fill='x', padx=10, pady=10)
    ttk.Label(qbt_frame, text="Protocol:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    protocol_dropdown = ttk.Combobox(qbt_frame, textvariable=qbt_protocol_temp, values=['http', 'https'], state='readonly', width=6)
    protocol_dropdown.grid(row=0, column=1, sticky='w', padx=5, pady=5)

    ttk.Label(qbt_frame, text="Host (IP/DNS):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
    ttk.Entry(qbt_frame, textvariable=qbt_host_temp, width=20).grid(row=1, column=1, sticky='w', padx=5, pady=5)

    ttk.Label(qbt_frame, text="Port:").grid(row=1, column=2, sticky='w', padx=5, pady=5)
    ttk.Entry(qbt_frame, textvariable=qbt_port_temp, width=10).grid(row=1, column=3, sticky='w', padx=5, pady=5)

    ttk.Label(qbt_frame, text="Username:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
    ttk.Entry(qbt_frame, textvariable=qbt_user_temp, width=20).grid(row=2, column=1, sticky='w', padx=5, pady=5)

    ttk.Label(qbt_frame, text="Password:").grid(row=2, column=2, sticky='w', padx=5, pady=5)
    ttk.Entry(qbt_frame, textvariable=qbt_pass_temp, show='*', width=10).grid(row=2, column=3, sticky='w', padx=5, pady=5)

    ttk.Checkbutton(qbt_frame, text="Verify SSL Certificate (Uncheck for self-signed certs)", variable=verify_ssl_temp).grid(row=3, column=0, columnspan=4, sticky='w', padx=5, pady=5)

    ttk.Label(qbt_frame, text="CA Cert (optional):").grid(row=4, column=0, sticky='w', padx=5, pady=5)
    ca_entry = ttk.Entry(qbt_frame, textvariable=ca_cert_temp, width=40)
    ca_entry.grid(row=4, column=1, columnspan=2, sticky='w', padx=5, pady=5)

    def browse_ca():
        path = filedialog.askopenfilename(title='Select CA certificate (PEM)', filetypes=[('PEM files','*.pem;*.crt;*.cer'), ('All files','*.*')])
        if path:
            ca_cert_temp.set(path)

    ttk.Button(qbt_frame, text='Browse...', command=browse_ca).grid(row=4, column=3, sticky='w', padx=5, pady=5)
    ttk.Label(qbt_frame, text="*Ensure WebUI is enabled in qBittorrent.").grid(row=7, column=0, columnspan=4, sticky='w', padx=5, pady=2)
    test_btn = ttk.Button(qbt_frame, text="Test Connection", command=lambda: qbt_api.test_qbittorrent_connection(qbt_protocol_temp, qbt_host_temp, qbt_port_temp, qbt_user_temp, qbt_pass_temp, verify_ssl_temp, ca_cert_temp))
    test_btn.grid(row=8, column=0, columnspan=4, pady=10)

    save_btn = ttk.Button(settings_win, text="Save All Settings", command=save_and_close, style='Accent.TButton')
    save_btn.pack(pady=10)


def setup_gui():
    config_set = config.load_config()
    root = tk.Tk()
    root.title("qBittorrent RSS Rules Sync")
    root.geometry("550x700")

    style = ttk.Style()
    style.theme_use('clam')
    root.configure(bg='white')
    style.configure('.', background='white')
    style.configure('TFrame', background='white')
    style.configure('TLabelFrame', background='white', bordercolor='#cccccc')
    style.configure('TLabel', background='white')
    style.configure('TCheckbutton', background='white', focuscolor='white')
    style.configure('Accent.TButton', foreground='white', background='#0078D4')

    current_year, current_season = get_current_anime_season()
    season_var = tk.StringVar(value=current_season)
    year_var = tk.StringVar(value=current_year)

    status_msg = f"Mode: {config.CONNECTION_MODE.upper()}. Ready to fetch titles."
    status_var = tk.StringVar(value=status_msg)
    global _APP_ROOT, _APP_STATUS_VAR, LISTBOX_WIDGET, LISTBOX_ITEMS
    _APP_ROOT = root
    _APP_STATUS_VAR = status_var

    if not config_set:
        status_var.set("🚨 CRITICAL: Please set qBittorrent credentials in Settings.")
        root.after(100, lambda: open_settings_window(root, status_var))

    main_frame = ttk.Frame(root, padding="15")
    main_frame.pack(fill='both', expand=True)

    top_config_frame = ttk.Frame(main_frame, padding="5")
    top_config_frame.pack(fill='x', pady=5)
    ttk.Label(top_config_frame, text="Season:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    season_dropdown = ttk.Combobox(top_config_frame, textvariable=season_var, values=["Winter", "Spring", "Summer", "Fall"], state="readonly", width=10)
    season_dropdown.grid(row=0, column=1, sticky='w', padx=5, pady=5)
    ttk.Label(top_config_frame, text="Year:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
    year_entry = ttk.Entry(top_config_frame, textvariable=year_var, width=10)
    year_entry.grid(row=0, column=3, sticky='w', padx=5, pady=5)
    settings_button = ttk.Button(top_config_frame, text="Settings", command=lambda: open_settings_window(root, status_var))
    settings_button.grid(row=0, column=4, sticky='e', padx=15)
    top_config_frame.grid_columnconfigure(4, weight=1)

    fetch_buttons_frame = ttk.Frame(main_frame)
    fetch_buttons_frame.pack(fill='x', pady=5)
    open_btn = ttk.Button(fetch_buttons_frame, text=" Open Config")
    open_btn.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
    refresh_btn = ttk.Button(fetch_buttons_frame, text="Refresh")
    refresh_btn.pack(side=tk.LEFT, fill='x', expand=True, padx=(5, 0))

    list_frame_container = ttk.LabelFrame(main_frame, text="Select Titles", padding="10")
    list_frame_container.pack(fill='both', expand=True, pady=10)
    ttk.Label(list_frame_container, text='Titles (use Ctrl/Shift to multi-select)', anchor='w').pack(fill='x', pady=(0,6))

    listbox = tk.Listbox(list_frame_container, selectmode='extended', activestyle='none')
    listbox.pack(side='left', fill='both', expand=True)
    scrollbar = ttk.Scrollbar(list_frame_container, orient='vertical', command=listbox.yview)
    scrollbar.pack(side='right', fill='y')
    listbox.configure(yscrollcommand=scrollbar.set)

    LISTBOX_WIDGET = listbox
    LISTBOX_ITEMS = []

    def _handle_vertical_scroll(units):
        try:
            if SCROLL_MODE == 'lines':
                LISTBOX_WIDGET.yview_scroll(units * SCROLL_LINES, 'units')
            else:
                try:
                    step = int((units * SCROLL_PIXELS) / 20)
                except Exception:
                    step = units
                LISTBOX_WIDGET.yview_scroll(step, 'units')
        except Exception:
            pass

    def _on_mousewheel_windows(event):
        try:
            raw_units = float(event.delta) / 120.0
        except Exception:
            raw_units = 0.0
        if SCROLL_MODE == 'lines':
            units = int(-raw_units)
        else:
            units = -raw_units * float(SCROLL_PIXELS)

    def _on_mousewheel_linux(event):
        if SCROLL_MODE == 'lines':
            if event.num == 4:
                _handle_vertical_scroll(-1)
            elif event.num == 5:
                _handle_vertical_scroll(1)
        else:
            if event.num == 4:
                _handle_vertical_scroll(-float(SCROLL_PIXELS))
            elif event.num == 5:
                _handle_vertical_scroll(float(SCROLL_PIXELS))

    def _bind_scroll(widget):
        try:
            widget.bind_all('<MouseWheel>', _on_mousewheel_windows, add='+')
            widget.bind_all('<Button-4>', _on_mousewheel_linux, add='+')
            widget.bind_all('<Button-5>', _on_mousewheel_linux, add='+')
        except Exception:
            pass

    def _unbind_scroll(widget):
        try:
            widget.unbind_all('<MouseWheel>')
            widget.unbind_all('<Button-4>')
            widget.unbind_all('<Button-5>')
        except Exception:
            pass

    def _on_enter(e):
        _bind_scroll(LISTBOX_WIDGET)

    def _on_leave(e):
        _unbind_scroll(LISTBOX_WIDGET)

    try:
        LISTBOX_WIDGET.bind('<Enter>', _on_enter)
        LISTBOX_WIDGET.bind('<Leave>', _on_leave)
    except Exception:
        pass

    load_rules_btn = ttk.Button(main_frame, text="View Existing Rules", command=lambda: handle_load_rules(root, status_var))
    load_rules_btn.pack(fill='x', pady=5)

    generate_btn = ttk.Button(main_frame, text="Generate/Sync Rules", command=lambda: dispatch_generation(root, season_var, year_entry, LISTBOX_WIDGET, status_var), style='Accent.TButton')
    generate_btn.pack(fill='x', pady=5)

    status_container = ttk.Frame(main_frame)
    status_container.pack(side='bottom', fill='x')

    _APP_SPINNER_LABEL = ttk.Label(status_container, text='', width=2, anchor='w')
    _APP_SPINNER_LABEL.pack(side='left', padx=(4,2), pady=2)

    status_bar = ttk.Label(status_container, textvariable=status_var, relief=tk.SUNKEN, anchor='w')
    status_bar.pack(side='left', fill='x', expand=True)

    root.mainloop()


def dispatch_generation(root, season_var, year_entry, list_frame, status_var):
    if not getattr(config, 'ALL_TITLES', None):
        messagebox.showwarning("Warning", "Please fetch titles first.")
        return

    selected_titles = []
    try:
        import tkinter as _tk
        if isinstance(list_frame, _tk.Listbox):
            global LISTBOX_ITEMS
            if not LISTBOX_ITEMS or list_frame.size() != len(LISTBOX_ITEMS):
                LISTBOX_ITEMS = []
                try:
                    list_frame.delete(0, 'end')
                except Exception:
                    pass
                try:
                    for media_type, items in config.ALL_TITLES.items():
                        header = f"--- {media_type.upper()} ({len(items)}) ---"
                        try:
                            list_frame.insert('end', header)
                        except Exception:
                            pass
                        LISTBOX_ITEMS.append(None)
                        for entry in items:
                            try:
                                node = entry.get('node', {}) if isinstance(entry, dict) else {}
                                title_text = node.get('title', str(entry))
                            except Exception:
                                title_text = str(entry)
                            try:
                                list_frame.insert('end', f"  {title_text}")
                            except Exception:
                                pass
                            LISTBOX_ITEMS.append((title_text, entry))
                except Exception:
                    pass

            sel = list_frame.curselection()
            for idx in sel:
                try:
                    mapped = LISTBOX_ITEMS[int(idx)]
                    if not mapped:
                        continue
                    title_text = mapped[0]
                    selected_titles.append(title_text)
                except Exception:
                    try:
                        lbl = list_frame.get(idx)
                        if lbl and not str(lbl).strip().startswith('---'):
                            selected_titles.append(str(lbl).strip())
                    except Exception:
                        pass
        else:
            messagebox.showwarning('Selection Error', 'Selection UI unsupported. Use the Listbox to select titles.')
            return
    except Exception:
        messagebox.showwarning('Selection Error', 'Failed to read selections from the UI.')
        return

    if not selected_titles:
        messagebox.showwarning("Warning", "Please select at least one title.")
        return

    rule_prefix = season_var.get()
    year = year_entry.get().strip()
    if not year.isdigit() or len(year) != 4:
        messagebox.showerror("Error", "Invalid year entered.")
        return

    generated = {}
    for title in selected_titles:
        sanitized_folder_name = title.replace(':', ' -').replace('/', '_').strip()
        rule_name = f"{rule_prefix} - {sanitized_folder_name}"
        save_path = os.path.join(config.DEFAULT_SAVE_PREFIX, f"{rule_prefix} {year}", sanitized_folder_name).replace('\\', '/')
        rule_def = create_qbittorrent_rule_def(rule_pattern=sanitized_folder_name, save_path=save_path, default_rss_feed=config.DEFAULT_RSS_FEED)
        generated[rule_name] = rule_def

    preview_and_edit_generated_rules(root, generated, config.CONNECTION_MODE, status_var)


__all__ = [
    'setup_gui', 'open_settings_window', 'handle_load_rules', 'dispatch_generation',
    'preview_and_edit_generated_rules', 'display_rules'
]
