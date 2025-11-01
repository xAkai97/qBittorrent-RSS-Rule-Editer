"""
File operations for import/export functionality.

Handles importing titles from files/clipboard and exporting rules to JSON.
"""
import json
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Tuple, Any, Optional
import threading

from src.config import config
from src.utils import sanitize_folder_name, validate_folder_name
from src.rss_rules import RSSRule
from src.gui.app_state import get_app_state

logger = logging.getLogger(__name__)


def normalize_titles_structure(data: Any) -> Optional[Dict[str, List]]:
    """
    Normalize various title input formats into standard structure.
    
    Args:
        data: Input data (dict, list, or other format)
        
    Returns:
        Dictionary with 'anime' key containing list of titles, or None if invalid
    """
    try:
        if isinstance(data, dict):
            # If already has media types, return as-is
            if any(k in data for k in ['anime', 'manga', 'novel']):
                return data
            # If it's a qBittorrent rules export, extract rules
            if 'rules' in data or all(isinstance(v, dict) for v in data.values()):
                rules = data.get('rules', data)
                return {'anime': list(rules.values()) if isinstance(rules, dict) else rules}
            # Single level dict, wrap it
            return {'anime': [data]}
        elif isinstance(data, list):
            return {'anime': data}
        elif isinstance(data, str):
            return {'anime': [{'node': {'title': data}, 'mustContain': data}]}
        return None
    except Exception as e:
        logger.error(f"Error normalizing titles structure: {e}")
        return None


def import_titles_from_text(text: str) -> Optional[Dict[str, List]]:
    """
    Import and normalize titles from text (JSON or line-delimited).
    
    Args:
        text: Text content containing titles
        
    Returns:
        Normalized titles structure, or None if parsing fails
    """
    try:
        parsed = json.loads(text)
    except Exception:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        parsed = lines if lines else None
        if not parsed:
            return None
    
    return normalize_titles_structure(parsed)


def prefix_titles_with_season_year(
    all_titles: Dict[str, List],
    season: str,
    year: str
) -> None:
    """
    Prefix all titles with season and year (e.g., "Fall 2025 - Title").
    Also adds season/year folder to save paths.
    
    Example:
    - Display title: "Fall 2025 - Anime Title"
    - Save path: "/mnt/disk5/Anime/Fall 2025/Anime Title/"
    
    Modifies titles in-place.
    
    Args:
        all_titles: Dictionary of titles organized by media type
        season: Season name
        year: Year string
    """
    try:
        if not season or not year:
            return
        
        prefix = f"{season} {year} - "
        season_year_folder = f"{season} {year}"
        
        if not isinstance(all_titles, dict):
            return
        
        for media_type, items in all_titles.items():
            if not isinstance(items, list):
                continue
            
            for i, entry in enumerate(items):
                try:
                    if isinstance(entry, dict):
                        node = entry.get('node', {})
                        title = node.get('title') or entry.get('title') or ''
                        orig_title = str(title) if title else ''
                        
                        if orig_title and not orig_title.startswith(prefix):
                            # Add prefix to display title
                            node['title'] = prefix + orig_title
                            entry['node'] = node
                            if not entry.get('mustContain'):
                                entry['mustContain'] = orig_title
                            
                            # Add season/year folder to save path
                            current_save_path = entry.get('savePath', '') or ''
                            if current_save_path:
                                import os.path
                                # Add season/year folder and title folder
                                # Example: "/mnt/disk5/Anime" -> "/mnt/disk5/Anime/Fall 2025/Anime Title"
                                new_save_path = os.path.join(current_save_path, season_year_folder, orig_title).replace('\\', '/')
                                entry['savePath'] = new_save_path
                                
                                # Also update torrentParams if it exists
                                if 'torrentParams' not in entry:
                                    entry['torrentParams'] = {}
                                entry['torrentParams']['save_path'] = new_save_path
                                
                                logger.debug(f"Updated save path: '{current_save_path}' -> '{new_save_path}'")
                    else:
                        # String entry
                        title = str(entry)
                        if title and not title.startswith(prefix):
                            items[i] = {
                                'node': {'title': prefix + title},
                                'mustContain': title
                            }
                except Exception as e:
                    logger.error(f"Error prefixing title {i}: {e}")
                    continue
    except Exception as e:
        logger.error(f"Error in prefix_titles_with_season_year: {e}")


def collect_invalid_folder_titles(all_titles: Dict[str, List]) -> List[Tuple[str, str, str]]:
    """
    Collect all titles with invalid folder names.
    
    Args:
        all_titles: Dictionary of titles organized by media type
        
    Returns:
        List of tuples (display_name, raw_name, error_message) for invalid titles
    """
    invalid = []
    
    try:
        if not isinstance(all_titles, dict):
            return invalid
        
        for media_type, items in all_titles.items():
            if not isinstance(items, list):
                continue
            
            for entry in items:
                try:
                    raw = ''
                    display = ''
                    
                    if isinstance(entry, dict):
                        node = entry.get('node', {})
                        display = node.get('title') or entry.get('title') or ''
                        raw = entry.get('mustContain') or entry.get('title') or entry.get('name') or ''
                        
                        # Try to extract raw from display if needed
                        if display and isinstance(display, str) and ' - ' in display:
                            parts = display.split(' - ', 1)
                            if len(parts) == 2:
                                maybe_raw = parts[1]
                                if maybe_raw and not raw:
                                    raw = maybe_raw
                    else:
                        display = str(entry)
                        raw = display
                    
                    if not raw:
                        continue
                    
                    is_valid, reason = validate_folder_name(raw)
                    if not is_valid:
                        invalid.append((display or raw, raw, reason))
                        
                except Exception as e:
                    logger.error(f"Error checking folder name: {e}")
                    continue
    except Exception as e:
        logger.error(f"Error in collect_invalid_folder_titles: {e}")
    
    return invalid


