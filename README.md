**qBittorrent RSS Rule Editor**

This is a Python GUI application designed to automate the process of setting up seasonal anime auto-download rules in qBittorrent.

It uses the **MyAnimeList (MAL) API** to fetch the latest seasonal anime titles and provides a interface (built with **Tkinter**) to select titles, configure save paths, and synchronize the rules directly to your qBittorrent WebUI.

**Features**

*   **MAL API Integration:** Fetches current seasonal anime data (TV, Movies, OVAs, etc.), allowing multi-select media type filtering.
*   **Local Caching:** Saves fetched MAL data to seasonal_cache.json to prevent unnecessary API calls.
*   **Robust Download Rules:** Generates **hyper-flexible Regular Expression (Regex)** rules to maximize torrent matching success by accounting for variations in torrent file names (e.g., optional spaces, different punctuation).
*   **Multi-Select GUI:** Allows easy selection of titles using **checkboxes, Shift-click (range select), and Ctrl-click (toggle select)**.
*   **Online Sync:** Connects directly to a remote qBittorrent instance (including Docker/NAS setups) via the Web API to create RSS rules instantly.
*   **Offline Mode:** Generates a standard qbittorrent_rules.json file for manual import.
*   **Persistent Configuration:** Saves all connection details and API keys in config.ini.

**Installation**

This project requires Python 3.8+ and the following libraries:

1.  **Clone the Repository (or save the script):**
    git clone \[your\_repo\_url\]
    cd qbt\_rss\_anime\_syncer

2.  **Create and Activate a Virtual Environment (Recommended):**
    python -m venv {venv_dir}
    .\\{venv_dir}\\Scripts\\activate \# On Windows
    \# source {venv_dir}/bin/activate \# On Linux/macOS

3.  Install Dependencies:
    Install all required libraries:
    pip install requirements.txt

**Usage Guide**

**1. Run the Application**

Execute the main script from your activated virtual environment:

**2. Configure Settings (CRITICAL)**

The **Settings** window will open automatically if credentials are not set. Ensure all fields are correct, particularly the qBittorrent WebUI section:

*   **Protocol:** **http** / **https** based on your server configuration.
*   **Port:** **8080**.
*   **Username/Password:** Must match your qBittorrent WebUI login.
*   **Verify SSL Certificate:** **UNCHECK THIS BOX** if your Docker setup uses a self-signed certificate.

**3. Fetch and Select Titles**

1.  Select the desired **Season** and **Year**.
2.  Adjust the **Media Types** checkboxes (TV, Movie, etc.).
3.  Click **"Fetch Titles"** (or **"Refresh Titles"** to bypass cache).
4.  In the **"Select Titles"** section, use **Shift + Click** or **Ctrl + Click** to select the anime you want.

**4. Generate/Sync Rules**

Click **"Generate/Sync Rules"** to push the robust, new rules directly to your qBittorrent client.

Running
-------

The project has been refactored into a package. Preferred ways to run the application:

- Run as a module (recommended):

    python -m qbt_editor

- (Legacy) If you previously used the top-level script, it was removed in this refactor. The package provides the same functionality via the `qbt_editor` package.

Dependencies
------------

The qBittorrent integration is optional at import-time. To enable online sync with qBittorrent, install the WebUI client library:

    pip install qbittorrent-api

If `qbittorrent-api` is not installed the application will still import and run in offline mode (generate JSON rules) but any online sync features will be disabled until the dependency is present.

Example
-------

Run the application using the module entrypoint (recommended):

```powershell
python -m qbt_editor
```

Thumbnails in Select Titles
---------------------------

This application can optionally show poster thumbnails next to each title in the "Select Titles" list. Notes:

- Dependency: The thumbnail feature uses the Pillow library. Install it with the project's dependencies:

    pip install -r requirements.txt

- Enable/Disable: Open the application's **Settings** window and toggle **Show thumbnails in Select Titles**. If disabled, the app will always show a compact, text-only list.

- Cache: Downloaded thumbnails are cached in the `.thumb_cache` directory next to the script to avoid re-downloading images.

- Fallback: If Pillow is not installed or a thumbnail fails to download, the app will gracefully fall back to a text-only view.

Displayed title details
-----------------------

For each anime listed in the "Select Titles" view the application displays key metadata fetched from MyAnimeList (when available). The fields shown include:

- Episodes: The total number of episodes (or expected episodes) for the title.
- Status: The broadcast / release status (e.g., "Finished Airing", "Currently Airing", "Not yet aired").
- Aired: The original air date range or start date.
- Synopsis: A short description or summary of the title.

These fields are used to help you decide which titles to include when generating RSS rules. The synopsis is truncated in the list view to keep the UI compact; you can view the full synopsis in the preview/edit window when generating rules.
