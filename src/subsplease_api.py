"""
SubsPlease API integration for fetching anime schedule and titles.

IMPORTANT: This uses SubsPlease's public API responsibly with caching.
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, Any

from .constants import CacheKeys
from .config import config

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None


def load_subsplease_cache() -> Dict[str, Dict[str, Any]]:
    """
    Loads cached SubsPlease schedule titles from cache.
    
    Returns:
        Dict with title as key and metadata dict as value:
        {
            "Anime Title": {
                      "subsplease": "SubsPlease Title",
                      "last_updated": "2024-01-15T10:30:00",
                      "exact_match": True
                  }
        }
    """
    try:
        if os.path.exists(config.CACHE_FILE):
            with open(config.CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
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
        titles_dict: Dictionary of titles with metadata
    
    Returns:
        bool: True if successful
    """
    try:
        # Import here to avoid circular dependency
        from . import cache as cache_module
        success = cache_module._update_cache_key(CacheKeys.SUBSPLEASE_TITLES, titles_dict)
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
    
    IMPORTANT: This uses SubsPlease's public API. Usage notes:
    - SubsPlease has no published terms restricting API access
    - Multiple open-source projects use this API
    - Rate limiting is handled through caching
    - Proper User-Agent headers identify the application
    
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
    
    # Try partial match (simple fuzzy matching)
    # Look for titles that contain the MAL title or vice versa
    best_match = None
    best_score = 0
    
    for cached_title, data in cached.items():
        cached_lower = cached_title.lower()
        
        # Check if one contains the other
        if mal_lower in cached_lower or cached_lower in mal_lower:
            # Calculate simple match score (length of match)
            score = min(len(mal_lower), len(cached_lower))
            if score > best_score:
                best_score = score
                best_match = data.get('subsplease', cached_title) if isinstance(data, dict) else cached_title
    
    return best_match
