"""
Application configuration management.
"""
# Standard library imports
import json
import logging
import os
from configparser import ConfigParser
from typing import Any, Dict, List, Optional

# Local application imports
from .constants import CacheKeys

logger = logging.getLogger(__name__)


class AppConfig:
    """Application configuration manager with type-safe access to settings."""
    
    def __init__(self):
        # File paths and defaults
        self.CONFIG_FILE: str = 'config.ini'
        self.OUTPUT_CONFIG_FILE_NAME: str = 'qbittorrent_rules.json'
        self.CACHE_FILE: str = 'seasonal_cache.json'
        
        self.DEFAULT_RSS_FEED: str = ""
        self.DEFAULT_SAVE_PATH: str = ""
        self.DEFAULT_DOWNLOAD_PATH: str = ""  # qBittorrent's default download path (used as base path)
        self.DEFAULT_CATEGORY: str = ""
        self.DEFAULT_AFFECTED_FEEDS: List[str] = []
        
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
        
        # ALL_TITLES uses a hybrid format where each entry contains both:
        # 1. qBittorrent RSS rule fields (mustContain, savePath, affectedFeeds, etc.)
        # 2. Internal tracking fields for display purposes:
        #    - 'node': {'title': 'Display Title'} - used for treeview display
        #    - 'ruleName': 'Title' - original rule name from qBittorrent
        #
        # Structure:
        # {
        #   'existing': [  # or 'anime', 'manga', etc.
        #     {
        #       # qBittorrent fields
        #       'mustContain': 'Title',
        #       'savePath': '/path/to/save',
        #       'assignedCategory': 'Category',
        #       'enabled': True,
        #       'affectedFeeds': ['url'],
        #       'torrentParams': {...},
        #       # Internal tracking fields (filtered out on export)
        #       'node': {'title': 'Display Title'},
        #       'ruleName': 'Title'
        #     }
        #   ]
        # }
        #
        # When exporting or previewing, internal fields ('node', 'ruleName') must be
        # filtered out to produce clean qBittorrent-compatible JSON.
        # See file_operations.py: _show_preview_dialog() for the filtering logic.
        self.ALL_TITLES: Dict[str, List[Any]] = {}
        
        # API Endpoints
        self.QBT_AUTH_LOGIN: str = "/api/v2/auth/login"
        self.QBT_TORRENTS_CATEGORIES: str = "/api/v2/torrents/categories"
        self.QBT_RSS_FEEDS: str = "/api/v2/rss/items"
        self.QBT_RSS_RULES: str = "/api/v2/rss/rules"
        self.QBT_API_BASE: str = "/api/v2"
    
    def get_pref(self, key: str, default: Any = None) -> Any:
        """Get a preference value with fallback."""
        cache = self._load_cache_data()
        return cache.get(CacheKeys.PREFS, {}).get(key, default)
    
    def set_pref(self, key: str, value: Any) -> bool:
        """Set a preference value."""
        try:
            cache = self._load_cache_data()
            cache.setdefault(CacheKeys.PREFS, {})[key] = value
            return self._save_cache_data(cache)
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
        cache = self._load_cache_data()
        self.CACHED_CATEGORIES = cache.get(CacheKeys.CATEGORIES, {})
        logger.info(f"Loaded {len(self.CACHED_CATEGORIES)} cached categories")
    
    def load_cached_feeds(self) -> None:
        """Load cached feeds from file."""
        cache = self._load_cache_data()
        self.CACHED_FEEDS = cache.get(CacheKeys.FEEDS, {})
        logger.info(f"Loaded {len(self.CACHED_FEEDS)} cached feeds")
    
    def add_recent_file(self, filepath: str) -> None:
        """Add a file to the recent files list."""
        # Remove if already exists to avoid duplicates
        if filepath in self.RECENT_FILES:
            self.RECENT_FILES.remove(filepath)
        
        # Add to front and keep only last 10
        self.RECENT_FILES.insert(0, filepath)
        self.RECENT_FILES = self.RECENT_FILES[:10]
        
        # Save to cache
        cache = self._load_cache_data()
        cache[CacheKeys.RECENT_FILES] = self.RECENT_FILES
        self._save_cache_data(cache)
        logger.info(f"Added recent file: {filepath}")
    
    def load_config(self) -> bool:
        """
        Loads qBittorrent connection configuration from config.ini file.
        
        Reads configuration file and populates configuration variables
        for qBittorrent API connection parameters.
        
        Returns:
            bool: True if configuration loaded successfully with host and port,
                  False otherwise
        """
        try:
            cfg = ConfigParser()
            cfg.read(self.CONFIG_FILE)

            qbt_loaded = 'QBITTORRENT_API' in cfg
            if qbt_loaded:
                qbt = cfg['QBITTORRENT_API']
                self.QBT_PROTOCOL = qbt.get('protocol', 'http')
                self.QBT_HOST = qbt.get('host', 'localhost')
                self.QBT_PORT = qbt.get('port', '8080')
                self.QBT_USER = qbt.get('username', '')
                self.QBT_PASS = qbt.get('password', '')
                self.CONNECTION_MODE = qbt.get('mode', 'online')
                self.QBT_VERIFY_SSL = qbt.get('verify_ssl', 'True').lower() == 'true'
                self.QBT_CA_CERT = qbt.get('ca_cert') or None
                self.DEFAULT_SAVE_PATH = qbt.get('default_save_path', '')
                self.DEFAULT_DOWNLOAD_PATH = qbt.get('default_download_path', '')
                self.DEFAULT_CATEGORY = qbt.get('default_category', '')
                
                # Load default affected feeds (comma-separated list)
                feeds_str = qbt.get('default_affected_feeds', '')
                self.DEFAULT_AFFECTED_FEEDS = [f.strip() for f in feeds_str.split(',') if f.strip()]
                
                logger.info(f"Loaded qBittorrent config: {self.QBT_PROTOCOL}://{self.QBT_HOST}:{self.QBT_PORT} (mode: {self.CONNECTION_MODE})")
            else:
                # Set defaults
                self.QBT_PROTOCOL, self.QBT_HOST, self.QBT_PORT = 'http', 'localhost', '8080'
                self.QBT_USER, self.QBT_PASS = '', ''
                self.QBT_VERIFY_SSL = False
                self.CONNECTION_MODE = 'online'
                logger.warning("No QBITTORRENT_API section found in config.ini, using defaults")

            return bool(self.QBT_HOST and self.QBT_PORT)
        except Exception as e:
            logger.error(f"Failed to load config from INI: {e}")
            self.QBT_PROTOCOL, self.QBT_HOST, self.QBT_PORT = 'http', 'localhost', '8080'
            self.QBT_USER, self.QBT_PASS = '', ''
            self.CONNECTION_MODE = 'online'
            return False
    
    def save_config(self, protocol: str, host: str, port: str, user: str, password: str, mode: str, verify_ssl: bool, 
                    default_save_path: str = '', default_category: str = '', default_affected_feeds: List[str] = None) -> bool:
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
            default_save_path: Default save path for new rules
            default_category: Default category for new rules
            default_affected_feeds: Default affected feeds for new rules (list of feed URLs)
        
        Returns:
            bool: True if save was successful, False otherwise
        """
        cfg = ConfigParser()
        
        # Prepare default affected feeds as comma-separated string
        feeds_str = ', '.join(default_affected_feeds) if default_affected_feeds else ''
        
        cfg['QBITTORRENT_API'] = {
                'protocol': protocol,
                'host': host,
                'port': port,
                'username': user,
                'password': password,
                'mode': mode,
                'verify_ssl': str(verify_ssl),
                'ca_cert': self.QBT_CA_CERT or '',
                'default_save_path': default_save_path,
                'default_download_path': self.DEFAULT_DOWNLOAD_PATH or '',
            'default_category': default_category,
            'default_affected_feeds': feeds_str,
        }
        
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                cfg.write(f)
        except Exception as e:
            logger.error(f"Failed to save config to INI: {e}")
            return False

        self.QBT_PROTOCOL, self.QBT_HOST, self.QBT_PORT, self.QBT_USER, self.QBT_PASS, self.CONNECTION_MODE, self.QBT_VERIFY_SSL = (
            protocol, host, port, user, password, mode, verify_ssl
        )
        self.DEFAULT_SAVE_PATH = default_save_path
        self.DEFAULT_CATEGORY = default_category
        self.DEFAULT_AFFECTED_FEEDS = default_affected_feeds or []
        logger.info(f"Saved qBittorrent config: {protocol}://{host}:{port} (mode: {mode})")
        return True
    
    def save_cached_categories(self, categories: Dict[str, Any]) -> bool:
        """Save cached categories to file."""
        try:
            cache = self._load_cache_data()
            cache[CacheKeys.CATEGORIES] = categories
            self._save_cache_data(cache)
            self.CACHED_CATEGORIES = categories
            logger.info(f"Saved {len(categories)} cached categories")
            return True
        except Exception as e:
            logger.error(f"Failed to save cached categories: {e}")
            return False
    
    def save_cached_feeds(self, feeds: Dict[str, Any]) -> bool:
        """Save cached feeds to file."""
        try:
            cache = self._load_cache_data()
            cache[CacheKeys.FEEDS] = feeds
            self._save_cache_data(cache)
            self.CACHED_FEEDS = feeds
            logger.info(f"Saved {len(feeds)} cached feeds")
            return True
        except Exception as e:
            logger.error(f"Failed to save cached feeds: {e}")
            return False
    
    def load_recent_files(self) -> None:
        """Load recent files list from cache."""
        try:
            cache = self._load_cache_data()
            self.RECENT_FILES = cache.get(CacheKeys.RECENT_FILES, [])
            logger.info(f"Loaded {len(self.RECENT_FILES)} recent files")
        except Exception as e:
            logger.error(f"Failed to load recent files: {e}")
            self.RECENT_FILES = []
    
    def clear_recent_files(self) -> bool:
        """Clear the recent files list."""
        try:
            self.RECENT_FILES = []
            cache = self._load_cache_data()
            cache[CacheKeys.RECENT_FILES] = []
            self._save_cache_data(cache)
            logger.info("Cleared recent files list")
            return True
        except Exception as e:
            logger.error(f"Failed to clear recent files: {e}")
            return False


# Global config instance
config = AppConfig()
