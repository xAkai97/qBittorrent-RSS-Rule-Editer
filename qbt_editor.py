import json
import os
import sys
import threading
import time
import tkinter as tk
import typing
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    import requests
except ImportError:
    requests = None

try:
    from qbittorrentapi import APIConnectionError, Client, Conflict409Error
except ImportError:
    Client = None
    class APIConnectionError(Exception):
        pass
    class Conflict409Error(Exception):
        pass


# ==================== Custom Exception Classes ====================
class QBittorrentConnectionError(Exception):
    """Raised when connection to qBittorrent fails."""
    pass


class QBittorrentAuthenticationError(Exception):
    """Raised when authentication with qBittorrent fails."""
    pass


class RuleValidationError(Exception):
    """Raised when RSS rule validation fails."""
    pass


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class MALAPIError(Exception):
    """Raised when MyAnimeList API requests fail."""
    pass


class FileOperationError(Exception):
    """Raised when file operations fail."""
    pass


CONFIG_FILE = 'config.ini'
OUTPUT_CONFIG_FILE_NAME = 'qbittorrent_rules.json'
CACHE_FILE = 'seasonal_cache.json'

DEFAULT_RSS_FEED = "https://subsplease.org/rss/?r=1080"
DEFAULT_SAVE_PREFIX = "/downloads/Anime/Web/"

QBT_PROTOCOL = None
QBT_HOST = None
QBT_PORT = None
QBT_USER = None
QBT_PASS = None
QBT_VERIFY_SSL = True
CONNECTION_MODE = 'online'
QBT_CA_CERT = None
RECENT_FILES = []
CACHED_CATEGORIES = {}

CACHED_FEEDS = {}

ALL_TITLES = {}


def _load_cache_data() -> dict:
    cache_path = Path(CACHE_FILE)
    try:
        if cache_path.exists():
            data = json.loads(cache_path.read_text(encoding='utf-8'))
            return data or {}
    except Exception:
        pass
    return {}


def _save_cache_data(data: dict) -> None:
    try:
        cache_path = Path(CACHE_FILE)
        cache_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    except Exception:
        pass


def _update_cache_key(key: str, value: typing.Any) -> None:
    try:
        data = _load_cache_data()
        data[key] = value
        _save_cache_data(data)
    except Exception:
        pass


def load_recent_files() -> list:
    global RECENT_FILES
    data = _load_cache_data()
    RECENT_FILES = data.get('recent_files', []) or []
    return RECENT_FILES


def load_cached_categories() -> dict:
    global CACHED_CATEGORIES
    data = _load_cache_data()
    CACHED_CATEGORIES = data.get('categories', {}) or {}
    return CACHED_CATEGORIES


def load_cached_feeds() -> dict:
    global CACHED_FEEDS
    data = _load_cache_data()
    CACHED_FEEDS = data.get('feeds', {}) or {}
    return CACHED_FEEDS


def save_cached_feeds(feeds: dict) -> None:
    global CACHED_FEEDS
    CACHED_FEEDS = feeds or {}
    _update_cache_key('feeds', CACHED_FEEDS)


def save_cached_categories(categories: dict) -> None:
    global CACHED_CATEGORIES
    CACHED_CATEGORIES = categories or {}
    _update_cache_key('categories', CACHED_CATEGORIES)


def save_recent_files() -> None:
    _update_cache_key('recent_files', RECENT_FILES)


def load_prefs() -> dict:
    data = _load_cache_data()
    return data.get('prefs', {}) or {}


def save_prefs(prefs: dict) -> None:
    _update_cache_key('prefs', prefs or {})


def get_pref(key: str, default: typing.Any = None) -> typing.Any:
    prefs = load_prefs()
    return prefs.get(key, default)


def set_pref(key: str, value: typing.Any) -> None:
    prefs = load_prefs()
    prefs[key] = value
    save_prefs(prefs)


def add_recent_file(path: str, limit: int = 10) -> None:
    global RECENT_FILES
    if not path:
        return

    load_recent_files()
    path = str(path)

    if path in RECENT_FILES:
        RECENT_FILES.remove(path)

    RECENT_FILES.insert(0, path)
    RECENT_FILES = RECENT_FILES[:limit]
    save_recent_files()


def clear_recent_files() -> None:
    global RECENT_FILES
    RECENT_FILES = []
    save_recent_files()


def load_config() -> bool:
    global QBT_PROTOCOL, QBT_HOST, QBT_PORT, QBT_USER, QBT_PASS, CONNECTION_MODE, QBT_VERIFY_SSL, QBT_CA_CERT
    config = ConfigParser()
    config.read(CONFIG_FILE)

    qbt_loaded = 'QBITTORRENT_API' in config
    if qbt_loaded:
        QBT_PROTOCOL = config['QBITTORRENT_API'].get('protocol', 'http')
        QBT_HOST = config['QBITTORRENT_API'].get('host', 'localhost')
        QBT_PORT = config['QBITTORRENT_API'].get('port', '8080')
        QBT_USER = config['QBITTORRENT_API'].get('username', '')
        QBT_PASS = config['QBITTORRENT_API'].get('password', '')
        CONNECTION_MODE = config['QBITTORRENT_API'].get('mode', 'online')
        QBT_VERIFY_SSL = config['QBITTORRENT_API'].get('verify_ssl', 'True').lower() == 'true'
        QBT_CA_CERT = config['QBITTORRENT_API'].get('ca_cert', '')
    else:
        QBT_PROTOCOL, QBT_HOST, QBT_PORT, QBT_USER, QBT_PASS = ('http', 'localhost', '8080', '', '')
        QBT_VERIFY_SSL = True
        CONNECTION_MODE = 'online'

    return bool(QBT_HOST and QBT_PORT)


def save_config(protocol: str, host: str, port: str, user: str, password: str, mode: str, verify_ssl: bool) -> None:
    global QBT_PROTOCOL, QBT_HOST, QBT_PORT, QBT_USER, QBT_PASS, CONNECTION_MODE, QBT_VERIFY_SSL, QBT_CA_CERT
    cfg = ConfigParser()
    cfg['QBITTORRENT_API'] = {
        'protocol': protocol,
        'host': host,
        'port': port,
        'username': user,
        'password': password,
        'mode': mode,
        'verify_ssl': str(verify_ssl),
        'ca_cert': QBT_CA_CERT or '',
    }
    with open(CONFIG_FILE, 'w') as f:
        cfg.write(f)

    QBT_PROTOCOL, QBT_HOST, QBT_PORT, QBT_USER, QBT_PASS, CONNECTION_MODE, QBT_VERIFY_SSL = (
        protocol, host, port, user, password, mode, verify_ssl
    )


__all__ = [
    'CONFIG_FILE', 'OUTPUT_CONFIG_FILE_NAME', 'CACHE_FILE',
    'DEFAULT_RSS_FEED', 'DEFAULT_SAVE_PREFIX',
    'load_config', 'save_config',
]

class _ConfigNamespace:

    CONFIG_FILE = CONFIG_FILE
    OUTPUT_CONFIG_FILE_NAME = OUTPUT_CONFIG_FILE_NAME
    CACHE_FILE = CACHE_FILE
    DEFAULT_RSS_FEED = DEFAULT_RSS_FEED
    DEFAULT_SAVE_PREFIX = DEFAULT_SAVE_PREFIX

    @property
    def QBT_PROTOCOL(self):
        return globals()['QBT_PROTOCOL']

    @property
    def QBT_HOST(self):
        return globals()['QBT_HOST']

    @property
    def QBT_PORT(self):
        return globals()['QBT_PORT']

    @property
    def QBT_USER(self):
        return globals()['QBT_USER']

    @property
    def QBT_PASS(self):
        return globals()['QBT_PASS']

    @property
    def QBT_VERIFY_SSL(self):
        return globals()['QBT_VERIFY_SSL']

    @property
    def CONNECTION_MODE(self):
        return globals()['CONNECTION_MODE']

    @property
    def QBT_CA_CERT(self):
        return globals()['QBT_CA_CERT']

    @QBT_CA_CERT.setter
    def QBT_CA_CERT(self, value):
        globals()['QBT_CA_CERT'] = value

    @property
    def RECENT_FILES(self):
        return globals()['RECENT_FILES']

    @property
    def CACHED_CATEGORIES(self):
        return globals()['CACHED_CATEGORIES']

    @property
    def CACHED_FEEDS(self):
        return globals()['CACHED_FEEDS']

    @property
    def ALL_TITLES(self):
        return globals()['ALL_TITLES']

    @ALL_TITLES.setter
    def ALL_TITLES(self, value):
        globals()['ALL_TITLES'] = value

    load_recent_files = staticmethod(load_recent_files)
    load_cached_categories = staticmethod(load_cached_categories)
    load_cached_feeds = staticmethod(load_cached_feeds)
    save_cached_feeds = staticmethod(save_cached_feeds)
    save_cached_categories = staticmethod(save_cached_categories)
    save_recent_files = staticmethod(save_recent_files)
    load_prefs = staticmethod(load_prefs)
    save_prefs = staticmethod(save_prefs)
    get_pref = staticmethod(get_pref)
    set_pref = staticmethod(set_pref)
    add_recent_file = staticmethod(add_recent_file)
    clear_recent_files = staticmethod(clear_recent_files)
    load_config = staticmethod(load_config)
    save_config = staticmethod(save_config)

config = _ConfigNamespace()


def get_current_anime_season() -> tuple[str, str]:
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


