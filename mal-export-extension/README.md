MAL Multi-Select Export (Clipboard)

Quick instructions to load the extension (Chrome / Edge / Brave / Chromium):

1. Open chrome://extensions/ (or edge://extensions/). Enable "Developer mode".
2. Click "Load unpacked" and select the `mal-export-extension` folder in this repo.
3. Visit a MyAnimeList page with many anime (season page, search results, or user lists).
4. A small toolbar will appear at the top of the page. Use the injected checkboxes on items to select them.
5. Click "Copy to clipboard" to copy a JSON array of selected items (title, url, malId, image). Or click "Download JSON".

Notes and limitations:
- This is a minimal content-script-only extension (no popup). It attempts to attach to many MAL page layouts but may miss custom or future MAL markup. If you see nodes not having checkboxes, please share a URL and I can add a more specific selector.
- No communication directly to your desktop app in this version. For that, we can add a Native Messaging host (requires a small Python helper and Windows registry manifest). See the repository TODOs for the native option.

Files:
- manifest.json - MV3 manifest
- content_script.js - injection and UI logic
- style.css - minimal styles

If you want, I can now:
- Add a CSV export button or a small popup to choose export format.
- Implement Native Messaging host to send directly to your app (requires install steps).