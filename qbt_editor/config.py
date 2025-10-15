"""Configuration utilities and persistence.

Contains config constants and functions to load/save `config.ini`.
"""
import os
from configparser import ConfigParser

# Files
CONFIG_FILE = 'config.ini'
OUTPUT_CONFIG_FILE_NAME = 'qbittorrent_rules.json'
CACHE_FILE = 'seasonal_cache.json'

# Defaults
DEFAULT_RSS_FEED = "https://subsplease.org/rss/?r=1080"
DEFAULT_SAVE_PREFIX = "/downloads/Anime/Web/"

# Runtime globals (set by load_config/save_config)
QBT_PROTOCOL = None
QBT_HOST = None
QBT_PORT = None
QBT_USER = None
QBT_PASS = None
QBT_VERIFY_SSL = True
CONNECTION_MODE = 'online'
QBT_CA_CERT = None


def load_config():
    """Load QBITTORRENT_API section from config file into module globals.

    Returns True when QBT host/port appear set (used by launcher to prompt
    for settings on first run).
    """
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


def save_config(protocol, host, port, user, password, mode, verify_ssl):
    """Persist qBittorrent connection settings to `config.ini`.

    Also updates the module-level globals.
    """
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