def sanitize_folder_name(name: str, replacement_char: str = '_', max_length: int = 255) -> str:
    if not name:
        return ''

    try:
        s = str(name).strip()
        if not s:
            return ''

        s = s.replace(':', ' -')

        bad_chars = '<>:"/\\|?*'
        trans_table = str.maketrans(bad_chars, replacement_char * len(bad_chars))
        s = s.translate(trans_table).strip()

        s = s.rstrip(' .')

        while replacement_char * 2 in s:
            s = s.replace(replacement_char * 2, replacement_char)

        if s:
            base = s.split('.')[0].upper()
            reserved = {'CON', 'PRN', 'AUX', 'NUL',
                       'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
                       'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
            if base in reserved:
                s = s + replacement_char

        if len(s) > max_length:
            s = s[:max_length]

        return s
    except Exception:
        try:
            return str(name).replace('/', replacement_char)[:max_length]
        except Exception:
            return ''


_HAVE_QBITTORRENTAPI = Client is not None


def _get_ssl_verification_parameter(verify_ssl: bool, ca_cert: typing.Optional[str] = None) -> typing.Union[bool, str]:
    return ca_cert if (ca_cert and verify_ssl) else verify_ssl


def _validate_qbittorrent_connection_config() -> tuple[bool, str]:
    if not config.QBT_HOST or not config.QBT_PORT:
        return False, "Host and Port are required"
    if not config.QBT_USER or not config.QBT_PASS:
        return False, "Username and Password are required"
    return True, ""


QBT_API_BASE = "/api/v2"
QBT_AUTH_LOGIN = f"{QBT_API_BASE}/auth/login"
QBT_APP_VERSION = f"{QBT_API_BASE}/app/version"
QBT_TORRENTS_CATEGORIES = f"{QBT_API_BASE}/torrents/categories"
QBT_RSS_FEEDS = f"{QBT_API_BASE}/rss/feeds"
QBT_RSS_RULES = f"{QBT_API_BASE}/rss/rules"


def _create_qbittorrent_rss_rule(save_path: str, must_contain: str, feed_url: str, category: str = "") -> dict:
    normalized_path = save_path.replace('\\', '/') if save_path else ''
    return {
        "addPaused": False,
        "affectedFeeds": [feed_url],
        "assignedCategory": category,
        "enabled": True,
        "episodeFilter": "",
        "ignoreDays": 0,
        "lastMatch": None,
        "mustContain": must_contain,
        "mustNotContain": "",
        "previouslyMatchedEpisodes": [],
        "priority": 0,
        "savePath": normalized_path,
        "smartFilter": False,
        "torrentContentLayout": None,
        "torrentParams": {
            "category": category,
            "download_limit": -1,
            "download_path": "",
            "inactive_seeding_time_limit": -2,
            "operating_mode": "AutoManaged",
            "ratio_limit": -2,
            "save_path": normalized_path,
            "seeding_time_limit": -2,
            "share_limit_action": "Default",
            "skip_checking": False,
            "ssl_certificate": "",
            "ssl_dh_params": "",
            "ssl_private_key": "",
            "stopped": False,
            "tags": [],
            "upload_limit": -1,
            "use_auto_tmm": False
        },
        "useRegex": False
    }


def create_qbittorrent_client(host: str, username: str, password: str, verify_ssl: bool) -> typing.Any:
    global_config_ca = getattr(config, 'QBT_CA_CERT', None)

    verify_param = _get_ssl_verification_parameter(verify_ssl, global_config_ca)

    try:
        return Client(host=host, username=username, password=password, verify_ssl=verify_param)
    except TypeError:
        client = Client(host=host, username=username, password=password)
        if not verify_ssl:
            for attr in ('_http_session', 'http_session', '_session', 'session', 'requests_session'):
                sess = getattr(client, attr, None)
                if sess is not None and hasattr(sess, 'verify'):
                    sess.verify = False
                    break
        return client


def sync_rules_to_qbittorrent_online(selected_titles: typing.List[str], rule_prefix: str, year: str, root: tk.Tk, status_var: tk.StringVar) -> None:
    is_valid, error_msg = _validate_qbittorrent_connection_config()
    if not is_valid:
        messagebox.showerror("Error", f"qBittorrent connection details are missing: {error_msg}")
        return

    full_host = f"{config.QBT_PROTOCOL}://{config.QBT_HOST}:{config.QBT_PORT}"
    status_var.set(f"Connecting to qBittorrent at {full_host}...")
    root.update()

    try:
        qbt = create_qbittorrent_client(host=full_host, username=config.QBT_USER, password=config.QBT_PASS, verify_ssl=config.QBT_VERIFY_SSL)
        qbt.auth_log_in()
    except APIConnectionError as e:
        messagebox.showerror("Connection Error", f"Failed to connect or authenticate to qBittorrent.\nDetails: {e}")
        status_var.set("Synchronization failed.")
        return
    except (QBittorrentAuthenticationError, Exception) as e:
        messagebox.showerror("Login Error", f"qBittorrent Login Failed. Check credentials.\nDetails: {e}")
        status_var.set("Synchronization failed.")
        return

    try:
        domain = config.DEFAULT_RSS_FEED.split('//')[1].split('/')[0]
        feed_path = f"Anime Feeds/{domain}"
        try:
            qbt.rss_add_feed(url=config.DEFAULT_RSS_FEED, item_path=feed_path)
            qbt.rss_refresh_item(item_path=feed_path)
        except Conflict409Error:
            pass

        successful_rules = 0
        try:
            config.load_cached_categories()
        except Exception:
            pass
        try:
            config.load_cached_feeds()
        except Exception:
            pass
        categories = getattr(config, 'CACHED_CATEGORIES', {}) or {}
        feeds = getattr(config, 'CACHED_FEEDS', {}) or {}
        try:
            session = requests.Session()
            verify_param = _get_ssl_verification_parameter(config.QBT_VERIFY_SSL, getattr(config, 'QBT_CA_CERT', None))
            login_url = f"{full_host}{QBT_AUTH_LOGIN}"
            lresp = session.post(login_url, data={"username": config.QBT_USER, "password": config.QBT_PASS}, timeout=10, verify=verify_param)
            if lresp.status_code in (200, 201) and (lresp.text or '').strip().lower() in ('ok.', 'ok'):
                cat_url = f"{full_host}{QBT_TORRENTS_CATEGORIES}"
                cresp = session.get(cat_url, timeout=10, verify=verify_param)
                if cresp.status_code == 200:
                    try:
                        categories = cresp.json() or {}
                        try:
                            config.save_cached_categories(categories)
                        except Exception:
                            pass
                    except Exception:
                        categories = {}
                feeds_url = f"{full_host}{QBT_RSS_FEEDS}"
                fresp = session.get(feeds_url, timeout=10, verify=verify_param)
                if fresp.status_code == 200:
                    try:
                        feeds = fresp.json() or {}
                        try:
                            config.save_cached_feeds(feeds)
                        except Exception:
                            pass
                    except Exception:
                        feeds = {}
        except Exception:
            categories = {}

        assigned_category = f"{rule_prefix} - Anime"
        for title in selected_titles:
            sanitized_folder_name = sanitize_folder_name(title)
            rule_name = f"{rule_prefix} {year} - {sanitized_folder_name}"
            save_path = os.path.join(config.DEFAULT_SAVE_PREFIX, f"{rule_prefix} {year}", sanitized_folder_name).replace('\\', '/')
            default_feed = config.DEFAULT_RSS_FEED
            try:
                if feeds:
                    if isinstance(feeds, dict):
                        vals = [v for v in (feeds.values() or []) if isinstance(v, dict) and v.get('url')]
                        if vals:
                            default_feed = vals[0].get('url') or default_feed
                    elif isinstance(feeds, list) and len(feeds) > 0:
                        first = feeds[0]
                        if isinstance(first, dict) and first.get('url'):
                            default_feed = first.get('url')
            except Exception:
                pass

            chosen_category = assigned_category
            if categories:
                if chosen_category not in categories:
                    prefix_lower = rule_prefix.lower()
                    candidate = next((k for k in categories.keys() if k and k.lower().startswith(prefix_lower)), None)
                    if candidate:
                        chosen_category = candidate

            rule_def = _create_qbittorrent_rss_rule(
                save_path=save_path,
                must_contain=sanitized_folder_name,
                feed_url=default_feed,
                category=chosen_category
            )

            qbt.rss_set_rule(rule_name=rule_name, rule_def=rule_def)
            successful_rules += 1

        messagebox.showinfo("Success (Online)", f"Successfully synchronized {successful_rules} rules to qBittorrent.\n\nAll rules are now active in your remote client.")
        status_var.set(f"Synchronization complete. {successful_rules} rules set.")
    except Exception as e:
        messagebox.showerror("Sync Error", f"An error occurred during rule synchronization: {e}")
        status_var.set("Synchronization failed.")


def test_qbittorrent_connection(
    protocol_var: tk.StringVar, 
    host_var: tk.StringVar, 
    port_var: tk.StringVar, 
    user_var: tk.StringVar, 
    pass_var: tk.StringVar, 
    verify_ssl_var: tk.BooleanVar, 
    ca_cert_var: typing.Optional[tk.StringVar] = None
) -> None:
    protocol = protocol_var.get().strip()
    host = host_var.get().strip()
    port = port_var.get().strip()
    user = user_var.get().strip()
    password = pass_var.get().strip()
    verify_ssl = verify_ssl_var.get()

    ca_cert = None
    if ca_cert_var is not None:
        ca_cert = ca_cert_var.get().strip() or None
    else:
        ca_cert = getattr(config, 'QBT_CA_CERT', None)

    if not host or not port:
        messagebox.showwarning("Test Failed", "Host and Port cannot be empty.")
        return

    full_host = f"{protocol}://{host}:{port}"

    try:
        verify_arg = _get_ssl_verification_parameter(verify_ssl, ca_cert)
        qbt = create_qbittorrent_client(host=full_host, username=user, password=password, verify_ssl=verify_arg)
        qbt.auth_log_in()
        app_version = qbt.app_version
        messagebox.showinfo("Test Success", f"Successfully connected to qBittorrent!\nProtocol: {protocol.upper()}\nVerification: {'ON' if verify_ssl else 'OFF'}\nVersion: {app_version}")
        return
    except requests.exceptions.SSLError:
        messagebox.showerror("Test Failed", "SSL Error: Certificate verification failed. Try providing a CA cert or unchecking 'Verify SSL Certificate' in settings.")
        return
    except APIConnectionError:
        pass
    except Exception:
        pass

    try:
        session = requests.Session()
        verify_param = _get_ssl_verification_parameter(verify_ssl, ca_cert)

        login_url = f"{full_host}{QBT_AUTH_LOGIN}"
        resp = session.post(login_url, data={"username": user, "password": password}, timeout=10, verify=verify_param)
        if resp.status_code not in (200, 201) or resp.text.strip().lower() not in ('ok.', 'ok'):
            messagebox.showerror("Test Failed", "Login failed. Check Username/Password and try again.")
            return

        version_url = f"{full_host}{QBT_APP_VERSION}"
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


def fetch_online_rules(root: tk.Tk) -> typing.Optional[dict]:
    is_valid, error_msg = _validate_qbittorrent_connection_config()
    if not is_valid:
        messagebox.showerror("Error", f"qBittorrent connection details are missing: {error_msg}")
        return None

    full_host = f"{config.QBT_PROTOCOL}://{config.QBT_HOST}:{config.QBT_PORT}"
    qbt = None
    lib_exc = None
    try:
        qbt = create_qbittorrent_client(host=full_host, username=config.QBT_USER, password=config.QBT_PASS, verify_ssl=config.QBT_VERIFY_SSL)
        qbt.auth_log_in()
        rules_dict = qbt.rss_rules()
        return rules_dict
    except Exception as e:
        lib_exc = e

    try:
        session = requests.Session()
        verify_param = _get_ssl_verification_parameter(config.QBT_VERIFY_SSL, getattr(config, 'QBT_CA_CERT', None))

        login_url = f"{full_host}{QBT_AUTH_LOGIN}"
        lresp = session.post(login_url, data={"username": config.QBT_USER, "password": config.QBT_PASS}, timeout=10, verify=verify_param)
        if lresp.status_code not in (200, 201) or lresp.text.strip().lower() not in ('ok.', 'ok'):
            body_snippet = (lresp.text or '')[:300]
            messagebox.showerror("Connection Error", f"Failed to authenticate to qBittorrent. Check credentials.\nHTTP {lresp.status_code}: {body_snippet}")
            return None

        rules_url = f"{full_host}{QBT_RSS_RULES}"
        rresp = session.get(rules_url, timeout=10, verify=verify_param)
        if rresp.status_code != 200:
            body_snippet = (rresp.text or '')[:300]
            messagebox.showerror("Connection Error", f"Failed to fetch RSS rules: HTTP {rresp.status_code}\n{body_snippet}")
            return None

        data = rresp.json()
        if isinstance(data, dict):
            rules_dict = data
        elif isinstance(data, list):
            rules_dict = {}
            for item in data:
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
        messagebox.showerror("Connection Error", f"Failed to connect to qBittorrent. Check credentials and server status.\nDetails: {e}")
    except Exception as e:
        extra = f"\nLibrary client error: {repr(lib_exc)}" if lib_exc is not None else ""
        messagebox.showerror("Error", f"An unexpected error occurred while fetching RSS rules: {e}{extra}")

    return None


def _create_authenticated_session(full_host: str, user: str, password: str, verify_param: typing.Union[bool, str], timeout: int = 10) -> typing.Tuple[typing.Optional[typing.Any], typing.Optional[str]]:
    try:
        session = requests.Session()
        login_url = f"{full_host}{QBT_AUTH_LOGIN}"
        resp = session.post(login_url, data={"username": user, "password": password},
                          timeout=timeout, verify=verify_param)

        if resp.status_code not in (200, 201) or resp.text.strip().lower() not in ('ok.', 'ok'):
            return None, f'Login failed (HTTP {resp.status_code})'

        return session, None
    except requests.exceptions.SSLError:
        return None, 'SSL verification failed'
    except requests.exceptions.ConnectionError as e:
        return None, f'Connection error: {e}'
    except Exception as e:
        return None, f'Error: {e}'


def ping_qbittorrent(protocol: str, host: str, port: str, user: str, password: str, verify_ssl: bool, ca_cert: typing.Optional[str] = None, timeout: int = 10) -> typing.Tuple[bool, str]:
    protocol = (protocol or '').strip()
    host = (host or '').strip()
    port = (port or '').strip()
    user = (user or '').strip()
    password = (password or '').strip()
    if not host or not port:
        return False, 'Host or Port empty'

    full_host = f"{protocol}://{host}:{port}"

    try:
        verify_arg = _get_ssl_verification_parameter(verify_ssl, ca_cert)
        qbt = create_qbittorrent_client(host=full_host, username=user, password=password, verify_ssl=verify_arg)
        qbt.auth_log_in()
        try:
            app_version = getattr(qbt, 'app_version', None)
            if app_version:
                return True, f'Connected (client) - {app_version}'
            return True, 'Connected (client)'
        except Exception:
            return True, 'Connected (client)'
    except Exception as e:
        lib_exc = e

    verify_param = ca_cert if (ca_cert and verify_ssl) else verify_ssl
    session, error = _create_authenticated_session(full_host, user, password, verify_param, timeout)

    if error:
        extra = f" ({repr(lib_exc)})" if 'lib_exc' in locals() and lib_exc is not None else ''
        return False, f'{error}{extra}'

    try:
        version_url = f"{full_host}{QBT_APP_VERSION}"
        vresp = session.get(version_url, timeout=timeout, verify=verify_param)
        if vresp.status_code == 200:
            return True, f'Connected - version {vresp.text.strip()}'
        else:
            return False, f'Authenticated but failed to read version (HTTP {vresp.status_code})'
    except Exception as e:
        return False, f'Error fetching version: {e}'


def fetch_categories(protocol: str, host: str, port: str, user: str, password: str, verify_ssl: bool, ca_cert: typing.Optional[str] = None, timeout: int = 10) -> typing.Tuple[bool, typing.Union[str, dict]]:
    protocol = (protocol or '').strip()
    host = (host or '').strip()
    port = (port or '').strip()
    user = (user or '').strip()
    password = (password or '').strip()
    if not host or not port:
        return False, 'Host or Port empty'

    full_host = f"{protocol}://{host}:{port}"

    try:
        verify_arg = ca_cert if (ca_cert and verify_ssl) else verify_ssl
        qbt = create_qbittorrent_client(host=full_host, username=user, password=password, verify_ssl=verify_arg)
        qbt.auth_log_in()
        try:
            getter = None
            for attr in ('torrents_categories', 'categories', 'torrents_categories_map'):
                if hasattr(qbt, attr):
                    getter = getattr(qbt, attr)
                    break
            if getter:
                cats = getter()
                return True, cats or {}
        except Exception:
            pass
    except Exception:
        pass

    verify_param = ca_cert if (ca_cert and verify_ssl) else verify_ssl
    session, error = _create_authenticated_session(full_host, user, password, verify_param, timeout)

    if error:
        return False, error

    try:
        url = f"{full_host}{QBT_TORRENTS_CATEGORIES}"
        cresp = session.get(url, timeout=timeout, verify=verify_param)
        if cresp.status_code != 200:
            return False, f'Failed to fetch categories: HTTP {cresp.status_code}'

        data = cresp.json()
        return True, data or {}
    except Exception as e:
        return False, f'Error parsing categories: {e}'


def fetch_feeds(protocol: str, host: str, port: str, user: str, password: str, verify_ssl: bool, ca_cert: typing.Optional[str] = None, timeout: int = 10) -> typing.Tuple[bool, typing.Union[str, dict]]:
    protocol = (protocol or '').strip()
    host = (host or '').strip()
    port = (port or '').strip()
    user = (user or '').strip()
    password = (password or '').strip()
    if not host or not port:
        return False, 'Host or Port empty'

    full_host = f"{protocol}://{host}:{port}"

    try:
        verify_arg = ca_cert if (ca_cert and verify_ssl) else verify_ssl
        qbt = create_qbittorrent_client(host=full_host, username=user, password=password, verify_ssl=verify_arg)
        qbt.auth_log_in()
        try:
            for attr in ('rss_feeds', 'rss_feed', 'rss_items'):
                if hasattr(qbt, attr):
                    try:
                        feeds = getattr(qbt, attr)()
                        return True, feeds or {}
                    except Exception:
                        continue
        except Exception:
            pass
    except Exception:
        pass

    verify_param = ca_cert if (ca_cert and verify_ssl) else verify_ssl
    session, error = _create_authenticated_session(full_host, user, password, verify_param, timeout)

    if error:
        return False, error

    candidate_paths = [
        QBT_RSS_FEEDS,
        f"{QBT_API_BASE}/rss/items",
        f"{QBT_API_BASE}/rss/rootItems",
        f"{QBT_API_BASE}/rss/tree",
        f"{QBT_API_BASE}/rss/feeds/list",
    ]

    last_err = None
    for path in candidate_paths:
        url = f"{full_host}{path}"
        try:
            fresp = session.get(url, timeout=timeout, verify=verify_param)
            if fresp.status_code != 200:
                last_err = f'HTTP {fresp.status_code} from {path}'
                continue

            data = fresp.json()
            return True, data or {}
        except Exception as e:
            last_err = f'Error with {path}: {e}'
            continue

    return False, last_err or 'No candidate endpoints available'


__all__ = [
    'create_qbittorrent_client',
    'sync_rules_to_qbittorrent_online',
    'fetch_online_rules',
    'test_qbittorrent_connection',
]

class _QbtApiNamespace:
    ping_qbittorrent = staticmethod(ping_qbittorrent)
    fetch_categories = staticmethod(fetch_categories)
    fetch_feeds = staticmethod(fetch_feeds)
    fetch_online_rules = staticmethod(fetch_online_rules)

qbt_api = _QbtApiNamespace()


SCROLL_MODE = 'lines'
SCROLL_LINES = 3
SCROLL_PIXELS = 60

LISTBOX_WIDGET = None
LISTBOX_ITEMS = []
_APP_ROOT = None
_APP_STATUS_VAR = None
TRASH_ITEMS = []


def update_listbox_with_titles(all_titles: typing.Union[dict, list]) -> None:
    global LISTBOX_WIDGET, LISTBOX_ITEMS
    if LISTBOX_WIDGET is None:
        return
    try:
        LISTBOX_WIDGET.delete(0, 'end')
    except Exception:
        pass
    LISTBOX_ITEMS = []
    try:
        for media_type, items in (all_titles.items() if isinstance(all_titles, dict) else [('anime', all_titles)]):
            for entry in items:
                try:
                    if isinstance(entry, dict):
                        node = entry.get('node') or {}
                        title_text = node.get('title') or entry.get('title') or entry.get('name') or str(entry)
                    else:
                        title_text = str(entry)
                    LISTBOX_WIDGET.insert('end', title_text)
                    LISTBOX_ITEMS.append((title_text, entry))
                except Exception:
                    continue
    except Exception:
        pass

def open_settings_window(root: tk.Tk, status_var: tk.StringVar) -> None:
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
    ttk.Label(mode_frame, text="Connection Status:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
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
    settings_conn_status = tk.StringVar(value='Not tested')
    ttk.Label(qbt_frame, textvariable=settings_conn_status).grid(row=8, column=0, columnspan=2, sticky='w', padx=5)

    def _run_test_and_update():
        def _worker():
            try:
                settings_conn_status.set('Testing...')
                ok, msg = qbt_api.ping_qbittorrent(qbt_protocol_temp.get(), qbt_host_temp.get(), qbt_port_temp.get(), qbt_user_temp.get(), qbt_pass_temp.get(), bool(verify_ssl_temp.get()), ca_cert_temp.get() if ca_cert_temp.get().strip() else None)
                if ok:
                    settings_conn_status.set('Connected: ' + msg)
                else:
                    settings_conn_status.set('Not connected: ' + msg)
            except Exception as e:
                settings_conn_status.set('Test failed: ' + str(e))
        try:
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            settings_conn_status.set('Test failed to start')

    test_btn = ttk.Button(qbt_frame, text="Test Connection", command=_run_test_and_update)
    test_btn.grid(row=8, column=2, columnspan=2, pady=10, sticky='e')

    try:
        cat_frame = ttk.LabelFrame(settings_win, text='Cached Categories', padding=6)
        cat_frame.pack(fill='x', padx=10, pady=(0,10))
        cat_listbox = tk.Listbox(cat_frame, height=6)
        cat_listbox.pack(side='left', fill='both', expand=True, padx=(4,0), pady=4)
        cat_scroll = ttk.Scrollbar(cat_frame, orient='vertical', command=cat_listbox.yview)
        cat_scroll.pack(side='left', fill='y', padx=(4,6), pady=4)
        cat_listbox.configure(yscrollcommand=cat_scroll.set)

        def _load_cached_categories_into_listbox():
            try:
                config.load_cached_categories()
                cats = getattr(config, 'CACHED_CATEGORIES', {}) or {}
                cat_listbox.delete(0, 'end')
                if isinstance(cats, dict):
                    keys = list(cats.keys())
                elif isinstance(cats, list):
                    keys = cats
                else:
                    keys = []
                for k in keys:
                    cat_listbox.insert('end', str(k))
            except Exception:
                pass

        def _clear_cached_categories():
            try:
                if not messagebox.askyesno('Confirm', 'Clear cached categories? This cannot be undone.'):
                    return
                config.save_cached_categories({})
                _load_cached_categories_into_listbox()
                status_var.set('Cached categories cleared.')
            except Exception:
                status_var.set('Failed to clear cached categories.')

        def _refresh_categories_from_server():
            def _worker():
                try:
                    settings_conn_status.set('Refreshing categories...')
                    ok, data = qbt_api.fetch_categories(qbt_protocol_temp.get(), qbt_host_temp.get(), qbt_port_temp.get(), qbt_user_temp.get(), qbt_pass_temp.get(), bool(verify_ssl_temp.get()), ca_cert_temp.get() if ca_cert_temp.get().strip() else None)
                    if ok:
                        try:
                            config.save_cached_categories(data)
                        except Exception:
                            pass
                        settings_conn_status.set('Categories refreshed.')
                        status_var.set('Categories updated from server.')
                        _load_cached_categories_into_listbox()
                    else:
                        settings_conn_status.set('Refresh failed: ' + str(data))
                        status_var.set('Failed to refresh categories.')
                except Exception as e:
                    settings_conn_status.set('Refresh error: ' + str(e))
            try:
                threading.Thread(target=_worker, daemon=True).start()
            except Exception:
                settings_conn_status.set('Failed to start refresh thread')

        btns_frame = ttk.Frame(cat_frame)
        btns_frame.pack(side='left', fill='y', padx=6, pady=4)
        ttk.Button(btns_frame, text='Refresh categories', command=_refresh_categories_from_server).pack(fill='x', pady=2)
        ttk.Button(btns_frame, text='Clear cached', command=_clear_cached_categories).pack(fill='x', pady=2)
        _load_cached_categories_into_listbox()
    except Exception:
        pass

    try:
        feeds_frame = ttk.LabelFrame(settings_win, text='Cached Feeds', padding=6)
        feeds_frame.pack(fill='x', padx=10, pady=(0,10))
        feeds_listbox = tk.Listbox(feeds_frame, height=6)
        feeds_listbox.pack(side='left', fill='both', expand=True, padx=(4,0), pady=4)
        feeds_scroll = ttk.Scrollbar(feeds_frame, orient='vertical', command=feeds_listbox.yview)
        feeds_scroll.pack(side='left', fill='y', padx=(4,6), pady=4)
        feeds_listbox.configure(yscrollcommand=feeds_scroll.set)

        def _load_cached_feeds_into_listbox():
            try:
                config.load_cached_feeds()
                f = getattr(config, 'CACHED_FEEDS', {}) or {}
                feeds_listbox.delete(0, 'end')
                if isinstance(f, dict):
                    for k, v in f.items():
                        if isinstance(v, dict) and v.get('url'):
                            feeds_listbox.insert('end', f"{k} -> {v.get('url')}")
                        else:
                            feeds_listbox.insert('end', str(k))
                elif isinstance(f, list):
                    for item in f:
                        if isinstance(item, dict) and item.get('url'):
                            feeds_listbox.insert('end', item.get('url'))
                        else:
                            feeds_listbox.insert('end', str(item))
            except Exception:
                pass

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
        fbtns_frame.pack(side='left', fill='y', padx=6, pady=4)
        ttk.Button(fbtns_frame, text='Refresh feeds', command=_refresh_feeds_from_server).pack(fill='x', pady=2)
        ttk.Button(fbtns_frame, text='Clear cached', command=_clear_cached_feeds).pack(fill='x', pady=2)
        _load_cached_feeds_into_listbox()
    except Exception:
        pass

    save_btn = ttk.Button(settings_win, text="Save All Settings", command=save_and_close, style='Accent.TButton')
    save_btn.pack(pady=10)


def setup_gui() -> tk.Tk:
    config_set = config.load_config()
    root = tk.Tk()
    root.title("qBittorrent RSS Rules Editor")
    root.geometry("900x700")

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

    def _get_connection_status():
        try:
            mode = (getattr(config, 'CONNECTION_MODE', '') or '').lower()
            if mode == 'online':
                return f"Online: {config.QBT_PROTOCOL}://{config.QBT_HOST}:{config.QBT_PORT}"
            if mode == 'offline':
                return 'Offline'
            if mode == 'auto':
                return 'Auto (will try online if available)'
            return f"Mode: {mode or 'unknown'}"
        except Exception:
            return 'Status Unknown'

    status_var = tk.StringVar(value=_get_connection_status())
    global _APP_ROOT, _APP_STATUS_VAR, LISTBOX_WIDGET, LISTBOX_ITEMS
    _APP_ROOT = root
    _APP_STATUS_VAR = status_var

    try:
        config_file_missing = not os.path.exists(getattr(config, 'CONFIG_FILE', 'config.ini'))
    except Exception:
        config_file_missing = False

    if not config_set and config_file_missing:
        status_var.set("🚨 CRITICAL: Please set qBittorrent credentials in Settings.")
        root.after(100, lambda: open_settings_window(root, status_var))

    def _start_auto_connect_thread():
        def worker():
            attempts = 0
            while attempts < 3:
                attempts += 1
                try:
                    status_var.set('Auto: attempting qBittorrent connection...')
                    ok, msg = qbt_api.ping_qbittorrent(config.QBT_PROTOCOL, config.QBT_HOST, str(config.QBT_PORT), config.QBT_USER or '', config.QBT_PASS or '', bool(config.QBT_VERIFY_SSL), getattr(config, 'QBT_CA_CERT', None))
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

    try:
        if (getattr(config, 'CONNECTION_MODE', '') or '').lower() == 'auto':
            _start_auto_connect_thread()
    except Exception:
        pass

    main_frame = ttk.Frame(root, padding="15")
    main_frame.pack(fill='both', expand=True)

    menubar = tk.Menu(root)
    file_menu = tk.Menu(menubar, tearoff=0)
    edit_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label='Open JSON File...', accelerator='Ctrl+O', command=lambda: import_titles_from_file(root, status_var))
    file_menu.add_command(label='Paste from Clipboard', command=lambda: import_titles_from_clipboard(root, status_var))
    recent_menu = tk.Menu(file_menu, tearoff=0)
    file_menu.add_cascade(label='Recent Files', menu=recent_menu)
    file_menu.add_separator()
    file_menu.add_command(label='Exit', command=root.quit)
    menubar.add_cascade(label='📁 File', menu=file_menu)
    menubar.add_cascade(label='✏️ Edit', menu=edit_menu)

    def refresh_recent_menu():
        try:
            recent_menu.delete(0, 'end')
        except Exception:
            pass
        try:
            config.load_recent_files()
            for path in (getattr(config, 'RECENT_FILES', []) or []):
                def _open_path(p=path):
                    try:
                        with open(p, 'r', encoding='utf-8') as f:
                            text = f.read()
                        parsed = import_titles_from_text(text)
                        if not parsed:
                            messagebox.showerror('Import Error', f'Failed to parse JSON from {p}.')
                            return
                        config.ALL_TITLES = parsed
                        update_listbox_with_titles(config.ALL_TITLES)
                        status_var.set(f'Imported {sum(len(v) for v in config.ALL_TITLES.values())} titles from {p}.')
                    except Exception as e:
                        messagebox.showerror('Open Recent', f'Failed to open {p}: {e}')
                recent_menu.add_command(label=path, command=_open_path)
            if (getattr(config, 'RECENT_FILES', None) or []):
                recent_menu.add_separator()
                recent_menu.add_command(label='Clear Recent Files', command=lambda: (config.clear_recent_files(), refresh_recent_menu()))
        except Exception:
            pass

    refresh_recent_menu()

    settings_menu = tk.Menu(menubar, tearoff=0)
    settings_menu.add_command(label='Settings...', accelerator='Ctrl+,', command=lambda: open_settings_window(root, status_var))
    menubar.add_cascade(label='⚙️ Settings', menu=settings_menu)

    info_menu = tk.Menu(menubar, tearoff=0)
    def show_about():
        messagebox.showinfo('About qBittorrent RSS Rule Editor', 'qBittorrent RSS Rule Editor\n\nGenerate and sync qBittorrent RSS rules for seasonal anime.\nRun: python -m qbt_editor')
    info_menu.add_command(label='About', command=show_about)
    menubar.add_cascade(label='ℹ️ Info', menu=info_menu)

    try:
        root.config(menu=menubar)
    except Exception:
        try:
            root['menu'] = menubar
        except Exception:
            pass

    top_config_frame = ttk.Frame(main_frame, padding="5")
    top_config_frame.pack(fill='x', pady=5)
    ttk.Label(top_config_frame, text="Season:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
    season_dropdown = ttk.Combobox(top_config_frame, textvariable=season_var, values=["Winter", "Spring", "Summer", "Fall"], state="readonly", width=10)
    season_dropdown.grid(row=0, column=1, sticky='w', padx=5, pady=5)
    ttk.Label(top_config_frame, text="Year:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
    year_entry = ttk.Entry(top_config_frame, textvariable=year_var, width=10)
    year_entry.grid(row=0, column=3, sticky='w', padx=5, pady=5)
    try:
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
        ttk.Checkbutton(top_config_frame, text='Prefix imports with Season/Year', variable=prefix_imports_var).grid(row=0, column=4, sticky='w', padx=6)
    except Exception:
        prefix_imports_var = tk.BooleanVar(value=True)
    try:
        def _sync_online_worker(root_ref, status_var_ref, btn_ref):
            def worker():
                try:
                    root_ref.after(0, lambda: (btn_ref.config(state='disabled'), status_var_ref.set('Sync: fetching existing rules...')))
                    rules = qbt_api.fetch_online_rules(root_ref)
                    def finish():
                        try:
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
                                            entries.append(rule_entry)
                                        else:
                                            entries.append({'node': {'title': name}})
                                elif isinstance(rules, list):
                                    for item in rules:
                                        if isinstance(item, dict) and item.get('ruleName'):
                                            name = item.get('ruleName')
                                        else:
                                            name = str(item)
                                        entries.append({'node': {'title': name}})

                                if entries:
                                    current = getattr(config, 'ALL_TITLES', {}) or {}
                                    existing_titles = set()
                                    try:
                                        if isinstance(current, dict):
                                            for k, lst in current.items():
                                                if not isinstance(lst, list):
                                                    continue
                                                for it in lst:
                                                    try:
                                                        if isinstance(it, dict):
                                                            t = (it.get('node') or {}).get('title') or it.get('ruleName') or it.get('name')
                                                        else:
                                                            t = str(it)
                                                        if t is not None:
                                                            existing_titles.add(str(t))
                                                    except Exception:
                                                        try:
                                                            existing_titles.add(str(it))
                                                        except Exception:
                                                            pass
                                    except Exception:
                                        existing_titles = set()

                                    new_entries = []
                                    for e in entries:
                                        try:
                                            if isinstance(e, dict):
                                                title = (e.get('node') or {}).get('title') or e.get('ruleName') or e.get('name')
                                            else:
                                                title = str(e)
                                            key = None if title is None else str(title)
                                        except Exception:
                                            key = None

                                        if key and key in existing_titles:
                                            continue
                                        try:
                                            if key:
                                                existing_titles.add(key)
                                        except Exception:
                                            pass
                                        new_entries.append(e)

                                    if new_entries:
                                        cur_list = current.get('existing', [])
                                        cur_list.extend(new_entries)
                                        current['existing'] = cur_list
                                        config.ALL_TITLES = current
                                        try:
                                            update_listbox_with_titles(config.ALL_TITLES)
                                            status_var_ref.set(f'Added {len(new_entries)} new existing rule(s) to Titles.')
                                        except Exception:
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
                    root_ref.after(0, lambda: (status_var_ref.set(f'Sync error: {e}'), btn_ref.config(state='normal')))
            t = threading.Thread(target=worker, daemon=True)
            t.start()

        def _on_sync_clicked():
            try:
                mode = (getattr(config, 'CONNECTION_MODE', '') or '').lower()
                if mode == 'online':
                    sync_btn.config(state='disabled')
                    _sync_online_worker(root, status_var, sync_btn)
                else:
                    import_titles_from_file(root, status_var)
            except Exception as e:
                messagebox.showerror('Sync Error', f'Failed to start sync: {e}')

        def _on_generate_clicked():
            try:
                dispatch_generation(root, season_var, year_entry, LISTBOX_WIDGET, status_var)
            except Exception as e:
                messagebox.showerror('Generate Error', f'Failed to generate: {e}')
        generate_btn = ttk.Button(top_config_frame, text='Generate/Sync to qBittorrent', command=_on_generate_clicked, style='Accent.TButton')
        generate_btn.grid(row=1, column=4, columnspan=2, sticky='e', padx=6, pady=(6, 0))

        sync_btn = ttk.Button(top_config_frame, text='Sync from qBittorrent1', command=_on_sync_clicked)
        sync_btn.grid(row=0, column=5, sticky='e', padx=6)
    except Exception:
        pass
    top_config_frame.grid_columnconfigure(5, weight=1)

    try:
        root.bind_all('<Control-o>', lambda e: import_titles_from_file(root, status_var))
        root.bind_all('<Control-O>', lambda e: import_titles_from_file(root, status_var))
        root.bind_all('<Control-s>', lambda e: dispatch_generation(root, season_var, year_entry, LISTBOX_WIDGET, status_var))
        root.bind_all('<Control-S>', lambda e: dispatch_generation(root, season_var, year_entry, LISTBOX_WIDGET, status_var))
        root.bind_all('<Control-e>', lambda e: export_selected_titles())
        root.bind_all('<Control-E>', lambda e: export_selected_titles())
        root.bind_all('<Control-Shift-E>', lambda e: export_all_titles())
        root.bind_all('<Control-Shift-e>', lambda e: export_all_titles())
        root.bind_all('<Control-z>', lambda e: undo_last_delete())
        root.bind_all('<Control-Z>', lambda e: undo_last_delete())
        root.bind_all('<Control-q>', lambda e: root.quit())
        root.bind_all('<Control-Q>', lambda e: root.quit())
        root.bind_all('<Control-Shift-C>', lambda e: clear_all_titles(root, status_var))
        root.bind_all('<Control-Shift-c>', lambda e: clear_all_titles(root, status_var))
    except Exception:
        pass


    list_frame_container = ttk.LabelFrame(main_frame, text="Titles (use Ctrl/Shift to multi-select)", padding="10")
    list_frame_container.pack(fill='both', expand=True, pady=10)

    listbox = tk.Listbox(list_frame_container, selectmode='extended', activestyle='none', width=60)
    listbox.pack(side='left', fill='both', expand=True)
    scrollbar = ttk.Scrollbar(list_frame_container, orient='vertical', command=listbox.yview)
    scrollbar.pack(side='right', fill='y')
    listbox.configure(yscrollcommand=scrollbar.set)

    try:
        def _ctx_edit_selected():
            try:
                open_full_rule_editor_for_selection()
            except Exception as e:
                messagebox.showerror('Edit Error', f'Failed to open editor: {e}')

        def _ctx_delete_selected():
            try:
                sel = LISTBOX_WIDGET.curselection()
                if not sel:
                    messagebox.showwarning('Delete', 'No title selected.')
                    return
                if not messagebox.askyesno('Confirm Delete', f'Delete {len(sel)} selected title(s)? This cannot be undone.'):
                    return

                removed = 0
                for s in sorted([int(i) for i in sel], reverse=True):
                    try:
                        title_text, entry = LISTBOX_ITEMS[s]
                    except Exception:
                        continue
                    try:
                        TRASH_ITEMS.append({'title': title_text, 'entry': entry, 'src': 'titles', 'index': s})
                    except Exception:
                        pass
                    try:
                        LISTBOX_WIDGET.delete(s)
                    except Exception:
                        pass
                    try:
                        LISTBOX_ITEMS.pop(s)
                    except Exception:
                        pass
                    try:
                        if getattr(config, 'ALL_TITLES', None):
                            for k, lst in (config.ALL_TITLES.items() if isinstance(config.ALL_TITLES, dict) else []):
                                for i in range(len(config.ALL_TITLES.get(k, [])) - 1, -1, -1):
                                    it = config.ALL_TITLES[k][i]
                                    try:
                                        candidate = (it.get('node') or {}).get('title') if isinstance(it, dict) else str(it)
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

                messagebox.showinfo('Delete', f'Moved {removed} title(s) to Trash (Undo available).')
            except Exception as e:
                messagebox.showerror('Delete Error', f'Failed to delete selected titles: {e}')

        def _ctx_copy_selected():
            try:
                sel = LISTBOX_WIDGET.curselection()
                if not sel:
                    messagebox.showwarning('Copy', 'No title selected to copy.')
                    return
                export_map = {}
                try:
                    sel_indices = [int(i) for i in sel]
                except Exception:
                    sel_indices = []
                try:
                    all_map = _build_qbittorrent_export_map({ 'anime': [it for it in [LISTBOX_ITEMS[i][1] for i in sel_indices] ] })
                    export_map = all_map
                except Exception:
                    for s in sel_indices:
                        try:
                            title_text, entry = LISTBOX_ITEMS[s]
                        except Exception:
                            continue
                        if isinstance(entry, dict):
                            export_map[title_text] = entry
                        else:
                            export_map[title_text] = {'title': str(entry)}
                try:
                    text = json.dumps(export_map, indent=4)
                except Exception as e:
                    messagebox.showerror('Copy Error', f'Failed to serialize selection to JSON: {e}')
                    return

                try:
                    root.clipboard_clear()
                    root.clipboard_append(text)
                    try:
                        root.update()
                    except Exception:
                        pass
                    messagebox.showinfo('Copy', f'Copied {len(export_map)} item(s) to clipboard as JSON.')
                except Exception as e:
                    messagebox.showerror('Copy Error', f'Failed to copy to clipboard: {e}')
            except Exception as e:
                messagebox.showerror('Copy Error', f'Failed to copy selected titles: {e}')

        def _on_listbox_right_click(event):
            try:
                idx = LISTBOX_WIDGET.nearest(event.y)
                if idx is None:
                    return
                cur = LISTBOX_WIDGET.curselection()
                if not cur or (idx not in [int(i) for i in cur]):
                    try:
                        LISTBOX_WIDGET.selection_clear(0, 'end')
                    except Exception:
                        pass
                    try:
                        LISTBOX_WIDGET.selection_set(idx)
                    except Exception:
                        pass
                try:
                    context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    context_menu.grab_release()
            except Exception:
                pass

        context_menu = tk.Menu(listbox, tearoff=0)
        context_menu.add_command(label='Copy', command=_ctx_copy_selected)
        context_menu.add_command(label='Edit', command=_ctx_edit_selected)
        context_menu.add_command(label='Delete', command=_ctx_delete_selected)
        LISTBOX_WIDGET = listbox
        LISTBOX_WIDGET.bind('<Button-3>', _on_listbox_right_click, add='+')
    except Exception:
        pass

    LISTBOX_WIDGET = listbox
    LISTBOX_ITEMS = []

    def export_selected_titles():
        try:
            sel = LISTBOX_WIDGET.curselection()
            if not sel:
                messagebox.showwarning('Export', 'No title selected to export.')
                return
            try:
                sel_indices = [int(i) for i in sel]
            except Exception:
                sel_indices = []
            try:
                selected_entries = [LISTBOX_ITEMS[i][1] for i in sel_indices]
                export_map = _build_qbittorrent_export_map({'anime': selected_entries})
            except Exception:
                export_map = {}
                for s in sel_indices:
                    try:
                        title_text, entry = LISTBOX_ITEMS[s]
                    except Exception:
                        continue
                    if isinstance(entry, dict):
                        export_map[title_text] = entry
                    else:
                        export_map[title_text] = {'title': str(entry)}

            path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON','*.json')])
            if not path:
                return
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(export_map, f, indent=4)
                messagebox.showinfo('Export', f'Exported {len(export_map)} item(s) to {path}')
            except Exception as e:
                messagebox.showerror('Export Error', f'Failed to export: {e}')
        except Exception as e:
            messagebox.showerror('Export Error', f'Failed to export selected titles: {e}')


    def export_all_titles():
        try:
            data = getattr(config, 'ALL_TITLES', None) or {}
            if not data:
                messagebox.showwarning('Export All', 'No titles available to export.')
                return
            path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON','*.json')])
            if not path:
                return
            try:
                try:
                    export_map = _build_qbittorrent_export_map(data)
                except Exception:
                    export_map = data
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(export_map, f, indent=4)
                messagebox.showinfo('Export All', f'Exported all titles to {path}')
            except Exception as e:
                messagebox.showerror('Export Error', f'Failed to export all titles: {e}')
        except Exception as e:
            messagebox.showerror('Export Error', f'Failed to export all titles: {e}')

    def undo_last_delete():
        try:
            if not TRASH_ITEMS:
                messagebox.showinfo('Undo', 'Trash is empty.')
                return
            item = TRASH_ITEMS.pop()
            if item.get('src') == 'titles':
                idx = item.get('index', None)
                title_text = item.get('title')
                entry = item.get('entry')
                if idx is None or idx < 0 or idx > LISTBOX_WIDGET.size():
                    LISTBOX_ITEMS.append((title_text, entry))
                    try:
                        LISTBOX_WIDGET.insert('end', title_text)
                    except Exception:
                        pass
                else:
                    try:
                        LISTBOX_ITEMS.insert(idx, (title_text, entry))
                    except Exception:
                        LISTBOX_ITEMS.append((title_text, entry))
                    try:
                        LISTBOX_WIDGET.insert(idx, title_text)
                    except Exception:
                        try:
                            LISTBOX_WIDGET.insert('end', title_text)
                        except Exception:
                            pass
                try:
                    if getattr(config, 'ALL_TITLES', None) is None:
                        config.ALL_TITLES = {'existing': []}
                    if isinstance(config.ALL_TITLES, dict):
                        config.ALL_TITLES.setdefault('existing', []).append(entry)
                except Exception:
                    pass
                messagebox.showinfo('Undo', f'Restored "{title_text}" from Trash.')
            else:
                messagebox.showinfo('Undo', 'Last delete cannot be automatically undone for that source.')
        except Exception as e:
            messagebox.showerror('Undo Error', f'Failed to undo last delete: {e}')

    def view_trash_dialog(parent):
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
                for it in TRASH_ITEMS:
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
                    for i in sorted([int(x) for x in sel], reverse=True):
                        try:
                            item = TRASH_ITEMS.pop(i)
                        except Exception:
                            continue
                        if item.get('src') == 'titles':
                            title_text = item.get('title')
                            entry = item.get('entry')
                            try:
                                LISTBOX_ITEMS.append((title_text, entry))
                                LISTBOX_WIDGET.insert('end', title_text)
                            except Exception:
                                pass
                    refresh()
                    messagebox.showinfo('Restore', 'Selected items restored to Titles.')
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
                            TRASH_ITEMS.pop(i)
                        except Exception:
                            pass
                    refresh()
                except Exception as e:
                    messagebox.showerror('Delete Error', f'Failed to permanently delete: {e}')

            def _empty_trash():
                try:
                    if not TRASH_ITEMS:
                        return
                    if not messagebox.askyesno('Empty Trash', 'Empty the trash permanently?'):
                        return
                    TRASH_ITEMS.clear()
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

    try:
        edit_menu.add_command(label='Clear All Titles', accelerator='Ctrl+Shift+C', command=lambda: clear_all_titles(root, status_var))
        edit_menu.add_command(label='Export Selected Titles...', accelerator='Ctrl+E', command=export_selected_titles)
        edit_menu.add_command(label='Export All Titles...', accelerator='Ctrl+Shift+E', command=lambda: export_all_titles())
        edit_menu.add_command(label='Undo Last Delete', accelerator='Ctrl+Z', command=lambda: undo_last_delete())
        edit_menu.add_command(label='View Trash...', command=lambda: view_trash_dialog(root))
    except Exception:
        pass

    editor_frame = ttk.Frame(list_frame_container, padding=8)
    try:
        editor_frame.pack(side='right', fill='y')
    except Exception:
        pass

    editor_rule_name = tk.StringVar(value='')
    editor_must = tk.StringVar(value='')
    editor_savepath = tk.StringVar(value='')
    editor_category = tk.StringVar(value='')
    editor_enabled = tk.BooleanVar(value=True)
    editor_lastmatch_text = tk.Text(editor_frame, height=2, width=40, state='disabled')

    ttk.Label(editor_frame, text='Selected Title / Rule', font=('Segoe UI', 10, 'bold')).pack(anchor='w')
    ttk.Label(editor_frame, text='Title:').pack(anchor='w', pady=(8,0))
    ttk.Entry(editor_frame, textvariable=editor_rule_name, width=60).pack(anchor='w', pady=(0,4))
    ttk.Label(editor_frame, text='Match Pattern:').pack(anchor='w')
    ttk.Entry(editor_frame, textvariable=editor_must, width=60).pack(anchor='w', pady=(0,4))
    ttk.Label(editor_frame, text='Last Match:').pack(anchor='w')
    editor_lastmatch_text.pack(anchor='w', pady=(0,4))
    lastmatch_status_label = tk.Label(editor_frame, text='', fg='green')
    lastmatch_status_label.pack(anchor='w', pady=(0,2))
    current_lastmatch_holder = {'value': None}
    try:
        pref_val = config.get_pref('time_24', True)
    except Exception:
        pref_val = True
    time_24_var = tk.BooleanVar(value=bool(pref_val))
    info_row = ttk.Frame(editor_frame)
    info_row.pack(fill='x', pady=(0,6))
    age_label = ttk.Label(info_row, text='Age: N/A')
    age_label.pack(side='left')
    time_toggle_btn = ttk.Checkbutton(info_row, text='24-hour', variable=time_24_var, onvalue=True, offvalue=False)
    time_toggle_btn.pack(side='right')
    ttk.Label(editor_frame, text='Save Path:').pack(anchor='w')
    ttk.Entry(editor_frame, textvariable=editor_savepath, width=60).pack(anchor='w', pady=(0,4))
    ttk.Label(editor_frame, text='Assigned Category:').pack(anchor='w')
    ttk.Entry(editor_frame, textvariable=editor_category, width=60).pack(anchor='w', pady=(0,4))
    ttk.Checkbutton(editor_frame, text='Enabled', variable=editor_enabled).pack(anchor='w', pady=(4,6))

    btns = ttk.Frame(editor_frame)
    btns.pack(anchor='e', pady=(6,0), fill='x')

    def _populate_editor_from_selection(event=None):
        try:
            sel = LISTBOX_WIDGET.curselection()
            if not sel:
                return
            idx = int(sel[0])
            mapped = LISTBOX_ITEMS[idx]
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
                save = '' if save_val is None else str(save_val).replace('/', '\\')

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
                        editor_lastmatch_text.delete('1.0', 'end')
                        editor_lastmatch_text.insert('1.0', '' if lm is None else str(lm))
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

    def _parse_datetime_from_string(s):
        from datetime import datetime, timezone
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
                from datetime import timezone as _tz
                dt = dt.replace(tzinfo=_tz.utc)
            return dt
        except Exception:
            return None

    def update_lastmatch_display(lm_value=None):
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
                    from datetime import datetime
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
        try:
            if not s or not isinstance(s, str):
                return False
            ss = s.strip()
            return ss.startswith('{') or ss.startswith('[') or ss.startswith('"')
        except Exception:
            return False

    def validate_lastmatch_json(event=None):
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
        time_toggle_btn.config(command=lambda: update_lastmatch_display())
    except Exception:
        pass

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


    def _apply_editor_changes():
        try:
            sel = LISTBOX_WIDGET.curselection()
            if not sel:
                messagebox.showwarning('Edit', 'No title selected.')
                return
            idx = int(sel[0])
            mapped = LISTBOX_ITEMS[idx]
            title_text, entry = mapped[0], mapped[1]
        except Exception:
            messagebox.showerror('Edit', 'Failed to locate selected item.')
            return

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
            messagebox.showerror('Validation Error', 'Title cannot be empty.')
            return
        try:
            if new_save and len(new_save) > 260:
                if not messagebox.askyesno('Validation Warning', 'Save Path is unusually long. Do you want to continue?'):
                    return
        except Exception:
            pass

        try:
            if not isinstance(entry, dict):
                entry = {'node': {'title': title_text}}
            entry['mustContain'] = new_must or new_title
            entry['savePath'] = new_save
            entry['assignedCategory'] = new_cat
            entry['enabled'] = new_en
            try:
                    lm_val = ''
                    if new_lastmatch:
                        s = new_lastmatch.strip()
                        if s.startswith('{') or s.startswith('[') or s.startswith('"'):
                            try:
                                lm_val = json.loads(new_lastmatch)
                            except Exception as e:
                                try:
                                    if not messagebox.askyesno('Invalid JSON', f'Last Match appears to be JSON but is invalid:\n{e}\n\nApply as raw text anyway?'):
                                        return
                                except Exception:
                                    return
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
            LISTBOX_ITEMS[idx] = (new_title, entry)
            try:
                if getattr(config, 'ALL_TITLES', None):
                    for k, lst in (config.ALL_TITLES.items() if isinstance(config.ALL_TITLES, dict) else []):
                        for i, it in enumerate(lst):
                            try:
                                candidate_title = (it.get('node') or {}).get('title') if isinstance(it, dict) else str(it)
                            except Exception:
                                candidate_title = str(it)
                            if candidate_title == title_text:
                                config.ALL_TITLES[k][i] = entry
                                raise StopIteration
            except StopIteration:
                pass
            try:
                LISTBOX_WIDGET.delete(idx)
                LISTBOX_WIDGET.insert(idx, new_title)
            except Exception:
                pass
            messagebox.showinfo('Edit', 'Changes applied to the selected title.')
        except Exception as e:
            messagebox.showerror('Edit Error', f'Failed to apply changes: {e}')

    def open_full_rule_editor_for_selection():
        try:
            sel = LISTBOX_WIDGET.curselection()
            if not sel:
                messagebox.showwarning('Edit', 'No title selected.')
                return
            idx = int(sel[0])
            title_text, entry = LISTBOX_ITEMS[idx]
        except Exception:
            messagebox.showerror('Edit', 'Failed to locate selected item.')
            return
        open_full_rule_editor(title_text, entry, idx)

    ttk.Button(btns, text='Edit Full Settings...', command=open_full_rule_editor_for_selection).pack(side='left', padx=(0,6))

    footer_edit_btns = ttk.Frame(editor_frame)
    footer_edit_btns.pack(fill='x', pady=(6,0))
    ttk.Button(footer_edit_btns, text='Refresh', command=_populate_editor_from_selection).pack(side='right')
    ttk.Button(footer_edit_btns, text='Apply', command=_apply_editor_changes).pack(side='right', padx=4)

    try:
        LISTBOX_WIDGET.bind('<<ListboxSelect>>', _populate_editor_from_selection)
        try:
            LISTBOX_WIDGET.bind('<Double-1>', lambda e: open_full_rule_editor_for_selection())
        except Exception:
            pass
    except Exception:
        pass

    def open_full_rule_editor(title_text, entry, idx):
        dlg = tk.Toplevel(root)
        dlg.title(f'Edit Full Rule - {title_text}')
        dlg.transient(root)
        dlg.grab_set()

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

        row = 0
        frm = ttk.Frame(dlg, padding=8)
        frm.grid(row=0, column=0, sticky='nsew')

        def grid_label(r, text=''):
            ttk.Label(frm, text=text).grid(row=r, column=0, sticky='w', padx=2, pady=2)

        affected_frame = ttk.Frame(frm)
        affected_var = tk.Text(affected_frame, height=3, width=40)

        prevmatches_frame = ttk.Frame(frm)
        prevmatches_text = tk.Text(prevmatches_frame, height=3, width=40)

        grid_label(row, 'addPaused:')
        ttk.Combobox(frm, textvariable=addPaused_var, values=['None', 'False', 'True'], width=10).grid(row=row, column=1, sticky='w')
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

        grid_label(row, 'Affected Feeds (one per line):')
        affected_frame.grid(row=row, column=1, sticky='w')
        affected_var.grid(row=0, column=0, sticky='w', padx=2, pady=2)
        try:
            af = entry.get('affectedFeeds') if isinstance(entry, dict) else []
            if isinstance(af, list):
                affected_var.delete('1.0', 'end')
                affected_var.insert('1.0', '\n'.join(af))
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
            feeds_select_frame = ttk.Frame(affected_frame)
            feeds_select_frame.grid(row=0, column=1, sticky='w', pady=(4,0))
            feeds_combo = ttk.Combobox(feeds_select_frame, values=feeds_choices, state='readonly', width=60)
            feeds_combo.pack(side='left', padx=(0,6))
            def _add_selected_feed():
                try:
                    val = feeds_combo.get().strip()
                    if not val:
                        return
                    if '->' in val:
                        val = val.split('->',1)[1].strip()
                    current = affected_var.get('1.0', 'end').strip().splitlines()
                    if val not in current:
                        if affected_var.get('1.0', 'end').strip():
                            affected_var.insert('end', '\n' + val)
                        else:
                            affected_var.insert('1.0', val)
                except Exception:
                    pass
            ttk.Button(feeds_select_frame, text='Add', command=_add_selected_feed).pack(side='left')
        except Exception:
            pass
        row += 1

        grid_label(row, 'Assigned Category:')
        ttk.Entry(frm, textvariable=assigned_var, width=50).grid(row=row, column=1, sticky='w')
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
        try:
            cat_frame = ttk.Frame(frm)
            cat_frame.grid(row=row, column=1, sticky='e', padx=(4,0))
            cat_combo = ttk.Combobox(cat_frame, values=cat_choices, state='readonly', width=60)
            cat_combo.pack(side='left')
            def _use_selected_category():
                try:
                    v = cat_combo.get().strip()
                    if not v:
                        return
                    assigned_var.set(v)
                    tp_category.set(v)
                except Exception:
                    pass
            ttk.Button(cat_frame, text='Use', command=_use_selected_category).pack(side='left', padx=(4,0))
        except Exception:
            pass
        row += 1

        grid_label(row, 'Enabled:')
        ttk.Checkbutton(frm, variable=enabled_var).grid(row=row, column=1, sticky='w')
        row += 1

        grid_label(row, 'Episode Filter:')
        ttk.Entry(frm, textvariable=episode_var, width=50).grid(row=row, column=1, sticky='w')
        row += 1

        grid_label(row, 'Ignore Days:')
        ttk.Entry(frm, textvariable=ignore_var, width=10).grid(row=row, column=1, sticky='w')
        row += 1

        grid_label(row, 'Last Match:')
        ttk.Entry(frm, textvariable=lastmatch_var, width=50).grid(row=row, column=1, sticky='w')
        try:
            lastmatch_full_status_label = tk.Label(frm, text='', fg='green')
            lastmatch_full_status_label.grid(row=row, column=2, sticky='w', padx=(8,0))
        except Exception:
            lastmatch_full_status_label = None
        row += 1

        grid_label(row, 'Must Contain:')
        ttk.Entry(frm, textvariable=must_var, width=50).grid(row=row, column=1, sticky='w')
        row += 1

        grid_label(row, 'Must Not Contain:')
        ttk.Entry(frm, textvariable=mustnot_var, width=50).grid(row=row, column=1, sticky='w')
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
        ttk.Entry(frm, textvariable=priority_var, width=10).grid(row=row, column=1, sticky='w')
        row += 1

        grid_label(row, 'Save Path:')
        ttk.Entry(frm, textvariable=savepath_var, width=50).grid(row=row, column=1, sticky='w')
        row += 1

        grid_label(row, 'Smart Filter:')
        ttk.Checkbutton(frm, variable=smart_var).grid(row=row, column=1, sticky='w')
        row += 1

        grid_label(row, 'Torrent Content Layout:')
        ttk.Entry(frm, textvariable=tcl_var, width=30).grid(row=row, column=1, sticky='w')
        row += 1

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=6)
        row += 1

        tp_frame = ttk.LabelFrame(frm, text='', padding=6)
        tp_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=6)
        try:
            header_font = ('Segoe UI', 9, 'bold')
        except Exception:
            header_font = None
        if header_font:
            ttk.Label(tp_frame, text='TorrentParams', font=header_font).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0,4))
        else:
            ttk.Label(tp_frame, text='TorrentParams').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0,4))
        tp_row = 1
        ttk.Label(tp_frame, text='category:').grid(row=tp_row, column=0, sticky='w', padx=2, pady=2)
        ttk.Entry(tp_frame, textvariable=tp_category, width=40).grid(row=tp_row, column=1, sticky='w')
        tp_row += 1

        ttk.Label(tp_frame, text='download_limit:').grid(row=tp_row, column=0, sticky='w', padx=2, pady=2)
        ttk.Entry(tp_frame, textvariable=tp_download_limit, width=10).grid(row=tp_row, column=1, sticky='w')
        tp_row += 1

        ttk.Label(tp_frame, text='download_path:').grid(row=tp_row, column=0, sticky='w', padx=2, pady=2)
        ttk.Entry(tp_frame, textvariable=tp_download_path, width=40).grid(row=tp_row, column=1, sticky='w')
        tp_row += 1

        ttk.Label(tp_frame, text='inactive_seeding_time_limit:').grid(row=tp_row, column=0, sticky='w', padx=2, pady=2)
        ttk.Entry(tp_frame, textvariable=tp_inactive_limit, width=10).grid(row=tp_row, column=1, sticky='w')
        tp_row += 1

        ttk.Label(tp_frame, text='operating_mode:').grid(row=tp_row, column=0, sticky='w', padx=2, pady=2)
        ttk.Entry(tp_frame, textvariable=tp_operating_mode, width=20).grid(row=tp_row, column=1, sticky='w')
        tp_row += 1

        ttk.Label(tp_frame, text='ratio_limit:').grid(row=tp_row, column=0, sticky='w', padx=2, pady=2)
        ttk.Entry(tp_frame, textvariable=tp_ratio_limit, width=10).grid(row=tp_row, column=1, sticky='w')
        tp_row += 1

        ttk.Label(tp_frame, text='save_path:').grid(row=tp_row, column=0, sticky='w', padx=2, pady=2)
        ttk.Entry(tp_frame, textvariable=tp_save_path, width=50).grid(row=tp_row, column=1, sticky='w')
        tp_row += 1

        ttk.Label(tp_frame, text='seeding_time_limit:').grid(row=tp_row, column=0, sticky='w', padx=2, pady=2)
        ttk.Entry(tp_frame, textvariable=tp_seeding_time, width=10).grid(row=tp_row, column=1, sticky='w')
        tp_row += 1

        ttk.Label(tp_frame, text='skip_checking:').grid(row=tp_row, column=0, sticky='w', padx=2, pady=2)
        ttk.Checkbutton(tp_frame, variable=tp_skip).grid(row=tp_row, column=1, sticky='w')
        tp_row += 1

        ttk.Label(tp_frame, text='tags (comma separated):').grid(row=tp_row, column=0, sticky='w', padx=2, pady=2)
        ttk.Entry(tp_frame, textvariable=tp_tags, width=40).grid(row=tp_row, column=1, sticky='w')
        tp_row += 1

        row += 1

        ttk.Label(frm, text='upload_limit:').grid(row=row, column=0, sticky='w', padx=2, pady=2)
        ttk.Entry(frm, textvariable=tp_upload_limit, width=10).grid(row=row, column=1, sticky='w')
        row += 1

        ttk.Label(frm, text='use_auto_tmm:').grid(row=row, column=0, sticky='w', padx=2, pady=2)
        ttk.Checkbutton(frm, variable=tp_auto_tmm).grid(row=row, column=1, sticky='w')
        row += 1

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=6)
        row += 1

        grid_label(row, 'Use Regex:')
        ttk.Checkbutton(frm, variable=useregex_var).grid(row=row, column=1, sticky='w')
        row += 1

        footer = ttk.Frame(dlg)
        footer.grid(row=1, column=0, sticky='ew', pady=6)

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

                feeds_raw = affected_var.get('1.0', 'end').strip()
                new_rule['affectedFeeds'] = [f.strip() for f in feeds_raw.splitlines() if f.strip()]
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

                LISTBOX_ITEMS[idx] = (new_rule.get('node', {}).get('title') or new_rule.get('mustContain') or title_text, new_rule)
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
                    LISTBOX_WIDGET.delete(idx)
                    LISTBOX_WIDGET.insert(idx, LISTBOX_ITEMS[idx][0])
                except Exception:
                    pass

                dlg.destroy()
                messagebox.showinfo('Edit', 'Full settings applied.')
            except Exception as e:
                messagebox.showerror('Apply Error', f'Failed to apply full settings: {e}')

        ttk.Button(footer, text='Apply', command=_apply_full).pack(side='right', padx=6)
        ttk.Button(footer, text='Cancel', command=dlg.destroy).pack(side='right')

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


    def normalize_titles_structure(raw):
        if not raw:
            return None
        if isinstance(raw, list):
            return {'anime': [ {'node': {'title': str(x)}} if not isinstance(x, dict) else x for x in raw ]}

        if isinstance(raw, dict):
            if all(isinstance(v, dict) for v in raw.values()):
                out = {'anime': []}
                try:
                    try:
                        pass
                    except Exception:
                        try:
                            import utils as _utils
                        except Exception:
                            _utils = None
                except Exception:
                    _utils = None

                for k, v in raw.items():
                    try:
                        entry = v.copy() if isinstance(v, dict) else {'node': {'title': str(k)}}

                        try:
                            must = entry.get('mustContain') or entry.get('title') or entry.get('name') or ''
                            savep = entry.get('savePath') or (entry.get('torrentParams') or {}).get('save_path') or ''
                            default_rss = ''
                            aff = entry.get('affectedFeeds')
                            if isinstance(aff, list) and aff:
                                default_rss = aff[0]
                            try:
                                sp_arg = savep if savep is not None else ''
                            except Exception:
                                sp_arg = savep or ''
                            try:
                                base = {
                                    "addPaused": False,
                                    "affectedFeeds": [default_rss],
                                    "assignedCategory": "",
                                    "enabled": True,
                                    "episodeFilter": "",
                                    "ignoreDays": 0,
                                    "lastMatch": None,
                                    "mustContain": must or k,
                                    "mustNotContain": "",
                                    "previouslyMatchedEpisodes": [],
                                    "priority": 0,
                                    "savePath": sp_arg,
                                    "smartFilter": False,
                                    "torrentContentLayout": None,
                                    "torrentParams": {
                                        "category": "",
                                        "download_limit": -1,
                                        "download_path": "",
                                        "inactive_seeding_time_limit": -2,
                                        "operating_mode": "AutoManaged",
                                        "ratio_limit": -2,
                                        "save_path": str(sp_arg).replace("\\", "/"),
                                        "seeding_time_limit": -2,
                                        "share_limit_action": "Default",
                                        "skip_checking": False,
                                        "ssl_certificate": "",
                                        "ssl_dh_params": "",
                                        "ssl_private_key": "",
                                        "stopped": False,
                                        "tags": [],
                                        "upload_limit": -1,
                                        "use_auto_tmm": False
                                    },
                                    "useRegex": False
                                }
                                try:
                                    base.update(entry)
                                except Exception:
                                    pass
                                entry = base
                            except Exception:
                                pass
                        except Exception:
                            pass

                        try:
                            node = entry.get('node') or {}
                            if not node.get('title'):
                                node_title = entry.get('mustContain') or entry.get('title') or k
                                node['title'] = node_title
                                entry['node'] = node
                        except Exception:
                            pass

                        out['anime'].append(entry)
                    except Exception:
                        out['anime'].append({'node': {'title': str(k)}})
                return out
            if all(isinstance(v, str) for v in raw.values()):
                return {'anime': [ {'node': {'title': v}} for v in raw.values() ]}
            if any(isinstance(v, list) for v in raw.values()):
                out = {}
                for k, v in raw.items():
                    if isinstance(v, list):
                        items = []
                        for it in v:
                            if isinstance(it, str):
                                items.append({'node': {'title': it}})
                            elif isinstance(it, dict) and ('title' in it or 'node' in it):
                                items.append(it if 'node' in it else {'node': {'title': it.get('title') or it.get('name') or str(it)}})
                        out[k] = items
                if out:
                    return out
            return {'anime': [ {'node': {'title': k}} for k in raw.keys() ]}

        return None

    def import_titles_from_text(text):
        try:
            parsed = json.loads(text)
        except Exception:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if lines:
                parsed = lines
            else:
                return None
        return normalize_titles_structure(parsed)


    def _prefix_titles_with_season_year(all_titles, season, year):
        try:
            if not season or not year:
                return
            prefix = f"{season} {year} - "
            if not isinstance(all_titles, dict):
                return
            for media_type, items in (all_titles.items() if isinstance(all_titles, dict) else []):
                if not isinstance(items, list):
                    continue
                for i, entry in enumerate(items):
                    try:
                        if isinstance(entry, dict):
                            node = entry.get('node')
                            if isinstance(node, dict):
                                title = node.get('title') or entry.get('title') or ''
                                orig_title = str(title) if title else ''
                                if orig_title and not orig_title.startswith(prefix):
                                    node['title'] = prefix + orig_title
                                    entry['node'] = node
                                    if not entry.get('mustContain'):
                                        try:
                                            entry['mustContain'] = orig_title
                                        except Exception:
                                            pass
                                elif not orig_title:
                                    fallback = entry.get('mustContain') or entry.get('title') or entry.get('name') or ''
                                    if fallback:
                                        fb = str(fallback)
                                        if not fb.startswith(prefix):
                                            node['title'] = prefix + fb
                                            entry['node'] = node
                                            if not entry.get('mustContain'):
                                                try:
                                                    entry['mustContain'] = fb
                                                except Exception:
                                                    pass
                            else:
                                title = entry.get('title') or entry.get('name') or ''
                                if title:
                                    t = str(title)
                                    if not t.startswith(prefix):
                                        entry['title'] = prefix + t
                                        if not entry.get('mustContain'):
                                            try:
                                                entry['mustContain'] = t
                                            except Exception:
                                                pass
                        else:
                            title = str(entry)
                            if title and not title.startswith(prefix):
                                items[i] = {'node': {'title': prefix + title}, 'mustContain': title}
                    except Exception:
                        continue
        except Exception:
            pass


    def _is_valid_folder_name(name):
        try:
            if not name or not isinstance(name, str) or not name.strip():
                return False, 'Empty name'
            s = name.strip()
            bad = set('<>:"/\\|?*')
            found = [c for c in s if c in bad]
            if found:
                return False, f'Contains invalid characters: {"".join(sorted(set(found)))}'
            if s.endswith(' ') or s.endswith('.'):
                return False, 'Ends with a space or dot (invalid for folder names on Windows)'
            base = s.split('.')[0].upper()
            reserved = {'CON','PRN','AUX','NUL'} | {f'COM{i}' for i in range(1,10)} | {f'LPT{i}' for i in range(1,10)}
            if base in reserved:
                return False, f'Reserved name: {base}'
            try:
                if len(s) > 255:
                    return False, 'Name too long (>255 chars)'
            except Exception:
                pass
            return True, None
        except Exception:
            return False, 'Validation error'


    def _collect_invalid_folder_titles(all_titles):
        out = []
        try:
            if not isinstance(all_titles, dict):
                return out
            for media_type, items in (all_titles.items() if isinstance(all_titles, dict) else []):
                if not isinstance(items, list):
                    continue
                for entry in items:
                    try:
                        raw = ''
                        display = ''
                        if isinstance(entry, dict):
                            node = entry.get('node') or {}
                            display = node.get('title') or entry.get('title') or ''
                            raw = entry.get('mustContain') or entry.get('title') or entry.get('name') or ''
                            if display and isinstance(display, str):
                                parts = display.split(' - ', 1)
                                if len(parts) == 2 and parts[0].istitle():
                                    maybe_raw = parts[1]
                                    if maybe_raw and not raw:
                                        raw = maybe_raw
                        else:
                            display = str(entry)
                            raw = display
                        if not raw:
                            continue
                        valid, reason = _is_valid_folder_name(raw)
                        if not valid:
                            out.append((display or raw, raw, reason))
                    except Exception:
                        continue
        except Exception:
            pass
        return out


    def _ensure_full_rule_entries(all_titles, season=None, year=None):
        try:
            try:
                pass
            except Exception:
                try:
                    import utils as _utils
                except Exception:
                    _utils = None
            if not isinstance(all_titles, dict):
                return
            season_str = str(season) if season else ''
            year_str = str(year) if year else ''
            for media_type, items in (all_titles.items() if isinstance(all_titles, dict) else []):
                if not isinstance(items, list):
                    continue
                for i, entry in enumerate(items):
                    try:
                        if not isinstance(entry, dict):
                            entry = {'node': {'title': str(entry)}, 'mustContain': str(entry)}
                        must = entry.get('mustContain') or (entry.get('node') or {}).get('title') or entry.get('title') or ''
                        savep = entry.get('savePath') or (entry.get('torrentParams') or {}).get('save_path') or ''
                        aff = entry.get('affectedFeeds')
                        default_rss = aff[0] if isinstance(aff, list) and aff else getattr(config, 'DEFAULT_RSS_FEED', '')

                        has_tp = isinstance(entry.get('torrentParams'), dict) and entry.get('savePath')
                        has_aff = bool(entry.get('affectedFeeds'))
                        if has_tp and has_aff:
                            node = entry.get('node') or {}
                            if not node.get('title'):
                                node['title'] = must or entry.get('title') or ''
                                entry['node'] = node
                            items[i] = entry
                            continue

                        try:
                            default_save_prefix = getattr(config, 'DEFAULT_SAVE_PREFIX', '')
                            if not savep and season_str and year_str and default_save_prefix:
                                sf = _utils.sanitize_folder_name(must or '')
                                savep = os.path.join(default_save_prefix, f"{season_str} {year_str}", sf).replace('\\', '/')
                        except Exception:
                            pass

                        try:
                            try:
                                sp_arg = (savep.replace('/', '\\') if savep else '')
                            except Exception:
                                sp_arg = savep or ''
                            base = {
                                "addPaused": False,
                                "affectedFeeds": [default_rss],
                                "assignedCategory": "",
                                "enabled": True,
                                "episodeFilter": "",
                                "ignoreDays": 0,
                                "lastMatch": None,
                                "mustContain": must or '',
                                "mustNotContain": "",
                                "previouslyMatchedEpisodes": [],
                                "priority": 0,
                                "savePath": sp_arg,
                                "smartFilter": False,
                                "torrentContentLayout": None,
                                "torrentParams": {
                                    "category": "",
                                    "download_limit": -1,
                                    "download_path": "",
                                    "inactive_seeding_time_limit": -2,
                                    "operating_mode": "AutoManaged",
                                    "ratio_limit": -2,
                                    "save_path": str(sp_arg).replace('\\', '/'),
                                    "seeding_time_limit": -2,
                                    "share_limit_action": "Default",
                                    "skip_checking": False,
                                    "ssl_certificate": "",
                                    "ssl_dh_params": "",
                                    "ssl_private_key": "",
                                    "stopped": False,
                                    "tags": [],
                                    "upload_limit": -1,
                                    "use_auto_tmm": False
                                },
                                "useRegex": False
                            }
                            try:
                                base.update(entry)
                            except Exception:
                                pass
                            try:
                                tp = base.get('torrentParams') or {}
                                if savep:
                                    tp['save_path'] = savep.replace('\\', '/')
                                base['torrentParams'] = tp
                            except Exception:
                                pass
                            node = base.get('node') or {}
                            if not node.get('title'):
                                node['title'] = base.get('mustContain') or base.get('title') or must or ''
                                base['node'] = node
                            items[i] = base
                        except Exception:
                            items[i] = entry
                    except Exception:
                        continue

        except Exception:
            pass

    def _build_qbittorrent_export_map(all_titles):
        out = {}
        try:
            try:
                pass
            except Exception:
                try:
                    import utils as _utils
                except Exception:
                    _utils = None
            if not isinstance(all_titles, dict):
                return out

            def _default_assigned_category():
                try:
                    cached = getattr(config, 'CACHED_CATEGORIES', {}) or {}
                    if isinstance(cached, dict) and cached:
                        for k in cached.keys():
                            return str(k)
                    if isinstance(cached, list) and cached:
                        return str(cached[0])
                except Exception:
                    pass
                return ''

            for media_type, items in (all_titles.items() if isinstance(all_titles, dict) else []):
                if not isinstance(items, list):
                    continue
                for entry in items:
                    try:
                        if isinstance(entry, dict):
                            node = entry.get('node') or {}
                            display_title = node.get('title') or entry.get('mustContain') or entry.get('title') or ''
                        else:
                            display_title = str(entry)

                        season = None
                        year = None
                        raw_name = ''
                        try:
                            if isinstance(display_title, str) and ' - ' in display_title:
                                left, right = display_title.split(' - ', 1)
                                parts = left.split()
                                if parts and parts[-1].isdigit() and len(parts[-1]) == 4:
                                    season = ' '.join(parts[:-1]) if len(parts) > 1 else parts[0]
                                    year = parts[-1]
                                    raw_name = right
                        except Exception:
                            raw_name = ''
                        if not raw_name:
                            try:
                                raw_name = entry.get('mustContain') or (entry.get('node') or {}).get('title') or entry.get('title') or display_title
                            except Exception:
                                raw_name = display_title

                        try:
                            sanitized = _utils.sanitize_folder_name(raw_name) if _utils and hasattr(_utils, 'sanitize_folder_name') else str(raw_name)
                        except Exception:
                            sanitized = str(raw_name)

                        try:
                            default_prefix = getattr(config, 'DEFAULT_SAVE_PREFIX', '') or ''
                            if season and year and default_prefix:
                                save_path_prefix = os.path.join(default_prefix, f"{season} {year}")
                                full_save_path = os.path.join(save_path_prefix, sanitized)
                            else:
                                if default_prefix:
                                    full_save_path = os.path.join(default_prefix, sanitized)
                                else:
                                    full_save_path = sanitized
                            full_save_path_local = str(full_save_path).replace('/', '\\')
                        except Exception:
                            full_save_path_local = str(sanitized).replace('/', '\\')

                        try:
                            aff = entry.get('affectedFeeds') if isinstance(entry, dict) else []
                            default_rss = aff[0] if isinstance(aff, list) and aff else getattr(config, 'DEFAULT_RSS_FEED', '')
                        except Exception:
                            default_rss = getattr(config, 'DEFAULT_RSS_FEED', '')

                        try:
                            try:
                                sp_arg = full_save_path_local if full_save_path_local is not None else ''
                            except Exception:
                                sp_arg = full_save_path_local or ''
                            base_candidate = {
                                "addPaused": False,
                                "affectedFeeds": [default_rss],
                                "assignedCategory": "",
                                "enabled": True,
                                "episodeFilter": "",
                                "ignoreDays": 0,
                                "lastMatch": None,
                                "mustContain": sanitized,
                                "mustNotContain": "",
                                "previouslyMatchedEpisodes": [],
                                "priority": 0,
                                "savePath": sp_arg,
                                "smartFilter": False,
                                "torrentContentLayout": None,
                                "torrentParams": {
                                    "category": "",
                                    "download_limit": -1,
                                    "download_path": "",
                                    "inactive_seeding_time_limit": -2,
                                    "operating_mode": "AutoManaged",
                                    "ratio_limit": -2,
                                    "save_path": str(sp_arg).replace('\\', '/'),
                                    "seeding_time_limit": -2,
                                    "share_limit_action": "Default",
                                    "skip_checking": False,
                                    "ssl_certificate": "",
                                    "ssl_dh_params": "",
                                    "ssl_private_key": "",
                                    "stopped": False,
                                    "tags": [],
                                    "upload_limit": -1,
                                    "use_auto_tmm": False
                                },
                                "useRegex": False
                            }
                            if isinstance(entry, dict):
                                base = entry.copy()
                                try:
                                    for k, v in base_candidate.items():
                                        if k not in base:
                                            base[k] = v
                                except Exception:
                                    base = base
                            else:
                                base = base_candidate
                        except Exception:
                            base = entry.copy() if isinstance(entry, dict) else {'node': {'title': display_title}, 'mustContain': sanitized}

                        try:
                            if isinstance(entry, dict):
                                base.update(entry)
                        except Exception:
                            pass

                        try:
                            if 'addPaused' not in base:
                                base['addPaused'] = False
                        except Exception:
                            pass

                        try:
                            ac = base.get('assignedCategory')
                            if not ac:
                                ac = ''
                            base['assignedCategory'] = ac
                        except Exception:
                            base['assignedCategory'] = ''

                        try:
                            if 'lastMatch' not in base or base.get('lastMatch') is None:
                                base['lastMatch'] = ''
                        except Exception:
                            base['lastMatch'] = ''

                        try:
                            tp = base.get('torrentParams') or {}
                            try:
                                tp['category'] = base.get('assignedCategory') or ''
                            except Exception:
                                pass
                            try:
                                tp['save_path'] = str(full_save_path).replace('\\', '/').replace('\\\\', '/')
                            except Exception:
                                pass
                            base['torrentParams'] = tp
                        except Exception:
                            pass

                        try:
                            base['savePath'] = str(full_save_path).replace('\\', '/')
                        except Exception:
                            try:
                                base['savePath'] = full_save_path_local.replace('\\', '/')
                            except Exception:
                                pass

                        try:
                            node = base.get('node') or {}
                            if not node.get('title'):
                                node['title'] = display_title or base.get('mustContain') or sanitized
                                base['node'] = node
                        except Exception:
                            pass

                        try:
                            export_rule = base.copy() if isinstance(base, dict) else base
                            if isinstance(export_rule, dict):
                                export_rule.pop('node', None)
                        except Exception:
                            export_rule = base
                        out[str(display_title)] = export_rule
                    except Exception:
                        continue
        except Exception:
            pass
        return out

    def _auto_sanitize_titles(all_titles):
        try:
            try:
                pass
            except Exception:
                try:
                    import utils as _utils
                except Exception:
                    _utils = None
            if _utils is None or not hasattr(_utils, 'sanitize_folder_name'):
                return


            if not isinstance(all_titles, dict):
                return
            for media_type, items in (all_titles.items() if isinstance(all_titles, dict) else []):
                if not isinstance(items, list):
                    continue
                for entry in items:
                    try:
                        raw = ''
                        if isinstance(entry, dict):
                            raw = entry.get('mustContain') or (entry.get('node') or {}).get('title') or entry.get('title') or entry.get('name') or ''
                        else:
                            raw = str(entry)
                        if not raw:
                            continue
                        sanitized = _utils.sanitize_folder_name(raw)
                        if sanitized and sanitized != raw:
                            try:
                                if isinstance(entry, dict):
                                    entry['mustContain'] = sanitized
                            except Exception:
                                continue
                    except Exception:
                        continue
        except Exception:
            pass

    def import_titles_from_file(root, status_var, path=None):
        if not path:
            path = filedialog.askopenfilename(title='Open JSON titles file', filetypes=[('JSON','*.json'), ('All files','*.*')])
        if not path:
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
            parsed = import_titles_from_text(text)
            if not parsed:
                messagebox.showerror('Import Error', 'Failed to parse JSON from selected file.')
                return False
            try:
                if prefix_imports_var.get():
                    _prefix_titles_with_season_year(parsed, season_var.get(), year_var.get())
            except Exception:
                pass
            try:
                invalids = _collect_invalid_folder_titles(parsed)
                try:
                    auto = config.get_pref('auto_sanitize_imports', True)
                except Exception:
                    auto = True
                if invalids:
                    if auto:
                        try:
                            _auto_sanitize_titles(parsed)
                            invalids = _collect_invalid_folder_titles(parsed)
                        except Exception:
                            invalids = _collect_invalid_folder_titles(parsed)
                    if invalids:
                        lines = []
                        for d, raw, reason in invalids:
                            lines.append(f"{d} -> {raw}: {reason}")
                        if not messagebox.askyesno('Invalid folder names', 'The following imported titles contain characters or names invalid for folder names:\n\n' + '\n'.join(lines) + '\n\nContinue import anyway?'):
                            return False
            except Exception:
                pass
            config.ALL_TITLES = parsed
            try:
                _ensure_full_rule_entries(config.ALL_TITLES, season_var.get(), year_var.get())
            except Exception:
                pass
            update_listbox_with_titles(config.ALL_TITLES)
            status_var.set(f'Imported {sum(len(v) for v in config.ALL_TITLES.values())} titles from file.')
            try:
                config.add_recent_file(path)
            except Exception:
                pass
            return True
        except Exception as e:
            messagebox.showerror('File Error', f'Error reading file: {e}')
            return False

    def import_titles_from_clipboard(root, status_var):
        try:
            text = root.clipboard_get()
        except Exception:
            messagebox.showwarning('Clipboard', 'No text found in clipboard.')
            return False
        parsed = import_titles_from_text(text)
        if not parsed:
            messagebox.showerror('Import Error', 'Failed to parse JSON or titles from clipboard text.')
            return False
        try:
            if prefix_imports_var.get():
                _prefix_titles_with_season_year(parsed, season_var.get(), year_var.get())
        except Exception:
            pass
        try:
            invalids = _collect_invalid_folder_titles(parsed)
            try:
                auto = config.get_pref('auto_sanitize_imports', True)
            except Exception:
                auto = True
            if invalids:
                if auto:
                    try:
                        _auto_sanitize_titles(parsed)
                        invalids = _collect_invalid_folder_titles(parsed)
                    except Exception:
                        invalids = _collect_invalid_folder_titles(parsed)
                if invalids:
                    lines = []
                    for d, raw, reason in invalids:
                        lines.append(f"{d} -> {raw}: {reason}")
                    if not messagebox.askyesno('Invalid folder names', 'The following imported titles contain characters or names invalid for folder names:\n\n' + '\n'.join(lines) + '\n\nContinue import anyway?'):
                        return False
        except Exception:
            pass
        config.ALL_TITLES = parsed
        try:
            _ensure_full_rule_entries(config.ALL_TITLES, season_var.get(), year_var.get())
        except Exception:
            pass
        update_listbox_with_titles(config.ALL_TITLES)
        status_var.set(f'Imported {sum(len(v) for v in config.ALL_TITLES.values())} titles from clipboard.')
        return True

    def clear_all_titles(root, status_var):
        try:
            has = bool(getattr(config, 'ALL_TITLES', None)) and any((getattr(config, 'ALL_TITLES') or {}).values())
        except Exception:
            has = bool(getattr(config, 'ALL_TITLES', None))

        if not has:
            status_var.set('No titles to clear.')
            try:
                LISTBOX_WIDGET.delete(0, 'end')
            except Exception:
                pass
            return False

        if not messagebox.askyesno('Clear All Titles', 'Are you sure you want to clear all loaded titles? This cannot be undone.'):
            return False

        try:
            config.ALL_TITLES = {}
        except Exception:
            pass
        try:
            LISTBOX_WIDGET.delete(0, 'end')
        except Exception:
            pass
        try:
            LISTBOX_ITEMS.clear()
        except Exception:
            pass
        status_var.set('Cleared all loaded titles.')
        return True

    def open_import_titles_dialog(root, status_var):
        dlg = tk.Toplevel(root)
        dlg.title('Import Titles')
        dlg.transient(root)
        dlg.grab_set()

        ttk.Label(dlg, text='Import titles from a JSON file, paste JSON, or paste newline-separated titles.').pack(fill='x', padx=10, pady=8)

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill='x', padx=10, pady=(0,6))
        def on_open_file():
            path = filedialog.askopenfilename(title='Open JSON titles file', filetypes=[('JSON','*.json'), ('All files','*.*')])
            if not path:
                return
            try:
                ok = import_titles_from_file(root, status_var, path)
                if ok:
                    dlg.destroy()
            except Exception as e:
                messagebox.showerror('File Error', f'Error importing file: {e}')

        def on_paste_clipboard():
            try:
                ok = import_titles_from_clipboard(root, status_var)
                if ok:
                    dlg.destroy()
            except Exception as e:
                messagebox.showerror('Clipboard Import Error', f'Error importing from clipboard: {e}')

        ttk.Button(btn_frame, text='Open JSON File...', command=on_open_file).pack(side='left', padx=4)
        ttk.Button(btn_frame, text='Paste from Clipboard', command=on_paste_clipboard).pack(side='left', padx=4)

        ttk.Label(dlg, text='Or paste JSON / newline titles below:').pack(fill='x', padx=10, pady=(6,0))
        text = tk.Text(dlg, height=12, width=80)
        text.pack(fill='both', expand=True, padx=10, pady=(4,6))

        def on_import_text():
            val = text.get('1.0', 'end').strip()
            if not val:
                messagebox.showwarning('Import', 'No text to import.')
                return
            parsed = import_titles_from_text(val)
            if not parsed:
                messagebox.showerror('Import Error', 'Failed to parse JSON or titles from pasted text.')
                return
            try:
                if prefix_imports_var.get():
                    _prefix_titles_with_season_year(parsed, season_var.get(), year_var.get())
            except Exception:
                pass
            try:
                invalids = _collect_invalid_folder_titles(parsed)
                try:
                    auto = config.get_pref('auto_sanitize_imports', True)
                except Exception:
                    auto = True
                if invalids:
                    if auto:
                        try:
                            _auto_sanitize_titles(parsed)
                            invalids = _collect_invalid_folder_titles(parsed)
                        except Exception:
                            invalids = _collect_invalid_folder_titles(parsed)
                    if invalids:
                        lines = []
                        for d, raw, reason in invalids:
                            lines.append(f"{d} -> {raw}: {reason}")
                        if not messagebox.askyesno('Invalid folder names', 'The following imported titles contain characters or names invalid for folder names:\n\n' + '\n'.join(lines) + '\n\nContinue import anyway?'):
                            return
            except Exception:
                pass
            config.ALL_TITLES = parsed
            try:
                _ensure_full_rule_entries(config.ALL_TITLES, season_var.get(), year_var.get())
            except Exception:
                pass
            update_listbox_with_titles(config.ALL_TITLES)
            status_var.set(f'Imported {sum(len(v) for v in config.ALL_TITLES.values())} titles from pasted text.')
            dlg.destroy()

        footer = ttk.Frame(dlg)
        footer.pack(fill='x', padx=10, pady=8)
        ttk.Button(footer, text='Import Text', command=on_import_text).pack(side='left')
        ttk.Button(footer, text='Cancel', command=dlg.destroy).pack(side='right')

    def dispatch_generation(root, season_var, year_entry, listbox_widget, status_var):
        try:
            season = season_var.get()
            year = year_entry.get()

            if not season or not year:
                messagebox.showwarning("Input Error", "Season and Year must be specified.")
                return

            items = []
            try:
                sel = listbox_widget.curselection()
                if sel:
                    indices = [int(i) for i in sel]
                else:
                    indices = list(range(len(LISTBOX_ITEMS)))
            except Exception:
                indices = list(range(len(LISTBOX_ITEMS)))

            for i in indices:
                try:
                    t, entry = LISTBOX_ITEMS[i]
                    items.append((t, entry))
                except Exception:
                    continue

            problems = []
            preview_list = []
            for title_text, entry in items:
                e = entry if isinstance(entry, dict) else {'node': {'title': str(entry)}}
                try:
                    node = e.get('node') or {}
                    node_title = node.get('title') or e.get('mustContain') or title_text
                except Exception:
                    node_title = title_text
                if not node_title or not str(node_title).strip():
                    problems.append(f'Missing title for item: {title_text}')

                try:
                    lm = e.get('lastMatch', '')
                    if isinstance(lm, str):
                        s = lm.strip()
                        if s and (s.startswith('{') or s.startswith('[') or s.startswith('"')):
                            try:
                                json.loads(s)
                            except Exception as ex:
                                problems.append(f'Invalid JSON lastMatch for "{title_text}": {ex}')
                except Exception:
                    pass

                try:
                    raw = e.get('mustContain') or (e.get('node') or {}).get('title') or e.get('title') or ''
                    if not raw:
                        display = (e.get('node') or {}).get('title') or e.get('title') or title_text
                        if display and ' - ' in display:
                            parts = display.split(' - ', 1)
                            if len(parts) == 2:
                                raw = parts[1]
                    if raw:
                        valid, reason = _is_valid_folder_name(raw)
                        if not valid:
                            problems.append(f'Invalid folder-name for "{title_text}": {reason}')
                except Exception:
                    pass

                preview_list.append(e)

            dlg = tk.Toplevel(root)
            dlg.title('Preview Generation')
            dlg.transient(root)
            dlg.grab_set()
            ttk.Label(dlg, text=f'Generate {len(preview_list)} rule(s) for {season} {year}').pack(anchor='w', padx=8, pady=(8,0))

            prob_frame = ttk.Frame(dlg)
            prob_frame.pack(fill='x', padx=8, pady=(6,0))
            if problems:
                ttk.Label(prob_frame, text='Validation issues:', foreground='red').pack(anchor='w')
                prob_box = tk.Text(prob_frame, height=min(10, max(3, len(problems))), width=100)
                prob_box.pack(fill='both', expand=True)
                try:
                    for p in problems:
                        prob_box.insert('end', p + '\n')
                    prob_box.config(state='disabled')
                except Exception:
                    pass
            else:
                ttk.Label(prob_frame, text='No validation issues detected.', foreground='green').pack(anchor='w')

            ttk.Label(dlg, text='Preview JSON (read-only):').pack(anchor='w', padx=8, pady=(6,0))
            preview_text = tk.Text(dlg, height=18, width=100)
            preview_text.pack(fill='both', expand=True, padx=8, pady=(0,6))
            try:
                preview_text.insert('1.0', json.dumps({'season': season, 'year': year, 'rules': preview_list}, indent=2))
            except Exception:
                preview_text.insert('1.0', str(preview_list))
            try:
                preview_text.config(state='disabled')
            except Exception:
                pass

            btns = ttk.Frame(dlg)
            btns.pack(fill='x', padx=8, pady=8)

            def _do_proceed():
                try:
                    if problems:
                        if not messagebox.askyesno('Proceed with Warnings', f'{len(problems)} validation issue(s) detected. Proceed anyway?'):
                            return
                    dlg.destroy()
                    status_var.set(f"Generating rules for {season} {year}...")
                    try:
                        listbox_widget.delete(0, 'end')
                    except Exception:
                        pass
                    try:
                        listbox_widget.insert('end', f"Generated {len(preview_list)} rules for {season} {year}")
                    except Exception:
                        pass
                    status_var.set(f"Generation complete for {season} {year}.")
                except Exception as e:
                    messagebox.showerror('Generation Error', f'An error occurred during generation: {e}')

            def _do_cancel():
                try:
                    dlg.destroy()
                except Exception:
                    pass

            ttk.Button(btns, text='Proceed', command=_do_proceed).pack(side='right', padx=(4,0))
            ttk.Button(btns, text='Cancel', command=_do_cancel).pack(side='right')

            dlg.wait_window()

        except Exception as e:
            messagebox.showerror("Generation Error", f"An error occurred during generation: {e}")

    try:
        root.mainloop()
    except Exception as e:
        try:
            messagebox.showerror("Unexpected Error", f"An unexpected error occurred: {e}")
        except Exception:
            pass


def exit_handler() -> None:

    def _custom_excepthook(exc_type, exc_value, exc_traceback):
        try:
            if exc_type is AttributeError and '_http_session' in str(exc_value):
                return
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _custom_excepthook


__all__ = ["setup_gui", "exit_handler"]


def main() -> None:
    exit_handler()
    setup_gui()


if __name__ == "__main__":
    main()