def auto_sanitize_titles(all_titles: Dict[str, List]) -> None:
    """
    Automatically sanitize folder names in titles.
    
    Modifies titles in-place.
    
    Args:
        all_titles: Dictionary of titles organized by media type
    """
    try:
        if not isinstance(all_titles, dict):
            return
        
        for media_type, items in all_titles.items():
            if not isinstance(items, list):
                continue
            
            for entry in items:
                try:
                    if isinstance(entry, dict):
                        # Sanitize mustContain field
                        must_contain = entry.get('mustContain', '')
                        if must_contain:
                            entry['mustContain'] = sanitize_folder_name(must_contain)
                        
                        # Sanitize node title if it contains raw folder name
                        node = entry.get('node', {})
                        node_title = node.get('title', '')
                        if node_title and ' - ' in node_title:
                            parts = node_title.split(' - ', 1)
                            if len(parts) == 2:
                                prefix, raw = parts
                                node['title'] = f"{prefix} - {sanitize_folder_name(raw)}"
                                entry['node'] = node
                except Exception as e:
                    logger.error(f"Error sanitizing title: {e}")
                    continue
    except Exception as e:
        logger.error(f"Error in auto_sanitize_titles: {e}")


def populate_missing_rule_fields(
    all_titles: Dict[str, List],
    season: str,
    year: str
) -> None:
    """
    Populate missing fields in rule entries with defaults.
    
    Applies default category and save path from config to imported rules
    that don't already have them set.
    
    Modifies titles in-place.
    
    Args:
        all_titles: Dictionary of titles
        season: Season name
        year: Year string
    """
    logger.debug(f"populate_missing_rule_fields called with {sum(len(v) for v in all_titles.values() if isinstance(v, list))} total titles")
    try:
        from src.utils import get_current_anime_season
        from src.config import config
        
        # Use provided season/year or current if not specified
        if not season or not year:
            year_val, season_val = get_current_anime_season()
            season = season or season_val
            year = year or str(year_val)
        
        # Get defaults from config
        default_save_path = getattr(config, 'DEFAULT_SAVE_PATH', '') or ''
        default_category = getattr(config, 'DEFAULT_CATEGORY', '') or ''
        default_affected_feeds = getattr(config, 'DEFAULT_AFFECTED_FEEDS', []) or []
        
        for media_type, items in all_titles.items():
            if not isinstance(items, list):
                continue
            
            for entry in items:
                if not isinstance(entry, dict):
                    continue
                
                try:
                    # Ensure basic fields exist
                    if 'node' not in entry:
                        entry['node'] = {}
                    
                    if 'enabled' not in entry:
                        entry['enabled'] = True
                    
                    # Populate mustContain from node title if missing
                    if not entry.get('mustContain'):
                        node = entry.get('node', {})
                        title = node.get('title') or entry.get('title', '')
                        if title:
                            entry['mustContain'] = title
                    
                    # Apply default category if missing
                    if not entry.get('assignedCategory') and default_category:
                        entry['assignedCategory'] = default_category
                        logger.debug(f"Applied default category '{default_category}' to {entry.get('mustContain', 'unknown')}")
                    
                    # Apply default save path if missing
                    if not entry.get('savePath') and default_save_path:
                        entry['savePath'] = default_save_path
                        logger.debug(f"Applied default save path '{default_save_path}' to {entry.get('mustContain', 'unknown')}")
                    
                    # Apply default affected feeds if missing or empty
                    if not entry.get('affectedFeeds') and default_affected_feeds:
                        entry['affectedFeeds'] = default_affected_feeds.copy()
                        logger.debug(f"Applied default affected feeds to {entry.get('mustContain', 'unknown')}")
                    
                    # Ensure torrentParams exist and sync category/save_path
                    if 'torrentParams' not in entry:
                        entry['torrentParams'] = {}
                    
                    # Sync category and save_path to torrentParams
                    if entry.get('assignedCategory'):
                        entry['torrentParams']['category'] = entry['assignedCategory']
                    if entry.get('savePath'):
                        entry['torrentParams']['save_path'] = entry['savePath']
                            
                except Exception as e:
                    logger.error(f"Error populating fields: {e}")
                    continue
    except Exception as e:
        logger.error(f"Error in populate_missing_rule_fields: {e}")


