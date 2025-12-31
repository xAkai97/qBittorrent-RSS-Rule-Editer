# Architecture Overview

## Project Structure

The qBittorrent RSS Rule Editor is built with a **fully modular architecture** featuring clean separation of concerns, making the codebase maintainable, testable, and extensible.

```
src/
├── constants.py           # Application constants and custom exceptions
├── config.py              # Configuration management and parsing
├── cache.py               # Persistent data storage (JSON-based)
├── utils.py               # Utility functions for common operations
├── subsplease_api.py      # SubsPlease API integration (seasonal anime data)
├── qbittorrent_api.py     # qBittorrent WebUI client and connection management
├── rss_rules.py           # RSS rule dataclass and business logic
└── gui/                   # GUI layer (Tkinter-based)
    ├── __init__.py        # GUI initialization and setup
    ├── app_state.py       # Centralized application state (singleton)
    ├── helpers.py         # GUI utility functions (colors, fonts, etc.)
    ├── widgets.py         # Reusable custom widgets
    ├── dialogs.py         # Dialog windows (settings, confirmations, etc.)
    ├── file_operations.py # Import/export functionality
    └── main_window.py     # Main application window and layout

tests/
├── test_modules.py               # Module import and structure tests
├── test_qbittorrent_api.py       # qBittorrent API integration tests
├── test_qbittorrent_api_errors.py # qBittorrent API error handling tests
├── test_rss_rules.py             # RSS rule management tests
├── test_integration.py           # End-to-end integration tests
├── test_filtering.py             # Data filtering and utility function tests
├── test_gui_components.py        # GUI component tests (mocked Tkinter)
└── test_import_export_edge_cases.py # Import/export edge case tests
```

## Core Modules

### Constants & Exceptions (`constants.py`)
- Centralized application constants (versions, API endpoints, timeouts)
- Custom exception classes for error handling
- RSS rule field definitions and validation

### Configuration Management (`config.py`)
- Persistent configuration file handling (config.ini)
- qBittorrent connection settings (host, port, credentials, SSL)
- Default configuration with user overrides

### Data Persistence (`cache.py`)
- JSON-based caching for seasonal anime data
- Cache invalidation (30-day TTL)
- Thread-safe file operations

### Utilities (`utils.py`)
- String manipulation (sanitization, normalization)
- List/dictionary operations
- Common filtering and validation functions

### API Integrations

#### SubsPlease API (`subsplease_api.py`)
- Fetch current seasonal anime titles
- Local caching to minimize API calls
- Graceful fallback when API is unavailable

#### qBittorrent API (`qbittorrent_api.py`)
- Dual connection mode: qbittorrent-api library (preferred) or requests fallback
- Client creation and lifecycle management
- Rule CRUD operations (get, set, remove)
- RSS feed management
- Category retrieval
- Comprehensive error handling and connection validation

### Business Logic (`rss_rules.py`)
- `RSSRule` dataclass: Immutable rule representation with validation
- Rule import/export (JSON serialization)
- Rule generation from anime titles
- Path building with seasonal context

## Data Flow

### Import Flow
```
User selects JSON file
    ↓
file_operations.py validates JSON structure
    ↓
rss_rules.py deserializes to RSSRule objects
    ↓
app_state.py stores in centralized state
    ↓
GUI refreshes to display imported rules
```

### Sync Flow
```
User clicks "Sync Rules"
    ↓
qbittorrent_api.py connects to WebUI
    ↓
Fetches existing rules and categories
    ↓
Compares with local rules
    ↓
Updates/adds new rules via API
    ↓
app_state.py updates local state
    ↓
GUI refreshes with sync status
```

### Export Flow
```
User selects "Export Rules"
    ↓
file_operations.py formats selected rules
    ↓
rss_rules.py serializes RSSRule to JSON
    ↓
User chooses save location
    ↓
File written with validation
    ↓
Confirmation dialog shown
```

## Design Patterns

### Singleton Pattern
- **Location:** `gui/app_state.py`
- **Purpose:** Centralized application state management
- **Benefits:** Single source of truth, prevents state inconsistencies
- **Implementation:** Lazy initialization with thread-safety

### Dataclass Pattern
- **Location:** `rss_rules.py` - `RSSRule` class
- **Purpose:** Immutable value objects for type safety
- **Benefits:** Automatic `__init__`, `__repr__`, `__eq__`, field validation
- **Features:** Post-init validation, JSON serialization support

