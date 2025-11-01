"""
qBittorrent RSS Rule Editor - Modular Package

A cross-platform Tkinter GUI for generating and synchronizing qBittorrent RSS rules.

"""

__version__ = "0.9.0-dev"  
__author__ = "xAkai97"

# Import core configuration
from .config import config

# Import GUI entry points
from .gui import setup_gui, exit_handler

# Import qBittorrent API
from . import qbittorrent_api

# Import RSS rules management
from . import rss_rules

__all__ = ["config", "setup_gui", "exit_handler", "qbittorrent_api", "rss_rules"]
