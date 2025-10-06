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
    python -m venv venvipy
    .\\venvipy\\Scripts\\activate \# On Windows
    \# source venvipy/bin/activate \# On Linux/macOS

3.  Install Dependencies:
    Install all required libraries using pip:
    pip install requests qbittorrent-api

**Usage Guide**

**1. Run the Application**

Execute the main script from your activated virtual environment:

python qbt\_rss\_anime\_syncer.py

**2. Configure Settings (CRITICAL)**

The **Settings** window will open automatically if credentials are not set. Ensure all fields are correct, particularly the qBittorrent WebUI section:

*   **Protocol:** **http** / **https** based on your server configuration.
*   **Port:** **8080**.
*   **Username/Password:** Must match your qBittorrent WebUI login.
*   **Verify SSL Certificate:** **UNCHECK THIS BOX** since your Docker setup uses a self-signed certificate.

**3. Fetch and Select Titles**

1.  Select the desired **Season** and **Year**.
2.  Adjust the **Media Types** checkboxes (TV, Movie, etc.).
3.  Click **"Fetch Titles"** (or **"Refresh Titles"** to bypass cache).
4.  In the **"2. Select Titles"** section, use **Shift + Click** or **Ctrl + Click** to select the anime you want.

**4. Generate/Sync Rules**

Click **"3. Generate/Sync Rules"** to push the robust, new rules directly to your qBittorrent client.
