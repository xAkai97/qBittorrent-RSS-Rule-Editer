"""
qBittorrent API Integration Module

This module provides a clean interface to qBittorrent's WebUI API.
It handles authentication, connection management, and all API operations
needed for RSS rule management.

Phase 4: qBittorrent Integration
"""
import logging
import typing
import warnings
from typing import Tuple, Optional, Union, Dict, List, Any

import requests
from requests.auth import HTTPBasicAuth

# Suppress SSL warnings when verify_ssl is disabled
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.config import config
from src.constants import QBittorrentError

logger = logging.getLogger(__name__)

# Try to import qbittorrentapi, fall back to requests if not available
try:
    from qbittorrentapi import APIConnectionError, Client, Conflict409Error
    HAS_QBT_API = True
except ImportError:
    HAS_QBT_API = False
    logger.warning("qbittorrentapi not available, using requests fallback")
    
    # Define fallback exceptions
    class APIConnectionError(Exception):
        """Raised when connection to qBittorrent API fails."""
        pass
    
    class Conflict409Error(Exception):
        """Raised when a 409 Conflict occurs (e.g., duplicate RSS feed)."""
        pass


# API Endpoints
QBT_API_BASE = "/api/v2"
QBT_AUTH_LOGIN = f"{QBT_API_BASE}/auth/login"
QBT_APP_VERSION = f"{QBT_API_BASE}/app/version"
QBT_TORRENTS_CATEGORIES = f"{QBT_API_BASE}/torrents/categories"
QBT_RSS_FEEDS = f"{QBT_API_BASE}/rss/items"
QBT_RSS_ADD_FEED = f"{QBT_API_BASE}/rss/addFeed"
QBT_RSS_SET_RULE = f"{QBT_API_BASE}/rss/setRule"
QBT_RSS_RULES = f"{QBT_API_BASE}/rss/rules"


