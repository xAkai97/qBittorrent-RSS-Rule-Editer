"""qbt_editor package

Provides a small programmatic API surface for the refactored app. Users
can import either the high-level `setup_gui` or individual submodules:

	from qbt_editor import setup_gui
	from qbt_editor import ui, config, qbt_api

The package re-exports the main setup function and the exit handler.
"""

from .core import setup_gui, exit_handler
from . import ui, config, qbt_api

__all__ = [
	'setup_gui',
	'exit_handler',
	'ui',
	'config',
	'qbt_api',
]
