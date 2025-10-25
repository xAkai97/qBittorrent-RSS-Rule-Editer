# mal-multi-select-export
MAL Multi-Select Export — select multiple MyAnimeList entries and copy/export as JSON

Short description
-----------------
Browser content script that injects checkboxes on MyAnimeList season pages so you can multi-select anime entries and export selected titles as JSON or copy them to the clipboard. Useful for quickly collecting titles to import into other tools (for example: qBittorrent RSS Rule Editor).

Install & test (developer / unpacked)
-----------------------------------
1. Clone the repository or download the ZIP and extract it.
2. Open your browser's extensions page:
	- Chrome/Edge/Brave: chrome://extensions/
	- Firefox (temporary install): about:debugging
3. Enable Developer mode (Chrome/Edge) or choose to load a temporary add-on (Firefox).
4. Click "Load unpacked" (or the equivalent) and select the extension folder (the folder containing `manifest.json`).

Usage
-----
- Visit a MyAnimeList seasonal page (e.g., https://myanimelist.net/anime/season).
- Use the injected toolbar to toggle multi-select checkboxes, pick titles, and export selected entries to clipboard or JSON.
- The exported JSON can be imported into `qBittorrent-RSS-Rule-Editer` (https://github.com/xAkai97/qBittorrent-RSS-Rule-Editer) via the "Import > Open JSON File" or "Import > Paste from Clipboard" options.

Related project
---------------
- qBittorrent RSS Rule Editor — https://github.com/xAkai97/qBittorrent-RSS-Rule-Editer

License
-------
This project is licensed under the MIT License. See the `LICENSE` file for details.


## Related project

- qBittorrent RSS Rule Editor — a desktop utility to turn anime title lists into qBittorrent RSS rules and sync with qBittorrent:
	- https://github.com/xAkai97/qBittorrent-RSS-Rule-Editer