class QBittorrentClient:
    """
    Wrapper for qBittorrent API client with connection management.
    
    Provides a unified interface whether using qbittorrentapi library
    or falling back to raw requests.
    """
    
    def __init__(self, protocol: str, host: str, port: str, 
                 username: str, password: str, verify_ssl: bool = True,
                 ca_cert: Optional[str] = None, timeout: int = 10):
        """
        Initialize qBittorrent client.
        
        Args:
            protocol: 'http' or 'https'
            host: qBittorrent host address
            port: qBittorrent WebUI port
            username: WebUI username
            password: WebUI password
            verify_ssl: Whether to verify SSL certificates
            ca_cert: Optional path to CA certificate file
            timeout: Request timeout in seconds
        """
        self.protocol = protocol.strip()
        self.host = host.strip()
        self.port = port.strip()
        self.username = username.strip()
        self.password = password.strip()
        self.verify_ssl = verify_ssl
        self.ca_cert = ca_cert
        self.timeout = timeout
        
        self.base_url = f"{self.protocol}://{self.host}:{self.port}"
        
        # SSL verification parameter
        if not verify_ssl:
            self.verify_param = False
        elif ca_cert:
            self.verify_param = ca_cert
        else:
            self.verify_param = verify_ssl
        
        logger.debug(f"QBittorrentClient initialized: verify_ssl={verify_ssl}, ca_cert={ca_cert}, verify_param={self.verify_param}")
        
        self._client = None
        self._session = None
        
    def _get_verify_param(self) -> Union[bool, str]:
        """Get SSL verification parameter."""
        if not self.verify_ssl:
            return False
        elif self.ca_cert:
            return self.ca_cert
        else:
            return self.verify_ssl
    
    def connect(self) -> bool:
        """
        Establish connection to qBittorrent.
        
        Returns:
            bool: True if connection successful
            
        Raises:
            APIConnectionError: If connection fails
            QBittorrentError: If authentication fails
        """
        if HAS_QBT_API:
            return self._connect_with_library()
        else:
            return self._connect_with_requests()
    
    def _connect_with_library(self) -> bool:
        """Connect using qbittorrentapi library."""
        try:
            # Try with VERIFY_WEBUI_CERTIFICATE parameter (newer versions)
            self._client = Client(
                host=self.base_url,
                username=self.username,
                password=self.password,
                VERIFY_WEBUI_CERTIFICATE=self.verify_param
            )
            self._client.auth_log_in()
            logger.info(f"Connected to qBittorrent at {self.base_url}")
            return True
        except TypeError:
            # Fallback: try without certificate parameter, then set session verify manually
            try:
                self._client = Client(
                    host=self.base_url,
                    username=self.username,
                    password=self.password
                )
                # Manually disable SSL verification if needed
                if not self.verify_ssl:
                    # Try to find and set the session's verify attribute
                    for attr in ('_http_session', '_session', 'http_session', 'session'):
                        sess = getattr(self._client, attr, None)
                        if sess is not None and hasattr(sess, 'verify'):
                            sess.verify = False
                            logger.debug(f"Disabled SSL verification via {attr}")
                            break
                self._client.auth_log_in()
                logger.info(f"Connected to qBittorrent at {self.base_url} (fallback mode)")
                return True
            except Exception as e:
                logger.error(f"Failed to connect with library: {e}")
                raise
    
    def _connect_with_requests(self) -> bool:
        """Connect using raw requests."""
        self._session = requests.Session()
        login_url = f"{self.base_url}{QBT_AUTH_LOGIN}"
        
        logger.debug(f"Connecting to {login_url} with verify={self.verify_param}")
        
        try:
            response = self._session.post(
                login_url,
                data={'username': self.username, 'password': self.password},
                timeout=self.timeout,
                verify=self.verify_param
            )
            
            if response.status_code == 200 and response.text.strip().lower() == 'ok':
                logger.info(f"Connected to qBittorrent at {self.base_url} (requests)")
                return True
            else:
                raise QBittorrentError(f"Authentication failed: {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(f"Connection failed: {e}")
    
    def get_version(self) -> str:
        """
        Get qBittorrent version.
        
        Returns:
            str: Version string
        """
        if self._client:
            try:
                return self._client.app_version()
            except:
                pass
        
        if self._session:
            url = f"{self.base_url}{QBT_APP_VERSION}"
            response = self._session.get(url, timeout=self.timeout, verify=self.verify_param)
            if response.status_code == 200:
                return response.text.strip()
        
        return "unknown"
    
    def get_categories(self) -> Dict[str, Any]:
        """
        Fetch all categories from qBittorrent.
        
        Returns:
            dict: Categories dictionary
        """
        if self._client:
            try:
                for attr in ('torrents_categories', 'categories', 'torrents_categories_map'):
                    if hasattr(self._client, attr):
                        return getattr(self._client, attr)() or {}
            except:
                pass
        
        if self._session:
            url = f"{self.base_url}{QBT_TORRENTS_CATEGORIES}"
            response = self._session.get(url, timeout=self.timeout, verify=self.verify_param)
            if response.status_code == 200:
                return response.json() or {}
        
        return {}
    
    def get_feeds(self) -> Dict[str, Any]:
        """
        Fetch all RSS feeds from qBittorrent.
        
        Returns:
            dict: Feeds dictionary
        """
        if self._client:
            try:
                for attr in ('rss_feeds', 'rss_feed', 'rss_items'):
                    if hasattr(self._client, attr):
                        return getattr(self._client, attr)() or {}
            except:
                pass
        
        if self._session:
            # Try multiple endpoints
            endpoints = [
                QBT_RSS_FEEDS,
                f"{QBT_API_BASE}/rss/rootItems",
                f"{QBT_API_BASE}/rss/tree",
            ]
            
            for endpoint in endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"
                    response = self._session.get(url, timeout=self.timeout, verify=self.verify_param)
                    if response.status_code == 200:
                        return response.json() or {}
                except:
                    continue
        
        return {}
    
    def get_rules(self) -> Dict[str, Any]:
        """
        Fetch all RSS download rules from qBittorrent.
        
        Returns:
            dict: Rules dictionary
        """
        if self._client:
            try:
                for attr in ('rss_rules', 'rss_rule', 'rss_download_rules'):
                    if hasattr(self._client, attr):
                        return getattr(self._client, attr)() or {}
            except:
                pass
        
        if self._session:
            url = f"{self.base_url}{QBT_RSS_RULES}"
            try:
                response = self._session.get(url, timeout=self.timeout, verify=self.verify_param)
                if response.status_code == 200:
                    return response.json() or {}
            except:
                pass
        
        return {}
    
    def add_feed(self, feed_url: str, feed_name: Optional[str] = None) -> bool:
        """
        Add an RSS feed to qBittorrent.
        
        Args:
            feed_url: URL of the RSS feed
            feed_name: Optional custom name for the feed
            
        Returns:
            bool: True if successful
        """
        if self._client:
            try:
                self._client.rss_add_feed(url=feed_url)
                logger.info(f"Added RSS feed: {feed_url}")
                return True
            except Conflict409Error:
                logger.info(f"RSS feed already exists: {feed_url}")
                return True
            except Exception as e:
                logger.error(f"Failed to add RSS feed: {e}")
                return False
        
        if self._session:
            url = f"{self.base_url}{QBT_RSS_ADD_FEED}"
            data = {'url': feed_url}
            if feed_name:
                data['path'] = feed_name
            
            try:
                response = self._session.post(
                    url,
                    data=data,
                    timeout=self.timeout,
                    verify=self.verify_param
                )
                if response.status_code in (200, 409):  # 409 = already exists
                    logger.info(f"Added RSS feed: {feed_url}")
                    return True
                logger.error(f"Failed to add RSS feed: HTTP {response.status_code}")
                return False
            except Exception as e:
                logger.error(f"Failed to add RSS feed: {e}")
                return False
        
        return False
    
    def set_rule(self, rule_name: str, rule_def: Dict[str, Any]) -> bool:
        """
        Create or update an RSS download rule.
        
        Args:
            rule_name: Name of the rule
            rule_def: Rule definition dictionary
            
        Returns:
            bool: True if successful
        """
        if self._client:
            try:
                self._client.rss_set_rule(rule_name=rule_name, rule_def=rule_def)
                logger.info(f"Set RSS rule: {rule_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to set RSS rule '{rule_name}': {e}")
                return False
        
        if self._session:
            url = f"{self.base_url}{QBT_RSS_SET_RULE}"
            import json
            data = {
                'ruleName': rule_name,
                'ruleDef': json.dumps(rule_def)
            }
            
            try:
                response = self._session.post(
                    url,
                    data=data,
                    timeout=self.timeout,
                    verify=self.verify_param
                )
                if response.status_code == 200:
                    logger.info(f"Set RSS rule: {rule_name}")
                    return True
                logger.error(f"Failed to set RSS rule: HTTP {response.status_code}")
                return False
            except Exception as e:
                logger.error(f"Failed to set RSS rule '{rule_name}': {e}")
                return False
        
        return False
    
    def close(self):
        """Close the connection."""
        if self._client:
            try:
                self._client.auth_log_out()
            except:
                pass
            self._client = None
        
        if self._session:
            try:
                self._session.close()
            except:
                pass
            self._session = None


# High-level API functions

def ping_qbittorrent(protocol: str, host: str, port: str, 
                    username: str, password: str, verify_ssl: bool = True,
                    ca_cert: Optional[str] = None, timeout: int = 10) -> Tuple[bool, str]:
    """
    Test connection to qBittorrent.
    
    Args:
        protocol: 'http' or 'https'
        host: qBittorrent host
        port: WebUI port
        username: Username
        password: Password
        verify_ssl: Verify SSL certificates
        ca_cert: Optional CA certificate path
        timeout: Connection timeout
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    if not host or not port:
        return False, "Host or port is empty"
    
    try:
        client = QBittorrentClient(
            protocol=protocol,
            host=host,
            port=port,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
            ca_cert=ca_cert,
            timeout=timeout
        )
        
        client.connect()
        version = client.get_version()
        client.close()
        
        return True, f"Connected - version {version}"
        
    except APIConnectionError as e:
        return False, f"Connection failed: {e}"
    except QBittorrentError as e:
        return False, f"Authentication failed: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def fetch_categories(protocol: str, host: str, port: str,
                    username: str, password: str, verify_ssl: bool = True,
                    ca_cert: Optional[str] = None, timeout: int = 10) -> Tuple[bool, Union[str, Dict]]:
    """
    Fetch categories from qBittorrent.
    
    Args:
        protocol: 'http' or 'https'
        host: qBittorrent host
        port: WebUI port
        username: Username
        password: Password
        verify_ssl: Verify SSL certificates
        ca_cert: Optional CA certificate path
        timeout: Request timeout
        
    Returns:
        Tuple[bool, Union[str, dict]]: (success, categories or error_message)
    """
    if not host or not port:
        return False, "Host or port is empty"
    
    try:
        client = QBittorrentClient(
            protocol=protocol,
            host=host,
            port=port,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
            ca_cert=ca_cert,
            timeout=timeout
        )
        
        client.connect()
        categories = client.get_categories()
        client.close()
        
        return True, categories
        
    except Exception as e:
        return False, str(e)


def fetch_feeds(protocol: str, host: str, port: str,
               username: str, password: str, verify_ssl: bool = True,
               ca_cert: Optional[str] = None, timeout: int = 10) -> Tuple[bool, Union[str, Dict]]:
    """
    Fetch RSS feeds from qBittorrent.
    
    Args:
        protocol: 'http' or 'https'
        host: qBittorrent host
        port: WebUI port
        username: Username
        password: Password
        verify_ssl: Verify SSL certificates
        ca_cert: Optional CA certificate path
        timeout: Request timeout
        
    Returns:
        Tuple[bool, Union[str, dict]]: (success, feeds or error_message)
    """
    if not host or not port:
        return False, "Host or port is empty"
    
    try:
        client = QBittorrentClient(
            protocol=protocol,
            host=host,
            port=port,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
            ca_cert=ca_cert,
            timeout=timeout
        )
        
        client.connect()
        feeds = client.get_feeds()
        client.close()
        
        return True, feeds
        
    except Exception as e:
        return False, str(e)


def fetch_rules(protocol: str, host: str, port: str,
               username: str, password: str, verify_ssl: bool = True,
               ca_cert: Optional[str] = None, timeout: int = 10) -> Tuple[bool, Union[str, Dict]]:
    """
    Fetch RSS download rules from qBittorrent.
    
    Args:
        protocol: 'http' or 'https'
        host: qBittorrent host
        port: WebUI port
        username: Username
        password: Password
        verify_ssl: Verify SSL certificates
        ca_cert: Optional CA certificate path
        timeout: Request timeout
        
    Returns:
        Tuple[bool, Union[str, dict]]: (success, rules or error_message)
    """
    if not host or not port:
        return False, "Host or port is empty"
    
    try:
        client = QBittorrentClient(
            protocol=protocol,
            host=host,
            port=port,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
            ca_cert=ca_cert,
            timeout=timeout
        )
        
        client.connect()
        rules = client.get_rules()
        client.close()
        
        return True, rules
        
    except Exception as e:
        return False, str(e)


__all__ = [
    'QBittorrentClient',
    'ping_qbittorrent',
    'fetch_categories',
    'fetch_feeds',
    'fetch_rules',
    'APIConnectionError',
    'Conflict409Error',
]
