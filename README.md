**qBittorrent RSS Rule Editor**

A small cross-platform Tkinter GUI that helps generate and synchronize qBittorrent RSS rules for seasonal anime, supporting offline JSON export and optional online sync to a qBittorrent WebUI.

**Features**

- Generate offline qBittorrent RSS rule JSON for manual import.
- Sync generated rules directly to a qBittorrent WebUI when `qbittorrent-api` is installed and configured.
- A simple Tkinter GUI to pick titles and set season/year prefixes.
- Config persistence in `config.ini` (qBittorrent host/port/credentials, connection mode, SSL options).

**Installation**

This project requires Python 3.8+ and the following libraries:

1.  **Clone the Repository (or save the script):**
    # qBittorrent RSS Rule Editor

    Small Tkinter GUI to generate or synchronize qBittorrent RSS rules (focused on seasonal anime).

    ## Quick start

    1. Create & activate a Python 3.8+ virtualenv:

    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate
    ```

    2. Install dependencies:

    ```powershell
    pip install -r requirements.txt
    ```

    3. Run the GUI:

    ```powershell
    python "filename.py"
    ```

    ## Configuration

    On first run open Settings and provide your qBittorrent WebUI details. Config is stored in `config.ini`.

    - Connection Mode: `online` (sync directly) or `offline` (generate JSON file for manual import).
    - For self-signed HTTPS, either provide a CA certificate path in Settings or uncheck "Verify SSL".

    ## Optional dependency

    Install `qbittorrent-api` only if you want online sync:

    ```powershell
    pip install qbittorrent-api
    ```

    If the library is not installed the package still imports and supports offline JSON generation.

     Browser extension (MAL export)
     -----------------------------

     The extension has been split into its own repository and is maintained separately:

     - mal-multi-select-export — https://github.com/xAkai97/mal-multi-select-export

     You can install or test the extension in one of two ways:

     1. Download or clone the extension repo and load it unpacked in your browser (Chrome/Edge/Brave):

         - Open `chrome://extensions/` and enable Developer mode.
         - Click "Load unpacked" and select the extension folder you cloned from the `mal-multi-select-export` repository.

     2. If you have a local copy in this repository at `mal-multi-select-export/`, you can also load that folder directly using the same "Load unpacked" workflow.

     See the extension repository for usage, releases, and installation notes: https://github.com/xAkai97/mal-multi-select-export