"""Module entrypoint for the qbt_editor package.

Allows running the application via `python -m qbt_editor`.
"""

from .core import exit_handler
from .ui import setup_gui


def main():
    # Install the conservative exit handler and launch the GUI
    exit_handler()
    setup_gui()


if __name__ == "__main__":
    main()
