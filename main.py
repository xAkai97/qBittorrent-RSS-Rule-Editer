#!/usr/bin/env python3
"""
qBittorrent RSS Rule Editor - Main Entry Point (Modular Version)

A cross-platform Tkinter GUI for generating and synchronizing qBittorrent RSS rules.
This is the new modular entry point that imports from the src package.

Usage:
    python main.py

For the legacy single-file version, use:
    python qbt_editor.py
"""
import logging
import sys

# Configure logging
logging.basicConfig(
    filename='qbt_editor.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the application."""
    try:
        logger.info("Starting qBittorrent RSS Rule Editor (Modular Version)")
        logger.info("Phase 3: GUI modularization in progress")
        
        # Import from modular structure
        from src.gui import setup_gui, exit_handler
        
        # Setup exit handler
        exit_handler()
        
        # Start the GUI
        setup_gui()
        
    except ImportError as e:
        print("=" * 60)
        print("ERROR: Failed to import required modules")
        print("=" * 60)
        print(f"\nDetails: {e}")
        print("\nPossible solutions:")
        print("  1. Make sure you're running from the project root directory")
        print("  2. Install required dependencies: pip install -r requirements.txt")
        print("  3. Use the legacy version: python qbt_editor.py")
        print()
        logger.error(f"Import error: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        print("=" * 60)
        print("ERROR: An unexpected error occurred")
        print("=" * 60)
        print(f"\nDetails: {e}")
        print("\nPlease check 'qbt_editor.log' for more information.")
        print()
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
