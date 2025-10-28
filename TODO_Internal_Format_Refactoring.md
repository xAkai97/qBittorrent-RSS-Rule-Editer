# TODO: Internal Format Refactoring Analysis

## Current Status
✅ **Preview format is now fixed** - Shows proper qBittorrent dictionary format  
✅ **Export works correctly** - Produces clean qBittorrent-compatible JSON  
⚠️ **Internal format has mixed concerns** - qBittorrent fields + tracking fields in same objects

---

## Approach 1: Current Hybrid Format (Status Quo)

### Structure
```python
config.ALL_TITLES = {
    'existing': [
        {
            # qBittorrent fields
            'mustContain': 'Title',
            'savePath': 'path/to/save',
            'assignedCategory': 'Category',
            'enabled': True,
            'affectedFeeds': [...],
            'torrentParams': {...},
            
            # Internal tracking fields (mixed in)
            'node': {'title': 'Display Title'},
            'ruleName': 'Title'
        }
    ]
}
```

### Pros
- ✅ Already implemented and working
- ✅ Simple to access - everything in one object
- ✅ No refactoring needed
- ✅ Easy to pass around - single data structure
- ✅ Backward compatible with existing cache files

### Cons
- ❌ Requires cleaning step before export/preview
- ❌ Mixed concerns - tracking data pollutes rule data
- ❌ Extra fields sent to `RSSRule.from_dict()` (though ignored)
- ❌ Potential confusion about which fields are "real"
- ❌ Need to remember to filter `node` and `ruleName` everywhere

### Performance
- **Memory**: Minimal extra overhead per entry (~50-100 bytes)
- **CPU**: Requires filtering loop for each export/preview operation
- **Code Complexity**: Medium - need to remember filtering

---

## Approach 2: Separated Metadata Format (Cleaner)

### Structure
```python
config.ALL_TITLES = {
    'existing': [
        {
            # ONLY qBittorrent fields (pure data)
            'mustContain': 'Title',
            'savePath': 'path/to/save',
            'assignedCategory': 'Category',
            'enabled': True,
            'affectedFeeds': [...],
            'torrentParams': {...}
        }
    ]
}

# Separate tracking/metadata dictionary
config.TITLE_METADATA = {
    'Title': {
        'display_name': 'Title',
        'original_name': 'Spring - Title',
        'import_source': 'qBittorrent',
        'import_date': '2025-10-28',
        'last_modified': '2025-10-28',
        'internal_id': 'uuid-here'
    }
}
```

### Pros
- ✅ Clean separation of concerns
- ✅ No filtering needed for export/preview
- ✅ Pure qBittorrent data in main structure
- ✅ Easier to understand what gets synced
- ✅ Can add more metadata without polluting rules
- ✅ Better for future extensions (tags, notes, history)

### Cons
- ❌ Requires significant refactoring
- ❌ Two data structures to maintain in sync
- ❌ More complex lookups (need to check both structures)
- ❌ Cache file format changes (migration needed)
- ❌ All import/sync/duplicate detection code needs updates

### Performance
- **Memory**: Similar total memory (data just organized differently)
- **CPU**: Faster export (no filtering), but slower lookups (two structures)
- **Code Complexity**: Higher initially (refactoring), cleaner long-term

---

## Refactoring Work Required for Approach 2

### Files to Modify
1. **src/config.py**
   - Add `TITLE_METADATA` dict
   - Add helper functions: `get_metadata()`, `set_metadata()`, `link_title_metadata()`

2. **src/cache.py**
   - Save/load TITLE_METADATA separately or embedded
   - Migration function for old cache format

3. **src/gui/file_operations.py**
   - `import_titles_from_file()` - Create metadata entries
   - `import_titles_from_clipboard()` - Create metadata entries
   - `update_treeview_with_titles()` - Look up display names from metadata
   - All duplicate detection code - Check metadata

4. **src/gui/main_window.py**
   - `_sync_online_worker()` - Create metadata entries
   - All display code - Use metadata for display names

5. **src/gui/dialogs.py**
   - Any code that accesses `node` or `ruleName`

### Estimated Work
- **Time**: 3-4 hours of careful refactoring
- **Testing**: 1-2 hours to verify all functionality
- **Risk**: Medium (lots of interconnected code)

---

## Recommendation

### For Now: **Keep Approach 1 (Current)**
**Reasons:**
1. ✅ It works correctly now
2. ✅ Preview and export are fixed
3. ✅ No breaking changes
4. ✅ Can revisit later if needed

### Future: **Consider Approach 2 If:**
- 📌 Adding more metadata fields (user notes, tags, history)
- 📌 Building import/export plugins
- 📌 Adding advanced filtering/search features
- 📌 Performance issues with current filtering
- 📌 Building a database backend

---

## Action Items

### Immediate (Now)
- [x] Fix preview format (DONE)
- [x] Clean export output (DONE)  
- [x] Remove redundant Enable/Disable buttons (DONE)
- [x] Fix Recent Files merge behavior (DONE)
- [x] Add default category/save path to imports (DONE)
- [x] Add season/year folders to prefixed imports (DONE)
- [ ] Document current format in code comments
- [ ] Add unit tests for filtering logic

### Short Term (1-2 weeks)
- [ ] Add helper functions for accessing titles safely
- [ ] Centralize filtering logic in one place
- [ ] Add validation to prevent accidental metadata pollution

### Long Term (Future Release)
- [ ] Evaluate if Approach 2 is needed based on feature roadmap
- [ ] If yes, create detailed migration plan
- [ ] Implement Approach 2 in feature branch
- [ ] Thorough testing before merge

---

## Notes
- Current filtering approach adds ~1-2ms overhead per export (negligible)
- Metadata in same object reduces lookup complexity
- Separation would be more "correct" from architecture perspective
- Pragmatic choice: **working > perfect** for now

---

**Decision**: Stick with current approach unless there's a compelling reason to refactor.

**Review Date**: 2025-11-28 (1 month)
