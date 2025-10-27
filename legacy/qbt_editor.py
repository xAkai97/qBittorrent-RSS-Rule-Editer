import json
import logging
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
from typing import Optional, Dict, List, Tuple, Any, Union

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

# ==================== Logging Configuration ====================
logging.basicConfig(
    filename='qbt_editor.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==================== Custom Exception Classes ====================
class QBittorrentAuthenticationError(Exception):
    """Raised when authentication with qBittorrent fails."""
    pass


# ==================== Constants ====================
class Season:
    """Season name constants."""
    WINTER = "Winter"
    SPRING = "Spring"
    SUMMER = "Summer"
    FALL = "Fall"


class CacheKeys:
    """Cache dictionary key constants."""
    RECENT_FILES = 'recent_files'
    CATEGORIES = 'categories'
    FEEDS = 'feeds'
    PREFS = 'prefs'
    SUBSPLEASE_TITLES = 'subsplease_titles'


class PrefKeys:
    """User preference key constants."""
    TIME_24 = 'time_24'
    AUTO_SANITIZE = 'auto_sanitize_imports'


class FileSystem:
    """Filesystem-related constants."""
    INVALID_CHARS = '<>:"/\\|?*'
    RESERVED_NAMES = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    MAX_PATH_LENGTH = 255


# ==================== Configuration Management ====================
class AppConfig:
    """Application configuration manager with type-safe access to settings."""
    
    def __init__(self):
        # File paths and defaults
        self.CONFIG_FILE: str = 'config.ini'
        self.OUTPUT_CONFIG_FILE_NAME: str = 'qbittorrent_rules.json'
        self.CACHE_FILE: str = 'seasonal_cache.json'
        
        self.DEFAULT_RSS_FEED: str = "https://subsplease.org/rss/?r=1080"
        self.DEFAULT_SAVE_PREFIX: str = "/downloads/Anime/Web/"
        
        # Connection configuration
        self.QBT_PROTOCOL: Optional[str] = None
        self.QBT_HOST: Optional[str] = None
        self.QBT_PORT: Optional[int] = None
        self.QBT_USER: Optional[str] = None
        self.QBT_PASS: Optional[str] = None
        self.QBT_VERIFY_SSL: bool = True
        self.CONNECTION_MODE: str = 'online'
        self.QBT_CA_CERT: Optional[str] = None
        
        # Application state
        self.RECENT_FILES: List[str] = []
        self.CACHED_CATEGORIES: Dict[str, Any] = {}
        self.CACHED_FEEDS: Dict[str, Any] = {}
        self.ALL_TITLES: Dict[str, List[Any]] = {}
        
        # API Endpoints
        self.QBT_AUTH_LOGIN: str = "/api/v2/auth/login"
        self.QBT_TORRENTS_CATEGORIES: str = "/api/v2/torrents/categories"
        self.QBT_RSS_FEEDS: str = "/api/v2/rss/items"
        self.QBT_RSS_RULES: str = "/api/v2/rss/rules"
        self.QBT_API_BASE: str = "/api/v2"
    
    def get_pref(self, key: str, default: Any = None) -> Any:
        """Get a preference value with fallback."""
        try:
            cache = self._load_cache_data()
            prefs = cache.get(CacheKeys.PREFS, {})
            return prefs.get(key, default)
        except Exception as e:
            logger.warning(f"Failed to get preference '{key}': {e}")
            return default
    
    def set_pref(self, key: str, value: Any) -> bool:
        """Set a preference value."""
        try:
            cache = self._load_cache_data()
            if CacheKeys.PREFS not in cache:
                cache[CacheKeys.PREFS] = {}
            cache[CacheKeys.PREFS][key] = value
            self._save_cache_data(cache)
            return True
        except Exception as e:
            logger.error(f"Failed to set preference '{key}': {e}")
            return False
    
    def _load_cache_data(self) -> Dict[str, Any]:
        """Load cache data from file."""
        try:
            if os.path.exists(self.CACHE_FILE):
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load cache file: {e}")
        return {}
    
    def _save_cache_data(self, data: Dict[str, Any]) -> bool:
        """Save cache data to file."""
        try:
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save cache file: {e}")
            return False
    
    def load_cached_categories(self) -> None:
        """Load cached categories from file."""
        try:
            cache = self._load_cache_data()
            self.CACHED_CATEGORIES = cache.get(CacheKeys.CATEGORIES, {})
            logger.info(f"Loaded {len(self.CACHED_CATEGORIES)} cached categories")
        except Exception as e:
            logger.error(f"Failed to load cached categories: {e}")
            self.CACHED_CATEGORIES = {}
    
    def load_cached_feeds(self) -> None:
        """Load cached feeds from file."""
        try:
            cache = self._load_cache_data()
            self.CACHED_FEEDS = cache.get(CacheKeys.FEEDS, {})
            logger.info(f"Loaded {len(self.CACHED_FEEDS)} cached feeds")
        except Exception as e:
            logger.error(f"Failed to load cached feeds: {e}")
            self.CACHED_FEEDS = {}
    
    def add_recent_file(self, filepath: str) -> None:
        """Add a file to the recent files list."""
        try:
            if filepath in self.RECENT_FILES:
                self.RECENT_FILES.remove(filepath)
            self.RECENT_FILES.insert(0, filepath)
            self.RECENT_FILES = self.RECENT_FILES[:10]  # Keep only last 10
            
            cache = self._load_cache_data()
            cache[CacheKeys.RECENT_FILES] = self.RECENT_FILES
            self._save_cache_data(cache)
            logger.info(f"Added recent file: {filepath}")
        except Exception as e:
            logger.error(f"Failed to add recent file: {e}")


# Global config instance
config = AppConfig()


# API Endpoints (deprecated - use config.QBT_* instead)
QBT_AUTH_LOGIN = config.QBT_AUTH_LOGIN
QBT_TORRENTS_CATEGORIES = config.QBT_TORRENTS_CATEGORIES
QBT_RSS_FEEDS = config.QBT_RSS_FEEDS
QBT_RSS_RULES = config.QBT_RSS_RULES
QBT_API_BASE = config.QBT_API_BASE

# File paths and defaults (deprecated - use config.* instead)
CONFIG_FILE = config.CONFIG_FILE
OUTPUT_CONFIG_FILE_NAME = config.OUTPUT_CONFIG_FILE_NAME
CACHE_FILE = config.CACHE_FILE

DEFAULT_RSS_FEED = config.DEFAULT_RSS_FEED
DEFAULT_SAVE_PREFIX = config.DEFAULT_SAVE_PREFIX

# Connection configuration (deprecated - use config.QBT_* instead)
QBT_PROTOCOL = config.QBT_PROTOCOL
QBT_HOST = config.QBT_HOST
QBT_PORT = config.QBT_PORT
QBT_USER = config.QBT_USER
QBT_PASS = config.QBT_PASS
QBT_VERIFY_SSL = config.QBT_VERIFY_SSL
CONNECTION_MODE = config.CONNECTION_MODE
QBT_CA_CERT = config.QBT_CA_CERT

# Application state (deprecated - use config.* instead)
RECENT_FILES = config.RECENT_FILES
CACHED_CATEGORIES = config.CACHED_CATEGORIES
CACHED_FEEDS = config.CACHED_FEEDS
ALL_TITLES = config.ALL_TITLES


def _load_cache_data() -> Dict[str, Any]:
    """
    Loads application cache data from JSON file.
    
    Returns:
        dict: Cache data containing recent files, categories, feeds, and preferences,
              or empty dict if cache doesn't exist or is invalid
    """
    cache_path = Path(CACHE_FILE)
    try:
        if cache_path.exists():
            data = json.loads(cache_path.read_text(encoding='utf-8'))
            return data or {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in cache file: {e}")
    except Exception as e:
        logger.error(f"Failed to load cache data: {e}")
    return {}


def _save_cache_data(data: Dict[str, Any]) -> bool:
    """
    Saves application cache data to JSON file.
    
    Args:
        data: Dictionary containing cache data to persist
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        cache_path = Path(CACHE_FILE)
        cache_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
        return True
    except Exception as e:
        logger.error(f"Failed to save cache data: {e}")
        return False


def _update_cache_key(key: str, value: Any) -> bool:
    """
    Updates a specific key in the cache file.
    
    Args:
        key: Cache key to update (e.g., 'recent_files', 'categories')
        value: New value to store for the key
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        data = _load_cache_data()
        data[key] = value
        return _save_cache_data(data)
    except Exception as e:
        logger.error(f"Failed to update cache key '{key}': {e}")
        return False


def load_recent_files() -> List[str]:
    """
    Loads the list of recently opened files from cache.
    
    Returns:
        list: List of recently opened file paths
    """
    global RECENT_FILES
    data = _load_cache_data()
    RECENT_FILES = data.get(CacheKeys.RECENT_FILES, []) or []
    return RECENT_FILES


def load_cached_categories() -> Dict[str, Any]:
    """
    Loads cached qBittorrent categories from cache.
    
    Returns:
        dict: Dictionary of cached categories
    """
    global CACHED_CATEGORIES
    try:
        data = _load_cache_data()
        CACHED_CATEGORIES = data.get(CacheKeys.CATEGORIES, {}) or {}
        logger.debug(f"Loaded {len(CACHED_CATEGORIES)} cached categories")
    except Exception as e:
        logger.error(f"Failed to load cached categories: {e}")
        CACHED_CATEGORIES = {}
    return CACHED_CATEGORIES


def load_cached_feeds() -> Dict[str, Any]:
    """
    Loads cached RSS feeds from cache.
    
    Returns:
        dict: Dictionary of cached RSS feed URLs
    """
    global CACHED_FEEDS
    try:
        data = _load_cache_data()
        CACHED_FEEDS = data.get(CacheKeys.FEEDS, {}) or {}
        logger.debug(f"Loaded {len(CACHED_FEEDS)} cached feeds")
    except Exception as e:
        logger.error(f"Failed to load cached feeds: {e}")
        CACHED_FEEDS = {}
    return CACHED_FEEDS


def save_cached_feeds(feeds: Dict[str, Any]) -> bool:
    """
    Saves RSS feeds to cache for future use.
    
    Args:
        feeds: Dictionary of RSS feed URLs to cache
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    global CACHED_FEEDS
    try:
        CACHED_FEEDS = feeds or {}
        return _update_cache_key(CacheKeys.FEEDS, CACHED_FEEDS)
    except Exception as e:
        logger.error(f"Failed to save cached feeds: {e}")
        return False


def save_cached_categories(categories: Dict[str, Any]) -> bool:
    """
    Saves qBittorrent categories to cache for future use.
    
    Args:
        categories: Dictionary of categories to cache
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    global CACHED_CATEGORIES
    try:
        CACHED_CATEGORIES = categories or {}
        return _update_cache_key(CacheKeys.CATEGORIES, CACHED_CATEGORIES)
    except Exception as e:
        logger.error(f"Failed to save cached categories: {e}")
        return False


def save_recent_files() -> bool:
    """
    Persists the current recent files list to cache.
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        return _update_cache_key(CacheKeys.RECENT_FILES, RECENT_FILES)
    except Exception as e:
        logger.error(f"Failed to save recent files: {e}")
        return False


def load_prefs() -> Dict[str, Any]:
    """
    Loads user preferences from cache.
    
    Returns:
        dict: Dictionary of user preferences
    """
    try:
        data = _load_cache_data()
        return data.get(CacheKeys.PREFS, {}) or {}
    except Exception as e:
        logger.error(f"Failed to load preferences: {e}")
        return {}


def save_prefs(prefs: Dict[str, Any]) -> bool:
    """
    Saves user preferences to cache.
    
    Args:
        prefs: Dictionary of user preferences to persist
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        return _update_cache_key(CacheKeys.PREFS, prefs or {})
    except Exception as e:
        logger.error(f"Failed to save preferences: {e}")
        return False


def get_pref(key: str, default: Any = None) -> Any:
    """
    Retrieves a specific preference value.
    
    Args:
        key: Preference key to retrieve
        default: Default value if key doesn't exist (default: None)
    
    Returns:
        Any: The preference value or default
    """
    try:
        prefs = load_prefs()
        return prefs.get(key, default)
    except Exception as e:
        logger.warning(f"Failed to get preference '{key}': {e}")
        return default


def set_pref(key: str, value: Any) -> bool:
    """
    Sets a specific preference value.
    
    Args:
        key: Preference key to set
        value: Value to store for the preference
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        prefs = load_prefs()
        prefs[key] = value
        return save_prefs(prefs)
    except Exception as e:
        logger.error(f"Failed to set preference '{key}': {e}")
        return False


def add_recent_file(path: str, limit: int = 10) -> bool:
    """
    Adds a file path to the recent files list with LRU (Least Recently Used) behavior.
    
    Args:
        path: Absolute path to the file
        limit: Maximum number of recent files to keep (default: 10)
    
    Returns:
        bool: True if file was added successfully, False otherwise
    """
    global RECENT_FILES
    try:
        if not path:
            return False

        load_recent_files()
        path = str(path)

        if path in RECENT_FILES:
            RECENT_FILES.remove(path)

        RECENT_FILES.insert(0, path)
        RECENT_FILES = RECENT_FILES[:limit]
        success = save_recent_files()
        if success:
            logger.info(f"Added recent file: {path}")
        return success
    except Exception as e:
        logger.error(f"Failed to add recent file: {e}")
        return False


def clear_recent_files() -> bool:
    """
    Clears the recent files list and persists the change.
    """
    global RECENT_FILES
    RECENT_FILES = []
    save_recent_files()


# ==================== SubsPlease Schedule Scraper ====================
def load_subsplease_cache() -> Dict[str, Dict[str, Any]]:
    """
    Loads cached SubsPlease schedule titles from cache.
    
    Returns:
        dict: Dictionary mapping MAL title -> feed title variations
              Format: {
                  "Anime Title": {
                      "subsplease": "SubsPlease Title",
                      "last_updated": timestamp,
                      "exact_match": bool
                  }
              }
    """
    try:
        data = _load_cache_data()
        cached = data.get(CacheKeys.SUBSPLEASE_TITLES, {}) or {}
        logger.info(f"Loaded {len(cached)} cached SubsPlease titles")
        return cached
    except Exception as e:
        logger.error(f"Failed to load SubsPlease cache: {e}")
        return {}


def save_subsplease_cache(titles_dict: Dict[str, Dict[str, Any]]) -> bool:
    """
    Saves SubsPlease schedule titles to cache.
    
    Args:
        titles_dict: Dictionary of title mappings to cache
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        success = _update_cache_key(CacheKeys.SUBSPLEASE_TITLES, titles_dict)
        if success:
            logger.info(f"Saved {len(titles_dict)} SubsPlease titles to cache")
        return success
    except Exception as e:
        logger.error(f"Failed to save SubsPlease cache: {e}")
        return False


def fetch_subsplease_schedule(force_refresh: bool = False) -> Tuple[bool, Union[List[str], str]]:
    """
    Fetches current anime titles from SubsPlease API.
    
    Uses the SubsPlease API (https://subsplease.org/api/?f=schedule&tz=UTC) 
    to get the current season's anime schedule and extract all show titles.
    
    IMPORTANT: This uses SubsPlease's public API. Please use responsibly and consider:
    - Rate limiting to avoid excessive requests
    - Caching results to minimize API calls
    - Checking SubsPlease's terms of service for any usage restrictions
    
    Args:
        force_refresh: If True, fetches from API even if cache exists
    
    Returns:
        Tuple[bool, Union[List[str], str]]: (success, list_of_titles or error_message)
    """
    if not requests:
        return False, "requests library not available"
    
    # Check cache first unless force refresh
    if not force_refresh:
        cached = load_subsplease_cache()
        if cached:
            titles = list(cached.keys())
            logger.info(f"Using cached SubsPlease titles: {len(titles)} entries")
            return True, titles
    
    try:
        # Use SubsPlease API instead of scraping HTML
        url = "https://subsplease.org/api/?f=schedule&tz=UTC"
        logger.info(f"Fetching SubsPlease schedule from API: {url}")
        
        # Add proper headers to identify the application
        headers = {
            'User-Agent': 'qBittorrent-RSS-Rule-Editor/1.0 (https://github.com/xAkai97/qBittorrent-RSS-Rule-Editer)',
            'Accept': 'application/json'
        }
        
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        
        if not isinstance(data, dict) or 'schedule' not in data:
            return False, "Invalid API response format"
        
        # Extract titles from all days
        titles = []
        schedule = data['schedule']
        
        for day, shows in schedule.items():
            if isinstance(shows, list):
                for show in shows:
                    if isinstance(show, dict):
                        title = show.get('title', '').strip()
                        if title and title not in titles:
                            titles.append(title)
        
        if not titles:
            return False, "No titles found in API response"
        
        # Cache the results with timestamp
        timestamp = datetime.now().isoformat()
        cache_dict = {}
        for title in titles:
            cache_dict[title] = {
                "subsplease": title,
                "last_updated": timestamp,
                "exact_match": True
            }
        
        save_subsplease_cache(cache_dict)
        logger.info(f"Successfully fetched {len(titles)} titles from SubsPlease API")
        
        return True, sorted(titles)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error fetching SubsPlease schedule: {e}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Error parsing SubsPlease schedule: {e}"
        logger.error(error_msg)
        return False, error_msg


def find_subsplease_title_match(mal_title: str) -> Optional[str]:
    """
    Finds matching SubsPlease title for a given MAL title from cache.
    
    Uses fuzzy matching if exact match not found.
    
    Args:
        mal_title: The anime title from MyAnimeList
    
    Returns:
        Optional[str]: Matching SubsPlease title or None if no match
    """
    cached = load_subsplease_cache()
    
    # Try exact match first
    if mal_title in cached:
        match_data = cached[mal_title]
        if isinstance(match_data, dict):
            return match_data.get('subsplease', mal_title)
        return str(match_data)
    
    # Try case-insensitive match
    mal_lower = mal_title.lower()
    for cached_title, data in cached.items():
        if cached_title.lower() == mal_lower:
            if isinstance(data, dict):
                return data.get('subsplease', cached_title)
            return cached_title
    
    # Try fuzzy matching
    try:
        from difflib import SequenceMatcher
        
        best_match = None
        best_ratio = 0.0
        threshold = 0.8  # 80% similarity threshold
        
        for cached_title in cached.keys():
            ratio = SequenceMatcher(None, mal_lower, cached_title.lower()).ratio()
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_match = cached_title
        
        if best_match:
            logger.info(f"Fuzzy match: '{mal_title}' -> '{best_match}' (similarity: {best_ratio:.2%})")
            match_data = cached[best_match]
            if isinstance(match_data, dict):
                return match_data.get('subsplease', best_match)
            return best_match
    
    except Exception as e:
        logger.error(f"Error in fuzzy matching: {e}")
    
    return None


def load_config() -> bool:
    """
    Loads qBittorrent connection configuration from config.ini file.
    
    Reads configuration file and populates global configuration variables
    for qBittorrent API connection parameters.
    
    Returns:
        bool: True if configuration loaded successfully with host and port,
              False otherwise
    """
    global QBT_PROTOCOL, QBT_HOST, QBT_PORT, QBT_USER, QBT_PASS, CONNECTION_MODE, QBT_VERIFY_SSL, QBT_CA_CERT
    
    try:
        cfg = ConfigParser()
        cfg.read(CONFIG_FILE)

        qbt_loaded = 'QBITTORRENT_API' in cfg
        if qbt_loaded:
            QBT_PROTOCOL = cfg['QBITTORRENT_API'].get('protocol', 'http')
            QBT_HOST = cfg['QBITTORRENT_API'].get('host', 'localhost')
            QBT_PORT = cfg['QBITTORRENT_API'].get('port', '8080')
            QBT_USER = cfg['QBITTORRENT_API'].get('username', '')
            QBT_PASS = cfg['QBITTORRENT_API'].get('password', '')
            CONNECTION_MODE = cfg['QBITTORRENT_API'].get('mode', 'online')
            QBT_VERIFY_SSL = cfg['QBITTORRENT_API'].get('verify_ssl', 'True').lower() == 'true'
            QBT_CA_CERT = cfg['QBITTORRENT_API'].get('ca_cert', '')
            logger.info(f"Loaded qBittorrent config: {QBT_PROTOCOL}://{QBT_HOST}:{QBT_PORT} (mode: {CONNECTION_MODE})")
        else:
            QBT_PROTOCOL, QBT_HOST, QBT_PORT, QBT_USER, QBT_PASS = ('http', 'localhost', '8080', '', '')
            QBT_VERIFY_SSL = False
            CONNECTION_MODE = 'online'
            logger.warning("No QBITTORRENT_API section found in config.ini, using defaults")

        return bool(QBT_HOST and QBT_PORT)
    except Exception as e:
        logger.error(f"Failed to load config from INI: {e}")
        return False


def save_config(protocol: str, host: str, port: str, user: str, password: str, mode: str, verify_ssl: bool) -> bool:
    """
    Saves qBittorrent connection configuration to config.ini file.
    
    Args:
        protocol: HTTP protocol ('http' or 'https')
        host: qBittorrent host address (IP or hostname)
        port: qBittorrent WebUI port number
        user: WebUI username
        password: WebUI password
        mode: Connection mode ('online' or 'offline')
        verify_ssl: Whether to verify SSL certificates
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    global QBT_PROTOCOL, QBT_HOST, QBT_PORT, QBT_USER, QBT_PASS, CONNECTION_MODE, QBT_VERIFY_SSL, QBT_CA_CERT
    
    try:
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
        logger.info(f"Saved qBittorrent config: {protocol}://{host}:{port} (mode: {mode})")
        return True
    except Exception as e:
        logger.error(f"Failed to save config to INI: {e}")
        return False


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
    """
    Determines the current anime season based on the current date.
    
    Returns:
        tuple[str, str]: A tuple containing (year, season) where season is one of:
                        "Winter" (Jan-Mar), "Spring" (Apr-Jun), 
                        "Summer" (Jul-Sep), or "Fall" (Oct-Dec)
    """
    now = datetime.now()
    year = now.year
    month = now.month
    
    if 1 <= month <= 3:
        season = Season.WINTER
    elif 4 <= month <= 6:
        season = Season.SPRING
    elif 7 <= month <= 9:
        season = Season.SUMMER
    else:
        season = Season.FALL
    
    return str(year), season


def sanitize_folder_name(name: str, replacement_char: str = '_', max_length: int = 255) -> str:
    """
    Sanitizes a string to be safe for use as a folder name.
    
    Removes or replaces invalid filesystem characters, normalizes whitespace,
    and ensures the name complies with Windows/Unix filesystem requirements.
    
    Args:
        name: The string to sanitize
        replacement_char: Character to use for replacing invalid characters (default: '_')
        max_length: Maximum length of the resulting folder name (default: 255)
    
    Returns:
        str: A sanitized folder name safe for filesystem use, or empty string if input is invalid
        
    Examples:
        >>> sanitize_folder_name("My Anime: Season 1")
        'My Anime - Season 1'
        >>> sanitize_folder_name("A/B\\C")
        'A_B_C'
    """
    if not name:
        return ''

    try:
        s = str(name).strip()
        if not s:
            return ''

        s = s.replace(':', ' -')

        # Replace all invalid filesystem characters
        trans_table = str.maketrans(FileSystem.INVALID_CHARS, 
                                    replacement_char * len(FileSystem.INVALID_CHARS))
        s = s.translate(trans_table).strip()

        # Remove trailing spaces and dots (invalid on Windows)
        s = s.rstrip(' .')

        # Collapse multiple replacement characters
        while replacement_char * 2 in s:
            s = s.replace(replacement_char * 2, replacement_char)

        # Handle Windows reserved names
        if s:
            base = s.split('.')[0].upper()
            if base in FileSystem.RESERVED_NAMES:
                s = s + replacement_char

        # Truncate to max length
        if len(s) > max_length:
            s = s[:max_length]

        return s
    except Exception:
        try:
            return str(name).replace('/', replacement_char)[:max_length]
        except Exception:
            return ''


def _get_ssl_verification_parameter(verify_ssl: bool, ca_cert: typing.Optional[str] = None) -> typing.Union[bool, str]:
    """
    Determines the SSL verification parameter for qBittorrent API requests.
    
    Args:
        verify_ssl: Whether SSL verification is enabled
        ca_cert: Optional path to CA certificate file
    
    Returns:
        Union[bool, str]: CA cert path if provided and SSL verification is enabled,
                         otherwise returns the verify_ssl boolean
    """
    return ca_cert if (ca_cert and verify_ssl) else verify_ssl


def _setup_rss_feed(qbt: typing.Any, feed_url: str) -> None:
    """
    Adds and refreshes an RSS feed in qBittorrent.
    
    Args:
        qbt: qBittorrent API client instance
        feed_url: RSS feed URL to add
    """
    try:
        domain = feed_url.split('//')[1].split('/')[0]
        feed_path = f"Anime Feeds/{domain}"
        try:
            qbt.rss_add_feed(url=feed_url, item_path=feed_path)
            qbt.rss_refresh_item(item_path=feed_path)
        except Conflict409Error:
            pass  # Feed already exists
    except Exception:
        pass


def _fetch_qbittorrent_metadata(full_host: str, username: str, password: str, verify_param: typing.Union[bool, str]) -> tuple[dict, dict]:
    """
    Fetches categories and feeds from qBittorrent via HTTP API.
    
    Args:
        full_host: Complete qBittorrent URL with protocol and port
        username: qBittorrent username
        password: qBittorrent password
        verify_param: SSL verification parameter
    
    Returns:
        tuple[dict, dict]: (categories, feeds) dictionaries
    """
    categories = {}
    feeds = {}
    
    try:
        session = requests.Session()
        login_url = f"{full_host}{QBT_AUTH_LOGIN}"
        lresp = session.post(login_url, data={"username": username, "password": password}, 
                            timeout=10, verify=verify_param)
        
        if lresp.status_code in (200, 201) and (lresp.text or '').strip().lower() in ('ok.', 'ok'):
            # Fetch categories
            cat_url = f"{full_host}{QBT_TORRENTS_CATEGORIES}"
            cresp = session.get(cat_url, timeout=10, verify=verify_param)
            if cresp.status_code == 200:
                try:
                    categories = cresp.json() or {}
                except Exception:
                    pass
            
            # Fetch feeds
            feeds_url = f"{full_host}{QBT_RSS_FEEDS}"
            fresp = session.get(feeds_url, timeout=10, verify=verify_param)
            if fresp.status_code == 200:
                try:
                    feeds = fresp.json() or {}
                except Exception:
                    pass
    except Exception:
        pass
    
    return categories, feeds


def _get_default_feed_url(feeds: dict, fallback: str) -> str:
    """
    Extracts a default feed URL from feeds dictionary.
    
    Args:
        feeds: Dictionary of RSS feeds from qBittorrent
        fallback: Fallback URL if no feeds found
    
    Returns:
        str: First available feed URL or fallback
    """
    if not feeds or not isinstance(feeds, dict):
        return fallback
    
    vals = [v for v in (feeds.values() or []) if isinstance(v, dict) and v.get('url')]
    if vals:
        return vals[0].get('url') or fallback
    
    return fallback


def _get_entry_title(entry: typing.Union[dict, str]) -> str:
    """
    Safely extracts the title from an entry.
    
    Args:
        entry: Entry dictionary or string
    
    Returns:
        str: Title string or empty string
    """
    if isinstance(entry, dict):
        node = entry.get('node') or {}
        return (node.get('title') or 
                entry.get('mustContain') or 
                entry.get('title') or 
                entry.get('name') or '')
    return str(entry) if entry else ''


def _get_entry_save_path(entry: dict) -> str:
    """
    Safely extracts the save path from an entry.
    
    Args:
        entry: Entry dictionary
    
    Returns:
        str: Save path or empty string
    """
    if not isinstance(entry, dict):
        return ''
    
    # Try direct savePath field
    save_path = entry.get('savePath') or entry.get('save_path')
    if save_path:
        return str(save_path)
    
    # Try torrentParams
    torrent_params = entry.get('torrentParams') or entry.get('torrent_params') or {}
    if isinstance(torrent_params, dict):
        return str(torrent_params.get('save_path') or torrent_params.get('download_path') or '')
    
    return ''


def _validate_qbittorrent_connection_config() -> tuple[bool, str]:
    """
    Validates that qBittorrent connection configuration is complete.
    
    Returns:
        tuple[bool, str]: (is_valid, error_message) where is_valid is True if
                         all required connection parameters are set
    """
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
    """
    Creates a qBittorrent RSS auto-download rule configuration dictionary.
    
    Args:
        save_path: Filesystem path where torrents should be saved
        must_contain: Pattern that RSS item titles must contain to match
        feed_url: RSS feed URL to monitor
        category: Optional qBittorrent category to assign to downloads
    
    Returns:
        dict: Complete RSS rule configuration matching qBittorrent's API schema
    """
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
    """
    Creates and configures a qBittorrent API client instance.
    
    Args:
        host: Full qBittorrent host URL (e.g., "http://localhost:8080")
        username: qBittorrent WebUI username
        password: qBittorrent WebUI password
        verify_ssl: Whether to verify SSL certificates
    
    Returns:
        Client: Configured qBittorrent API client instance
        
    Raises:
        TypeError: If the qBittorrent API client doesn't support the verify_ssl parameter
    """
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
    """
    Synchronizes RSS download rules to a running qBittorrent instance.
    
    Creates and uploads RSS auto-download rules for the provided anime titles
    to the configured qBittorrent server.
    
    Args:
        selected_titles: List of anime title strings to create rules for
        rule_prefix: Prefix to add to rule names (typically "Season Year")
        year: Year string for organizing downloads
        root: Tkinter root window for UI updates
        status_var: StringVar for status message updates
        
    Raises:
        Shows error dialogs if connection fails or sync encounters errors
    """
    # Validate configuration
    is_valid, error_msg = _validate_qbittorrent_connection_config()
    if not is_valid:
        messagebox.showerror("Error", f"qBittorrent connection details are missing: {error_msg}")
        return

    # Connect to qBittorrent
    full_host = f"{config.QBT_PROTOCOL}://{config.QBT_HOST}:{config.QBT_PORT}"
    status_var.set(f"Connecting to qBittorrent at {full_host}...")
    root.update()

    try:
        qbt = create_qbittorrent_client(host=full_host, username=config.QBT_USER, 
                                       password=config.QBT_PASS, verify_ssl=config.QBT_VERIFY_SSL)
        qbt.auth_log_in()
    except APIConnectionError as e:
        messagebox.showerror("Connection Error", f"Failed to connect or authenticate to qBittorrent.\nDetails: {e}")
        status_var.set("Synchronization failed.")
        return
    except (QBittorrentAuthenticationError, Exception) as e:
        messagebox.showerror("Login Error", f"qBittorrent Login Failed. Check credentials.\nDetails: {e}")
        status_var.set("Synchronization failed.")
        return

    # Setup RSS feed
    _setup_rss_feed(qbt, config.DEFAULT_RSS_FEED)

    # Fetch metadata (categories and feeds)
    try:
        config.load_cached_categories()
        config.load_cached_feeds()
    except Exception:
        pass
    
    verify_param = _get_ssl_verification_parameter(config.QBT_VERIFY_SSL, getattr(config, 'QBT_CA_CERT', None))
    categories, feeds = _fetch_qbittorrent_metadata(full_host, config.QBT_USER, config.QBT_PASS, verify_param)
    
    # Cache the fetched metadata
    if categories:
        try:
            config.save_cached_categories(categories)
        except Exception:
            pass
    if feeds:
        try:
            config.save_cached_feeds(feeds)
        except Exception:
            pass
    
    # Fall back to cached data if fetch failed
    if not categories:
        categories = getattr(config, 'CACHED_CATEGORIES', {}) or {}
    if not feeds:
        feeds = getattr(config, 'CACHED_FEEDS', {}) or {}

    # Create rules for each title
    successful_rules = 0
    assigned_category = f"{rule_prefix} - Anime"
    default_feed = _get_default_feed_url(feeds, config.DEFAULT_RSS_FEED)

    try:
        for title in selected_titles:
            sanitized_folder_name = sanitize_folder_name(title)
            rule_name = f"{rule_prefix} {year} - {sanitized_folder_name}"
            save_path = os.path.join(config.DEFAULT_SAVE_PREFIX, f"{rule_prefix} {year}", 
                                    sanitized_folder_name).replace('\\', '/')

            # Choose appropriate category
            chosen_category = assigned_category
            if categories and chosen_category not in categories:
                prefix_lower = rule_prefix.lower()
                candidate = next((k for k in categories.keys() if k and k.lower().startswith(prefix_lower)), None)
                if candidate:
                    chosen_category = candidate

            # Create and set the rule
            rule_def = _create_qbittorrent_rss_rule(
                save_path=save_path,
                must_contain=sanitized_folder_name,
                feed_url=default_feed,
                category=chosen_category
            )

            qbt.rss_set_rule(rule_name=rule_name, rule_def=rule_def)
            successful_rules += 1

        messagebox.showinfo("Success (Online)", 
                          f"Successfully synchronized {successful_rules} rules to qBittorrent.\n\n"
                          f"All rules are now active in your remote client.")
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
    """
    Tests connection to qBittorrent WebUI with the provided credentials.
    
    Attempts to authenticate with qBittorrent API using both the qbittorrentapi
    library and raw requests, displaying success or failure messages to the user.
    
    Args:
        protocol_var: Tkinter variable containing protocol ('http' or 'https')
        host_var: Tkinter variable containing host address
        port_var: Tkinter variable containing port number
        user_var: Tkinter variable containing username
        pass_var: Tkinter variable containing password
        verify_ssl_var: Tkinter variable for SSL verification toggle
        ca_cert_var: Optional Tkinter variable containing CA certificate path
    """
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
    """
    Fetches existing RSS auto-download rules from qBittorrent.
    
    Args:
        root: Tkinter root window for showing error dialogs
    
    Returns:
        Optional[dict]: Dictionary of rule_name -> rule_config mappings,
                       or None if fetch fails
    """
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
    """
    Creates an authenticated requests session with qBittorrent WebUI.
    
    Args:
        full_host: Complete host URL including protocol and port
        user: Username for authentication
        password: Password for authentication
        verify_param: SSL verification parameter (bool or CA cert path)
        timeout: Request timeout in seconds (default: 10)
    
    Returns:
        Tuple[Optional[Session], Optional[str]]: (authenticated session, error message)
                                                 Session is None if authentication failed
    """
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
    """
    Performs a connectivity test to qBittorrent WebUI.
    
    Attempts to connect using both qbittorrentapi library and raw requests
    to verify API accessibility.
    
    Args:
        protocol: HTTP protocol ('http' or 'https')
        host: qBittorrent host address
        port: qBittorrent WebUI port
        user: WebUI username
        password: WebUI password
        verify_ssl: Whether to verify SSL certificates
        ca_cert: Optional path to CA certificate file
        timeout: Connection timeout in seconds (default: 10)
    
    Returns:
        Tuple[bool, str]: (success, status_message) indicating connection result
    """
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
    """
    Fetches the list of categories from qBittorrent.
    
    Args:
        protocol: HTTP protocol ('http' or 'https')
        host: qBittorrent host address
        port: qBittorrent WebUI port
        user: WebUI username
        password: WebUI password
        verify_ssl: Whether to verify SSL certificates
        ca_cert: Optional path to CA certificate file
        timeout: Request timeout in seconds (default: 10)
    
    Returns:
        Tuple[bool, Union[str, dict]]: (success, categories_dict or error_message)
    """
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
    """
    Fetches the list of RSS feeds from qBittorrent.
    
    Args:
        protocol: HTTP protocol ('http' or 'https')
        host: qBittorrent host address
        port: qBittorrent WebUI port
        user: WebUI username
        password: WebUI password
        verify_ssl: Whether to verify SSL certificates
        ca_cert: Optional path to CA certificate file
        timeout: Request timeout in seconds (default: 10)
    
    Returns:
        Tuple[bool, Union[str, dict]]: (success, feeds_dict or error_message)
    """
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

TREEVIEW_WIDGET = None
LISTBOX_ITEMS = []
_APP_ROOT = None
_APP_STATUS_VAR = None
TRASH_ITEMS = []


def update_treeview_with_titles(all_titles: typing.Union[dict, list]) -> None:
    """
    Updates the main treeview widget with anime titles.
    
    Populates the treeview with titles from either a dictionary (organized by type)
    or a simple list of titles, showing title, category, and save path columns.
    Auto-sizes columns based on content unless user manually resized them.
    
    Args:
        all_titles: Dictionary with media types as keys and title lists as values,
                   or a flat list of titles
    """
    global TREEVIEW_WIDGET, LISTBOX_ITEMS
    if TREEVIEW_WIDGET is None:
        return
    try:
        # Clear all items from treeview
        for item in TREEVIEW_WIDGET.get_children():
            TREEVIEW_WIDGET.delete(item)
    except Exception:
        pass
    LISTBOX_ITEMS = []
    
    # Track maximum lengths for all auto-sizeable columns
    max_index_len = 0
    max_title_len = 0
    max_category_len = 0
    max_savepath_len = 0
    
    try:
        index = 0
        for media_type, items in (all_titles.items() if isinstance(all_titles, dict) else [('anime', all_titles)]):
            for entry in items:
                try:
                    if isinstance(entry, dict):
                        node = entry.get('node') or {}
                        title_text = node.get('title') or entry.get('title') or entry.get('name') or str(entry)
                        
                        # Extract category and save path
                        category = entry.get('assignedCategory') or entry.get('assigned_category') or entry.get('category') or ''
                        
                        # Get save path from various possible locations
                        save_path = entry.get('savePath') or entry.get('save_path') or ''
                        if not save_path:
                            tp = entry.get('torrentParams') or entry.get('torrent_params') or {}
                            save_path = tp.get('save_path') or tp.get('savePath') or tp.get('download_path') or ''
                        
                        # Clean up save path display (convert backslashes to forward slashes)
                        save_path = str(save_path).replace('\\', '/') if save_path else ''
                        
                        # Track longest values for auto-sizing
                        if title_text:
                            max_title_len = max(max_title_len, len(str(title_text)))
                        if category:
                            max_category_len = max(max_category_len, len(str(category)))
                        if save_path:
                            max_savepath_len = max(max_savepath_len, len(save_path))
                    else:
                        title_text = str(entry)
                        category = ''
                        save_path = ''
                        if title_text:
                            max_title_len = max(max_title_len, len(title_text))
                    
                    # Insert into treeview with columns
                    index += 1
                    max_index_len = max(max_index_len, len(str(index)))
                    TREEVIEW_WIDGET.insert('', 'end', text=str(index), 
                                         values=(title_text, category, save_path))
                    LISTBOX_ITEMS.append((title_text, entry))
                except Exception:
                    continue
    except Exception:
        pass
    
    # Auto-adjust column widths based on content (only if not manually resized)
    try:
        # Access the columns_manual_resize tracker from the widget
        if hasattr(TREEVIEW_WIDGET, '_columns_manual_resize'):
            manual_resize = TREEVIEW_WIDGET._columns_manual_resize
            
            # Index column (#0)
            if not manual_resize.get('#0', {}).get('disabled', False):
                if max_index_len > 0:
                    # Include header "#" length as minimum
                    header_len = len('#')
                    calculated_width = max(20, max(max_index_len, header_len) * 8 + 20)
                    TREEVIEW_WIDGET.column('#0', width=calculated_width)
            
            # Title column
            if not manual_resize.get('title', {}).get('disabled', False):
                if max_title_len > 0:
                    # Include header "Title" length as minimum
                    header_len = len('Title')
                    calculated_width = max(150, max(max_title_len, header_len) * 8 + 20)
                    TREEVIEW_WIDGET.column('title', width=calculated_width)
            
            # Category column
            if not manual_resize.get('category', {}).get('disabled', False):
                if max_category_len > 0:
                    # Include header "Category" length as minimum
                    header_len = len('Category')
                    calculated_width = max(100, max(max_category_len, header_len) * 8 + 20)
                    TREEVIEW_WIDGET.column('category', width=calculated_width)
            
            # Save Path column
            if not manual_resize.get('savepath', {}).get('disabled', False):
                if max_savepath_len > 0:
                    # Include header "Save Path" length as minimum
                    header_len = len('Save Path')
                    calculated_width = max(150, max(max_savepath_len, header_len) * 8 + 20)
                    TREEVIEW_WIDGET.column('savepath', width=calculated_width)
    except Exception:
        pass


def _treeview_get_selection_indices():
    """
    Helper function to get selected item indices from Treeview (compatible with Listbox curselection).
    
    Returns:
        tuple: Tuple of integer indices of selected items
    """
    global TREEVIEW_WIDGET
    if TREEVIEW_WIDGET is None:
        return ()
    try:
        selected_items = TREEVIEW_WIDGET.selection()
        indices = []
        all_items = TREEVIEW_WIDGET.get_children()
        for item in selected_items:
            try:
                idx = all_items.index(item)
                indices.append(idx)
            except:
                pass
        return tuple(indices)
    except Exception:
        return ()


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
    screen_height = root.winfo_screenheight()
    optimal_height = min(900, screen_height - 100)  # Leave 100px for taskbar
    settings_win.geometry(f"700x{optimal_height}")
    settings_win.minsize(700, 500)
    settings_win.transient(root)
    settings_win.grab_set()
    settings_win.configure(bg='#f5f5f5')

    qbt_protocol_temp = tk.StringVar(value=config.QBT_PROTOCOL or 'http')
    qbt_host_temp = tk.StringVar(value=config.QBT_HOST or 'localhost')
    qbt_port_temp = tk.StringVar(value=config.QBT_PORT or '8080')
    qbt_user_temp = tk.StringVar(value=config.QBT_USER or '')
    qbt_pass_temp = tk.StringVar(value=config.QBT_PASS or '')
    mode_temp = tk.StringVar(value=config.CONNECTION_MODE or 'online')
    verify_ssl_temp = tk.BooleanVar(value=config.QBT_VERIFY_SSL if config.QBT_VERIFY_SSL is not None else False)
    ca_cert_temp = tk.StringVar(value=getattr(config, 'QBT_CA_CERT', '') or "")

    def save_and_close():
        """
        Saves connection settings and closes the settings dialog.
        """
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

    # Create canvas with scrollbar for main content
    canvas_frame = ttk.Frame(settings_win)
    canvas_frame.pack(fill='both', expand=True, padx=0, pady=0)
    
    canvas = tk.Canvas(canvas_frame, bg='#f5f5f5', highlightthickness=0)
    scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
    main_container = ttk.Frame(canvas)
    
    def _update_settings_scrollregion(event=None):
        try:
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Show/hide scrollbar based on content
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
    
    main_container.bind("<Configure>", _update_settings_scrollregion)
    
    canvas_window = canvas.create_window((0, 0), window=main_container, anchor="nw", width=680)
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Resize canvas window when canvas size changes
    def _on_canvas_configure(event):
        canvas.itemconfig(canvas_window, width=event.width - 5)
    canvas.bind('<Configure>', _on_canvas_configure)
    
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Enable mouse wheel scrolling - widget-specific binding
    def _on_settings_mousewheel(event):
        try:
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except Exception:
            pass
    
    def _bind_settings_mousewheel(event):
        try:
            canvas.bind("<MouseWheel>", _on_settings_mousewheel)
        except Exception:
            pass
    
    def _unbind_settings_mousewheel(event):
        try:
            canvas.unbind("<MouseWheel>")
        except Exception:
            pass
    
    canvas.bind("<Enter>", _bind_settings_mousewheel)
    canvas.bind("<Leave>", _unbind_settings_mousewheel)
    main_container.bind("<Enter>", _bind_settings_mousewheel)
    main_container.bind("<Leave>", _unbind_settings_mousewheel)
    
    # Cleanup on close
    def _cleanup_settings():
        try:
            canvas.unbind("<Enter>")
            canvas.unbind("<Leave>")
            canvas.unbind("<MouseWheel>")
            main_container.unbind("<Enter>")
            main_container.unbind("<Leave>")
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

    qbt_frame = ttk.LabelFrame(main_container, text="🔧 qBittorrent Web UI Configuration", padding=12)
    qbt_frame.pack(fill='x', pady=(0, 10), padx=10)
    qbt_frame = ttk.LabelFrame(main_container, text="🔧 qBittorrent Web UI Configuration", padding=15)
    qbt_frame.pack(fill='x', pady=(0, 15))
    
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
    
    # Status and test section
    status_frame = ttk.Frame(qbt_frame)
    status_frame.grid(row=6, column=0, columnspan=4, sticky='ew', padx=5, pady=(15, 5))
    
    settings_conn_status = tk.StringVar(value='⚪ Not tested')
    status_label = ttk.Label(status_frame, textvariable=settings_conn_status, font=('Segoe UI', 9))
    status_label.pack(side='left', padx=5)
    
    ttk.Label(qbt_frame, text="💡 Tip: Ensure WebUI is enabled in qBittorrent settings",
              font=('Segoe UI', 8), foreground='#666').grid(row=7, column=0, columnspan=4, sticky='w', padx=5, pady=(5, 0))

    def _run_test_and_update():
        """
        Runs connection test in background thread and updates status.
        """
        def _worker():
            try:
                settings_conn_status.set('⏳ Testing connection...')
                ok, msg = qbt_api.ping_qbittorrent(qbt_protocol_temp.get(), qbt_host_temp.get(), qbt_port_temp.get(), qbt_user_temp.get(), qbt_pass_temp.get(), bool(verify_ssl_temp.get()), ca_cert_temp.get() if ca_cert_temp.get().strip() else None)
                if ok:
                    settings_conn_status.set('✅ Connected: ' + msg)
                else:
                    settings_conn_status.set('❌ Failed: ' + msg)
            except Exception as e:
                settings_conn_status.set('❌ Error: ' + str(e))
        try:
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            settings_conn_status.set('❌ Test failed to start')

    test_btn = ttk.Button(status_frame, text="🔍 Test Connection", command=_run_test_and_update, style='Accent.TButton')
    test_btn.pack(side='right', padx=5)

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
            try:
                cat_listbox.yview_scroll(int(-1*(event.delta/120)), "units")
                return "break"  # Prevent event propagation
            except Exception:
                pass
        
        cat_listbox.bind("<MouseWheel>", _on_cat_mousewheel)

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

    # Footer with buttons - outside scrollable area
    footer_frame = ttk.Frame(settings_win, padding=10)
    footer_frame.pack(fill='x', side='bottom')
    
    save_btn = ttk.Button(footer_frame, text="💾 Save & Close", command=save_and_close, style='Accent.TButton', width=20)
    save_btn.pack(side='right', padx=5)
    
    cancel_btn = ttk.Button(footer_frame, text="✕ Cancel", command=settings_win.destroy, width=15)
    cancel_btn.pack(side='right')


def setup_gui() -> tk.Tk:
    """
    Initializes and configures the main application GUI.
    
    Creates the main window with all UI components including:
    - Menu bar with File, Edit, Settings, and Info menus
    - Season/Year selection controls
    - Title listbox with context menu
    - Rule editor panel
    - Status bar
    
    Returns:
        tk.Tk: Configured root Tkinter window
    """
    config_set = config.load_config()
    root = tk.Tk()
    root.title("qBittorrent RSS Rules Editor")
    
    # Position window away from taskbar
    try:
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = 1200
        window_height = 900
        # Position at top-center with some margin from top
        x = (screen_width - window_width) // 2
        y = 50  # 50px from top to avoid covering with taskbar
        root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    except Exception:
        root.geometry("1200x900")
    
    root.minsize(1000, 700)

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
    style.configure('RefreshButton.TButton', font=('Segoe UI', 18), padding=0)  # Larger icon, no padding for full button fill
    style.configure('TCombobox', padding=5)
    style.configure('TEntry', padding=5)
    
    # Configure treeview scrollbar colors
    style.configure('TScrollbar', background=frame_bg, troughcolor=bg_color)

    current_year, current_season = get_current_anime_season()
    season_var = tk.StringVar(value=current_season)
    year_var = tk.StringVar(value=current_year)

    def _get_connection_status():
        """
        Generates a status message describing the current connection mode.
        
        Returns:
            str: Connection status message based on current mode
        """
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
    global _APP_ROOT, _APP_STATUS_VAR, TREEVIEW_WIDGET, LISTBOX_ITEMS
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
        """
        Starts a background thread to automatically connect to qBittorrent.
        
        Attempts up to 3 connection retries with 2-second delays between attempts.
        Updates status_var with connection progress and results.
        """
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
        elif (getattr(config, 'CONNECTION_MODE', '') or '').lower() == 'online':
            # Auto-test connection for online mode if settings are filled
            def _auto_test_online():
                def worker():
                    try:
                        # Check if required settings are filled
                        host = getattr(config, 'QBT_HOST', '').strip()
                        port = str(getattr(config, 'QBT_PORT', '')).strip()
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

    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill='both', expand=True)
    root.configure(bg='#f5f5f5')

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
        """
        Refreshes the Recent Files menu with current file history.
        
        Clears and rebuilds the recent files menu, adding commands to open
        each recent file and a command to clear the history.
        """
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
                        update_treeview_with_titles(config.ALL_TITLES)
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

    def open_log_viewer():
        """
        Opens a window displaying the application log file.
        
        Shows the last 500 lines of the log file with auto-refresh capability
        and buttons to clear or open the full log file.
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

    info_menu = tk.Menu(menubar, tearoff=0)
    def show_about():
        """
        Displays the About dialog with application information.
        """
        messagebox.showinfo('About qBittorrent RSS Rule Editor', 'qBittorrent RSS Rule Editor\n\nGenerate and sync qBittorrent RSS rules for seasonal anime.\nRun: python -m qbt_editor')
    info_menu.add_command(label='View Logs...', command=open_log_viewer)
    info_menu.add_separator()
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
    top_config_frame.pack(fill='x', pady=(0, 5))
    
    # Add a title label
    title_label = ttk.Label(top_config_frame, text="Season Configuration", font=('Segoe UI', 11, 'bold'))
    title_label.grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 3))
    
    ttk.Label(top_config_frame, text="Season:").grid(row=1, column=0, sticky='w', padx=(0, 5), pady=5)
    season_dropdown = ttk.Combobox(top_config_frame, textvariable=season_var, values=["Winter", "Spring", "Summer", "Fall"], state="readonly", width=5)
    season_dropdown.grid(row=1, column=1, sticky='w', padx=5, pady=5)
    
    ttk.Label(top_config_frame, text="Year:").grid(row=1, column=2, sticky='w', padx=(15, 5), pady=5)
    year_entry = ttk.Entry(top_config_frame, textvariable=year_var, width=5)
    year_entry.grid(row=1, column=3, sticky='w', padx=5, pady=5)
    
    # Keep prefix_imports_var for compatibility but don't show checkbox (moved to settings)
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
    except Exception:
        prefix_imports_var = tk.BooleanVar(value=True)
    
    top_config_frame.grid_columnconfigure(3, weight=1)

    # Sync from qBittorrent button stays at top
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
                                            update_treeview_with_titles(config.ALL_TITLES)
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
        
        # Add Secondary style for sync button
        style.configure('Secondary.TButton', foreground='white', background='#5c636a', font=('Segoe UI', 9))
        style.map('Secondary.TButton', background=[('active', '#4a5056')])
        
        # Sync button at top with better color
        sync_btn = ttk.Button(top_config_frame, text='🔄 Sync from qBittorrent', 
                             command=_on_sync_clicked, style='Secondary.TButton')
        sync_btn.grid(row=2, column=0, columnspan=4, sticky='ew', padx=0, pady=(10, 0))
    except Exception:
        pass

    try:
        root.bind_all('<Control-o>', lambda e: import_titles_from_file(root, status_var))
        root.bind_all('<Control-O>', lambda e: import_titles_from_file(root, status_var))
        root.bind_all('<Control-s>', lambda e: dispatch_generation(root, season_var, year_entry, TREEVIEW_WIDGET, status_var))
        root.bind_all('<Control-S>', lambda e: dispatch_generation(root, season_var, year_entry, TREEVIEW_WIDGET, status_var))
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


    list_frame_container = ttk.LabelFrame(main_frame, text="📋 Title Rules Library", padding="15")
    list_frame_container.pack(fill='both', expand=True, pady=(10, 5))

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
            # Get sash position after a short delay to ensure it's updated
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
            # Reset to approximately 60/40 split (library gets 60%)
            total_width = paned.winfo_width()
            if total_width > 100:
                default_pos = int(total_width * 0.6)
                paned.sashpos(0, default_pos)
                config.set_pref('paned_sash_position', default_pos)
        except Exception:
            pass
    
    paned.bind('<Double-Button-1>', _reset_paned_sash)

    # Create a frame for treeview with better styling (takes remaining space)
    treeview_frame = ttk.Frame(paned)
    paned.add(treeview_frame, weight=3)
    
    # Create Treeview with columns
    treeview = ttk.Treeview(treeview_frame, selectmode='extended', 
                           columns=('title', 'category', 'savepath'),
                           show='tree headings', height=20)
    
    # Define column headings
    treeview.heading('#0', text='#', anchor='w')
    treeview.heading('title', text='Title', anchor='w')
    treeview.heading('category', text='Category', anchor='w')
    treeview.heading('savepath', text='Save Path', anchor='w')
    
    # Load saved column widths or use defaults
    try:
        saved_col_widths = config.get_pref('treeview_column_widths', {})
    except Exception:
        saved_col_widths = {}
    
    # Track if user manually resized columns (disable auto-size until restart or double-click)
    columns_manual_resize = {
        '#0': {'disabled': False},
        'title': {'disabled': False},
        'category': {'disabled': False},
        'savepath': {'disabled': False}
    }
    
    # Configure column widths - stretch=False allows horizontal scrolling beyond visible area
    treeview.column('#0', width=saved_col_widths.get('#0', 20), minwidth=20, stretch=False)
    treeview.column('title', width=saved_col_widths.get('title', 300), minwidth=150, stretch=False)
    treeview.column('category', width=saved_col_widths.get('category', 150), minwidth=100, stretch=False)
    treeview.column('savepath', width=saved_col_widths.get('savepath', 400), minwidth=150, stretch=False)
    
    # Function to auto-fit column to content
    def _auto_fit_column(col_id):
        """Auto-fit column width based on content and re-enable auto-sizing"""
        try:
            max_width = 50  # Minimum width
            
            # Measure header text
            if col_id == '#0':
                header_text = '#'
            elif col_id == 'title':
                header_text = 'Title'
            elif col_id == 'category':
                header_text = 'Category'
            elif col_id == 'savepath':
                header_text = 'Save Path'
            else:
                header_text = ''
            
            # Roughly 8 pixels per character for header
            max_width = max(max_width, len(header_text) * 8 + 20)
            
            # Measure all items in column
            for item in treeview.get_children():
                try:
                    if col_id == '#0':
                        text = treeview.item(item, 'text')
                    else:
                        values = treeview.item(item, 'values')
                        if col_id == 'title' and len(values) > 0:
                            text = values[0]
                        elif col_id == 'category' and len(values) > 1:
                            text = values[1]
                        elif col_id == 'savepath' and len(values) > 2:
                            text = values[2]
                        else:
                            text = ''
                    
                    if text:
                        # Roughly 8 pixels per character + padding
                        text_width = len(str(text)) * 8 + 20
                        max_width = max(max_width, text_width)
                except Exception:
                    pass
            
            # Set the column width
            treeview.column(col_id, width=int(max_width))
            
            # Re-enable auto-sizing for this column (double-click re-enables)
            if col_id in columns_manual_resize:
                columns_manual_resize[col_id]['disabled'] = False
        except Exception:
            pass
    
    # Function to save column widths and track manual resize
    def _save_column_widths(event=None):
        try:
            widths = {
                '#0': treeview.column('#0', 'width'),
                'title': treeview.column('title', 'width'),
                'category': treeview.column('category', 'width'),
                'savepath': treeview.column('savepath', 'width')
            }
            config.set_pref('treeview_column_widths', widths)
            
            # Check if user manually resized any column
            if event:
                try:
                    # Get column from x coordinate
                    region = treeview.identify_region(event.x, event.y)
                    if region == "separator":
                        col = treeview.identify_column(event.x)
                        # Disable auto-sizing for the resized column
                        if col == '#0':
                            columns_manual_resize['#0']['disabled'] = True
                        elif col == '#1':
                            columns_manual_resize['title']['disabled'] = True
                        elif col == '#2':
                            columns_manual_resize['category']['disabled'] = True
                        elif col == '#3':
                            columns_manual_resize['savepath']['disabled'] = True
                except Exception:
                    pass
        except Exception:
            pass
    
    # Bind column resize event to save widths
    treeview.bind('<ButtonRelease-1>', _save_column_widths)
    
    # Add double-click to auto-fit column
    def _on_double_click(event):
        try:
            region = treeview.identify_region(event.x, event.y)
            if region == "separator":
                # Get the column to the left of the separator
                col = treeview.identify_column(event.x)
                if col:
                    # Convert column string to index
                    if col == '#0':
                        _auto_fit_column('#0')
                    elif col == '#1':
                        _auto_fit_column('title')
                    elif col == '#2':
                        _auto_fit_column('category')
                    elif col == '#3':
                        _auto_fit_column('savepath')
                    _save_column_widths()
                    return "break"  # Prevent event from propagating to other handlers
        except Exception:
            pass
    
    treeview.bind('<Double-Button-1>', _on_double_click)
    
    # Style the treeview
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
    
    # Create scrollbars
    vsb = ttk.Scrollbar(treeview_frame, orient='vertical', command=treeview.yview)
    hsb = ttk.Scrollbar(treeview_frame, orient='horizontal', command=treeview.xview)
    
    # Custom scrollbar set functions to show/hide scrollbars as needed
    def _vsb_set(*args):
        try:
            vsb.set(*args)
            # Show/hide vertical scrollbar based on whether scrolling is needed
            if float(args[0]) <= 0.0 and float(args[1]) >= 1.0:
                vsb.grid_remove()
            else:
                vsb.grid()
        except Exception:
            vsb.set(*args)
    
    def _hsb_set(*args):
        try:
            hsb.set(*args)
            # Show/hide horizontal scrollbar based on whether scrolling is needed
            if float(args[0]) <= 0.0 and float(args[1]) >= 1.0:
                hsb.grid_remove()
            else:
                hsb.grid()
        except Exception:
            hsb.set(*args)
    
    treeview.configure(yscrollcommand=_vsb_set, xscrollcommand=_hsb_set)
    
    # Grid layout for scrollbars (shown/hidden dynamically)
    treeview.grid(row=0, column=0, sticky='nsew')
    vsb.grid(row=0, column=1, sticky='ns')
    hsb.grid(row=1, column=0, sticky='ew')
    
    # Configure grid weights
    treeview_frame.grid_rowconfigure(0, weight=1)
    treeview_frame.grid_columnconfigure(0, weight=1)
    
    # Attach columns manual resize tracker to treeview widget for access from update function
    treeview._columns_manual_resize = columns_manual_resize
    
    # Add compatibility methods for Treeview to work like Listbox
    def _curselection():
        """Compatibility method: returns tuple of selected indices like Listbox.curselection()"""
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
        """Compatibility method: delete items like Listbox.delete()"""
        try:
            if first == 0 and last == 'end':
                # Clear all
                for item in treeview.get_children():
                    treeview.delete(item)
            elif isinstance(first, int):
                # Delete specific index
                all_items = treeview.get_children()
                if first < len(all_items):
                    treeview.delete(all_items[first])
        except Exception:
            pass
    
    def _insert_item(parent_or_position, index_or_text, text=None, **kw):
        """Compatibility method: insert like Listbox.insert() or Treeview.insert()"""
        try:
            # Check if this is a Treeview-style call (parent, index, ...) or Listbox-style (position, text)
            if text is None and not kw:
                # Listbox-style: insert(index, text) where index is int or 'end'
                # Need to re-populate with all data from LISTBOX_ITEMS
                if isinstance(parent_or_position, int):
                    # Inserting at specific index - need to update the entire treeview
                    # This is complex, so we'll refresh from LISTBOX_ITEMS
                    all_items = treeview.get_children()
                    if parent_or_position < len(all_items):
                        # Get the item data from LISTBOX_ITEMS at this index
                        if parent_or_position < len(LISTBOX_ITEMS):
                            title_text, entry = LISTBOX_ITEMS[parent_or_position]
                            
                            # Extract category and save path
                            category = ''
                            save_path = ''
                            if isinstance(entry, dict):
                                category = entry.get('assignedCategory') or entry.get('assigned_category') or entry.get('category') or ''
                                save_path = entry.get('savePath') or entry.get('save_path') or ''
                                if not save_path:
                                    tp = entry.get('torrentParams') or entry.get('torrent_params') or {}
                                    save_path = tp.get('save_path') or tp.get('savePath') or tp.get('download_path') or ''
                                save_path = str(save_path).replace('\\', '/') if save_path else ''
                            
                            # Update the existing item in the treeview
                            item_id = all_items[parent_or_position]
                            treeview.item(item_id, text=str(parent_or_position + 1), values=(title_text, category, save_path))
                elif parent_or_position == 'end':
                    # Simple string insertion at end
                    treeview.insert('', 'end', text='', values=(index_or_text, '', ''))
            else:
                # Treeview-style: insert(parent, index, text=..., values=...)
                # Pass through to the original Treeview insert method
                return ttk.Treeview.insert(treeview, parent_or_position, index_or_text, text=text, **kw)
        except Exception as e:
            pass
    
    def _nearest(y):
        """Compatibility method: get item nearest to y coordinate"""
        try:
            item = treeview.identify_row(y)
            if item:
                all_items = treeview.get_children()
                return all_items.index(item)
            return 0
        except Exception:
            return 0
    
    def _see(index):
        """Compatibility method: ensure item at index is visible"""
        try:
            all_items = treeview.get_children()
            if index < len(all_items):
                treeview.see(all_items[index])
        except Exception:
            pass
    
    def _selection_set(index):
        """Compatibility method: select item at index"""
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

    try:
        def _ctx_edit_selected():
            try:
                open_full_rule_editor_for_selection()
            except Exception as e:
                messagebox.showerror('Edit Error', f'Failed to open editor: {e}')

        def _ctx_delete_selected():
            try:
                sel = TREEVIEW_WIDGET.curselection()
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
                        TREEVIEW_WIDGET.delete(s)
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
                sel = TREEVIEW_WIDGET.curselection()
                if not sel:
                    messagebox.showwarning('Copy', 'No title selected to copy.')
                    return
                export_map = {}
                try:
                    sel_indices = [int(i) for i in sel]
                except Exception:
                    sel_indices = []
                try:
                    all_map = build_qbittorrent_rules_dict({ 'anime': [it for it in [LISTBOX_ITEMS[i][1] for i in sel_indices] ] })
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
                idx = TREEVIEW_WIDGET.nearest(event.y)
                if idx is None:
                    return
                cur = TREEVIEW_WIDGET.curselection()
                if not cur or (idx not in [int(i) for i in cur]):
                    try:
                        TREEVIEW_WIDGET.selection_clear(0, 'end')
                    except Exception:
                        pass
                    try:
                        TREEVIEW_WIDGET.selection_set(idx)
                    except Exception:
                        pass
                try:
                    context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    context_menu.grab_release()
            except Exception:
                pass

        context_menu = tk.Menu(treeview, tearoff=0)
        context_menu.add_command(label='Copy', command=_ctx_copy_selected)
        context_menu.add_command(label='Edit', command=_ctx_edit_selected)
        context_menu.add_command(label='Delete', command=_ctx_delete_selected)
        TREEVIEW_WIDGET = treeview
        TREEVIEW_WIDGET.bind('<Button-3>', _on_listbox_right_click, add='+')
    except Exception:
        pass

    TREEVIEW_WIDGET = treeview
    LISTBOX_ITEMS = []

    def export_selected_titles():
        """
        Exports selected titles from the listbox to a JSON file.
        
        Prompts user for save location and exports selected titles with their
        configuration as a JSON file.
        """
        try:
            sel = TREEVIEW_WIDGET.curselection()
            if not sel:
                messagebox.showwarning('Export', 'No title selected to export.')
                return
            try:
                sel_indices = [int(i) for i in sel]
            except Exception:
                sel_indices = []
            try:
                selected_entries = [LISTBOX_ITEMS[i][1] for i in sel_indices]
                export_map = build_qbittorrent_rules_dict({'anime': selected_entries})
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
        """
        Exports all titles from the current collection to a JSON file.
        
        Prompts user for save location and exports all titles with their
        configuration as a JSON file.
        """
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
                    export_map = build_qbittorrent_rules_dict(data)
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
        """
        Restores the most recently deleted item from the trash.
        
        Pops the last item from TRASH_ITEMS and reinserts it into the
        listbox and ALL_TITLES collection at its original position.
        """
        try:
            if not TRASH_ITEMS:
                messagebox.showinfo('Undo', 'Trash is empty.')
                return
            item = TRASH_ITEMS.pop()
            if item.get('src') == 'titles':
                idx = item.get('index', None)
                title_text = item.get('title')
                entry = item.get('entry')
                if idx is None or idx < 0 or idx > TREEVIEW_WIDGET.size():
                    LISTBOX_ITEMS.append((title_text, entry))
                    try:
                        TREEVIEW_WIDGET.insert('end', title_text)
                    except Exception:
                        pass
                else:
                    try:
                        LISTBOX_ITEMS.insert(idx, (title_text, entry))
                    except Exception:
                        LISTBOX_ITEMS.append((title_text, entry))
                    try:
                        TREEVIEW_WIDGET.insert(idx, title_text)
                    except Exception:
                        try:
                            TREEVIEW_WIDGET.insert('end', title_text)
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
        """
        Opens a dialog showing all deleted items in the trash.
        
        Args:
            parent: Parent Tkinter window
        """
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
                                TREEVIEW_WIDGET.insert('end', title_text)
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

    # Create editor container for PanedWindow
    editor_container = ttk.Frame(paned)
    paned.add(editor_container, weight=2)
    
    # Restore saved sash position after adding both panes
    def _restore_or_set_default_sash():
        try:
            total_width = paned.winfo_width()
            if total_width > 100:
                if saved_sash_pos is not None and 100 < saved_sash_pos < total_width - 100:
                    # Use saved position if valid
                    paned.sashpos(0, saved_sash_pos)
                else:
                    # Set default 60/40 split (library gets 60%)
                    default_pos = int(total_width * 0.6)
                    paned.sashpos(0, default_pos)
        except Exception:
            pass
    
    # Use after_idle to ensure the paned window has been rendered
    root.after_idle(_restore_or_set_default_sash)
    
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

    editor_rule_name = tk.StringVar(value='')
    editor_must = tk.StringVar(value='')
    editor_savepath = tk.StringVar(value='')
    editor_category = tk.StringVar(value='')
    editor_enabled = tk.BooleanVar(value=True)
    
    # Improved text widget styling
    editor_lastmatch_text = tk.Text(editor_frame, height=2, width=40, state='disabled',
                                     font=('Consolas', 9), bg='#fafafa', fg='#333333',
                                     relief='flat', bd=1, highlightthickness=1,
                                     highlightbackground='#e0e0e0', highlightcolor='#0078D4')

    # Create header row with title and refresh button
    editor_header = ttk.Frame(editor_frame)
    editor_header.pack(fill='x', pady=(0, 10))
    ttk.Label(editor_header, text='📝 Rule Editor', font=('Segoe UI', 11, 'bold')).pack(side='left')
    editor_refresh_btn = ttk.Button(editor_header, text='🔄', command=lambda: None, width=3, style='RefreshButton.TButton')
    editor_refresh_btn.pack(side='right', padx=(5, 0))
    
    ttk.Separator(editor_frame, orient='horizontal').pack(fill='x', pady=(0, 10))
    
    ttk.Label(editor_frame, text='Title:', font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 2))
    ttk.Entry(editor_frame, textvariable=editor_rule_name, font=('Segoe UI', 9)).pack(anchor='w', fill='x', pady=(0, 8))
    
    ttk.Label(editor_frame, text='Match Pattern:', font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 2))
    ttk.Entry(editor_frame, textvariable=editor_must, font=('Segoe UI', 9)).pack(anchor='w', fill='x', pady=(0, 8))
    
    # ==================== Feed Title Lookup Section ====================
    feed_lookup_frame = ttk.LabelFrame(editor_frame, text='📡 Feed Title Variations', padding=10)
    feed_lookup_frame.pack(fill='x', pady=(0, 10))
    
    # Info label explaining the feature
    info_label = ttk.Label(feed_lookup_frame, 
                          text='💡 Match your titles with SubsPlease RSS feed naming',
                          font=('Segoe UI', 8), 
                          foreground='#666')
    info_label.pack(fill='x', pady=(0, 5))
    
    # SubsPlease title display
    subsplease_title_var = tk.StringVar(value='')
    subsplease_row = ttk.Frame(feed_lookup_frame)
    subsplease_row.pack(fill='x', pady=2)
    ttk.Label(subsplease_row, text='SubsPlease:', font=('Segoe UI', 9, 'bold'), width=15).pack(side='left')
    subsplease_label = ttk.Label(subsplease_row, textvariable=subsplease_title_var, font=('Segoe UI', 9), foreground='#0078D4')
    subsplease_label.pack(side='left', fill='x', expand=True)
    
    def _use_subsplease_title():
        """Copies SubsPlease title to Match Pattern field."""
        sp_title = subsplease_title_var.get()
        if sp_title and sp_title != 'Not found in cache':
            editor_must.set(sp_title)
            status_var.set(f'Applied SubsPlease title: {sp_title}')
    
    use_sp_btn = ttk.Button(subsplease_row, text='Use', command=_use_subsplease_title, width=8)
    use_sp_btn.pack(side='right', padx=(5, 0))
    
    # Fetch/Refresh button
    fetch_btn_frame = ttk.Frame(feed_lookup_frame)
    fetch_btn_frame.pack(fill='x', pady=(5, 0))
    
    fetch_status_var = tk.StringVar(value='')
    fetch_status_label = ttk.Label(fetch_btn_frame, textvariable=fetch_status_var, font=('Segoe UI', 8), foreground='#666')
    fetch_status_label.pack(side='left', fill='x', expand=True)
    
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
                return
            
            # Check cache for match
            sp_match = find_subsplease_title_match(current_title)
            
            if sp_match:
                subsplease_title_var.set(sp_match)
                fetch_status_var.set('✅ Match found in cache')
            else:
                subsplease_title_var.set('Not found in cache')
                fetch_status_var.set('⚠️ No match - click Fetch to update cache')
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
    
    # Load Cache button (tries cache first, then API if empty)
    load_cache_btn = ttk.Button(fetch_btn_frame, text='� Load Cache', 
                                command=lambda: _fetch_subsplease_titles(force_refresh=False),
                                width=14)
    load_cache_btn.pack(side='right', padx=(2, 0))
    ToolTip(load_cache_btn, "Loads from local cache, or fetches from API if cache is empty")
    
    # Fetch Fresh button (always fetches from API)
    fetch_fresh_btn = ttk.Button(fetch_btn_frame, text='🔄 Fetch Fresh', 
                                  command=lambda: _fetch_subsplease_titles(force_refresh=True),
                                  width=14)
    fetch_fresh_btn.pack(side='right', padx=(2, 0))
    ToolTip(fetch_fresh_btn, "Always fetches the latest data from SubsPlease API")
    
    # Load initial cache status
    try:
        cached = load_subsplease_cache()
        if cached:
            fetch_status_var.set(f'📦 {len(cached)} titles in cache')
        else:
            fetch_status_var.set('📦 Cache empty - click Load Cache to fetch')
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
    ttk.Entry(editor_frame, textvariable=editor_savepath, font=('Segoe UI', 9)).pack(anchor='w', fill='x', pady=(0, 8))
    
    ttk.Label(editor_frame, text='Category:', font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 2))
    # Use Combobox for category with cached categories
    editor_category_combo = ttk.Combobox(editor_frame, textvariable=editor_category, font=('Segoe UI', 9))
    editor_category_combo.pack(anchor='w', fill='x', pady=(0, 8))
    
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
            for title_text, entry in LISTBOX_ITEMS:
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
    
    # Update cache initially and when selection changes
    _update_category_cache()
    
    ttk.Checkbutton(editor_frame, text='Enabled', variable=editor_enabled).pack(anchor='w', pady=(0, 10))

    # Add prefix button
    def _add_prefix_to_selected():
        """
        Adds season/year prefix to the selected title.
        """
        try:
            sel = TREEVIEW_WIDGET.curselection()
            if not sel:
                messagebox.showwarning('Prefix', 'No title selected.')
                return
            idx = int(sel[0])
            title_text, entry = LISTBOX_ITEMS[idx]
            
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
            LISTBOX_ITEMS[idx] = (new_title, entry)
            TREEVIEW_WIDGET.delete(idx)
            TREEVIEW_WIDGET.insert(idx, new_title)
            TREEVIEW_WIDGET.selection_set(idx)
            TREEVIEW_WIDGET.see(idx)
            
            # Update config
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
                                break
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
            sel = TREEVIEW_WIDGET.curselection()
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
    
    # Configure refresh button command now that function is defined
    try:
        editor_refresh_btn.config(command=_populate_editor_from_selection)
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


    def _apply_editor_changes():
        """
        Applies changes from the editor panel to the selected listbox item.
        
        Updates the selected title's configuration with values from the editor
        fields and refreshes the display.
        """
        try:
            sel = TREEVIEW_WIDGET.curselection()
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
            
            # Sync category to torrentParams.category
            if 'torrentParams' not in entry:
                entry['torrentParams'] = {}
            if not isinstance(entry['torrentParams'], dict):
                entry['torrentParams'] = {}
            entry['torrentParams']['category'] = new_cat
            
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
                TREEVIEW_WIDGET.delete(idx)
                TREEVIEW_WIDGET.insert(idx, new_title)
                TREEVIEW_WIDGET.selection_set(idx)
                TREEVIEW_WIDGET.see(idx)
            except Exception:
                pass
            # Auto-refresh the editor to show updated values
            try:
                _populate_editor_from_selection()
            except Exception:
                pass
            messagebox.showinfo('Edit', 'Changes applied to the selected title.')
        except Exception as e:
            messagebox.showerror('Edit Error', f'Failed to apply changes: {e}')

    def open_full_rule_editor_for_selection():
        """
        Opens the full rule editor dialog for the selected listbox item.
        """
        try:
            sel = TREEVIEW_WIDGET.curselection()
            if not sel:
                messagebox.showwarning('Edit', 'No title selected.')
                return
            idx = int(sel[0])
            title_text, entry = LISTBOX_ITEMS[idx]
        except Exception:
            messagebox.showerror('Edit', 'Failed to locate selected item.')
            return
        open_full_rule_editor(title_text, entry, idx)

    ttk.Button(btns, text='🔧 Advanced Settings...', command=open_full_rule_editor_for_selection, style='Secondary.TButton', width=25).pack(fill='x', pady=(0, 5))

    footer_edit_btns = ttk.Frame(editor_frame)
    footer_edit_btns.pack(fill='x', pady=(5, 0))
    ttk.Button(footer_edit_btns, text='✓ Apply', command=_apply_editor_changes, style='Accent.TButton').pack(side='right')

    try:
        TREEVIEW_WIDGET.bind('<<TreeviewSelect>>', _populate_editor_from_selection)
        try:
            def _on_item_double_click(event):
                """Open editor only if not clicking on separator"""
                try:
                    region = TREEVIEW_WIDGET.identify_region(event.x, event.y)
                    if region != "separator":
                        open_full_rule_editor_for_selection()
                except Exception:
                    pass
            TREEVIEW_WIDGET.bind('<Double-1>', _on_item_double_click)
        except Exception:
            pass
    except Exception:
        pass

    def open_full_rule_editor(title_text, entry, idx):
        """
        Opens a comprehensive editor dialog for all rule settings.
        
        Args:
            title_text: Display name of the title being edited
            entry: Rule entry dictionary containing all configuration
            idx: Index of the item in LISTBOX_ITEMS
        """
        dlg = tk.Toplevel(root)
        dlg.title(f'🔧 Advanced Rule Editor - {title_text}')
        
        # Auto-size to monitor height (use 85% of screen height)
        try:
            screen_height = dlg.winfo_screenheight()
            dialog_height = int(screen_height * 0.85)
            dialog_height = max(600, min(dialog_height, screen_height - 100))
            dlg.geometry(f'750x{dialog_height}')
        except Exception:
            dlg.geometry('750x700')
        
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
                # Bind only to this specific canvas widget, not globally
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
        # Use Listbox instead of Text for better multi-line management
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
        affected_listbox_frame.pack(side='top', fill='both', expand=True, pady=(0, 4))
        affected_listbox.pack(side='left', fill='both', expand=True)
        affected_scrollbar.pack(side='right', fill='y')
        
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
            feeds_select_frame = ttk.Frame(affected_frame)
            feeds_select_frame.pack(side='top', fill='x', pady=(0, 4))
            
            feeds_combo = ttk.Combobox(feeds_select_frame, values=feeds_choices, state='readonly', width=80)
            feeds_combo.pack(side='left', padx=(0, 6))
            
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
                except Exception:
                    pass
            
            def _delete_selected_feeds():
                try:
                    selected = affected_listbox.curselection()
                    if not selected:
                        return
                    for idx in reversed(selected):
                        affected_listbox.delete(idx)
                except Exception:
                    pass
            
            ttk.Button(feeds_select_frame, text='Add', command=_add_selected_feed).pack(side='left', padx=2)
            ttk.Button(feeds_select_frame, text='Delete', command=_delete_selected_feeds).pack(side='left', padx=2)
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
            for title_text_item, entry_item in LISTBOX_ITEMS:
                if isinstance(entry_item, dict):
                    cat = entry_item.get('assignedCategory') or entry_item.get('assigned_category') or entry_item.get('category') or ''
                    if cat and cat not in cat_choices:
                        cat_choices.append(str(cat))
        except Exception:
            pass
        
        assigned_combo = ttk.Combobox(frm, textvariable=assigned_var, values=sorted(cat_choices), width=48, font=('Segoe UI', 9))
        assigned_combo.grid(row=row, column=1, sticky='w', padx=5, pady=4)
        
        # Sync assigned_var with tp_category when either changes
        def _sync_assigned_to_tp(*args):
            try:
                tp_category.set(assigned_var.get())
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
        ttk.Entry(frm, textvariable=savepath_var, font=('Segoe UI', 9)).grid(row=row, column=1, sticky='ew', padx=5, pady=4)
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
        ttk.Entry(tp_frame, textvariable=tp_save_path, font=('Segoe UI', 9)).grid(row=tp_row, column=1, sticky='ew', padx=5, pady=4)
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

        footer = ttk.Frame(dlg, padding=10)
        footer.grid(row=1, column=0, sticky='ew', pady=(0, 5), padx=10)

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

                LISTBOX_ITEMS[idx] = (new_title, new_rule)
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
                    TREEVIEW_WIDGET.delete(idx)
                    TREEVIEW_WIDGET.insert(idx, new_title)
                    TREEVIEW_WIDGET.selection_set(idx)
                    TREEVIEW_WIDGET.see(idx)
                except Exception:
                    pass

                dlg.destroy()
                # Auto-refresh the editor to show updated values
                try:
                    _populate_editor_from_selection()
                except Exception:
                    pass
                messagebox.showinfo('Edit', 'Full settings applied.')
            except Exception as e:
                messagebox.showerror('Apply Error', f'Failed to apply full settings: {e}')

        ttk.Button(footer, text='✓ Apply', command=_apply_full, style='Accent.TButton', width=12).pack(side='right', padx=5)
        ttk.Button(footer, text='✕ Cancel', command=dlg.destroy, width=12).pack(side='right')

    def _handle_vertical_scroll(units):
        """
        Handles vertical scrolling for the listbox.
        
        Args:
            units: Number of scroll units (positive=down, negative=up)
        """
        try:
            if SCROLL_MODE == 'lines':
                TREEVIEW_WIDGET.yview_scroll(units * SCROLL_LINES, 'units')
            else:
                try:
                    step = int((units * SCROLL_PIXELS) / 20)
                except Exception:
                    step = units
                TREEVIEW_WIDGET.yview_scroll(step, 'units')
        except Exception:
            pass

    def _on_mousewheel_windows(event):
        """
        Handles mouse wheel scrolling on Windows.
        
        Args:
            event: Tkinter mouse wheel event
        """
        try:
            raw_units = float(event.delta) / 120.0
        except Exception:
            raw_units = 0.0
        if SCROLL_MODE == 'lines':
            units = int(-raw_units)
        else:
            units = -raw_units * float(SCROLL_PIXELS)

    def _on_mousewheel_linux(event):
        """
        Handles mouse wheel scrolling on Linux.
        
        Args:
            event: Tkinter mouse wheel event (Button-4 = up, Button-5 = down)
        """
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
        """
        Binds mouse wheel scroll events to a widget.
        
        Args:
            widget: Tkinter widget to bind scrolling to
        """
        try:
            widget.bind_all('<MouseWheel>', _on_mousewheel_windows, add='+')
            widget.bind_all('<Button-4>', _on_mousewheel_linux, add='+')
            widget.bind_all('<Button-5>', _on_mousewheel_linux, add='+')
        except Exception:
            pass

    def _unbind_scroll(widget):
        """
        Unbinds mouse wheel scroll events from a widget.
        
        Args:
            widget: Tkinter widget to unbind scrolling from
        """
        try:
            widget.unbind_all('<MouseWheel>')
            widget.unbind_all('<Button-4>')
            widget.unbind_all('<Button-5>')
        except Exception:
            pass

    def _on_enter(e):
        """Binds scroll events when mouse enters listbox."""
        _bind_scroll(TREEVIEW_WIDGET)

    def _on_leave(e):
        """Unbinds scroll events when mouse leaves listbox."""
        _unbind_scroll(TREEVIEW_WIDGET)
    
    # Horizontal scrolling support with Shift+MouseWheel
    def _on_horizontal_scroll(event):
        """Handle horizontal scrolling with Shift+MouseWheel or scroll wheel tilt."""
        try:
            # Calculate scroll amount (multiplied for faster scrolling)
            if hasattr(event, 'delta'):
                # Windows: event.delta - multiply by 10 for faster scrolling
                scroll_amount = int(-1 * (event.delta / 120) * 10)
            else:
                # Linux: Button-6 (left) or Button-7 (right) - scroll 10 units at a time
                scroll_amount = 10 if event.num == 7 else -10

            TREEVIEW_WIDGET.xview_scroll(scroll_amount, 'units')
        except Exception:
            pass
    
    # Bind horizontal scroll events
    try:
        # Shift+MouseWheel for horizontal scrolling
        TREEVIEW_WIDGET.bind('<Shift-MouseWheel>', _on_horizontal_scroll)
        # Linux horizontal scroll buttons (tilt wheel)
        TREEVIEW_WIDGET.bind('<Button-6>', _on_horizontal_scroll)
        TREEVIEW_WIDGET.bind('<Button-7>', _on_horizontal_scroll)
    except Exception:
        pass
    
    # Enable scrolling when hovering over scrollbars
    def _on_hsb_enter(event):
        """Enable scrolling when mouse enters horizontal scrollbar."""
        try:
            hsb.bind('<MouseWheel>', lambda e: _on_horizontal_scroll(e))
            hsb.bind('<Button-6>', lambda e: _on_horizontal_scroll(e))
            hsb.bind('<Button-7>', lambda e: _on_horizontal_scroll(e))
        except Exception:
            pass
    
    def _on_hsb_leave(event):
        """Disable scrolling when mouse leaves horizontal scrollbar."""
        try:
            hsb.unbind('<MouseWheel>')
            hsb.unbind('<Button-6>')
            hsb.unbind('<Button-7>')
        except Exception:
            pass
    
    def _on_vsb_enter(event):
        """Enable vertical scrolling when mouse enters vertical scrollbar."""
        try:
            vsb.bind('<MouseWheel>', lambda e: TREEVIEW_WIDGET.yview_scroll(int(-1*(e.delta/120)), "units"))
            vsb.bind('<Button-4>', lambda e: TREEVIEW_WIDGET.yview_scroll(-1, "units"))
            vsb.bind('<Button-5>', lambda e: TREEVIEW_WIDGET.yview_scroll(1, "units"))
        except Exception:
            pass
    
    def _on_vsb_leave(event):
        """Disable vertical scrolling when mouse leaves vertical scrollbar."""
        try:
            vsb.unbind('<MouseWheel>')
            vsb.unbind('<Button-4>')
            vsb.unbind('<Button-5>')
        except Exception:
            pass
    
    try:
        TREEVIEW_WIDGET.bind('<Enter>', _on_enter)
        TREEVIEW_WIDGET.bind('<Leave>', _on_leave)
        hsb.bind('<Enter>', _on_hsb_enter)
        hsb.bind('<Leave>', _on_hsb_leave)
        vsb.bind('<Enter>', _on_vsb_enter)
        vsb.bind('<Leave>', _on_vsb_leave)
    except Exception:
        pass


    def normalize_titles_structure(raw):
        """
        Normalizes various input formats into a consistent structure.
        
        Converts lists, dicts, or other formats into the standard
        {'anime': [entries]} structure used by the application.
        
        Args:
            raw: Raw input data (list, dict, or other format)
        
        Returns:
            dict or None: Normalized structure, or None if input is invalid
        """
        if not raw:
            return None
        if isinstance(raw, list):
            return {'anime': [ {'node': {'title': str(x)}} if not isinstance(x, dict) else x for x in raw ]}

        if isinstance(raw, dict):
            if all(isinstance(v, dict) for v in raw.values()):
                out = {'anime': []}

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
        """
        Imports and normalizes titles from text (JSON or line-delimited).
        
        Args:
            text: Text content containing titles (JSON or line-separated)
        
        Returns:
            dict or None: Normalized titles structure, or None if parsing fails
        """
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
        """
        Prefixes all titles with season and year (e.g., "Fall 2025 - Title").
        
        Args:
            all_titles: Dictionary of titles organized by media type
            season: Season name (e.g., "Fall", "Winter")
            year: Year string (e.g., "2025")
        """
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
        """
        Validates if a string is a valid folder name.
        
        Checks for invalid characters, reserved names, and other Windows
        filesystem restrictions.
        
        Args:
            name: Folder name string to validate
        
        Returns:
            tuple[bool, str]: (is_valid, error_message)
        """
        try:
            if not name or not isinstance(name, str) or not name.strip():
                return False, 'Empty name'
            
            s = name.strip()
            
            # Check for invalid characters
            found_invalid = [c for c in s if c in FileSystem.INVALID_CHARS]
            if found_invalid:
                return False, f'Contains invalid characters: {"".join(sorted(set(found_invalid)))}'
            
            # Check for trailing space or dot
            if s.endswith(' ') or s.endswith('.'):
                return False, 'Ends with a space or dot (invalid for folder names on Windows)'
            
            # Check for Windows reserved names
            base = s.split('.')[0].upper()
            if base in FileSystem.RESERVED_NAMES:
                return False, f'Reserved name: {base}'
            
            # Check length
            try:
                if len(s) > FileSystem.MAX_PATH_LENGTH:
                    return False, f'Name too long (>{FileSystem.MAX_PATH_LENGTH} chars)'
            except Exception:
                pass
            
            return True, None
        except Exception:
            return False, 'Validation error'


    def _collect_invalid_folder_titles(all_titles):
        """
        Collects all titles with invalid folder names.
        
        Args:
            all_titles: Dictionary of titles organized by media type
        
        Returns:
            list: List of tuples (display_name, raw_name, error_message) for invalid titles
        """
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


    def create_default_qbittorrent_rule(save_path='', must_contain='', rss_feed=''):
        """
        Creates a default RSS rule template with all required qBittorrent fields.
        
        Args:
            save_path: Path where torrents should be saved (Unix-style with forward slashes)
            must_contain: Pattern that must be present in torrent name
            rss_feed: RSS feed URL to monitor
        
        Returns:
            dict: Complete rule template with all qBittorrent fields
        """
        return {
            "addPaused": False,
            "affectedFeeds": [rss_feed] if rss_feed else [],
            "assignedCategory": "",
            "enabled": True,
            "episodeFilter": "",
            "ignoreDays": 0,
            "lastMatch": None,
            "mustContain": must_contain,
            "mustNotContain": "",
            "previouslyMatchedEpisodes": [],
            "priority": 0,
            "savePath": save_path,
            "smartFilter": False,
            "torrentContentLayout": None,
            "torrentParams": {
                "category": "",
                "download_limit": -1,
                "download_path": "",
                "inactive_seeding_time_limit": -2,
                "operating_mode": "AutoManaged",
                "ratio_limit": -2,
                "save_path": save_path,
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


    def build_save_path_from_title(title, season=None, year=None):
        """
        Generates a save path for a title based on season and year.
        
        Args:
            title: Title name to use in path
            season: Optional season name
            year: Optional year
        
        Returns:
            str: Generated save path with forward slashes (Unix-style for qBittorrent)
        """
        try:
            sanitized = sanitize_folder_name(title or '')
            default_prefix = getattr(config, 'DEFAULT_SAVE_PREFIX', '') or ''
            
            if season and year and default_prefix:
                path = os.path.join(default_prefix, f"{season} {year}", sanitized)
            elif default_prefix:
                path = os.path.join(default_prefix, sanitized)
            else:
                return sanitized
            
            # qBittorrent uses forward slashes for all paths
            return path.replace('\\', '/')
        except Exception:
            return str(title)


    def populate_missing_rule_fields(all_titles, season=None, year=None):
        """
        Ensures all entries have complete RSS rule configuration.
        
        Fills in missing fields with defaults, generates save paths based on
        season/year, and ensures all required qBittorrent rule fields exist.
        
        Args:
            all_titles: Dictionary of titles organized by media type
            season: Optional season name for save path generation
            year: Optional year for save path generation
        """
        if not isinstance(all_titles, dict):
            return
        
        default_rss = getattr(config, 'DEFAULT_RSS_FEED', '')
        
        for media_type, items in all_titles.items():
            if not isinstance(items, list):
                continue
            
            for i, entry in enumerate(items):
                try:
                    # Normalize entry to dict
                    if not isinstance(entry, dict):
                        entry = {'node': {'title': str(entry)}, 'mustContain': str(entry)}
                    
                    # Extract title and check if already complete
                    must = entry.get('mustContain') or (entry.get('node') or {}).get('title') or entry.get('title') or ''
                    has_complete_config = (
                        isinstance(entry.get('torrentParams'), dict) and 
                        entry.get('savePath') and 
                        entry.get('affectedFeeds')
                    )
                    
                    if has_complete_config:
                        # Ensure node title exists
                        node = entry.get('node') or {}
                        if not node.get('title'):
                            node['title'] = must or entry.get('title') or ''
                            entry['node'] = node
                        items[i] = entry
                        continue
                    
                    # Generate save path if missing
                    save_path = entry.get('savePath') or (entry.get('torrentParams') or {}).get('save_path') or ''
                    if not save_path and season and year:
                        save_path = build_save_path_from_title(must, season, year)
                    
                    # Get RSS feed
                    aff = entry.get('affectedFeeds')
                    rss_feed = aff[0] if isinstance(aff, list) and aff else default_rss
                    
                    # Create base template and merge with existing data
                    base = create_default_qbittorrent_rule(save_path, must, rss_feed)
                    base.update(entry)
                    
                    # Update torrentParams save_path if needed
                    if save_path:
                        tp = base.get('torrentParams') or {}
                        tp['save_path'] = save_path
                        base['torrentParams'] = tp
                    
                    # Ensure node title
                    node = base.get('node') or {}
                    if not node.get('title'):
                        node['title'] = base.get('mustContain') or base.get('title') or must or ''
                        base['node'] = node
                    
                    items[i] = base
                except Exception:
                    continue

    def parse_title_metadata(entry):
        """
        Extracts display title and metadata from an entry.
        
        Args:
            entry: Entry dict or string
        
        Returns:
            tuple: (display_title, raw_name, season, year)
        """
        if isinstance(entry, dict):
            node = entry.get('node') or {}
            display_title = node.get('title') or entry.get('mustContain') or entry.get('title') or ''
        else:
            display_title = str(entry)
        
        season = None
        year = None
        raw_name = ''
        
        # Parse "Season Year - Title" format
        if isinstance(display_title, str) and ' - ' in display_title:
            left, right = display_title.split(' - ', 1)
            parts = left.split()
            if parts and parts[-1].isdigit() and len(parts[-1]) == 4:
                season = ' '.join(parts[:-1]) if len(parts) > 1 else parts[0]
                year = parts[-1]
                raw_name = right
        
        if not raw_name:
            if isinstance(entry, dict):
                raw_name = entry.get('mustContain') or (entry.get('node') or {}).get('title') or entry.get('title') or display_title
            else:
                raw_name = display_title
        
        return display_title, raw_name, season, year


    def build_qbittorrent_rules_dict(all_titles):
        """
        Builds a complete qBittorrent-compatible export map from titles.
        
        Converts the internal title structure into a dictionary format suitable
        for direct import into qBittorrent's RSS auto-download rules.
        
        Args:
            all_titles: Dictionary of titles organized by media type
        
        Returns:
            dict: Export map with rule names as keys and rule configurations as values
        """
        if not isinstance(all_titles, dict):
            return {}
        
        export_map = {}
        default_rss = getattr(config, 'DEFAULT_RSS_FEED', '')
        
        for media_type, items in all_titles.items():
            if not isinstance(items, list):
                continue
            
            for entry in items:
                try:
                    # Extract title information
                    display_title, raw_name, season, year = parse_title_metadata(entry)
                    
                    # Sanitize the title for use as folder name
                    try:
                        sanitized = sanitize_folder_name(raw_name)
                    except Exception:
                        sanitized = str(raw_name)
                    
                    # Generate save path
                    save_path = build_save_path_from_title(sanitized, season, year)
                    
                    # Get RSS feed
                    if isinstance(entry, dict):
                        aff = entry.get('affectedFeeds') or []
                        rss_feed = aff[0] if isinstance(aff, list) and aff else default_rss
                    else:
                        rss_feed = default_rss
                    
                    # Create base rule from template
                    base = create_default_qbittorrent_rule(save_path, sanitized, rss_feed)
                    
                    # Merge existing entry data
                    if isinstance(entry, dict):
                        base.update(entry)
                    
                    # Ensure critical fields are set correctly
                    base['addPaused'] = base.get('addPaused', False)
                    base['assignedCategory'] = base.get('assignedCategory') or ''
                    base['lastMatch'] = base.get('lastMatch') or ''
                    
                    # Update torrentParams with current values
                    tp = base.get('torrentParams') or {}
                    tp['category'] = base.get('assignedCategory') or ''
                    tp['save_path'] = save_path
                    base['torrentParams'] = tp
                    
                    # Ensure savePath is set
                    base['savePath'] = save_path
                    
                    # Ensure node title
                    node = base.get('node') or {}
                    if not node.get('title'):
                        node['title'] = display_title or base.get('mustContain') or sanitized
                        base['node'] = node
                    
                    # Remove node from export (internal use only)
                    export_rule = base.copy()
                    export_rule.pop('node', None)
                    
                    export_map[str(display_title)] = export_rule
                except Exception:
                    continue
        
        return export_map

    def _auto_sanitize_titles(all_titles):
        """
        Automatically sanitizes mustContain fields to be valid folder names.
        
        Updates entries in-place, replacing mustContain values with sanitized
        versions suitable for use as folder names.
        
        Args:
            all_titles: Dictionary of titles organized by media type
        """
        try:
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
                        sanitized = sanitize_folder_name(raw)
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
        """
        Imports titles from a JSON file and updates the application state.
        
        Args:
            root: Parent Tkinter window
            status_var: Status bar variable for displaying import status
            path: Optional file path (opens dialog if None)
        
        Returns:
            bool: True if import succeeded, False otherwise
        """
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
            
            # Merge with existing titles instead of replacing
            try:
                current = getattr(config, 'ALL_TITLES', {}) or {}
                if not isinstance(current, dict):
                    current = {}
                
                # Get existing title names to avoid duplicates
                existing_titles = set()
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
                            pass
                
                # Merge new titles, skipping duplicates
                new_count = 0
                for media_type, items in parsed.items():
                    if not isinstance(items, list):
                        continue
                    if media_type not in current:
                        current[media_type] = []
                    
                    for item in items:
                        try:
                            if isinstance(item, dict):
                                title = (item.get('node') or {}).get('title') or item.get('ruleName') or item.get('name')
                            else:
                                title = str(item)
                            key = None if title is None else str(title)
                        except Exception:
                            key = None
                        
                        if key and key not in existing_titles:
                            current[media_type].append(item)
                            existing_titles.add(key)
                            new_count += 1
                
                config.ALL_TITLES = current
                status_msg = f'Imported {new_count} new titles from file.'
                if new_count < sum(len(v) for v in parsed.values()):
                    status_msg += f' ({sum(len(v) for v in parsed.values()) - new_count} duplicates skipped)'
            except Exception:
                # Fallback to replace if merge fails
                config.ALL_TITLES = parsed
                status_msg = f'Imported {sum(len(v) for v in parsed.values())} titles from file.'
            
            try:
                populate_missing_rule_fields(config.ALL_TITLES, season_var.get(), year_var.get())
            except Exception:
                pass
            update_treeview_with_titles(config.ALL_TITLES)
            status_var.set(status_msg)
            try:
                config.add_recent_file(path)
            except Exception:
                pass
            return True
        except Exception as e:
            messagebox.showerror('File Error', f'Error reading file: {e}')
            return False

    def import_titles_from_clipboard(root, status_var):
        """
        Imports titles from clipboard text and updates the application state.
        
        Args:
            root: Parent Tkinter window
            status_var: Status bar variable for displaying import status
        
        Returns:
            bool: True if import succeeded, False otherwise
        """
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
        
        # Merge with existing titles instead of replacing
        try:
            current = getattr(config, 'ALL_TITLES', {}) or {}
            if not isinstance(current, dict):
                current = {}
            
            # Get existing title names to avoid duplicates
            existing_titles = set()
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
                        pass
            
            # Merge new titles, skipping duplicates
            new_count = 0
            for media_type, items in parsed.items():
                if not isinstance(items, list):
                    continue
                if media_type not in current:
                    current[media_type] = []
                
                for item in items:
                    try:
                        if isinstance(item, dict):
                            title = (item.get('node') or {}).get('title') or item.get('ruleName') or item.get('name')
                        else:
                            title = str(item)
                        key = None if title is None else str(title)
                    except Exception:
                        key = None
                    
                    if key and key not in existing_titles:
                        current[media_type].append(item)
                        existing_titles.add(key)
                        new_count += 1
            
            config.ALL_TITLES = current
            status_msg = f'Imported {new_count} new titles from clipboard.'
            if new_count < sum(len(v) for v in parsed.values()):
                status_msg += f' ({sum(len(v) for v in parsed.values()) - new_count} duplicates skipped)'
        except Exception:
            # Fallback to replace if merge fails
            config.ALL_TITLES = parsed
            status_msg = f'Imported {sum(len(v) for v in parsed.values())} titles from clipboard.'
        
        try:
            populate_missing_rule_fields(config.ALL_TITLES, season_var.get(), year_var.get())
        except Exception:
            pass
        update_treeview_with_titles(config.ALL_TITLES)
        status_var.set(status_msg)
        return True

    def clear_all_titles(root, status_var):
        """
        Clears all loaded titles after user confirmation.
        
        Args:
            root: Parent Tkinter window
            status_var: Status bar variable for displaying clear status
        
        Returns:
            bool: True if titles were cleared, False otherwise
        """
        try:
            has = bool(getattr(config, 'ALL_TITLES', None)) and any((getattr(config, 'ALL_TITLES') or {}).values())
        except Exception:
            has = bool(getattr(config, 'ALL_TITLES', None))

        if not has:
            status_var.set('No titles to clear.')
            try:
                TREEVIEW_WIDGET.delete(0, 'end')
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
            TREEVIEW_WIDGET.delete(0, 'end')
        except Exception:
            pass
        try:
            LISTBOX_ITEMS.clear()
        except Exception:
            pass
        status_var.set('Cleared all loaded titles.')
        return True

    def open_import_titles_dialog(root, status_var):
        """
        Opens a dialog with multiple options for importing titles.
        
        Args:
            root: Parent Tkinter window
            status_var: Status bar variable for displaying import status
        """
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
                populate_missing_rule_fields(config.ALL_TITLES, season_var.get(), year_var.get())
            except Exception:
                pass
            update_treeview_with_titles(config.ALL_TITLES)
            status_var.set(f'Imported {sum(len(v) for v in config.ALL_TITLES.values())} titles from pasted text.')
            dlg.destroy()

        footer = ttk.Frame(dlg)
        footer.pack(fill='x', padx=10, pady=8)
        ttk.Button(footer, text='Import Text', command=on_import_text).pack(side='left')
        ttk.Button(footer, text='Cancel', command=dlg.destroy).pack(side='right')

    # ==================== BOTTOM BAR (Always Visible) ====================
    # This section must be defined AFTER all helper functions but BEFORE dispatch_generation
    # Pack with side='bottom' to keep it pinned at the bottom
    
    # Generate button function
    def _on_generate_clicked():
        try:
            dispatch_generation(root, season_var, year_entry, TREEVIEW_WIDGET, status_var)
        except Exception as e:
            messagebox.showerror('Generate Error', f'Failed to generate: {e}')
    
    # Bottom action bar container (always visible at bottom)
    bottom_bar = ttk.Frame(main_frame, style='TFrame')
    bottom_bar.pack(fill='x', side='bottom', pady=(10, 0))
    
    # Generate button (only this button at bottom, sync stays at top)
    generate_btn = ttk.Button(bottom_bar, text='⚡ Generate/Sync to qBittorrent', 
                              command=_on_generate_clicked, style='Accent.TButton')
    generate_btn.pack(fill='x', pady=(0, 5))
    
    # Status bar at bottom (always visible)
    status_bar_frame = ttk.Frame(bottom_bar, style='TFrame')
    status_bar_frame.pack(fill='x', side='bottom')
    
    status_bar = ttk.Label(status_bar_frame, textvariable=status_var, 
                           font=('Segoe UI', 9), 
                           relief='flat', 
                           padding=(10, 5),
                           background='#e8e8e8', 
                           foreground='#333333')
    status_bar.pack(fill='x', side='left', expand=True)
    # ==================== END BOTTOM BAR ====================


    def dispatch_generation(root, season_var, year_entry, treeview_widget, status_var):
        """
        Handles the generation and synchronization of RSS rules to qBittorrent.
        
        Validates inputs, generates rules for selected titles, shows preview dialog,
        and syncs rules to qBittorrent based on connection mode.
        
        Args:
            root: Parent Tkinter window
            season_var: Tkinter variable containing season selection
            year_entry: Entry widget containing year value
            treeview_widget: Treeview widget with title selections
            status_var: Status bar variable for displaying progress
        """
        try:
            season = season_var.get()
            year = year_entry.get()

            if not season or not year:
                messagebox.showwarning("Input Error", "Season and Year must be specified.")
                return

            items = []
            try:
                sel = treeview_widget.curselection()
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
                        treeview_widget.delete(0, 'end')
                    except Exception:
                        pass
                    try:
                        treeview_widget.insert('end', f"Generated {len(preview_list)} rules for {season} {year}")
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


__all__ = ["setup_gui", "exit_handler"]


def main() -> None:
    """
    Main entry point for the qBittorrent RSS Rule Editor application.
    
    Initializes exit handlers and starts the GUI.
    """
    exit_handler()
    setup_gui()


if __name__ == "__main__":
    main()