def update_treeview_with_titles(all_titles: Dict[str, List]) -> None:
    """
    Update the main treeview widget with anime titles.
    
    Args:
        all_titles: Dictionary of titles organized by media type
    """
    app_state = get_app_state()
    treeview = app_state.treeview
    
    if not treeview:
        logger.warning("No treeview widget available")
        return
    
    # DEBUG: Check treeview configuration
    try:
        logger.debug(f"Treeview columns: {treeview['columns']}")
        logger.debug(f"Treeview displaycolumns: {treeview['displaycolumns']}")
        logger.debug(f"Treeview show: {treeview['show']}")
    except Exception as e:
        logger.error(f"Error checking treeview config: {e}")
    
    try:
        # Clear existing items
        items_before_clear = len(treeview.get_children())
        logger.debug(f"BEFORE CLEAR: Treeview has {items_before_clear} children")
        
        # Use the real ttk.Treeview.delete method to bypass any monkey-patching
        import tkinter.ttk as ttk
        for item in treeview.get_children():
            ttk.Treeview.delete(treeview, item)
        
        items_after_clear = len(treeview.get_children())
        logger.debug(f"AFTER CLEAR: Treeview has {items_after_clear} children (should be 0)")
        
        if items_after_clear != 0:
            logger.error(f"CLEAR FAILED! Still have {items_after_clear} items after clearing!")
        
        app_state.items.clear()
        logger.debug(f"Cleared {items_before_clear} items from treeview")
        
        # Add new items
        index = 0
        items_added = 0
        for media_type, items in (all_titles.items() if isinstance(all_titles, dict) else [('anime', all_titles)]):
            logger.debug(f"Processing media_type '{media_type}' with {len(items) if isinstance(items, list) else 'N/A'} items")
            for entry in items:
                try:
                    if isinstance(entry, dict):
                        node = entry.get('node', {})
                        title_text = node.get('title') or entry.get('title') or entry.get('name') or str(entry)
                        
                        # Extract category and save path
                        category = entry.get('assignedCategory') or entry.get('category') or ''
                        
                        # Get save path
                        save_path = entry.get('savePath') or entry.get('save_path') or ''
                        if not save_path:
                            tp = entry.get('torrentParams') or entry.get('torrent_params') or {}
                            save_path = tp.get('save_path') or tp.get('savePath') or ''
                        
                        save_path = str(save_path).replace('\\', '/') if save_path else ''
                        
                        # Get enabled status (default to True if not specified)
                        enabled = entry.get('enabled', True)
                        enabled_mark = '✓' if enabled else ''
                    else:
                        title_text = str(entry)
                        category = ''
                        save_path = ''
                        enabled_mark = '✓'  # Default enabled
                    
                    # Insert into treeview with enabled column first, then index
                    index += 1
                    items_added += 1
                    
                    before_insert_count = len(treeview.get_children())
                    logger.debug(f"Inserting item {index}: enabled={enabled_mark!r}, title={title_text!r}")
                    logger.debug(f"Insert values: {(enabled_mark, str(index), title_text, category, save_path)}")
                    
                    # Use the real ttk.Treeview.insert method to bypass any monkey-patching
                    import tkinter.ttk as ttk
                    try:
                        item_id = ttk.Treeview.insert(treeview, '', 'end', 
                                      values=(enabled_mark, str(index), title_text, category, save_path))
                        logger.debug(f"Insert returned item_id: {item_id!r}")
                    except Exception as insert_err:
                        logger.error(f"INSERT FAILED with error: {insert_err}", exc_info=True)
                        continue
                    
                    after_insert_count = len(treeview.get_children())
                    logger.debug(f"After insert: before={before_insert_count}, after={after_insert_count}")
                    
                    if after_insert_count != before_insert_count + 1:
                        logger.warning(f"Treeview insert anomaly: before={before_insert_count}, after={after_insert_count}, expected={before_insert_count + 1}")
                    
                    app_state.add_item(title_text, entry)
                    
                except Exception as e:
                    logger.error(f"Error adding title to treeview: {e}")
                    continue
        
        logger.debug(f"Added {items_added} items to treeview (final count: {len(treeview.get_children())})")
    except Exception as e:
        logger.error(f"Error updating treeview: {e}")


