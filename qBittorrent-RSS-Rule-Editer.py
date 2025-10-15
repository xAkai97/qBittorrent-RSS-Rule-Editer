import requests
import threading
import concurrent.futures
import atexit
import os
import json
from datetime import datetime
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, filedialog
from configparser import ConfigParser 
from qbittorrentapi import Client, APIConnectionError, Conflict409Error
"""Launcher for qbt_editor package.

This file is intentionally small: it imports the refactored application
logic from the `qbt_editor` package and starts the GUI. Keeping this
launcher preserves the original entrypoint and lets users run the app
exactly the same way as before.
"""

from qbt_editor import setup_gui, exit_handler
import sys

# Workaround: qbittorrent-api has a known issue where its Request.__del__ can
# raise an AttributeError during interpreter shutdown if internals have been
# partially cleaned up (e.g. missing _http_session). That shows up as
# "Exception ignored in: <function Request.__del__ ...>" in the console.
# Monkeypatch a safe __del__ that swallows such errors to avoid noisy output
# while keeping the rest of the library functional.
try:
    # Import the Request class from the library module and replace its __del__
    # with a no-op that safely ignores AttributeError and other teardown errors.
    from qbittorrentapi.request import Request as _QBRequest

    def _safe_request_del(self):
        try:
            # The original destructor attempts to initialize or access session
            # attributes; we avoid accessing any possibly-removed attributes.
            if hasattr(self, '_trigger_session_initialization'):
                try:
                    self._trigger_session_initialization()
                except Exception:
                    # Intentionally ignore any exceptions during teardown
                    pass
        except Exception:
            # Swallow everything to ensure no exception propagates from __del__
            pass

    # Apply the monkeypatch
    _QBRequest.__del__ = _safe_request_del
except Exception:
    # If anything goes wrong importing or patching, silently continue; this
    # only attempts to improve the shutdown behavior and is non-critical.
    pass


def create_qbittorrent_client(host: str, username: str, password: str, verify_ssl: bool):
    """Create a qbittorrentapi.Client in a way that's compatible with
    multiple versions of qbittorrent-api.

    Some older/newer versions accept a `verify_ssl` keyword. Others don't.
    We try the preferred signature first and fall back to creating the client
    without that kwarg. If verification is disabled, attempt to set the
    underlying requests session verify flag to False when possible.
    """
    try:
        # Preferred: pass verify_ssl if supported
        # If a CA cert path is available and verify_ssl is True, pass that through
        global QBT_CA_CERT
        if QBT_CA_CERT:
            # Some qbittorrent-api implementations accept 'verify_ssl' as True/False
            # and some accept a path (requests verify parameter). Try both.
            try:
                return Client(host=host, username=username, password=password, verify_ssl=QBT_CA_CERT if verify_ssl else False)
            except TypeError:
                return Client(host=host, username=username, password=password, verify_ssl=verify_ssl)
        else:
            return Client(host=host, username=username, password=password, verify_ssl=verify_ssl)
    except TypeError:
        # The installed qbittorrent-api doesn't accept verify_ssl kwarg.
        # Create client without it and try to disable verification on the
        # underlying requests session if verify_ssl is False.
        client = Client(host=host, username=username, password=password)
        if not verify_ssl:
            try:
                # Try a few possible attribute names for the internal session
                sess = getattr(client, '_http_session', None) or getattr(client, 'http_session', None) or getattr(client, '_session', None) or getattr(client, 'session', None) or getattr(client, 'requests_session', None)
                if sess is not None and hasattr(sess, 'verify'):
                    sess.verify = False
            except Exception:
                # Best-effort only; if it fails, we leave the client as-is and
                # let the call fail with a clear connection error later.
                pass
        return client
import sys # Import remains for general use

# ==============================================================================
# 0. CONFIGURATION & CREDENTIALS
# ==============================================================================
CONFIG_FILE = 'config.ini' 
OUTPUT_CONFIG_FILE_NAME = 'qbittorrent_rules.json' # Used for OFFLINE mode
CACHE_FILE = 'seasonal_cache.json' # NEW: Cache file name

# --- DEFAULT RULE SETTINGS (These are the values used inside qBittorrent) ---
DEFAULT_RSS_FEED = "https://subsplease.org/rss/?r=1080"
# NOTE: This path is for the Docker container's *host volume mount*, adjust if needed!
DEFAULT_SAVE_PREFIX = "/downloads/Anime/Web/" 
# --------------------------------------------------------------------------------

# Global variables (will be initialized later)
MAL_CLIENT_ID = None
QBT_PROTOCOL = None
QBT_HOST = None
QBT_PORT = None
QBT_USER = None
QBT_PASS = None
QBT_VERIFY_SSL = True # Global SSL flag
CONNECTION_MODE = 'online'
ALL_TITLES = {}
RAW_FETCHED_DATA = []  # Prevents NameError before fetching
QBT_CA_CERT = None

# Scrolling configuration: choose between 'lines' or 'pixels' scrolling.
# 'lines' behaves like discrete line-based scroll (good for keyboard/mouse
# wheel). 'pixels' gives finer control suitable for trackpads; mapping to
# canvas scroll units is best-effort since Tkinter's canvas scroll API
# primarily accepts 'units' and 'pages'.
SCROLL_MODE = 'lines'  # 'lines' or 'pixels'
# Amount to scroll when using line-based mode (units per wheel notch)
SCROLL_LINES = 3
# Amount to scale when using pixel-ish mode (rough mapping to scroll units)
SCROLL_PIXELS = 60

# ==============================================================================
# CONFIGURATION MANAGEMENT FUNCTIONS
# ==============================================================================

