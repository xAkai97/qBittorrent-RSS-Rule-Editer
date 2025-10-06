qBittorrent RSS Rule Editor
This is a Python GUI application designed to automate the process of setting up seasonal anime auto-download rules in qBittorrent.

It uses the MyAnimeList (MAL) API to fetch the latest seasonal anime titles and provides a friendly interface (built with Tkinter) to select titles, configure save paths, and synchronize the rules directly to your qBittorrent WebUI.

Features
MAL API Integration: Fetches current seasonal anime data (TV, Movies, OVAs, etc.).

Local Caching: Saves fetched MAL data to seasonal_cache.json to prevent unnecessary API calls.

Multi-Select GUI: Allows easy selection of titles using checkboxes, Shift-click (range select), and Ctrl-click (toggle select).

Online Sync: Connects directly to a remote qBittorrent instance (including Docker/NAS setups) via the Web API to create RSS rules instantly.

Offline Mode: Generates a standard qbittorrent_rules.json file for manual import.

Customizable Filtering: Filter the display list by media type (TV, Movie, OVA, etc.).

Persistent Configuration: Saves all connection details and API keys in config.ini.

Installation
This project requires Python 3.8+ and the following libraries:

Clone the Repository (or save the script):

git clone [your_repo_url]
cd qbt_rss_anime_syncer

Create and Activate a Virtual Environment (Recommended):

python -m venv venvipy
.\venvipy\Scripts\activate  # On Windows
# source venvipy/bin/activate # On Linux/macOS

Install Dependencies:
Install all required libraries using pip:

pip install requests qbittorrent-api

Usage Guide
1. Run the Application
Execute the main script from your activated virtual environment:

python qbt_rss_anime_syncer.py

2. Configure Settings (First Run)
The Settings window will open automatically if your credentials are not yet saved.

Section

Field

Description

Connection Mode

Online (Direct API Sync)

Recommended. Rules are instantly pushed to your running qBittorrent client.



Offline (Generate JSON File)

Creates a local .json file for manual import.

MyAnimeList API

Client ID

The ID obtained from your MAL API application registration.

qBittorrent Web UI API

Protocol

Select https if you use SSL/TLS (like in a Docker/NAS setup).



Host / Port

Your qBittorrent WebUI IP address and port (e.g., 192.168.1.100 and 8080).



Username / Password

Your qBittorrent WebUI login credentials.



Verify SSL Certificate

UNCHECK this if your qBittorrent server uses a self-signed certificate (common in Docker/NAS).

Click "Save All Settings" to store credentials in config.ini. You can return to the Settings menu anytime.

3. Fetch and Select Titles
Select the desired Season and Year.

Adjust the Media Types checkboxes (e.g., enable TV, Movie, etc.).

Click "Fetch Titles" (or "Refresh Titles" to bypass cache).

In the "2. Select Titles" section, click the checkboxes next to the anime titles you want to download.

Shift + Click: Selects a range of titles.

Ctrl + Click: Toggles individual titles.

4. Generate/Sync Rules
Click "3. Generate/Sync Rules".

Online Mode: Rules are created instantly in your remote qBittorrent client.

Offline Mode: The qbittorrent_rules.json file is created in the project folder. You must manually import this file into qBittorrent's RSS Downloader settings.