def import_titles_from_file(
    root: tk.Tk,
    status_var: tk.StringVar,
    season_var: tk.StringVar,
    year_var: tk.StringVar,
    prefix_imports: bool = False,
    path: Optional[str] = None
) -> bool:
    """
    Import titles from a JSON file and update application state.
    
    Args:
        root: Parent window
        status_var: Status bar variable
        season_var: Season selection variable
        year_var: Year selection variable
        prefix_imports: Whether to prefix titles with season/year
        path: Optional file path (opens dialog if None)
        
    Returns:
        True if import succeeded, False otherwise
    """
    if not path:
        path = filedialog.askopenfilename(
            title='Open JSON titles file',
            filetypes=[('JSON', '*.json'), ('All files', '*.*')]
        )
    
    if not path:
        return False
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        parsed = import_titles_from_text(text)
        if not parsed:
            messagebox.showerror('Import Error', 'Failed to parse JSON from selected file.')
            return False
        
        # Note: Prefix will be applied AFTER populate_missing_rule_fields
        # so that save paths are populated first
        
        # Check for invalid folder names
        try:
            auto_sanitize = config.get_pref('auto_sanitize_imports', True)
        except Exception:
            auto_sanitize = True
        
        invalid_titles = collect_invalid_folder_titles(parsed)
        
        if invalid_titles:
            if auto_sanitize:
                auto_sanitize_titles(parsed)
                invalid_titles = collect_invalid_folder_titles(parsed)
            
            if invalid_titles:
                # Create a more readable display with better formatting
                lines = []
                for display, raw, reason in invalid_titles:
                    # Truncate long titles for display
                    display_short = display if len(display) <= 60 else display[:57] + "..."
                    lines.append(f"• {display_short}\n  → {reason}")
                
                # Build message with better formatting
                message_parts = [
                    'The following imported titles contain characters or names\n'
                    'invalid for folder names:\n'
                ]
                
                # Show up to 8 items with better spacing
                display_count = min(8, len(lines))
                message_parts.append('\n'.join(lines[:display_count]))
                
                if len(lines) > display_count:
                    message_parts.append(f'\n... and {len(lines) - display_count} more titles with issues')
                
                message_parts.append('\n\nContinue import anyway?')
                
                if not messagebox.askyesno(
                    'Invalid folder names',
                    '\n'.join(message_parts),
                    icon='warning'
                ):
                    return False
        
        # Merge with existing titles
        try:
            current = getattr(config, 'ALL_TITLES', {}) or {}
            if not isinstance(current, dict):
                current = {}
            
            # Get existing title names, mustContain, and ruleNames to avoid duplicates
            existing_titles = set()
            existing_must_contain = set()
            existing_rule_names = set()
            
            for k, lst in current.items():
                if not isinstance(lst, list):
                    continue
                for it in lst:
                    try:
                        if isinstance(it, dict):
                            t = (it.get('node') or {}).get('title') or it.get('ruleName') or it.get('name')
                            if t:
                                existing_titles.add(str(t))
                            # Also track mustContain and ruleName
                            must = it.get('mustContain')
                            if must:
                                existing_must_contain.add(str(must))
                            rule_name = it.get('ruleName') or it.get('name')
                            if rule_name:
                                existing_rule_names.add(str(rule_name))
                        else:
                            t = str(it)
                            existing_titles.add(t)
                    except Exception:
                        pass
            
            # Merge new titles, skipping duplicates
            # Track newly added items for prefix application
            new_items = {media_type: [] for media_type in parsed.keys() if isinstance(parsed.get(media_type), list)}
            new_count = 0
            
            for media_type, items in parsed.items():
                if not isinstance(items, list):
                    continue
                if media_type not in current:
                    current[media_type] = []
                
                for item in items:
                    try:
                        if isinstance(item, dict):
                            title = (item.get('node') or {}).get('title') or item.get('ruleName') or item.get('name')
                            must = item.get('mustContain')
                            rule_name = item.get('ruleName') or item.get('name')
                        else:
                            # Convert string items to proper dict format
                            title = str(item)
                            must = title
                            rule_name = title
                            # Convert to dict format
                            item = {'node': {'title': title}, 'mustContain': must, 'ruleName': rule_name}
                        
                        key = str(title) if title else None
                    except Exception:
                        key = None
                        must = None
                        rule_name = None
                    
                    # Check if it's a duplicate by title, mustContain, or ruleName
                    is_duplicate = False
                    if key and key in existing_titles:
                        is_duplicate = True
                    elif must and str(must) in existing_must_contain:
                        is_duplicate = True
                    elif rule_name and str(rule_name) in existing_rule_names:
                        is_duplicate = True
                    
                    if not is_duplicate:
                        current[media_type].append(item)
                        new_items[media_type].append(item)  # Track new items
                        if key:
                            existing_titles.add(key)
                        if must:
                            existing_must_contain.add(str(must))
                        if rule_name:
                            existing_rule_names.add(str(rule_name))
                        new_count += 1
            
            config.ALL_TITLES = current
            total_imported = sum(len(v) for v in parsed.values() if isinstance(v, list))
            duplicates = total_imported - new_count
            
            # Debug logging
            total_in_all_titles = sum(len(v) for v in current.values() if isinstance(v, list))
            logger.info(f"Import merge complete: {new_count} new, {duplicates} duplicates, total in ALL_TITLES: {total_in_all_titles}")
            
            status_msg = f'Imported {new_count} new titles from file.'
            if duplicates > 0:
                status_msg += f' ({duplicates} duplicates skipped)'
                
        except Exception as e:
            logger.error(f"Error merging titles: {e}")
            # Fallback to replace
            config.ALL_TITLES = parsed
            status_msg = f'Imported {sum(len(v) for v in parsed.values())} titles from file.'
        
        # Populate missing fields ONLY for newly imported items (not existing online rules)
        try:
            season = season_var.get()
            year = year_var.get()
            
            if 'new_items' in locals():
                # Only populate defaults for new items
                logger.debug(f"Populating fields for {sum(len(v) for v in new_items.values())} new items only")
                populate_missing_rule_fields(new_items, season, year)
                
                # Apply prefix ONLY to newly imported items
                if prefix_imports:
                    logger.debug(f"Applying prefix to {sum(len(v) for v in new_items.values())} new items only")
                    prefix_titles_with_season_year(new_items, season, year)
        except Exception as e:
            logger.error(f"Error populating fields: {e}")
        
        # Update UI
        total_titles = sum(len(v) for v in config.ALL_TITLES.values() if isinstance(v, list))
        logger.info(f"About to update treeview with {total_titles} total titles")
        logger.debug(f"ALL_TITLES keys: {list(config.ALL_TITLES.keys())}")
        for key, val in config.ALL_TITLES.items():
            if isinstance(val, list):
                logger.debug(f"  '{key}': {len(val)} items")
        
        update_treeview_with_titles(config.ALL_TITLES)
        
        # Debug: Check actual treeview count after update
        app_state = get_app_state()
        if app_state.treeview:
            treeview_count = len(app_state.treeview.get_children())
            logger.info(f"Treeview now has {treeview_count} visible items")
        
        status_var.set(status_msg)
        
        # Add to recent files
        try:
            from src.cache import save_recent_files
            recent = getattr(config, 'RECENT_FILES', []) or []
            if path not in recent:
                recent.insert(0, path)
                recent = recent[:10]  # Keep last 10
                config.RECENT_FILES = recent
                save_recent_files(recent)
        except Exception as e:
            logger.error(f"Error saving recent file: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error importing from file: {e}")
        messagebox.showerror('File Error', f'Error reading file: {e}')
        return False