def load_config():
    """Loads configuration from config.ini."""
    global QBT_PROTOCOL, QBT_HOST, QBT_PORT, QBT_USER, QBT_PASS, CONNECTION_MODE, QBT_VERIFY_SSL
    config = ConfigParser()
    config.read(CONFIG_FILE)

    # Load QBT Config
    qbt_loaded = 'QBITTORRENT_API' in config
    if qbt_loaded:
        QBT_PROTOCOL = config['QBITTORRENT_API'].get('protocol', 'http')
        QBT_HOST = config['QBITTORRENT_API'].get('host', 'localhost')
        QBT_PORT = config['QBITTORRENT_API'].get('port', '8080')
        QBT_USER = config['QBITTORRENT_API'].get('username', '')
        QBT_PASS = config['QBITTORRENT_API'].get('password', '')
        CONNECTION_MODE = config['QBITTORRENT_API'].get('mode', 'online')
        # Load SSL setting (stored as string, converted to boolean)
        QBT_VERIFY_SSL = config['QBITTORRENT_API'].get('verify_ssl', 'True').lower() == 'true'
        # Optional CA certificate path for trusting self-signed certs
        global QBT_CA_CERT
        QBT_CA_CERT = config['QBITTORRENT_API'].get('ca_cert', '')
    else:
        QBT_PROTOCOL, QBT_HOST, QBT_PORT, QBT_USER, QBT_PASS = ('http', 'localhost', '8080', '', '')
        QBT_VERIFY_SSL = True
        CONNECTION_MODE = 'online'

    # Consider config 'set' when qBittorrent host/port are provided
    is_qbt_host_set = bool(QBT_HOST and QBT_PORT)
    return is_qbt_host_set

def save_config(protocol, host, port, user, password, mode, verify_ssl):
    """Saves general configuration to config.ini (MAL network removed)."""
    config = ConfigParser()

    config['QBITTORRENT_API'] = {
        'protocol': protocol,
        'host': host,
        'port': port,
        'username': user,
        'password': password,
        'mode': mode,
        'verify_ssl': str(verify_ssl),
        'ca_cert': '',
    }
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)

    global QBT_PROTOCOL, QBT_HOST, QBT_PORT, QBT_USER, QBT_PASS, CONNECTION_MODE, QBT_VERIFY_SSL
    QBT_PROTOCOL, QBT_HOST, QBT_PORT, QBT_USER, QBT_PASS, CONNECTION_MODE, QBT_VERIFY_SSL = (
        protocol, host, port, user, password, mode, verify_ssl
    )

    # Persist CA cert into the config file properly (update the file with provided value)
    try:
        cfg = ConfigParser()
        cfg.read(CONFIG_FILE)
        if 'QBITTORRENT_API' not in cfg:
            cfg['QBITTORRENT_API'] = {}
        cfg['QBITTORRENT_API']['ca_cert'] = QBT_CA_CERT or ''
        with open(CONFIG_FILE, 'w') as f:
            cfg.write(f)
    except Exception:
        pass

# Note: media-type persistence and per-media UI were removed. Related helpers and
# debounced save logic have been deleted for simplicity.

# ==============================================================================
# UTILITY FUNCTIONS 
# ==============================================================================

def create_qbittorrent_rule_def(rule_pattern, save_path):
    """Creates the rule definition dictionary for the qbittorrent-api or offline config."""
    return {
        "affectedFeeds": [DEFAULT_RSS_FEED],
        "assignedCategory": "Anime/Seasonal",
        "enabled": True,
        "mustContain": rule_pattern,
        "mustNotContain": "dub|batch",
        "useRegex": False,
        "savePath": save_path, 
        "torrentParams": {
            "category": "Anime/Seasonal",
            "save_path": save_path.replace("\\", "/"),
            "operating_mode": "AutoManaged",
            "ratio_limit": -2,
            "seeding_time_limit": -2,
        }
    }

def get_current_anime_season():
    """Determines current year and season (for default GUI values)."""
    now = datetime.now()
    year = now.year
    month = now.month
    
    if 1 <= month <= 3:
        season = "Winter"
    elif 4 <= month <= 6:
        season = "Spring"
    elif 7 <= month <= 9:
        season = "Summer"
    else:
        season = "Fall"
    
    return str(year), season

# ==============================================================================
# OFFLINE GENERATION (No change)
# ==============================================================================

def generate_offline_config(selected_titles, rule_prefix, year, status_var):
    """Writes the configuration to a local JSON file."""
    final_rules = {}
    
    for title in selected_titles:
        sanitized_folder_name = title.replace(':', ' -').replace('/', '_').strip()
        rule_name = f"{rule_prefix} - {sanitized_folder_name}"
        save_path_prefix = os.path.join(DEFAULT_SAVE_PREFIX, f"{rule_prefix} {year}")
        full_save_path = os.path.join(save_path_prefix, sanitized_folder_name)
        
        # Use backslashes for the 'savePath' field in the local config structure 
        # (matching your original format)
        full_save_path_local = full_save_path.replace('/', '\\') 
        
        rule_def = create_qbittorrent_rule_def(
            rule_pattern=sanitized_folder_name, 
            save_path=full_save_path_local
        )
        
        # When creating the final JSON object for file writing, the structure 
        # needs to match what qBittorrent expects when importing.
        final_rules[rule_name] = rule_def
        final_rules[rule_name]['savePath'] = full_save_path_local # Ensure backslashes are saved

    try:
        with open(OUTPUT_CONFIG_FILE_NAME, 'w', encoding='utf-8') as f:
            # We need to manually adjust paths for torrentParams for the local file write
            json_dump_rules = {}
            for name, rule in final_rules.items():
                rule['torrentParams']['save_path'] = rule['torrentParams']['save_path'].replace('\\', '/')
                json_dump_rules[name] = rule
                
            json.dump(json_dump_rules, f, indent=4)
        
        messagebox.showinfo("Success (Offline)", 
            f"The file '{OUTPUT_CONFIG_FILE_NAME}' has been created with {len(selected_titles)} rules.\n\nNext step: Import this JSON file into your qBittorrent RSS settings."
        )
        status_var.set(f"Config file generated: {OUTPUT_CONFIG_FILE_NAME}")

    except IOError as e:
        messagebox.showerror("File Error", f"Error writing file {OUTPUT_CONFIG_FILE_NAME}: {e}")
        status_var.set("Config generation failed.")

