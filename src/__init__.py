"""
qBittorrent RSS Rule Editor - Modular Package

A cross-platform Tkinter GUI for generating and synchronizing qBittorrent RSS rules.

Phase 3: GUI modularization in progress
Phase 4: qBittorrent integration complete
Phase 5: RSS rules management complete
"""

__version__ = "0.5.0-dev"  # Phase 5 development
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