def import_titles_from_clipboard(
    root: tk.Tk,
    status_var: tk.StringVar,
    season_var: tk.StringVar,
    year_var: tk.StringVar,
    prefix_imports: bool = False
) -> bool:
    """
    Import titles from clipboard text and update application state.
    
    Args:
        root: Parent window
        status_var: Status bar variable
        season_var: Season selection variable
        year_var: Year selection variable
        prefix_imports: Whether to prefix titles with season/year
        
    Returns:
        True if import succeeded, False otherwise
    """
    try:
        text = root.clipboard_get()
    except Exception:
        messagebox.showwarning('Clipboard', 'No text found in clipboard.')
        return False
    
    parsed = import_titles_from_text(text)
    if not parsed:
        messagebox.showerror('Import Error', 'Failed to parse JSON or titles from clipboard text.')
        return False
    
    # Apply prefix if requested
    if prefix_imports:
        season = season_var.get()
        year = year_var.get()
        prefix_titles_with_season_year(parsed, season, year)
    
    # Check for invalid folder names
    try:
        auto_sanitize = config.get_pref('auto_sanitize_imports', True)
    except Exception:
        auto_sanitize = True
    
    invalid_titles = collect_invalid_folder_titles(parsed)
    
    if invalid_titles:
        if auto_sanitize:
            auto_sanitize_titles(parsed)
            invalid_titles = collect_invalid_folder_titles(parsed)
        
        if invalid_titles:
            # Create a more readable display with better formatting
            lines = []
            for display, raw, reason in invalid_titles:
                # Truncate long titles for display
                display_short = display if len(display) <= 60 else display[:57] + "..."
                lines.append(f"• {display_short}\n  → {reason}")
            
            # Build message with better formatting
            message_parts = [
                'The following imported titles contain characters or names\n'
                'invalid for folder names:\n'
            ]
            
            # Show up to 8 items with better spacing
            display_count = min(8, len(lines))
            message_parts.append('\n'.join(lines[:display_count]))
            
            if len(lines) > display_count:
                message_parts.append(f'\n... and {len(lines) - display_count} more titles with issues')
            
            message_parts.append('\n\nContinue import anyway?')
            
            if not messagebox.askyesno(
                'Invalid folder names',
                '\n'.join(message_parts),
                icon='warning'
            ):
                return False
    
    # Merge with existing titles
    try:
        current = getattr(config, 'ALL_TITLES', {}) or {}
        if not isinstance(current, dict):
            current = {}
        
        # Get existing title names, mustContain, and ruleNames to avoid duplicates
        existing_titles = set()
        existing_must_contain = set()
        existing_rule_names = set()
        
        for k, lst in current.items():
            if not isinstance(lst, list):
                continue
            for it in lst:
                try:
                    if isinstance(it, dict):
                        t = (it.get('node') or {}).get('title') or it.get('ruleName') or it.get('name')
                        if t:
                            existing_titles.add(str(t))
                        # Also track mustContain and ruleName
                        must = it.get('mustContain')
                        if must:
                            existing_must_contain.add(str(must))
                        rule_name = it.get('ruleName') or it.get('name')
                        if rule_name:
                            existing_rule_names.add(str(rule_name))
                    else:
                        t = str(it)
                        existing_titles.add(t)
                except Exception:
                    pass
        
        # Merge new titles
        new_count = 0
        for media_type, items in parsed.items():
            if not isinstance(items, list):
                continue
            if media_type not in current:
                current[media_type] = []
            
            for item in items:
                try:
                    if isinstance(item, dict):
                        title = (item.get('node') or {}).get('title') or item.get('ruleName') or item.get('name')
                        must = item.get('mustContain')
                        rule_name = item.get('ruleName') or item.get('name')
                    else:
                        # Convert string items to proper dict format
                        title = str(item)
                        must = title
                        rule_name = title
                        # Convert to dict format
                        item = {'node': {'title': title}, 'mustContain': must, 'ruleName': rule_name}
                    
                    key = str(title) if title else None
                except Exception:
                    key = None
                    must = None
                    rule_name = None
                
                # Check if it's a duplicate by title, mustContain, or ruleName
                is_duplicate = False
                if key and key in existing_titles:
                    is_duplicate = True
                elif must and str(must) in existing_must_contain:
                    is_duplicate = True
                elif rule_name and str(rule_name) in existing_rule_names:
                    is_duplicate = True
                
                if not is_duplicate:
                    current[media_type].append(item)
                    if key:
                        existing_titles.add(key)
                    if must:
                        existing_must_contain.add(str(must))
                    if rule_name:
                        existing_rule_names.add(str(rule_name))
                    new_count += 1
        
        config.ALL_TITLES = current
        total_imported = sum(len(v) for v in parsed.values() if isinstance(v, list))
        duplicates = total_imported - new_count
        
        status_msg = f'Imported {new_count} new titles from clipboard.'
        if duplicates > 0:
            status_msg += f' ({duplicates} duplicates skipped)'
            
    except Exception as e:
        logger.error(f"Error merging titles: {e}")
        config.ALL_TITLES = parsed
        status_msg = f'Imported {sum(len(v) for v in parsed.values())} titles from clipboard.'
    
    # Populate missing fields
    try:
        season = season_var.get()
        year = year_var.get()
        populate_missing_rule_fields(config.ALL_TITLES, season, year)
    except Exception:
        pass
    
    # Update UI
    update_treeview_with_titles(config.ALL_TITLES)
    status_var.set(status_msg)
    
    return True


def export_selected_titles() -> None:
    """Export selected titles from the listbox to a JSON file."""
    app_state = get_app_state()
    treeview = app_state.treeview
    
    if not treeview:
        return
    
    try:
        sel = treeview.curselection()
        if not sel:
            messagebox.showwarning('Export', 'No title selected to export.')
            return
        
        indices = [int(i) for i in sel]
        selected_entries = [app_state.items[i][1] for i in indices]
        
        # Build rules dict
        from src.rss_rules import build_rules_from_titles
        export_map = build_rules_from_titles({'anime': selected_entries})
        
        path = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('JSON', '*.json')]
        )
        
        if not path:
            return
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(export_map, f, indent=4)
        
        messagebox.showinfo('Export', f'Exported {len(export_map)} rule(s) to {path}')
        
    except Exception as e:
        logger.error(f"Error exporting selected titles: {e}")
        messagebox.showerror('Export Error', f'Failed to export: {e}')