# ==============================================================================
# ONLINE SYNCHRONIZATION (No change)
# ==============================================================================

def sync_rules_to_qbittorrent_online(selected_titles, rule_prefix, year, root, status_var):
    """Connects directly to qBittorrent Web API and creates RSS rules."""
    
    if not QBT_USER or not QBT_PASS or not QBT_HOST or not QBT_PORT:
        messagebox.showerror("Error", "qBittorrent connection details are missing. Check Settings.")
        return

    full_host = f"{QBT_PROTOCOL}://{QBT_HOST}:{QBT_PORT}"
    status_var.set(f"Connecting to qBittorrent at {full_host}...")
    root.update()

    qbt = None
    try:
        # Determine verify argument for requests
        # NOTE: verify=True requires a valid certificate. verify=False bypasses check.
        verify_ssl_setting = QBT_VERIFY_SSL 
        
        # Create client using the standard verify argument for direct connection
        # This is the oldest, most compatible way to handle SSL verification.
        qbt = create_qbittorrent_client(host=full_host, username=QBT_USER, password=QBT_PASS, verify_ssl=verify_ssl_setting)
        qbt.auth_log_in()
    except APIConnectionError as e:
        messagebox.showerror("Connection Error", f"Failed to connect or authenticate to qBittorrent.\nDetails: {e}")
        status_var.set("Synchronization failed.")
        return
    except Exception as e:
        messagebox.showerror("Login Error", f"qBittorrent Login Failed. Check credentials.\nDetails: {e}")
        status_var.set("Synchronization failed.")
        return

    # Synchronization Logic
    try:
        feed_path = "Anime Feeds/" + DEFAULT_RSS_FEED.split('//')[1].split('/')[0]
        try:
            qbt.rss_add_feed(url=DEFAULT_RSS_FEED, item_path=feed_path)
            qbt.rss_refresh_item(item_path=feed_path)
        except Conflict409Error:
            pass # Feed already exists

        successful_rules = 0
        for title in selected_titles:
            sanitized_folder_name = title.replace(':', ' -').replace('/', '_').strip()
            rule_name = f"{rule_prefix} - {sanitized_folder_name}"
            # Construct the save path expected by the Docker volume mount (Unix path)
            save_path = os.path.join(DEFAULT_SAVE_PREFIX, f"{rule_prefix} {year}", sanitized_folder_name).replace('\\', '/')
            
            rule_def = create_qbittorrent_rule_def(
                rule_pattern=sanitized_folder_name, 
                save_path=save_path
            )
            # The API call only needs the key/value pairs from the rule_def
            qbt.rss_set_rule(rule_name=rule_name, rule_def=rule_def)
            successful_rules += 1

        messagebox.showinfo("Success (Online)", 
            f"Successfully synchronized {successful_rules} rules to qBittorrent.\n\nAll rules are now active in your remote client."
        )
        status_var.set(f"Synchronization complete. {successful_rules} rules set.")

    except Exception as e:
        messagebox.showerror("Sync Error", f"An error occurred during rule synchronization: {e}")
        status_var.set("Synchronization failed.")
    finally:
        # Relying on core Python garbage collection now.
        pass 

# ==============================================================================
# MAIN GENERATION DISPATCHER (No change)
# ==============================================================================

def dispatch_generation(root, season_var, year_entry, list_frame, status_var):
    """
    Checks the selected connection mode and dispatches to the correct function.
    """
    # Check if we have fetched data at all
    if not ALL_TITLES:
        messagebox.showwarning("Warning", "Please fetch titles first.")
        return

    selected_titles = []
    # If the UI is the Listbox, map selected indices to underlying entries using LISTBOX_ITEMS.
    try:
        import tkinter as _tk
        if isinstance(list_frame, _tk.Listbox):
            # Ensure the listbox is populated from ALL_TITLES if needed
            try:
                global LISTBOX_ITEMS
                # If sizes mismatch, rebuild mapping
                if not LISTBOX_ITEMS or list_frame.size() != len(LISTBOX_ITEMS):
                    # Build mapping: None for header rows, (title, entry) for title rows
                    def populate_listbox_from_all_titles(lb):
                        global LISTBOX_ITEMS
                        LISTBOX_ITEMS = []
                        try:
                            lb.delete(0, 'end')
                        except Exception:
                            pass
                        try:
                            for media_type, items in ALL_TITLES.items():
                                header = f"--- {media_type.upper()} ({len(items)}) ---"
                                try:
                                    lb.insert('end', header)
                                except Exception:
                                    pass
                                LISTBOX_ITEMS.append(None)  # header placeholder
                                for entry in items:
                                    try:
                                        node = entry.get('node', {}) if isinstance(entry, dict) else {}
                                        title_text = node.get('title', str(entry))
                                    except Exception:
                                        title_text = str(entry)
                                    try:
                                        lb.insert('end', f"  {title_text}")
                                    except Exception:
                                        pass
                                    LISTBOX_ITEMS.append((title_text, entry))
                        except Exception:
                            pass

                    populate_listbox_from_all_titles(list_frame)

                sel = list_frame.curselection()
                for idx in sel:
                    try:
                        mapped = LISTBOX_ITEMS[int(idx)]
                        if not mapped:
                            continue
                        # mapped is (title_text, entry)
                        title_text = mapped[0]
                        selected_titles.append(title_text)
                    except Exception:
                        # fallback: try to read displayed label
                        try:
                            lbl = list_frame.get(idx)
                            if lbl and not str(lbl).strip().startswith('---'):
                                selected_titles.append(str(lbl).strip())
                        except Exception:
                            pass
            except Exception:
                pass
        else:
            # Unsupported selection UI - request user to use Listbox
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

    # Build initial generated rules dict (name -> rule_def)
    generated = {}
    for title in selected_titles:
        sanitized_folder_name = title.replace(':', ' -').replace('/', '_').strip()
        rule_name = f"{rule_prefix} - {sanitized_folder_name}"
        save_path = os.path.join(DEFAULT_SAVE_PREFIX, f"{rule_prefix} {year}", sanitized_folder_name).replace('\\', '/')
        rule_def = create_qbittorrent_rule_def(rule_pattern=sanitized_folder_name, save_path=save_path)
        generated[rule_name] = rule_def

    # Open a preview/editor for the generated rules before applying
    preview_and_edit_generated_rules(root, generated, CONNECTION_MODE, status_var)

