"""
Constants used throughout the application.
"""


# ==================== Custom Exception Classes ====================
class QBittorrentAuthenticationError(Exception):
    """Raised when authentication with qBittorrent fails."""
    pass


class QBittorrentError(Exception):
    """General qBittorrent-related errors."""
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
        'CON1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    MAX_PATH_LENGTH = 255