def export_all_titles() -> None:
    """Export all titles to a JSON file."""
    try:
        data = getattr(config, 'ALL_TITLES', None) or {}
        if not data:
            messagebox.showwarning('Export All', 'No titles available to export.')
            return
        
        path = filedialog.asksaveasfilename(
            defaultextension='.json',
            filetypes=[('JSON', '*.json')]
        )
        
        if not path:
            return
        
        # Build rules dict
        try:
            from src.rss_rules import build_rules_from_titles
            export_map = build_rules_from_titles(data)
        except Exception:
            export_map = data
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(export_map, f, indent=4)
        
        messagebox.showinfo('Export All', f'Exported all titles to {path}')
        
    except Exception as e:
        logger.error(f"Error exporting all titles: {e}")
        messagebox.showerror('Export Error', f'Failed to export: {e}')


def clear_all_titles(root: tk.Tk, status_var: tk.StringVar) -> bool:
    """
    Clear all loaded titles after user confirmation.
    
    Args:
        root: Parent window
        status_var: Status bar variable
        
    Returns:
        True if titles were cleared, False otherwise
    """
    app_state = get_app_state()
    
    try:
        has_titles = bool(getattr(config, 'ALL_TITLES', None)) and any(
            (getattr(config, 'ALL_TITLES') or {}).values()
        )
    except Exception:
        has_titles = bool(getattr(config, 'ALL_TITLES', None))
    
    if not has_titles:
        status_var.set('No titles to clear.')
        if app_state.treeview:
            try:
                for item in app_state.treeview.get_children():
                    app_state.treeview.delete(item)
            except Exception:
                pass
        return False
    
    if not messagebox.askyesno(
        'Clear All Titles',
        'Are you sure you want to clear all loaded titles? This cannot be undone.'
    ):
        return False
    
    try:
        config.ALL_TITLES = {}
    except Exception:
        pass
    
    if app_state.treeview:
        try:
            for item in app_state.treeview.get_children():
                app_state.treeview.delete(item)
        except Exception:
            pass
    
    app_state.clear_items()
    
    # Refresh treeview to ensure display is synchronized
    update_treeview_with_titles(config.ALL_TITLES)
    
    status_var.set('Cleared all loaded titles.')
    return True


