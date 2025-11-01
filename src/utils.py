"""
Utility functions for the application.
"""
import logging
import re
from datetime import datetime
from typing import Tuple

from .constants import FileSystem

logger = logging.getLogger(__name__)


def get_current_anime_season() -> Tuple[str, str]:
    """
    Returns the current anime season and year based on the current date.
    
    Returns:
        Tuple[str, str]: (season_name, year_string)
        
    Anime seasons:
    - Winter: January-March
    - Spring: April-June
    - Summer: July-September
    - Fall: October-December
    """
    now = datetime.now()
    month = now.month
    year = str(now.year)
    
    season_map = {
        (1, 2, 3): "Winter",
        (4, 5, 6): "Spring",
        (7, 8, 9): "Summer",
        (10, 11, 12): "Fall"
    }
    
    for months, season in season_map.items():
        if month in months:
            return season, year
    
    return "Fall", year  # Fallback (shouldn't happen)


def sanitize_folder_name(name: str, replacement_char: str = '_', max_length: int = 255) -> str:
    """
    Sanitizes a folder name by removing or replacing invalid characters.
    
    Args:
        name: The original folder name
        replacement_char: Character to use for replacing invalid characters
        max_length: Maximum length for the folder name
    
    Returns:
        str: Sanitized folder name safe for filesystem use
    """
    if not name:
        return replacement_char
    
    # Remove or replace invalid characters
    sanitized = name
    for char in FileSystem.INVALID_CHARS:
        sanitized = sanitized.replace(char, replacement_char)
    
    # Remove leading/trailing spaces and dots (Windows doesn't allow these)
    sanitized = sanitized.strip().strip('.')
    
    # Check for Windows reserved names
    base_name = sanitized.split('.')[0].upper()
    if base_name in FileSystem.RESERVED_NAMES:
        sanitized = f"{replacement_char}{sanitized}"
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Ensure we didn't end up with an empty string
    if not sanitized:
        sanitized = replacement_char
    
    return sanitized


def validate_folder_name(name: str) -> Tuple[bool, str]:
    """
    Validates if a string is a valid folder name.
    
    Args:
        name: Folder name to validate
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if not name or not isinstance(name, str) or not name.strip():
        return False, 'Folder name cannot be empty'
    
    s = name.strip()
    
    # Check for invalid characters
    found_invalid = [c for c in s if c in FileSystem.INVALID_CHARS]
    if found_invalid:
        return False, f"Contains invalid characters: {', '.join(found_invalid)}"
    
    # Check for trailing space or dot
    if s.endswith(' ') or s.endswith('.'):
        return False, 'Cannot end with space or period'
    
    # Check for Windows reserved names
    base = s.split('.')[0].upper()
    if base in FileSystem.RESERVED_NAMES:
        return False, f"'{base}' is a reserved Windows name"
    
    # Check length
    if len(s) > FileSystem.MAX_PATH_LENGTH:
        return False, f'Exceeds maximum length ({FileSystem.MAX_PATH_LENGTH} characters)'
    
    return True, ''
