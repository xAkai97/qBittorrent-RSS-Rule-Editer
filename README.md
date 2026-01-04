# qBittorrent RSS Rule Editor

A cross-platform Tkinter GUI for generating and synchronizing qBittorrent RSS download rules for seasonal anime. Supports offline JSON export and optional online sync to qBittorrent WebUI.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-129%20passing-brightgreen.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Features

- **🎯 Smart Rule Generation** - Create qBittorrent RSS download rules with seasonal paths
- **📤 Dual Mode Operation** - Export JSON files or sync directly to qBittorrent WebUI
- **� Sonarr Integration** - Bulk-add series to Sonarr with automatic matching
- **🔄 SubsPlease Integration** - Fetch current seasonal anime titles with local caching
- **📋 MAL Import** - Import anime lists from MyAnimeList via browser extension
- **🔍 Search & Filter** - Quickly find rules by title, category, or save path
- **✏️ Bulk Edit** - Edit multiple rules simultaneously (category, save path, enabled)- **✨ Auto-Sanitization** - Automatically fixes invalid folder names based on target filesystem
- **⚠️ Validation Indicators** - Visual warnings for titles with validation issues in treeview
- **💾 Filesystem Selection** - Choose between Windows and Linux/Unix/Unraid validation rules- **📋 Rule Templates** - Save and apply common rule configurations (5 built-in templates)
- **↩️ Undo** - Restore deleted rules with Ctrl+Z
- **⌨️ Keyboard Shortcuts** - Ctrl+S, Ctrl+O, Ctrl+F, Ctrl+B, Ctrl+T, Ctrl+Shift+S, and more
- **📂 Drag & Drop** - Drop JSON files directly onto the window to import

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
python main.py
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open/Import JSON file |
| `Ctrl+S` | Generate/Sync rules |
| `Ctrl+Shift+S` | Export to Sonarr |
| `Ctrl+E` | Export selected rules |
| `Ctrl+Shift+E` | Export all rules |
| `Ctrl+B` | Bulk edit selected rules |
| `Ctrl+Z` | Undo last delete |
| `Ctrl+T` | Save rule as template |
| `Ctrl+Shift+T` | Apply template to rule |
| `Ctrl+F` | Focus search filter |
| `Ctrl+Shift+C` | Clear all titles |
| `Ctrl+Q` | Quit |
| `F5` | Refresh display |
| `Space` | Toggle enable/disable |

## Project Structure

Fully modular architecture with clean separation of concerns:

```
src/
├── constants.py       # Constants & exceptions
├── config.py          # Configuration management
├── cache.py           # Data persistence
├── utils.py           # Utility & helper functions
├── subsplease_api.py  # SubsPlease API integration
├── qbittorrent_api.py # qBittorrent API client
├── rss_rules.py       # RSS rule management
└── gui/               # GUI modules
    ├── app_state.py      - Centralized state management
    ├── helpers.py        - GUI utility functions
    ├── widgets.py        - Reusable components
    ├── dialogs.py        - Dialog windows
    ├── file_operations.py - Import/export logic
    └── main_window.py    - Main window & setup

tests/
├── test_modules.py               # Foundation tests (6)
├── test_qbittorrent_api.py       # API tests (5)
├── test_qbittorrent_api_errors.py # API error tests (25)
├── test_rss_rules.py             # RSS rules tests (9)
├── test_integration.py           # Integration tests (10)
├── test_filtering.py             # Helper & filter tests (18)
├── test_gui_components.py        # GUI component tests (15)
├── test_import_export_edge_cases.py # Edge case tests (21)
└── test_validation.py            # Validation & sanitization tests (20)
```

**Total Test Coverage:** 129 tests across 9 test files

## Configuration

On first run, open **Settings** (Ctrl+,) and configure your qBittorrent WebUI details.

### Connection Modes

- **Online Mode** - Sync rules directly to qBittorrent WebUI
- **Offline Mode** - Generate JSON file for manual import

### Filesystem Validation

Configure your target filesystem in Settings for proper folder name validation:

- **🐧 Linux/Unix/Unraid (Default)** - Allows colons and quotes, blocks forward slashes
- **🪟 Windows** - Strict validation: blocks colons, quotes, trailing dots, and reserved names

**⚠️ Note:** Linux folders with colons (`:`) will appear without colons when accessed from Windows via SMB shares.

### Auto-Sanitization

Enable automatic folder name sanitization in Settings (enabled by default):
- Automatically fixes invalid characters when syncing from qBittorrent
- Example: `"Title: Name"` → `"Title Name"`
- Works with both Windows and Linux validation modes

### Validation Indicators

Titles with validation issues display visual warnings in the treeview:
- **❌ Red highlight** - Critical validation errors (invalid folder names)
- **⚠️ Orange highlight** - Warnings (empty titles, etc.)

### SSL/TLS Support

For self-signed HTTPS certificates:
- Provide a CA certificate path in Settings, OR
- Uncheck "Verify SSL" (not recommended for production)

## Dependencies

### Required
```
requests
qbittorrent-api
configparser
Pillow
```

### Optional
```
tkinterdnd2  # Enables drag-and-drop file import
```

Install optional dependency:
```powershell
pip install tkinterdnd2
```

## SubsPlease API Integration

Fetches current anime titles from SubsPlease's public API for RSS feed title matching.

- **Caching:** Results cached locally for 30 days
- **Rate Limiting:** Automatic through caching mechanism
- **Optional:** The tool works fine without this feature

## MAL Multi-Select Export Integration

Import anime lists from MyAnimeList using the companion browser extension.

### Extension Repository
🔗 https://github.com/xAkai97/mal-multi-select-export

### Usage
1. Install the browser extension
2. Select anime on MyAnimeList seasonal pages
3. Export as JSON or copy to clipboard
4. Import into RSS Rule Editor via **Import > Paste from Clipboard**

## Running Tests

```powershell
# Run all 129 tests
python -m pytest -v

# Or using test runner script
python run_tests.py

# Run individual test suites
pytest tests/test_filtering.py       # 18 tests
pytest tests/test_import_export_edge_cases.py # 21 tests
pytest tests/test_validation.py      # 20 tests - NEW!
pytest tests/test_gui_components.py  # 15 tests
pytest tests/test_qbittorrent_api_errors.py # 25 tests
pytest tests/test_integration.py     # 10 tests
pytest tests/test_rss_rules.py       # 9 tests
pytest tests/test_qbittorrent_api.py # 5 tests
pytest tests/test_modules.py         # 6 tests
```

**Test Coverage Breakdown:**
- ✅ **Core Modules** (6 tests) - Module imports and structure
- ✅ **qBittorrent API** (5 tests) - Client and API operations
- ✅ **qBittorrent API Errors** (25 tests) - Error handling and edge cases
- ✅ **RSS Rules** (9 tests) - Rule management and serialization
- ✅ **Integration Tests** (10 tests) - End-to-end workflows
- ✅ **Data Filtering** (18 tests) - Utility functions and filters
- ✅ **GUI Components** (15 tests) - GUI widgets and dialogs (mocked)
- ✅ **Import/Export Edge Cases** (21 tests) - Malformed data, Unicode, large files
- ✅ **Validation & Sanitization** (20 tests) - Filesystem validation and auto-sanitization

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design, modules, data flow, and design patterns
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Development setup, coding standards, and testing guidelines
- **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** - Complete API reference for all modules

## Author

**xAkai97**
