# qBittorrent RSS Rule Editor

A cross-platform Tkinter GUI that helps generate and synchronize qBittorrent RSS rules for seasonal anime, supporting offline JSON export and optional online sync to a qBittorrent WebUI.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-30%2F30%20passing-brightgreen.svg)](tests/)

## Features

- **🎯 Smart Rule Generation** - Create qBittorrent RSS download rules with seasonal paths
- **📤 Dual Mode Operation** - Export JSON files or sync directly to qBittorrent WebUI
- **🔄 SubsPlease Integration** - Fetch current seasonal anime titles with local caching
- **📋 MAL Import** - Import anime lists from MyAnimeList Seasonal via browser extension

## Quick Start

### 1. Create & Activate Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Run the Application

```powershell
# Modular version (recommended)
python main.py

# OR legacy single-file version
python legacy/qbt_editor.py
```

Both versions are fully functional and share the same configuration files.

## Project Structure

This project features a fully modular architecture with clean separation of concerns:

```
src/
├── constants.py       ✅ Constants & exceptions
├── config.py          ✅ Configuration management
├── cache.py           ✅ Data persistence
├── utils.py           ✅ Utility functions
├── subsplease_api.py  ✅ SubsPlease integration
├── qbittorrent_api.py ✅ qBittorrent API client
├── rss_rules.py       ✅ RSS rule management
└── gui/               ✅ GUI modules (COMPLETE)
    ├── app_state.py      - Centralized state management
    ├── helpers.py        - GUI utility functions
    ├── widgets.py        - Reusable components
    ├── dialogs.py        - All dialog windows
    ├── file_operations.py - Import/export logic
    └── main_window.py    - Main window setup
```

**Modularization:** 100% Complete - All 2,350+ lines extracted from legacy monolith  
**Test Coverage:** 30/30 tests passing (100%) ✅

## Configuration

On first run, open **Settings** and configure your qBittorrent WebUI details. Configuration is stored in `config.ini`.

### Connection Modes

- **Online Mode** - Sync rules directly to qBittorrent WebUI (requires `qbittorrent-api`)
- **Offline Mode** - Generate JSON file for manual import

### SSL/TLS Support

For self-signed HTTPS certificates:
- Provide a CA certificate path in Settings, OR
- Uncheck "Verify SSL" (not recommended for production)

### Optional Dependency

Install `qbittorrent-api` for online sync capability:

```powershell
pip install qbittorrent-api
```

**Note:** The application works in offline mode without this library.

## SubsPlease API Integration

The "Feed Title Variations" feature fetches current anime titles from SubsPlease's public API to help match your titles with their RSS feed naming conventions.

### API Usage Details

- **Endpoint:** `https://subsplease.org/api/?f=schedule&tz=UTC`
- **Access:** Public API with no published restrictions
- **Caching:** Results cached locally for 30 days in `seasonal_cache.json`
- **Rate Limiting:** Automatic through caching mechanism
- **User-Agent:** Identifies itself properly to SubsPlease
- **Usage:** Multiple open-source projects use this API responsibly

### How to Use

- **Load Cache** - Uses local cache if available, fetches only if cache is empty
- **Fetch Fresh** - Always fetches latest data from SubsPlease API
- **Optional** - The tool works fine without this feature

**Please use responsibly** - The caching system minimizes API load automatically.

## MAL Multi-Select Export Integration

This tool integrates with the **MAL Multi-Select Export** browser extension to import anime lists from MyAnimeList.

### Extension Repository
🔗 https://github.com/xAkai97/mal-multi-select-export

### How to Use

1. **Install the Extension** (developer mode):
   - Clone or download the extension repository
   - In Chrome/Edge/Brave: Navigate to `chrome://extensions/`
   - Enable "Developer mode"
   - Click "Load unpacked" and select the extension folder (containing `manifest.json`)

2. **Export from MyAnimeList:**
   - Visit MyAnimeList seasonal anime pages
   - Use checkboxes to multi-select titles
   - Export as JSON or copy to clipboard

3. **Import into RSS Rule Editor:**
   - Use **"Import > Paste from Clipboard"** or **"Import > Open JSON File"**
   - Generate qBittorrent RSS rules from imported titles

### Why Separate Repository?

The extension is maintained separately to allow independent development, issues tracking, CI/CD, and releases.

## Development

### Running Tests

```powershell
# Run all tests
python test_modules.py        # Foundation modules (6/6)
python test_qbittorrent_api.py  # qBittorrent API (5/5)
python test_rss_rules.py       # RSS rules (9/9)
python test_integration.py     # Integration (10/10)
```

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Author

**xAkai97**
