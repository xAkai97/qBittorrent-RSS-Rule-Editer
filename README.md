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

Browser extension (MAL Multi-Select Export)
------------------------------------------

This project can be used together with a small browser extension that helps collect anime titles from MyAnimeList.

- Extension repo: https://github.com/xAkai97/mal-multi-select-export

How to use the extension with this tool
1. Install the extension (developer/unpacked install):
   - Clone the extension repository or download the ZIP and extract it.
   - In Chrome/Edge/Brave, open chrome://extensions/ and enable "Developer mode".
   - Click "Load unpacked" and select the extension folder (the one containing `manifest.json`).
2. On MyAnimeList season pages the extension adds checkboxes for multi-select. Select titles and export as JSON or copy to clipboard.
3. In this project, use "Import > Paste from Clipboard" or "Import > Open JSON File" to load the exported titles and generate qBittorrent RSS rules.

Notes
- The extension is maintained separately so it can evolve independently (its own issues, CI, and releases).
- If you prefer a single-repo workflow you can import the extension into this repository, or add it as a git submodule — see the `mal-multi-select-export` repo for details.

Related links
- Extension repository: https://github.com/xAkai97/mal-multi-select-export