### Factory Pattern
- **Location:** `rss_rules.py` - `from_titles()` class method
- **Purpose:** Create rules from anime titles with default values
- **Benefits:** Encapsulates complex rule creation logic

### Strategy Pattern
- **Location:** `qbittorrent_api.py` - Connection strategies
- **Purpose:** Support both qbittorrent-api library and requests fallback
- **Benefits:** Graceful degradation when library unavailable

### Observer Pattern
- **Location:** `gui/` - Tkinter variable tracing
- **Purpose:** React to configuration and state changes
- **Benefits:** Decoupled UI updates from business logic

## Error Handling Strategy

### Three-Tier Error Handling

1. **Application Layer** (`constants.py`)
   - `QBittorrentError` - Connection/API failures
   - `ConfigError` - Configuration issues
   - `ValidationError` - Data validation failures

2. **API Layer** (`qbittorrent_api.py`)
   - Catches network exceptions (timeouts, connection refused, SSL errors)
   - Wraps in `QBittorrentError` with context
   - Returns tuple `(success, data/message)` for graceful degradation

3. **GUI Layer** (`gui/dialogs.py`)
   - Displays user-friendly error messages
   - Provides recovery options
   - Logs detailed errors for debugging

## Testing Architecture

### Test Categories (109 Total Tests)

| Category | Count | Coverage |
|----------|-------|----------|
| Core Modules | 48 | Imports, module structure, basic functionality |
| Edge Cases | 21 | Empty files, malformed JSON, Unicode, large data |
| GUI Components | 15 | Widgets, dialogs, state management (mocked) |
| API Errors | 25 | Connection errors, auth failures, network issues |

### Mock-Based Testing Strategy
- No real network calls in tests
- No Tkinter initialization required (using unittest.mock)
- Isolated test units with controlled dependencies
- Fast execution (~15 seconds for all 109 tests)

## Dependency Graph

```
main.py
├── src.gui (GUI initialization)
├── src.config (Configuration)
├── src.cache (Persistent storage)
├── src.rss_rules (Business logic)
├── src.qbittorrent_api (WebUI connection)
└── src.subsplease_api (Seasonal data)

GUI Layer
├── gui.main_window (Main UI)
├── gui.app_state (Centralized state)
├── gui.dialogs (Modal windows)
├── gui.file_operations (Import/export)
├── gui.widgets (Custom components)
└── gui.helpers (UI utilities)

Core Modules
├── constants (Constants & exceptions)
├── config (Settings management)
├── cache (Data persistence)
└── utils (Helper functions)
```

## Configuration & State Management

### Configuration Hierarchy
1. **Default values** in code (src/constants.py)
2. **User config file** (config.ini) - persistent overrides
3. **Runtime settings** (accessed via src/config.py)

### State Management
- **Global State:** `AppState` singleton in `gui/app_state.py`
- **Cached State:** Seasonal anime data in `cache.py`
- **Persistent State:** Configuration file (config.ini)
- **Session State:** Current rule selections, UI state

## Performance Considerations

### Caching Strategy
- SubsPlease data cached for 30 days locally
- Reduces API calls and improves startup time
- Cache invalidation on version updates

### GUI Optimization
- Lazy loading of dialogs
- Efficient treeview rendering with virtual scrolling
- Debounced search/filter operations

### Connection Management
- Connection pooling via requests.Session
- Configurable timeouts (default 10s)
- Automatic retry logic for transient failures

## Security Considerations

### SSL/TLS Support
- Optional certificate verification
- Custom CA certificate support
- Self-signed certificate handling

### Credential Management
- Credentials stored in config.ini (user responsibility for protection)
- No logging of sensitive credentials
- Secure transmission via HTTPS when available

### Input Validation
- JSON schema validation on import
- Title sanitization before rule creation
- Rule parameter validation before API calls

## Extension Points

### Adding New Data Sources
1. Create new API module (e.g., `anilist_api.py`)
2. Implement title fetching and caching
3. Integrate in `gui/dialogs.py`

### Adding New Export Formats
1. Extend `file_operations.py` with new format handler
2. Add format selection in export dialog
3. Implement serialization in `rss_rules.py`

### Customizing GUI
1. Extend widgets in `gui/widgets.py`
2. Add new dialogs in `gui/dialogs.py`
3. Update layout in `gui/main_window.py`

## Future Improvements

- [ ] Async/await for non-blocking API calls
- [ ] Database backend for large rule sets
- [ ] CLI interface for headless operation
- [ ] Plugin system for custom rule generation
- [ ] Web-based UI as alternative to Tkinter
- [ ] Rule scheduling and automation
