"""Utility helpers (paths, rule creation, season detection).

Small helpers used across the package.
"""
import os
import json
from datetime import datetime
from tkinter import messagebox

def create_qbittorrent_rule_def(rule_pattern, save_path, default_rss_feed):
    """Creates the rule definition dictionary used by qBittorrent or the
    offline JSON export.
    """
    return {
        "affectedFeeds": [default_rss_feed],
        "assignedCategory": "Anime/Seasonal",
        "enabled": True,
        "mustContain": rule_pattern,
        "mustNotContain": "dub|batch",
        "useRegex": False,
        "savePath": save_path,
        "torrentParams": {
            "category": "Anime/Seasonal",
            "save_path": save_path.replace("\\", "/"),
            "operating_mode": "AutoManaged",
            "ratio_limit": -2,
            "seeding_time_limit": -2,
        }
    }


def get_current_anime_season():
    now = datetime.now()
    year = now.year
    month = now.month
    if 1 <= month <= 3:
        season = "Winter"
    elif 4 <= month <= 6:
        season = "Spring"
    elif 7 <= month <= 9:
        season = "Summer"
    else:
        season = "Fall"
    return str(year), season


def generate_offline_config(selected_titles, rule_prefix, year, status_var, output_file, default_save_prefix, default_rss_feed):
    """Write generated rules to a local JSON file and notify user via messagebox.

    This mirrors the previous behavior but keeps path constants provided by
    the caller (usually the config module).
    """
    final_rules = {}
    for title in selected_titles:
        sanitized_folder_name = title.replace(':', ' -').replace('/', '_').strip()
        rule_name = f"{rule_prefix} - {sanitized_folder_name}"
        save_path_prefix = os.path.join(default_save_prefix, f"{rule_prefix} {year}")
        full_save_path = os.path.join(save_path_prefix, sanitized_folder_name)
        full_save_path_local = full_save_path.replace('/', '\\')

        rule_def = create_qbittorrent_rule_def(rule_pattern=sanitized_folder_name, save_path=full_save_path_local, default_rss_feed=default_rss_feed)
        final_rules[rule_name] = rule_def
        final_rules[rule_name]['savePath'] = full_save_path_local

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json_dump_rules = {}
            for name, rule in final_rules.items():
                rule['torrentParams']['save_path'] = rule['torrentParams']['save_path'].replace('\\', '/')
                json_dump_rules[name] = rule
            json.dump(json_dump_rules, f, indent=4)

        messagebox.showinfo("Success (Offline)", f"The file '{output_file}' has been created with {len(selected_titles)} rules.\n\nNext step: Import this JSON file into your qBittorrent RSS settings.")
        status_var.set(f"Config file generated: {output_file}")
    except IOError as e:
        messagebox.showerror("File Error", f"Error writing file {output_file}: {e}")
        status_var.set("Config generation failed.")
