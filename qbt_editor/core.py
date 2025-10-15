"""Minimal compatibility shim for the qbt_editor package.

This file intentionally contains only a very small compatibility surface so
the original top-level launcher (and any external callers) can continue to
import ``setup_gui`` and ``exit_handler`` from ``qbt_editor``. All heavy
implementation lives in the submodules (``qbt_editor.ui``, ``qbt_editor.config``,
``qbt_editor.qbt_api``, ``qbt_editor.utils``).
"""

import sys
from .ui import setup_gui


def exit_handler():
    """Install a conservative excepthook that suppresses a noisy
    qbittorrent-api AttributeError during interpreter shutdown.

    The monolithic script installed a similar hook; keep a minimal compatible
    version so existing callers can call ``exit_handler()`` without extra
    runtime noise.
    """

    def _custom_excepthook(exc_type, exc_value, exc_traceback):
        try:
            if exc_type is AttributeError and '_http_session' in str(exc_value):
                # Swallow the known qbittorrent-api teardown AttributeError
                return
        except Exception:
            # On any introspection error, fall through to the default hook
            pass
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = _custom_excepthook


__all__ = ["setup_gui", "exit_handler"]
