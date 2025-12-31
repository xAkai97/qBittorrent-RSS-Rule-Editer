# API Documentation

Complete API reference for all modules in the qBittorrent RSS Rule Editor.

## Table of Contents
- [Constants Module](#constants-module)
- [Configuration Module](#configuration-module)
- [Cache Module](#cache-module)
- [Utilities Module](#utilities-module)
- [RSS Rules Module](#rss-rules-module)
- [qBittorrent API Module](#qbittorrent-api-module)
- [SubsPlease API Module](#subsplease-api-module)
- [GUI Module](#gui-module)

---

## Constants Module

**Location:** `src/constants.py`

### Exceptions

#### `QBittorrentError`
Raised when qBittorrent connection or API operations fail.

```python
try:
    client.connect()
except QBittorrentError as e:
    print(f"Connection failed: {e}")
```

#### `ConfigError`
Raised when configuration is invalid or missing.

```python
try:
    load_config()
except ConfigError as e:
    print(f"Config error: {e}")
```

#### `ValidationError`
Raised when data validation fails.

```python
try:
    validate_rule(rule)
except ValidationError as e:
    print(f"Invalid rule: {e}")
```

### Constants

```python
# Application
APP_NAME = "qBittorrent RSS Rule Editor"
APP_VERSION = "2.0.0"

# API Defaults
DEFAULT_TIMEOUT = 10
QBT_AUTH_LOGIN = "/api/v2/auth/login"
QBT_RULES_PATH = "/api/v2/rss/rules"

# Cache
CACHE_TTL_DAYS = 30
CACHE_FILE = "seasonal_cache.json"
```

---

## Configuration Module

**Location:** `src/config.py`

### Functions

#### `load_config() -> Config`
Load configuration from config.ini file.

```python
from src.config import load_config

config = load_config()
host = config.qbt_host
port = config.qbt_port
```

#### `save_config(config: Config) -> None`
Save configuration to config.ini file.

```python
from src.config import save_config, Config

config = Config(
    qbt_protocol="https",
    qbt_host="qbittorrent.example.com",
    qbt_port="8080",
    qbt_username="admin",
    qbt_password="password"
)
save_config(config)
```

### Config Object

```python
@dataclass
class Config:
    # qBittorrent Connection
    qbt_protocol: str = "http"
    qbt_host: str = "localhost"
    qbt_port: str = "8080"
    qbt_username: str = ""
    qbt_password: str = ""
    qbt_verify_ssl: bool = False
    qbt_ca_cert: str = ""
    
    # Application Settings
    default_save_path: str = "/downloads"
    theme: str = "light"
    window_geometry: str = ""
```

---

## Cache Module

**Location:** `src/cache.py`

### Functions

#### `load_cache(key: str) -> Optional[Dict]`
Load cached data by key.

```python
from src.cache import load_cache

anime_data = load_cache("subsplease_seasonal")
if anime_data:
    print(f"Found {len(anime_data)} cached anime")
```

#### `save_cache(key: str, data: Dict, ttl_days: int = 30) -> None`
Save data to cache with expiration.

```python
from src.cache import save_cache

anime_list = {"anime1": {...}, "anime2": {...}}
save_cache("subsplease_seasonal", anime_list, ttl_days=30)
```

#### `clear_cache(key: Optional[str] = None) -> None`
Clear specific cache or all cache.

```python
from src.cache import clear_cache

# Clear specific key
clear_cache("subsplease_seasonal")

# Clear all cache
clear_cache()
```

#### `is_cache_valid(key: str) -> bool`
Check if cache exists and hasn't expired.

```python
from src.cache import is_cache_valid

if is_cache_valid("subsplease_seasonal"):
    anime_data = load_cache("subsplease_seasonal")
else:
    # Fetch fresh data from API
    anime_data = fetch_from_api()
```

---

## Utilities Module

**Location:** `src/utils.py`

### String Utilities

#### `sanitize_title(title: str) -> str`
Remove special characters and normalize whitespace.

```python
from src.utils import sanitize_title

dirty_title = "  Attack  on  Titan  [2024]  "
clean_title = sanitize_title(dirty_title)
# Result: "Attack on Titan 2024"
```

#### `normalize_path(path: str) -> str`
Normalize file path separators for current OS.

```python
from src.utils import normalize_path

path = normalize_path("anime/2024/winter")
# Windows: "anime\2024\winter"
# Linux/Mac: "anime/2024/winter"
```

### List/Dict Utilities

#### `flatten_dict(d: Dict, parent_key: str = "") -> Dict`
Flatten nested dictionary.

```python
from src.utils import flatten_dict

nested = {"a": {"b": 1, "c": 2}, "d": 3}
flat = flatten_dict(nested)
# Result: {"a_b": 1, "a_c": 2, "d": 3}
```

#### `merge_dicts(dict1: Dict, dict2: Dict) -> Dict`
Recursively merge two dictionaries.

```python
from src.utils import merge_dicts

d1 = {"a": 1, "b": {"c": 2}}
d2 = {"b": {"d": 3}, "e": 4}
merged = merge_dicts(d1, d2)
# Result: {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}
```

### Validation Utilities

#### `is_valid_url(url: str) -> bool`
Validate URL format.

```python
from src.utils import is_valid_url

valid = is_valid_url("http://example.com:8080")  # True
invalid = is_valid_url("not a url")  # False
```

#### `is_valid_json(text: str) -> bool`
Check if text is valid JSON.

```python
from src.utils import is_valid_json

valid = is_valid_json('{"key": "value"}')  # True
invalid = is_valid_json("{invalid}")  # False
```

---

## RSS Rules Module

**Location:** `src/rss_rules.py`

### RSSRule Dataclass

```python
from dataclasses import dataclass
from src.rss_rules import RSSRule

@dataclass
class RSSRule:
    """Represents a single qBittorrent RSS rule."""
    
    ruleName: str          # Rule identifier
    mustContain: str       # Required keywords (regex supported)
    mustNotContain: str    # Excluded keywords
    useRegex: bool         # Enable regex matching
    enabled: bool          # Rule active
    savePath: str          # Download destination
    addPaused: bool        # Add torrents paused
    assignCategory: str    # Torrent category
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API."""
    
    @classmethod
    def from_dict(cls, data: Dict) -> "RSSRule":
        """Create from dictionary (from API)."""
    
    def validate(self) -> bool:
        """Validate rule fields."""
```

### Functions

#### `from_titles(titles: List[str], base_path: str = "/downloads") -> List[RSSRule]`
Generate rules from anime titles.

```python
from src.rss_rules import from_titles

titles = ["Attack on Titan", "Demon Slayer"]
rules = from_titles(titles, base_path="/anime")
# Generates rules with sanitized titles and save paths
```

#### `export_rules_to_json(rules: List[RSSRule], filepath: str) -> None`
Export rules to JSON file.

```python
from src.rss_rules import export_rules_to_json

rules = [rule1, rule2]
export_rules_to_json(rules, "exported_rules.json")
```

#### `import_rules_from_json(filepath: str) -> List[RSSRule]`
Import rules from JSON file.

```python
from src.rss_rules import import_rules_from_json

rules = import_rules_from_json("exported_rules.json")
print(f"Imported {len(rules)} rules")
```

---

## qBittorrent API Module

**Location:** `src/qbittorrent_api.py`

### QBittorrentClient Class

#### Initialization

```python
from src.qbittorrent_api import QBittorrentClient

client = QBittorrentClient(
    protocol="http",
    host="localhost",
    port="8080",
    username="admin",
    password="password",
    verify_ssl=False,
    ca_cert=None,
    timeout=10
)
```

#### Connection Management

##### `connect() -> bool`
Establish connection to qBittorrent.

```python
try:
    success = client.connect()
    if success:
        print("Connected to qBittorrent")
except QBittorrentError as e:
    print(f"Connection failed: {e}")
```

##### `close() -> None`
Close the connection.

```python
client.close()
```

#### Rule Operations

##### `get_rules() -> Dict[str, Dict]`
Fetch all RSS rules from qBittorrent.

```python
try:
    rules = client.get_rules()
    for rule_name, rule_data in rules.items():
        print(f"Rule: {rule_name}")
except QBittorrentError as e:
    print(f"Failed to fetch rules: {e}")
```

##### `set_rule(rule_data: Dict) -> bool`
Create or update an RSS rule.

```python
rule = {
    "ruleName": "New Rule",
    "mustContain": "720p",
    "savePath": "/downloads/anime"
}

try:
    success = client.set_rule(rule)
    if success:
        print("Rule created successfully")
except QBittorrentError as e:
    print(f"Failed to set rule: {e}")
```

##### `remove_rule(rule_name: str) -> bool`
Delete an RSS rule.

```python
try:
    success = client.remove_rule("Old Rule")
    if success:
        print("Rule removed")
except QBittorrentError as e:
    print(f"Failed to remove rule: {e}")
```

#### Category Operations

##### `get_categories() -> Dict[str, Dict]`
Fetch available torrent categories.

```python
try:
    categories = client.get_categories()
    for cat_name, cat_info in categories.items():
        print(f"Category: {cat_name}")
except QBittorrentError as e:
    print(f"Failed to fetch categories: {e}")
```

#### RSS Feed Operations

##### `get_feeds() -> Dict[str, Dict]`
Fetch RSS feeds.

```python
try:
    feeds = client.get_feeds()
    for feed_url, feed_data in feeds.items():
        print(f"Feed: {feed_url}")
except QBittorrentError as e:
    print(f"Failed to fetch feeds: {e}")
```

##### `get_version() -> str`
Get qBittorrent version.

```python
try:
    version = client.get_version()
    print(f"qBittorrent version: {version}")
except QBittorrentError as e:
    print(f"Failed to get version: {e}")
```

### Module Functions

#### `ping_qbittorrent(...) -> Tuple[bool, str]`
Test connection to qBittorrent.

```python
from src.qbittorrent_api import ping_qbittorrent

success, message = ping_qbittorrent(
    protocol="http",
    host="localhost",
    port="8080",
    username="admin",
    password="password"
)

if success:
    print(f"Ping successful: {message}")
else:
    print(f"Ping failed: {message}")
```

#### `fetch_rules(...) -> Tuple[bool, Union[str, Dict]]`
Fetch rules with error handling.

```python
from src.qbittorrent_api import fetch_rules

success, result = fetch_rules(
    protocol="http",
    host="localhost",
    port="8080",
    username="admin",
    password="password"
)

if success:
    rules = result
    print(f"Fetched {len(rules)} rules")
else:
    error_msg = result
    print(f"Error: {error_msg}")
```

#### `fetch_categories(...) -> Tuple[bool, Union[str, Dict]]`
Fetch categories with error handling.

```python
from src.qbittorrent_api import fetch_categories

success, result = fetch_categories(
    protocol="http",
    host="localhost",
    port="8080",
    username="admin",
    password="password"
)

if success:
    categories = result
else:
    error_msg = result
```

---

## SubsPlease API Module

**Location:** `src/subsplease_api.py`

### SubsPleaseAPI Class

#### Functions

##### `fetch_seasonal_anime() -> Dict[str, Dict]`
Fetch current seasonal anime from SubsPlease.

```python
from src.subsplease_api import SubsPleaseAPI

api = SubsPleaseAPI()
try:
    anime = api.fetch_seasonal_anime()
    for title, info in anime.items():
        print(f"{title}: {info}")
except Exception as e:
    print(f"Failed to fetch: {e}")
```

##### `is_anime_valid(title: str) -> bool`
Check if title matches known anime.

```python
from src.subsplease_api import SubsPleaseAPI

api = SubsPleaseAPI()
valid = api.is_anime_valid("Attack on Titan")  # True
invalid = api.is_anime_valid("Random Text")  # False
```

---

## GUI Module

**Location:** `src/gui/`

### Main Window

**File:** `gui/main_window.py`

#### `setup_gui() -> None`
Initialize and start the GUI.

```python
from src.gui import setup_gui

setup_gui()  # Blocks until user closes window
```

### App State

**File:** `gui/app_state.py`

#### `AppState` (Singleton)

```python
from src.gui.app_state import AppState

# Get singleton instance
state = AppState()

# Access properties
state.root              # Tkinter root window
state.treeview          # Rule treeview widget
state.status_var        # Status bar StringVar
state.selected_rules    # Currently selected rules

# Set properties
state.root = tk.Tk()
state.set_status("Connected to qBittorrent")
```

### Dialogs

**File:** `gui/dialogs.py`

#### `open_settings_window(root: tk.Tk) -> None`
Show settings dialog.

```python
from src.gui.dialogs import open_settings_window
import tkinter as tk

root = tk.Tk()
open_settings_window(root)
```

#### `confirm_dialog(title: str, message: str) -> bool`
Show confirmation dialog.

```python
from src.gui.dialogs import confirm_dialog

if confirm_dialog("Delete Rule", "Remove this rule permanently?"):
    # User confirmed
    delete_rule()
```

#### `error_dialog(title: str, message: str) -> None`
Show error dialog.

```python
from src.gui.dialogs import error_dialog

error_dialog("Connection Error", "Failed to connect to qBittorrent")
```

### File Operations

**File:** `gui/file_operations.py`

#### `import_from_file(root: tk.Tk) -> Optional[List[RSSRule]]`
Show file dialog and import rules.

```python
from src.gui.file_operations import import_from_file
import tkinter as tk

root = tk.Tk()
rules = import_from_file(root)
if rules:
    print(f"Imported {len(rules)} rules")
```

#### `export_to_file(root: tk.Tk, rules: List[RSSRule]) -> bool`
Show file dialog and export rules.

```python
from src.gui.file_operations import export_to_file
import tkinter as tk

root = tk.Tk()
success = export_to_file(root, selected_rules)
```

### Widgets

**File:** `gui/widgets.py`

Custom reusable widgets for the GUI.

#### `create_button(parent: tk.Widget, text: str, command: Callable) -> tk.Button`
Create styled button.

#### `create_entry(parent: tk.Widget, label: str, default: str = "") -> Tuple[tk.Entry, tk.Label]`
Create labeled entry field.

#### `create_scrollbar(parent: tk.Widget, widget: tk.Widget) -> tk.Scrollbar`
Create linked scrollbar.

---

## Usage Examples

### Complete Workflow Example

```python
from src.config import load_config
from src.qbittorrent_api import QBittorrentClient
from src.rss_rules import from_titles, export_rules_to_json

# 1. Load configuration
config = load_config()

# 2. Create client and connect
client = QBittorrentClient(
    protocol=config.qbt_protocol,
    host=config.qbt_host,
    port=config.qbt_port,
    username=config.qbt_username,
    password=config.qbt_password,
    verify_ssl=config.qbt_verify_ssl,
    ca_cert=config.qbt_ca_cert if config.qbt_ca_cert else None
)

try:
    client.connect()
    print("Connected successfully")
    
    # 3. Generate rules from titles
    titles = ["Attack on Titan", "Demon Slayer", "Jujutsu Kaisen"]
    rules = from_titles(titles, base_path=config.default_save_path)
    
    # 4. Export to file
    export_rules_to_json(rules, "my_rules.json")
    print(f"Exported {len(rules)} rules")
    
    # 5. Get existing rules from qBittorrent
    existing_rules = client.get_rules()
    print(f"Found {len(existing_rules)} existing rules")
    
finally:
    client.close()
```

### Error Handling Example

```python
from src.qbittorrent_api import QBittorrentClient
from src.constants import QBittorrentError

client = QBittorrentClient(...)

try:
    client.connect()
    rules = client.get_rules()
    
except QBittorrentError as e:
    print(f"qBittorrent error: {e}")
    # Handle connection error
    
except TimeoutError as e:
    print(f"Request timeout: {e}")
    # Handle timeout
    
except Exception as e:
    print(f"Unexpected error: {e}")
    # Handle unexpected errors
    
finally:
    client.close()
```

---

## Related Resources

- [ARCHITECTURE.md](ARCHITECTURE.md) - System design and patterns
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) - Development guidelines and practices
- [README.md](README.md) - User-facing documentation