def test_qbittorrent_connection(protocol_var, host_var, port_var, user_var, pass_var, verify_ssl_var, ca_cert_var=None):
    """Attempts to connect and log in to qBittorrent using temporary values.

    First tries qbittorrent-api client, then falls back to a manual requests
    login/version check so we can explicitly pass a CA file or disable
    verification when needed.
    """
    protocol = protocol_var.get().strip()
    host = host_var.get().strip()
    port = port_var.get().strip()
    user = user_var.get().strip()
    password = pass_var.get().strip()
    verify_ssl = verify_ssl_var.get() # Get boolean value

    # Resolve CA cert (prefer passed var, fall back to global)
    ca_cert = None
    if ca_cert_var is not None:
        try:
            ca_cert = ca_cert_var.get().strip() or None
        except Exception:
            ca_cert = None
    else:
        global QBT_CA_CERT
        ca_cert = QBT_CA_CERT

    if not host or not port:
        messagebox.showwarning("Test Failed", "Host and Port cannot be empty.")
        return

    full_host = f"{protocol}://{host}:{port}"

    # Try library client first
    try:
        verify_arg = ca_cert if (ca_cert and verify_ssl) else verify_ssl
        qbt = create_qbittorrent_client(host=full_host, username=user, password=password, verify_ssl=verify_arg)
        qbt.auth_log_in()
        app_version = qbt.app_version
        messagebox.showinfo("Test Success", f"Successfully connected to qBittorrent!\nProtocol: {protocol.upper()}\nVerification: {'ON' if verify_ssl else 'OFF'}\nVersion: {app_version}")
        return
    except requests.exceptions.SSLError:
        messagebox.showerror("Test Failed", "SSL Error: Certificate verification failed. Try providing a CA cert or unchecking 'Verify SSL Certificate' in settings.")
        return
    except APIConnectionError:
        # Fall through to manual requests check
        pass
    except Exception:
        pass

    # Manual requests-based fallback (explicit TLS control)
    try:
        session = requests.Session()
        verify_param = ca_cert if (ca_cert and verify_ssl) else verify_ssl

        login_url = f"{full_host}/api/v2/auth/login"
        resp = session.post(login_url, data={"username": user, "password": password}, timeout=10, verify=verify_param)
        if resp.status_code not in (200, 201) or resp.text.strip().lower() not in ('ok.', 'ok'):
            messagebox.showerror("Test Failed", "Login failed. Check Username/Password and try again.")
            return

        version_url = f"{full_host}/api/v2/app/version"
        vresp = session.get(version_url, timeout=10, verify=verify_param)
        if vresp.status_code == 200:
            app_version = vresp.text.strip()
            messagebox.showinfo("Test Success", f"Successfully connected to qBittorrent!\nProtocol: {protocol.upper()}\nVerification: {'ON' if verify_ssl else 'OFF'}\nVersion: {app_version}")
            return
        else:
            messagebox.showerror("Test Failed", "Authenticated but failed to read qBittorrent version. Check permissions.")
            return

    except requests.exceptions.SSLError:
        messagebox.showerror("Test Failed", "SSL Error: Certificate verification failed. Provide a CA cert or disable verification.")
    except requests.exceptions.ConnectionError:
        messagebox.showerror("Test Failed", "Connection refused. Check Host/Port/Protocol and ensure qBittorrent WebUI is running.")
    except Exception as e:
        messagebox.showerror("Test Failed", f"Login or connection error. Check Username/Password.\nDetails: {e}")


def fetch_online_rules(root):
    """Connects to qBittorrent and fetches existing RSS rules."""
    if not QBT_USER or not QBT_PASS or not QBT_HOST or not QBT_PORT:
        messagebox.showerror("Error", "qBittorrent connection details are missing. Check Settings.")
        return None

    full_host = f"{QBT_PROTOCOL}://{QBT_HOST}:{QBT_PORT}" # Use protocol here

    qbt = None
    lib_exc = None
    try:
        # First try using the library client (preferred)
        verify_ssl_setting = QBT_VERIFY_SSL
        qbt = create_qbittorrent_client(host=full_host, username=QBT_USER, password=QBT_PASS, verify_ssl=verify_ssl_setting)
        qbt.auth_log_in()
        # Fetch rules. rss_rules() returns a dictionary of rules.
        rules_dict = qbt.rss_rules()
        return rules_dict
    except Exception as e:
        # Keep the library exception for debugging if fallback also fails
        lib_exc = e

    # Fall back to manual requests-based retrieval so we can explicitly
    # control TLS verification and authentication.
    try:
        session = requests.Session()
        verify_param = QBT_CA_CERT if (QBT_CA_CERT and QBT_VERIFY_SSL) else QBT_VERIFY_SSL

        # Login via API
        login_url = f"{full_host}/api/v2/auth/login"
        lresp = session.post(login_url, data={"username": QBT_USER, "password": QBT_PASS}, timeout=10, verify=verify_param)
        if lresp.status_code not in (200, 201) or lresp.text.strip().lower() not in ('ok.', 'ok'):
            # Provide more context (status + body snippet) for easier debugging
            body_snippet = (lresp.text or '')[:300]
            messagebox.showerror("Connection Error", f"Failed to authenticate to qBittorrent. Check credentials.\nHTTP {lresp.status_code}: {body_snippet}")
            return None

        # Fetch RSS rules
        rules_url = f"{full_host}/api/v2/rss/rules"
        rresp = session.get(rules_url, timeout=10, verify=verify_param)
        if rresp.status_code != 200:
            body_snippet = (rresp.text or '')[:300]
            messagebox.showerror("Connection Error", f"Failed to fetch RSS rules: HTTP {rresp.status_code}\n{body_snippet}")
            return None

        data = rresp.json()
        # Normalize into a dict { rule_name: rule_data }
        if isinstance(data, dict):
            rules_dict = data
        elif isinstance(data, list):
            rules_dict = {}
            for item in data:
                # Try common name keys
                name = None
                if isinstance(item, dict):
                    name = item.get('ruleName') or item.get('name') or item.get('title') or item.get('rule') or item.get('rule_name')
                if not name:
                    name = str(item)
                rules_dict[name] = item
        else:
            messagebox.showerror("Connection Error", "Unexpected RSS rules response format.")
            return None

        return rules_dict
    except requests.exceptions.SSLError:
        messagebox.showerror("Connection Error", "SSL Error: Certificate verification failed. Try unchecking 'Verify SSL Certificate' in settings or provide CA cert.")
    except requests.exceptions.ConnectionError as e:
        # Include underlying exception message to help diagnose networking issues
        messagebox.showerror("Connection Error", f"Failed to connect to qBittorrent. Check credentials and server status.\nDetails: {e}")
    except Exception as e:
        # Show both the fallback exception and the original library exception (if any)
        extra = f"\nLibrary client error: {repr(lib_exc)}" if lib_exc is not None else ""
        messagebox.showerror("Error", f"An unexpected error occurred while fetching RSS rules: {e}{extra}")

    return None

