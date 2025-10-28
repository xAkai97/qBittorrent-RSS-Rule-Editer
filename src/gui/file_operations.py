"""
File operations for import/export functionality.

Handles importing titles from files/clipboard and exporting rules to JSON.
"""
import json
import logging
import tkinter as tk
from tkinter import filedialog, messagebox
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
                # Looks like qBittorrent format
                rules = data.get('rules', data)
                return {'anime': list(rules.values()) if isinstance(rules, dict) else rules}
            # Single level dict, wrap it
            return {'anime': [data]}
        elif isinstance(data, list):
            # List of titles
            return {'anime': data}
        elif isinstance(data, str):
            # Single title string
            return {'anime': [{'node': {'title': data}, 'mustContain': data}]}
        else:
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
        # Try parsing as JSON first
        parsed = json.loads(text)
    except Exception:
        # Fall back to line-separated titles
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if lines:
            parsed = lines
        else:
            return None
    
    return normalize_titles_structure(parsed)


def prefix_titles_with_season_year(
    all_titles: Dict[str, List],
    season: str,
    year: str
) -> None:
    """
    Prefix all titles with season and year (e.g., "Fall 2025 - Title").
    
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
                            node['title'] = prefix + orig_title
                            entry['node'] = node
                            if not entry.get('mustContain'):
                                entry['mustContain'] = orig_title
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
    
    Modifies titles in-place.
    
    Args:
        all_titles: Dictionary of titles
        season: Season name
        year: Year string
    """
    logger.debug(f"populate_missing_rule_fields called with {sum(len(v) for v in all_titles.values() if isinstance(v, list))} total titles")
    try:
        from src.utils import get_current_anime_season
        
        # Use provided season/year or current if not specified
        if not season or not year:
            year_val, season_val = get_current_anime_season()
            season = season or season_val
            year = year or str(year_val)
        
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
                    
                    # Insert into treeview with enabled column
                    index += 1
                    items_added += 1
                    
                    before_insert_count = len(treeview.get_children())
                    treeview.insert('', 'end', text=str(index),
                                  values=(enabled_mark, title_text, category, save_path))
                    after_insert_count = len(treeview.get_children())
                    
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
                lines = [f"{display} -> {raw}: {reason}" 
                        for display, raw, reason in invalid_titles]
                if not messagebox.askyesno(
                    'Invalid folder names',
                    'The following imported titles contain characters or names invalid for folder names:\n\n' +
                    '\n'.join(lines[:10]) +  # Limit display
                    (f'\n... and {len(lines) - 10} more' if len(lines) > 10 else '') +
                    '\n\nContinue import anyway?'
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
        
        # Populate missing fields
        try:
            season = season_var.get()
            year = year_var.get()
            populate_missing_rule_fields(config.ALL_TITLES, season, year)
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
            lines = [f"{display} -> {raw}: {reason}" 
                    for display, raw, reason in invalid_titles]
            if not messagebox.askyesno(
                'Invalid folder names',
                'The following imported titles contain invalid characters:\n\n' +
                '\n'.join(lines[:10]) +
                (f'\n... and {len(lines) - 10} more' if len(lines) > 10 else '') +
                '\n\nContinue import anyway?'
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
    'clear_all_titles',
]