def dispatch_generation(
    root: tk.Tk,
    season_var: tk.StringVar,
    year_var: tk.StringVar,
    status_var: tk.StringVar
) -> None:
    """
    Handles generation and synchronization of RSS rules to qBittorrent.
    
    Shows preview dialog with validation, allows user to review and confirm
    before syncing rules to qBittorrent.
    
    Args:
        root: Parent Tkinter window
        season_var: Tkinter variable containing season selection
        year_var: Tkinter variable containing year value
        status_var: Status bar variable for displaying progress
    """
    from src.constants import FileSystem
    from src.qbittorrent_api import QBittorrentClient
    from src.gui.app_state import get_app_state
    from src.rss_rules import build_rules_from_titles
    
    try:
        season = season_var.get()
        year = year_var.get()

        if not season or not year:
            messagebox.showwarning("Input Error", "Season and Year must be specified.")
            return

        app_state = get_app_state()
        listbox_items = app_state.listbox_items
        treeview = app_state.treeview

        # Get selected items or all items
        items = []
        try:
            if treeview:
                sel = treeview.selection()
                if sel:
                    # Match by index column (second column, index 1)
                    indices = []
                    for item_id in sel:
                        try:
                            values = treeview.item(item_id, 'values')
                            if values and len(values) >= 2:
                                idx_str = values[1]  # index column
                                idx = int(idx_str) - 1  # Convert to 0-based
                                if 0 <= idx < len(listbox_items):
                                    indices.append(idx)
                        except Exception:
                            pass
                else:
                    indices = list(range(len(listbox_items)))
            else:
                indices = list(range(len(listbox_items)))
        except Exception:
            indices = list(range(len(listbox_items)))

        for i in indices:
            try:
                if i < len(listbox_items):
                    t, entry = listbox_items[i]
                    items.append((t, entry))
            except Exception:
                continue

        if not items:
            messagebox.showwarning('No Items', 'No titles to generate rules for.')
            return

        # Validation helper
        def _is_valid_folder_name(name):
            """Validates if a string is a valid folder name."""
            try:
                if not name or not isinstance(name, str) or not str(name).strip():
                    return False, 'Empty name'
                
                s = str(name).strip()
                
                # Check for invalid characters
                found_invalid = [c for c in s if c in FileSystem.INVALID_CHARS]
                if found_invalid:
                    return False, f'Contains invalid characters: {"".join(sorted(set(found_invalid)))}'
                
                # Check for trailing space or dot
                if s.endswith(' ') or s.endswith('.'):
                    return False, 'Ends with a space or dot (invalid on Windows)'
                
                # Check for Windows reserved names
                base = s.split('.')[0].upper()
                if base in FileSystem.RESERVED_NAMES:
                    return False, f'Reserved name: {base}'
                
                # Check length
                if len(s) > FileSystem.MAX_PATH_LENGTH:
                    return False, f'Name too long (>{FileSystem.MAX_PATH_LENGTH} chars)'
                
                return True, None
            except Exception:
                return False, 'Validation error'

        # Validate all items
        problems = []
        preview_list = []
        
        for title_text, entry in items:
            e = entry if isinstance(entry, dict) else {'node': {'title': str(entry)}}
            
            try:
                node = e.get('node') or {}
                node_title = node.get('title') or e.get('mustContain') or title_text
            except Exception:
                node_title = title_text
                
            if not node_title or not str(node_title).strip():
                problems.append(f'Missing title for item: {title_text}')

            # Validate lastMatch JSON
            try:
                lm = e.get('lastMatch', '')
                if isinstance(lm, str):
                    s = lm.strip()
                    if s and (s.startswith('{') or s.startswith('[') or s.startswith('"')):
                        try:
                            json.loads(s)
                        except Exception as ex:
                            problems.append(f'Invalid JSON lastMatch for "{title_text}": {ex}')
            except Exception:
                pass

            # Validate folder name
            try:
                raw = e.get('mustContain') or (e.get('node') or {}).get('title') or e.get('title') or ''
                if not raw:
                    display = (e.get('node') or {}).get('title') or e.get('title') or title_text
                    if display and ' - ' in display:
                        parts = display.split(' - ', 1)
                        if len(parts) == 2:
                            raw = parts[1]
                if raw:
                    valid, reason = _is_valid_folder_name(raw)
                    if not valid:
                        problems.append(f'Invalid folder-name for "{title_text}": {reason}')
            except Exception:
                pass

            preview_list.append(e)

        # Show preview dialog
        dlg = tk.Toplevel(root)
        dlg.title('Preview Generation & Sync')
        dlg.geometry('800x700')
        dlg.transient(root)
        dlg.grab_set()
        dlg.configure(bg='#f5f5f5')
        
        # Header
        header_frame = ttk.Frame(dlg, padding=10)
        header_frame.pack(fill='x')
        ttk.Label(header_frame, text=f'Generate {len(preview_list)} rule(s) for {season} {year}',
                 font=('Segoe UI', 10, 'bold')).pack(anchor='w')

        # Validation issues section
        prob_frame = ttk.LabelFrame(dlg, text='Validation', padding=10)
        prob_frame.pack(fill='both', padx=10, pady=(0, 10), expand=False)
        
        if problems:
            ttk.Label(prob_frame, text='⚠️ Validation issues detected:', 
                     foreground='#d32f2f', font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(0, 5))
            prob_box = tk.Text(prob_frame, height=min(10, max(3, len(problems))), width=90,
                              font=('Consolas', 9), wrap='word', bg='#fff3cd', fg='#856404')
            prob_box.pack(fill='both', expand=True)
            prob_scroll = ttk.Scrollbar(prob_frame, orient='vertical', command=prob_box.yview)
            prob_scroll.pack(side='right', fill='y')
            prob_box.configure(yscrollcommand=prob_scroll.set)
            
            for p in problems:
                prob_box.insert('end', f'• {p}\n')
            prob_box.config(state='disabled')
        else:
            ttk.Label(prob_frame, text='✅ No validation issues detected.',
                     foreground='#2e7d32', font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        # Preview JSON section
        preview_frame = ttk.LabelFrame(dlg, text='Rules Preview (JSON)', padding=10)
        preview_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        preview_text = tk.Text(preview_frame, height=20, width=90, font=('Consolas', 9),
                               wrap='none', bg='#fafafa', fg='#333333')
        preview_text.pack(side='left', fill='both', expand=True)
        
        preview_scroll_y = ttk.Scrollbar(preview_frame, orient='vertical', command=preview_text.yview)
        preview_scroll_y.pack(side='right', fill='y')
        preview_scroll_x = ttk.Scrollbar(preview_frame, orient='horizontal', command=preview_text.xview)
        preview_scroll_x.pack(side='bottom', fill='x')
        
        preview_text.configure(yscrollcommand=preview_scroll_y.set, xscrollcommand=preview_scroll_x.set)
        
        try:
            # Build actual qBittorrent rules format for preview
            from src.rss_rules import build_rules_from_titles
            
            # Create clean data without internal tracking fields
            clean_titles = {}
            for media_type, items in config.ALL_TITLES.items():
                clean_items = []
                for item in items:
                    if isinstance(item, dict):
                        # Create clean copy without internal tracking fields
                        clean_item = {}
                        for key, value in item.items():
                            # Skip internal tracking fields
                            if key not in ['node', 'ruleName']:
                                clean_item[key] = value
                        clean_items.append(clean_item)
                    else:
                        clean_items.append(item)
                clean_titles[media_type] = clean_items
            
            # Build rules dict - this returns {"Rule Name": {rule_data}, ...}
            rules_dict = build_rules_from_titles(clean_titles)
            
            # Display as proper qBittorrent dictionary format (not a list)
            preview_text.insert('1.0', json.dumps(rules_dict, indent=2, ensure_ascii=False))
        except Exception as e:
            # Fallback to original format if build fails
            try:
                preview_data = {
                    'season': season,
                    'year': year,
                    'rule_count': len(preview_list),
                    'rules': preview_list
                }
                preview_text.insert('1.0', json.dumps(preview_data, indent=2, ensure_ascii=False))
            except Exception:
                preview_text.insert('1.0', str(preview_list))
        preview_text.config(state='disabled')

        # Sync mode selection frame
        mode_frame = ttk.LabelFrame(dlg, text='Sync Mode', padding=10)
        mode_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        sync_mode = tk.StringVar(value='replace')
        
        ttk.Radiobutton(mode_frame, text='🔄 Replace All Rules (remove old rules, then add new ones)', 
                       variable=sync_mode, value='replace').pack(anchor='w', pady=2)
        ttk.Radiobutton(mode_frame, text='➕ Add/Update Only (keep existing rules, add or update new ones)', 
                       variable=sync_mode, value='add').pack(anchor='w', pady=2)

        # Button frame
        btns = ttk.Frame(dlg, padding=10)
        btns.pack(fill='x', side='bottom')

        def _do_proceed():
            """Proceed with sync after validation."""
            try:
                if problems:
                    if not messagebox.askyesno('Proceed with Warnings', 
                        f'{len(problems)} validation issue(s) detected.\n\nProceed anyway?'):
                        return
                
                # Get selected sync mode
                selected_mode = sync_mode.get()
                
                dlg.destroy()
                status_var.set(f"⏳ Syncing {len(preview_list)} rules to qBittorrent...")
                root.update()
                
                # Check connection mode
                mode = config.CONNECTION_MODE or 'online'
                if mode == 'offline':
                    messagebox.showinfo('Offline Mode', 
                        'In offline mode. Rules would be generated to JSON file only.\n\n'
                        'Use File > Export to save rules.')
                    status_var.set('Offline mode - use Export to save rules')
                    return
                
                # Build rules from the validated preview list
                try:
                    rules_dict = build_rules_from_titles(config.ALL_TITLES)
                    if not rules_dict:
                        messagebox.showwarning('Sync', 'No valid rules to sync.')
                        status_var.set('No rules generated')
                        return
                except Exception as e:
                    messagebox.showerror('Build Error', f'Failed to build rules: {e}')
                    status_var.set('❌ Failed to build rules')
                    return
                
                # Connect and sync to qBittorrent
                try:
                    api = QBittorrentClient(
                        protocol=config.QBT_PROTOCOL,
                        host=config.QBT_HOST,
                        port=config.QBT_PORT,
                        username=config.QBT_USER,
                        password=config.QBT_PASS,
                        verify_ssl=config.QBT_VERIFY_SSL,
                        ca_cert=getattr(config, 'QBT_CA_CERT', None)
                    )
                    
                    # Connect to qBittorrent
                    if not api.connect():
                        status_var.set('❌ Failed to connect to qBittorrent')
                        messagebox.showerror('Connection Failed', 'Could not connect to qBittorrent.')
                        return
                    
                    removed_count = 0
                    
                    # If replace mode, remove all existing rules first
                    if selected_mode == 'replace':
                        # Get existing rules
                        existing_rules = api.get_rules()
                        
                        # Remove all existing rules first (to replace them)
                        if existing_rules:
                            for old_rule_name in list(existing_rules.keys()):
                                try:
                                    if api.remove_rule(old_rule_name):
                                        removed_count += 1
                                        status_var.set(f"🗑️ Removing old rules... ({removed_count}/{len(existing_rules)})")
                                        root.update()
                                except Exception as e:
                                    logger.error(f"Failed to remove rule '{old_rule_name}': {e}")
                    
                    # Now add/update the new rules
                    success_count = 0
                    failed_count = 0
                    
                    for rule_name, rule_def in rules_dict.items():
                        try:
                            if api.set_rule(rule_name, rule_def):
                                success_count += 1
                                status_var.set(f"⏳ Synced {success_count}/{len(rules_dict)} rules...")
                                root.update()
                            else:
                                failed_count += 1
                        except Exception as e:
                            logger.error(f"Failed to set rule '{rule_name}': {e}")
                            failed_count += 1
                    
                    # Show results
                    if success_count > 0:
                        if selected_mode == 'replace':
                            msg = f'✅ Successfully replaced {removed_count} old rule(s) with {success_count} new rule(s)!'
                        else:
                            msg = f'✅ Successfully added/updated {success_count} rule(s)!'
                        
                        status_var.set(f'✅ Synced {success_count} rule(s) for {season} {year}')
                        if failed_count > 0:
                            messagebox.showwarning('Sync Complete', 
                                f'{msg}\n\n'
                                f'{failed_count} rule(s) failed to sync.')
                        else:
                            messagebox.showinfo('Sync Complete', 
                                f'{msg}\n\n'
                                f'Season: {season} {year}')
                    else:
                        status_var.set('❌ Sync failed')
                        messagebox.showerror('Sync Failed', 'Failed to sync any rules to qBittorrent.')
                        
                except Exception as e:
                    status_var.set(f'❌ Sync error')
                    messagebox.showerror('Sync Error', f'Failed to connect to qBittorrent:\n\n{e}')
                    
            except Exception as e:
                logger.error(f"Error in _do_proceed: {e}")
                messagebox.showerror('Generation Error', f'An error occurred: {e}')

        def _do_cancel():
            """Cancel the operation."""
            try:
                dlg.destroy()
                status_var.set('Sync cancelled')
            except Exception:
                pass

        ttk.Button(btns, text='✓ Proceed & Sync', command=_do_proceed, 
                  style='Accent.TButton').pack(side='right', padx=(5, 0))
        ttk.Button(btns, text='✕ Cancel', command=_do_cancel).pack(side='right')

        dlg.wait_window()

    except Exception as e:
        logger.error(f"Error in dispatch_generation: {e}")
        messagebox.showerror("Generation Error", f"An error occurred: {e}")


__all__ = [
    'normalize_titles_structure',
    'import_titles_from_text',
    'prefix_titles_with_season_year',
    'collect_invalid_folder_titles',
    'auto_sanitize_titles',
    'populate_missing_rule_fields',
    'update_treeview_with_titles',
    'import_titles_from_file',
    'import_titles_from_clipboard',
    'export_selected_titles',
    'export_all_titles',
    'build_rules_from_titles',
    'clear_all_titles',
    'dispatch_generation',
]
