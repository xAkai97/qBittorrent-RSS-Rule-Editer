# TODO: qBittorrent RSS Rule Editor

## Project Status
✅ **Core Functionality Complete** - All main features working  
✅ **Modularization Complete** - Clean architecture with 100% extraction  
✅ **Test Coverage** - 129 tests passing (48 core + 21 edge cases + 15 GUI tests + 25 API error tests + 20 validation tests)

---

## Recently Completed
- [x] Preview format fixed (proper qBittorrent dictionary format)
- [x] Export produces clean qBittorrent-compatible JSON
- [x] Helper functions for title entry access (`get_display_title`, `get_rule_name`, etc.)
- [x] Centralized filtering logic in `src/utils.py`
- [x] Validation functions to prevent metadata pollution
- [x] Unit tests for filtering and helper functions
- [x] Code organization - PEP 8 import standards across all modules (2025-12-30)
- [x] RSS validation bug fix - proper tuple handling in RSSRule.validate() (2025-12-30)
- [x] App state null-safety - guards added to all convenience functions (2025-12-30)
- [x] MAL extension optimization - targeted event handlers and mutation observer (2025-12-30)
- [x] RSSRule converted to dataclass - cleaner code with automatic methods (2025-12-30)
- [x] Edge case tests for import/export - 21 comprehensive tests covering empty files, malformed JSON, invalid data, Unicode, large files, special paths, and round-trip consistency (2025-12-30)
- [x] GUI component tests - 15 tests using unittest.mock for tooltips, window setup, dialogs, file operations, AppState, and error handling (2025-12-30)
- [x] qBittorrent API error tests - 25 comprehensive tests for connection errors, authentication, API responses, network issues, rule operations, SSL configuration, parameter validation, and error propagation (2025-12-30)
- [x] Test warnings fixed - Removed all pytest return warnings (45 tests fixed) (2025-12-30)
- [x] Documentation improvements - Created ARCHITECTURE.md, DEVELOPER_GUIDE.md, and API_DOCUMENTATION.md (2025-12-31)
- [x] **Bulk Edit** - Edit multiple selected rules at once (category, save path, enabled status) with Ctrl+B shortcut and dialog with selective field updates (2025-12-31)
- [x] **Undo/Redo** - Ctrl+Z keyboard shortcut for undoing delete operations with original position restoration and undo count feedback (2025-12-31)
- [x] **Filesystem Validation** - User-selectable validation rules for Windows vs Linux/Unraid filesystem types with preference persistence (2025-12-31)
- [x] **Auto-Sanitization** - Automatic folder name sanitization when syncing from qBittorrent, removes invalid characters based on target filesystem (2025-12-31)
- [x] **Validation Indicators** - Visual error/warning indicators in treeview for titles with validation issues (red for errors, orange for warnings) (2025-12-31)
- [x] **Validation Tests** - Comprehensive test suite (20 tests) covering filesystem validation, sanitization, preferences, integration, and edge cases (2025-12-31)

---

## Short Term Improvements

### Code Quality
- [x] Add type hints to remaining functions in `gui/main_window.py`
- [x] Add docstrings to undocumented functions (all modules have complete documentation)
- [x] Consider using dataclasses for `RSSRule` instead of manual dict handling

### Testing
- [x] Add GUI tests using `unittest.mock` for Tkinter widgets
- [x] Add edge case tests for import/export operations
- [x] Add tests for qBittorrent API error handling

### User Experience
- [x] Add keyboard shortcuts (Ctrl+S save, Ctrl+O open, etc.)
- [x] Add drag-and-drop support for JSON file import
- [x] Add status bar with operation feedback (implemented)
- [x] Improve error messages with actionable suggestions (partially complete - main window errors improved)

---

## Feature Ideas

### High Priority
- [x] **Bulk Edit** - Edit multiple selected rules at once (category, save path, enabled)
- [x] **Search/Filter** - Filter rules by name, category, or enabled status
- [x] **Undo/Redo** - Basic undo for delete operations with Ctrl+Z

### Medium Priority
- [ ] **Rule Templates** - Save and apply common rule configurations
- [ ] **Export Formats** - Support for other torrent clients (Deluge, Transmission)
- [ ] **Backup/Restore** - One-click backup of all rules from qBittorrent

### Low Priority
- [ ] **Dark Mode** - Tkinter theme support
- [ ] **Localization** - Multi-language support
- [ ] **Auto-Update Check** - Notify when new version available

---

## Technical Debt

### Completed
- [x] Duplicate treeview code in `main_window.py` - extracted to helper method
- [x] Redundant inline imports - consolidated at module level
- [x] Inline `node.get('title')` patterns - replaced with `get_display_title()`
- [x] Error handling patterns - reviewed, already reasonably consistent

### Deferred (Low ROI)
- [ ] Extract sync logic from `main_window.py` - tightly coupled with UI callbacks, high effort/low benefit

### Nice to Have
- [ ] Replace `config.ini` with JSON for consistency
- [ ] Add logging configuration UI
- [ ] Add performance profiling for large rule sets

---

## Documentation

- [x] Add inline code examples in docstrings
- [x] Create CONTRIBUTING.md with development guidelines (DEVELOPER_GUIDE.md)
- [x] Add architecture diagram to README (ARCHITECTURE.md)
- [x] Document the browser extension integration workflow
- [x] Create comprehensive API documentation (API_DOCUMENTATION.md)
- [x] Create developer guide (DEVELOPER_GUIDE.md)

**Documentation Files Created:**
- `ARCHITECTURE.md` - System architecture, data flow, design patterns
- `DEVELOPER_GUIDE.md` - Setup, coding standards, testing guide
- `API_DOCUMENTATION.md` - Complete API reference with examples

---

## Notes

### Helper Functions Available (`src/utils.py`)
```python
# Title entry access
get_display_title(entry)          # Get display name safely
get_rule_name(entry)              # Get rule name safely
get_must_contain(entry)           # Get search pattern
create_title_entry(...)           # Create proper entry structure
find_entry_by_title(titles, name) # Find entry by title
is_duplicate_title(titles, name)  # Check for duplicates

# Filtering
strip_internal_fields(entry)              # Clean single entry
strip_internal_fields_from_titles(titles) # Clean entire structure

# Validation
validate_entry_structure(entry)           # Check for pollution
validate_entries_for_export(titles)       # Validate before export
sanitize_entry_for_export(entry)          # Aggressive cleanup
```

### Test Commands
```powershell
# Run all tests at once
python run_tests.py               # All 48 tests

# Run individual test files
python tests/test_filtering.py    # 18 tests - helpers & filtering
python tests/test_modules.py      # 6 tests - foundation
python tests/test_qbittorrent_api.py  # 5 tests - API
python tests/test_rss_rules.py    # 9 tests - RSS rules
python tests/test_integration.py  # 10 tests - integration
```

---

**Last Updated:** 2025-12-30