def load_offline_rules(root):
    """Opens a file dialog and loads existing rules from a local JSON file."""
    filepath = filedialog.askopenfilename(
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")],
        title="Open qBittorrent Rules File"
    )
    if not filepath:
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            rules_dict = json.load(f)
        return rules_dict
    except json.JSONDecodeError:
        messagebox.showerror("File Error", "Invalid JSON format in file.")
    except Exception as e:
        messagebox.showerror("File Error", f"Error reading file: {e}")
    return None


def preview_and_edit_generated_rules(root, rules_dict, connection_mode, status_var):
    """Show a preview of generated rules where the user can edit before applying.

    rules_dict is a mutable dict of rule_name -> rule_def.
    connection_mode is 'online' or 'offline'.
    """
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
        # If offline mode, export; if online, attempt to apply
        if connection_mode == 'offline':
            export_rules()
            preview_win.destroy()
            status_var.set('Exported generated rules (offline).')
            return

        # Online: attempt to connect and apply
        try:
            verify_arg = QBT_CA_CERT if (QBT_CA_CERT and QBT_VERIFY_SSL) else QBT_VERIFY_SSL
            full_host = f"{QBT_PROTOCOL}://{QBT_HOST}:{QBT_PORT}"
            qbt = create_qbittorrent_client(host=full_host, username=QBT_USER, password=QBT_PASS, verify_ssl=verify_arg)
            qbt.auth_log_in()
            applied = 0
            for name, data in list(rules_dict.items()):
                rule_def = {
                    'affectedFeeds': data.get('affectedFeeds', [DEFAULT_RSS_FEED]),
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
                except Conflict409Error:
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
    """Creates a pop-up window to display and edit the loaded rules.

    The window shows rules in a Treeview with columns for Enabled, Name,
    Match Pattern, and Save Path. Selecting a rule and clicking Edit will
    open a small dialog to edit those fields. Changes update the in-memory
    rules_dict so they can be saved or applied.
    """
    if not rules_dict:
        messagebox.showinfo("Info", f"No rules found from {source_name}.")
        return

    # Keep a mutable reference to the rules dict so edits modify caller data
    rules = rules_dict

    display_win = tk.Toplevel(root)
    display_win.title(f"Existing Rules - Source: {source_name}")
    display_win.transient(root)
    display_win.grab_set()

    # Create Treeview
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

    # Populate tree
    for name, data in rules.items():
        en = data.get('enabled', True)
        must = data.get('mustContain', data.get('must_contain', ''))
        sp = data.get('savePath', data.get('save_path', ''))
        tree.insert('', 'end', iid=name, values=(str(bool(en)), name, must, sp))

    # Action buttons frame
    btn_frame = ttk.Frame(display_win)
    btn_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=(0,10))

    def edit_selected():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning('Edit Rule', 'Please select a rule to edit.')
            return
        key = sel[0]
        entry = rules.get(key, {})

        # Open edit dialog
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
            # Update dict: if name changed, move the entry key
            new_entry = dict(entry)  # copy
            new_entry['enabled'] = bool(enabled_var.get())
            # Keep both naming conventions to be safe for later export
            new_entry['mustContain'] = match_var.get()
            new_entry['savePath'] = save_var.get()

            if new_name != key:
                # Remove old, insert new
                rules.pop(key, None)
                rules[new_name] = new_entry
                # Update tree: remove old row and insert new
                tree.delete(key)
                tree.insert('', 'end', iid=new_name, values=(str(bool(new_entry['enabled'])), new_name, new_entry['mustContain'], new_entry['savePath']))
            else:
                rules[key] = new_entry
                tree.item(key, values=(str(bool(new_entry['enabled'])), key, new_entry['mustContain'], new_entry['savePath']))

            dlg.destroy()

        ttk.Button(dlg, text='Apply', command=apply_changes).grid(row=4, column=0, padx=10, pady=10)
        ttk.Button(dlg, text='Cancel', command=dlg.destroy).grid(row=4, column=1, padx=10, pady=10)

    def export_rules():
        # Export current in-memory rules to JSON file
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
        # Helper to apply current rules dict to qBittorrent online using existing sync logic
        # This will attempt to connect and call qbt.rss_set_rule for each rule
        if not rules:
            messagebox.showwarning('Apply', 'No rules to apply')
            return

        # Convert rules into a list of tuples for processing
        apply_list = []
        for name, data in rules.items():
            apply_list.append((name, data))

        # Ask user for confirmation
        if not messagebox.askyesno('Apply Online', f'Apply {len(apply_list)} rules to qBittorrent now?'):
            return

        # Attempt to connect and apply
        try:
            verify_arg = QBT_CA_CERT if (QBT_CA_CERT and QBT_VERIFY_SSL) else QBT_VERIFY_SSL
            full_host = f"{QBT_PROTOCOL}://{QBT_HOST}:{QBT_PORT}"
            qbt = create_qbittorrent_client(host=full_host, username=QBT_USER, password=QBT_PASS, verify_ssl=verify_arg)
            qbt.auth_log_in()
            applied = 0
            for name, data in apply_list:
                rule_def = {
                    'affectedFeeds': data.get('affectedFeeds', [DEFAULT_RSS_FEED]),
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
                except Conflict409Error:
                    # Try to overwrite by deleting then setting
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

    # Make the window resize-friendly
    display_win.columnconfigure(0, weight=1)
    display_win.rowconfigure(0, weight=1)
    
def handle_load_rules(root, status_var):
    """Dispatches rule loading based on the current connection mode."""
    # Reload configuration so any recently saved settings are applied
    load_config()
    status_var.set("Loading existing rules...")
    rules_dict = None
    source_name = ""

    if CONNECTION_MODE == 'online':
        rules_dict = fetch_online_rules(root)
        source_name = f"Online ({QBT_PROTOCOL}://{QBT_HOST}:{QBT_PORT})"
    else: # 'offline'
        rules_dict = load_offline_rules(root)
        source_name = "Local JSON File"
    
    if rules_dict is not None:
        display_rules(root, rules_dict, source_name)
        status_var.set(f"Successfully loaded {len(rules_dict)} existing rules from {source_name}.")
    else:
        status_var.set(f"Failed to load existing rules in {CONNECTION_MODE} mode.")


# ==============================================================================
# SETTINGS WINDOW
# ==============================================================================

def open_settings_window(root, status_var):
    """Creates a new top-level window for changing the configuration."""
    settings_win = tk.Toplevel(root)
    settings_win.title("Settings - Configuration")
    settings_win.transient(root)
    settings_win.grab_set()

    # --- Temporary variables for the settings window ---
    qbt_protocol_temp = tk.StringVar(value=QBT_PROTOCOL)
    qbt_host_temp = tk.StringVar(value=QBT_HOST)
    qbt_port_temp = tk.StringVar(value=QBT_PORT)
    qbt_user_temp = tk.StringVar(value=QBT_USER)
    qbt_pass_temp = tk.StringVar(value=QBT_PASS)
    mode_temp = tk.StringVar(value=CONNECTION_MODE)
    verify_ssl_temp = tk.BooleanVar(value=QBT_VERIFY_SSL) # SSL verification flag
    ca_cert_temp = tk.StringVar(value=QBT_CA_CERT or "")
    
    # Media type filtering has been removed; keep an empty placeholder
    media_type_vars = {}

    def save_and_close():
        """Collect values from settings UI, update globals, persist, and close window."""
    # MAL client ID removed; ignore
        new_qbt_protocol = qbt_protocol_temp.get().strip()
        new_qbt_host = qbt_host_temp.get().strip()
        new_qbt_port = qbt_port_temp.get().strip()
        new_qbt_user = qbt_user_temp.get().strip()
        new_qbt_pass = qbt_pass_temp.get().strip()
        new_mode = mode_temp.get()
        new_verify_ssl = verify_ssl_temp.get()  # Get SSL boolean value
        new_ca_cert = ca_cert_temp.get().strip()

        if not new_qbt_host or not new_qbt_port:
            messagebox.showwarning("Warning", "Host and Port are required.")
            return

        # Update global CA cert path before saving
        global QBT_CA_CERT
        QBT_CA_CERT = new_ca_cert or None

    
    # --- Connection Mode Frame ---
    mode_frame = ttk.LabelFrame(settings_win, text="Connection Mode", padding=10)
    mode_frame.pack(fill='x', padx=10, pady=10)
    ttk.Label(mode_frame, text="Choose how to apply the rules:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    
    ttk.Radiobutton(mode_frame, text="Online (Direct API Sync)", variable=mode_temp, value='online').grid(row=1, column=0, sticky='w', padx=5)
    ttk.Radiobutton(mode_frame, text="Offline (Generate JSON File)", variable=mode_temp, value='offline').grid(row=1, column=1, sticky='w', padx=5)

    # --- qBittorrent API Frame ---
    qbt_frame = ttk.LabelFrame(settings_win, text="qBittorrent Web UI API", padding=10)
    qbt_frame.pack(fill='x', padx=10, pady=10)
    
    # Protocol Choice
    ttk.Label(qbt_frame, text="Protocol:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    protocol_dropdown = ttk.Combobox(qbt_frame, textvariable=qbt_protocol_temp, 
                                     values=['http', 'https'], state='readonly', width=6)
    protocol_dropdown.grid(row=0, column=1, sticky='w', padx=5, pady=5)

    ttk.Label(qbt_frame, text="Host (IP/DNS):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
    ttk.Entry(qbt_frame, textvariable=qbt_host_temp, width=20).grid(row=1, column=1, sticky='w', padx=5, pady=5)

    ttk.Label(qbt_frame, text="Port:").grid(row=1, column=2, sticky='w', padx=5, pady=5)
    ttk.Entry(qbt_frame, textvariable=qbt_port_temp, width=10).grid(row=1, column=3, sticky='w', padx=5, pady=5)

    ttk.Label(qbt_frame, text="Username:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
    ttk.Entry(qbt_frame, textvariable=qbt_user_temp, width=20).grid(row=2, column=1, sticky='w', padx=5, pady=5)

    ttk.Label(qbt_frame, text="Password:").grid(row=2, column=2, sticky='w', padx=5, pady=5)
    ttk.Entry(qbt_frame, textvariable=qbt_pass_temp, show='*', width=10).grid(row=2, column=3, sticky='w', padx=5, pady=5)
    
    # SSL Verification Checkbox
    ttk.Checkbutton(qbt_frame, text="Verify SSL Certificate (Uncheck for self-signed certs)", 
                    variable=verify_ssl_temp).grid(row=3, column=0, columnspan=4, sticky='w', padx=5, pady=5)

    # CA Certificate path (optional)
    ttk.Label(qbt_frame, text="CA Cert (optional):").grid(row=4, column=0, sticky='w', padx=5, pady=5)
    ca_entry = ttk.Entry(qbt_frame, textvariable=ca_cert_temp, width=40)
    ca_entry.grid(row=4, column=1, columnspan=2, sticky='w', padx=5, pady=5)

    def browse_ca():
        path = filedialog.askopenfilename(title='Select CA certificate (PEM)', filetypes=[('PEM files','*.pem;*.crt;*.cer'), ('All files','*.*')])
        if path:
            ca_cert_temp.set(path)

    ttk.Button(qbt_frame, text='Browse...', command=browse_ca).grid(row=4, column=3, sticky='w', padx=5, pady=5)

    # Move the helper label down so it doesn't overlap the CA cert row
    ttk.Label(qbt_frame, text="*Ensure WebUI is enabled in qBittorrent.").grid(row=7, column=0, columnspan=4, sticky='w', padx=5, pady=2)
    # Test Connection Button (placed below helper label) - move down one row to avoid overlap
    test_btn = ttk.Button(qbt_frame, text="Test Connection", 
                          command=lambda: test_qbittorrent_connection(
                              qbt_protocol_temp, qbt_host_temp, qbt_port_temp, qbt_user_temp, qbt_pass_temp, verify_ssl_temp, ca_cert_temp
                          ))
    test_btn.grid(row=8, column=0, columnspan=4, pady=10)


    # --- Save Button ---
    save_btn = ttk.Button(settings_win, text="Save All Settings", command=save_and_close, style='Accent.TButton')
    save_btn.pack(pady=10)

# ==============================================================================
# GUI SETUP (Tkinter)
# ==============================================================================

def setup_gui():
    config_set = load_config()
    
    root = tk.Tk()
    root.title("qBittorrent RSS Rules Sync")
    
    # Set a larger default window size for better list viewing
    root.geometry("550x700") 
    
    # --- Style Configuration for White/High-Contrast GUI ---
    style = ttk.Style()
    style.theme_use('clam')
    
    # Configure root window and frames to be white
    root.configure(bg='white')
    style.configure('.', background='white')
    style.configure('TFrame', background='white')
    style.configure('TLabelFrame', background='white', bordercolor='#cccccc')
    style.configure('TLabel', background='white')
    style.configure('TCheckbutton', background='white', focuscolor='white')
    
    # Accent button style remains
    style.configure('Accent.TButton', foreground='white', background='#0078D4')
    
    current_year, current_season = get_current_anime_season()
    season_var = tk.StringVar(value=current_season)
    year_var = tk.StringVar(value=current_year)
    
    status_msg = f"Mode: {CONNECTION_MODE.upper()}. Ready to fetch titles."
    status_var = tk.StringVar(value=status_msg)
    # Expose root and status var to save/flush callbacks so they can show a brief message
    global _APP_ROOT, _APP_STATUS_VAR
    _APP_ROOT = root
    _APP_STATUS_VAR = status_var
    
    # --- Open settings window immediately if config is missing ---
    if not config_set:
         status_var.set("🚨 CRITICAL: Please set qBittorrent credentials in Settings.")
         # Defer the call until the main window is fully loaded
         root.after(100, lambda: open_settings_window(root, status_var))


    # --- Main Frame ---
    main_frame = ttk.Frame(root, padding="15")
    main_frame.pack(fill='both', expand=True)
    
    # --- Top Configuration Bar (Simplified) ---
    top_config_frame = ttk.Frame(main_frame, padding="5")
    top_config_frame.pack(fill='x', pady=5)
    
    ttk.Label(top_config_frame, text="Season:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    season_dropdown = ttk.Combobox(top_config_frame, textvariable=season_var, 
                                   values=["Winter", "Spring", "Summer", "Fall"], state="readonly", width=10)
    season_dropdown.grid(row=0, column=1, sticky='w', padx=5, pady=5)
    
    ttk.Label(top_config_frame, text="Year:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
    year_entry = ttk.Entry(top_config_frame, textvariable=year_var, width=10)
    year_entry.grid(row=0, column=3, sticky='w', padx=5, pady=5)
    
    # Settings Button
    settings_button = ttk.Button(top_config_frame, text="Settings", 
                                 command=lambda: open_settings_window(root, status_var))
    settings_button.grid(row=0, column=4, sticky='e', padx=15)
    top_config_frame.grid_columnconfigure(4, weight=1)

    # --- Fetch and Refresh Buttons (moved above Select Titles) ---
    fetch_buttons_frame = ttk.Frame(main_frame)
    fetch_buttons_frame.pack(fill='x', pady=5)

    # Primary Fetch Button (Uses Cache if available)
    # list_frame will be created below; we capture a lambda that references it later via closure.
    open_btn = ttk.Button(fetch_buttons_frame, text=" Open Config")
    open_btn.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))

    # Secondary Refresh Button
    refresh_btn = ttk.Button(fetch_buttons_frame, text="Refresh")
    refresh_btn.pack(side=tk.LEFT, fill='x', expand=True, padx=(5, 0))

    # --- Anime List Area (Scrollable Frame) ---
    list_frame_container = ttk.LabelFrame(main_frame, text="Select Titles", padding="10")
    list_frame_container.pack(fill='both', expand=True, pady=10)

    # Tabbed selector removed: the app now uses a single Listbox area to show
    # discovered titles. Keep a small header label for clarity.
    ttk.Label(list_frame_container, text='Titles (use Ctrl/Shift to multi-select)', anchor='w').pack(fill='x', pady=(0,6))

    
    # Use a simple Listbox for selection
    listbox = tk.Listbox(list_frame_container, selectmode='extended', activestyle='none')
    listbox.pack(side='left', fill='both', expand=True)

    scrollbar = ttk.Scrollbar(list_frame_container, orient='vertical', command=listbox.yview)
    scrollbar.pack(side='right', fill='y')
    listbox.configure(yscrollcommand=scrollbar.set)

    # Expose the listbox globally for other functions
    global LISTBOX_WIDGET, LISTBOX_ITEMS
    LISTBOX_WIDGET = listbox
    LISTBOX_ITEMS = []

    # --- Enable mouse-wheel scrolling when pointer is over the canvas/list area ---
    # Many users expect the mouse wheel or trackpad to scroll the list when
    # hovering anywhere over it. Tk's default behavior only routes wheel
    # events to the widget directly under the pointer in some setups, and on
    # Windows the scroll events sometimes only work when over the scrollbar.
    # We bind enter/leave to attach the appropriate wheel events to the
    # canvas so scrolling works reliably across platforms.

    def _handle_vertical_scroll(units):
        try:
            if SCROLL_MODE == 'lines':
                # 'units' uses integer steps; multiply by SCROLL_LINES
                LISTBOX_WIDGET.yview_scroll(units * SCROLL_LINES, 'units')
            else:
                # Pixel-precise scrolling: map a pixel delta into a fractional
                # movement across the total scrollable height and use
                # canvas.yview_moveto to move by that fraction. We accept
                # 'units' here as a pixel-like delta (can be fractional).
                try:
                    # Fallback to integer scroll if precise pixel movement is needed
                    try:
                        step = int((units * SCROLL_PIXELS) / 20)
                    except Exception:
                        step = units
                    LISTBOX_WIDGET.yview_scroll(step, 'units')
                except Exception:
                    try:
                        step = int((units * SCROLL_PIXELS) / 20)
                    except Exception:
                        step = units
                    LISTBOX_WIDGET.yview_scroll(step, 'units')
        except Exception:
            pass

    def _on_mousewheel_windows(event):
        # On Windows, event.delta is multiples of 120 (positive up)
        try:
            raw_units = float(event.delta) / 120.0
        except Exception:
            raw_units = 0.0
        # For 'lines' mode we expect integer notches; for 'pixels' mode map
        # the raw_units to SCROLL_PIXELS per notch.
        if SCROLL_MODE == 'lines':
            units = int(-raw_units)
        else:
            # Map to pixels (negative because event.delta positive is up)
            units = -raw_units * float(SCROLL_PIXELS)


    def _on_mousewheel_mac(event):
        # On macOS, event.delta may be small; treat it as 1 or -1 per notch
        try:
            raw_units = float(event.delta)
        except Exception:
            raw_units = 0.0

        if SCROLL_MODE == 'lines':
            units = int(-raw_units)
        else:
            # macOS deltas are often smaller; scale them into pixel delta
            units = -raw_units * float(SCROLL_PIXELS) / 3.0


    def _on_mousewheel_linux(event):
        # On X11, Button-4 = vertical up, Button-5 = vertical down
        # Some environments emit Button-6/7 for horizontal scrolling
        if SCROLL_MODE == 'lines':
            if event.num == 4:
                _handle_vertical_scroll(-1)
            elif event.num == 5:
                _handle_vertical_scroll(1)
        else:
            # Pixel mode: map button clicks to pixel deltas
            if event.num == 4:
                _handle_vertical_scroll(-float(SCROLL_PIXELS))
            elif event.num == 5:
                _handle_vertical_scroll(float(SCROLL_PIXELS))


    def _bind_scroll(widget):
        # Bind platform-appropriate events to the given widget
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

    # When the pointer enters the canvas area, bind the wheel to scroll it.
    # When it leaves, unbind to avoid interfering with other widgets.
    def _on_enter(e):
        _bind_scroll(LISTBOX_WIDGET)

    def _on_leave(e):
        _unbind_scroll(LISTBOX_WIDGET)

    # Bind enter/leave on the listbox so scrolling works when mouse is over it
    try:
        LISTBOX_WIDGET.bind('<Enter>', _on_enter)
        LISTBOX_WIDGET.bind('<Leave>', _on_leave)
    except Exception:
        pass

    # --- Load Rules Button ---
    load_rules_btn = ttk.Button(main_frame, text="View Existing Rules", 
                                command=lambda: handle_load_rules(root, status_var))
    load_rules_btn.pack(fill='x', pady=5)
    
    # --- Generation/Synchronization Button ---
    generate_btn = ttk.Button(main_frame, text="Generate/Sync Rules", 
                              command=lambda: dispatch_generation(
                                  root, season_var, year_entry, LISTBOX_WIDGET, status_var
                              ), style='Accent.TButton')
    generate_btn.pack(fill='x', pady=5)
    
    # --- Status Bar + Spinner ---
    status_container = ttk.Frame(main_frame)
    status_container.pack(side='bottom', fill='x')

    # Spinner label (small) on the left
    _APP_SPINNER_LABEL = ttk.Label(status_container, text='', width=2, anchor='w')
    _APP_SPINNER_LABEL.pack(side='left', padx=(4,2), pady=2)

    status_bar = ttk.Label(status_container, textvariable=status_var, relief=tk.SUNKEN, anchor='w')
    status_bar.pack(side='left', fill='x', expand=True)

    root.mainloop()

if __name__ == "__main__":
    
    # Define a custom exit handler that suppresses the known bug
    # Apply the package-provided exit handler to suppress a noisy
    # qbittorrent-api shutdown AttributeError when present.
    try:
        exit_handler()
    except Exception:
        # Best-effort: continue even if the handler can't be set
        pass

    # Start the GUI
    setup_gui()
