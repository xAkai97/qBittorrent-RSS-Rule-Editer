"""
Application configuration management.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

from .constants import CacheKeys

logger = logging.getLogger(__name__)


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
