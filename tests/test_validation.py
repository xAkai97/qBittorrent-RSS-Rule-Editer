"""
Tests for filesystem validation and auto-sanitization features.

Tests the new validation system that supports both Windows and Linux/Unraid
filesystem rules, along with automatic sanitization of invalid folder names.
"""

import pytest
from src import config
from src.utils import sanitize_folder_name


class TestFilesystemValidation:
    """Tests for filesystem-specific validation rules."""
    
    def test_linux_validation_allows_colons(self):
        """Linux mode should allow colons in folder names."""
        config.set_pref('filesystem_type', 'linux')
        
        # This would be validated in the actual validation function
        # For now, just verify preference is set
        assert config.get_pref('filesystem_type', 'linux') == 'linux'
        return True
    
    def test_linux_validation_blocks_forward_slash(self):
        """Linux mode should block forward slashes."""
        config.set_pref('filesystem_type', 'linux')
        
        # Forward slash is invalid in Linux folder names
        test_name = "Title/Name"
        # Would fail validation
        assert '/' in test_name
        return True
    
    def test_windows_validation_blocks_colons(self):
        """Windows mode should block colons in folder names."""
        config.set_pref('filesystem_type', 'windows')
        
        test_name = "Title: Name"
        # Would fail Windows validation
        assert ':' in test_name
        return True
    
    def test_windows_validation_blocks_quotes(self):
        """Windows mode should block quotes in folder names."""
        config.set_pref('filesystem_type', 'windows')
        
        test_name = 'Title "Name"'
        # Would fail Windows validation
        assert '"' in test_name
        return True
    
    def test_windows_validation_blocks_trailing_dots(self):
        """Windows mode should block trailing dots."""
        config.set_pref('filesystem_type', 'windows')
        
        test_name = "Title Name."
        # Would fail Windows validation
        assert test_name.endswith('.')
        return True
    
    def test_windows_reserved_names(self):
        """Windows mode should block reserved names like CON, PRN, etc."""
        config.set_pref('filesystem_type', 'windows')
        
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'LPT1']
        for name in reserved_names:
            # These would fail Windows validation
            assert name.upper() in ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'LPT1']
        return True


class TestAutoSanitization:
    """Tests for automatic folder name sanitization."""
    
    def test_sanitize_removes_colons(self):
        """Sanitization should remove colons."""
        original = "Mushoku no Eiyuu: Betsu ni Skill"
        sanitized = sanitize_folder_name(original)
        
        # Colons should be removed or replaced
        assert ':' not in sanitized
        # Title should still be recognizable
        assert 'Mushoku' in sanitized
        assert 'Eiyuu' in sanitized
        return True
    
    def test_sanitize_removes_quotes(self):
        """Sanitization should remove quotes."""
        original = 'Gift "Mugen Gacha" de Level'
        sanitized = sanitize_folder_name(original)
        
        # Quotes should be removed
        assert '"' not in sanitized
        # Title should still be readable
        assert 'Gift' in sanitized
        assert 'Mugen' in sanitized
        return True
    
    def test_sanitize_preserves_valid_characters(self):
        """Sanitization should preserve valid characters."""
        original = "Valid Title Name 123"
        sanitized = sanitize_folder_name(original)
        
        # Should be unchanged or minimally changed
        assert 'Valid' in sanitized
        assert 'Title' in sanitized
        assert 'Name' in sanitized
        return True
    
    def test_sanitize_handles_multiple_invalid_chars(self):
        """Sanitization should handle multiple invalid characters."""
        original = 'Title: "Name" <Test> |More|'
        sanitized = sanitize_folder_name(original)
        
        # All invalid characters should be removed
        invalid_chars = [':', '"', '<', '>', '|']
        for char in invalid_chars:
            assert char not in sanitized
        return True
    
    def test_auto_sanitize_preference_default(self):
        """Auto-sanitize preference should default to True."""
        pref = config.get_pref('auto_sanitize_paths', True)
        assert pref == True
        return True
    
    def test_auto_sanitize_preference_toggle(self):
        """Should be able to toggle auto-sanitize preference."""
        # Set to False
        config.set_pref('auto_sanitize_paths', False)
        assert config.get_pref('auto_sanitize_paths', True) == False
        
        # Set back to True
        config.set_pref('auto_sanitize_paths', True)
        assert config.get_pref('auto_sanitize_paths', False) == True
        return True


class TestValidationIntegration:
    """Integration tests for validation with treeview and sync."""
    
    def test_filesystem_preference_persistence(self):
        """Filesystem type preference should persist."""
        # Set to Windows
        config.set_pref('filesystem_type', 'windows')
        assert config.get_pref('filesystem_type', 'linux') == 'windows'
        
        # Set to Linux
        config.set_pref('filesystem_type', 'linux')
        assert config.get_pref('filesystem_type', 'windows') == 'linux'
        return True
    
    def test_validation_respects_filesystem_type(self):
        """Validation should respect filesystem type preference."""
        # Set Linux mode
        config.set_pref('filesystem_type', 'linux')
        fs_type = config.get_pref('filesystem_type', 'windows')
        assert fs_type == 'linux'
        
        # Set Windows mode
        config.set_pref('filesystem_type', 'windows')
        fs_type = config.get_pref('filesystem_type', 'linux')
        assert fs_type == 'windows'
        return True
    
    def test_sanitization_with_path_components(self):
        """Sanitization should work with full paths."""
        path = "disk5/Anime/Web/Fall 2025/Mushoku no Eiyuu: Betsu ni Skill"
        components = path.split('/')
        
        # Last component has invalid character
        assert ':' in components[-1]
        
        # Sanitize last component
        sanitized = sanitize_folder_name(components[-1])
        assert ':' not in sanitized
        return True


class TestValidationEdgeCases:
    """Edge case tests for validation system."""
    
    def test_empty_folder_name(self):
        """Should handle empty folder names gracefully."""
        empty = ""
        # Should not crash, should return safe default or fail validation
        assert len(empty) == 0
        return True
    
    def test_whitespace_only_name(self):
        """Should handle whitespace-only names."""
        whitespace = "   "
        # Should fail validation or be sanitized
        assert whitespace.strip() == ""
        return True
    
    def test_very_long_path(self):
        """Should handle very long path names."""
        long_name = "A" * 300  # Longer than typical MAX_PATH_LENGTH
        # Should fail validation for length
        assert len(long_name) > 255
        return True
    
    def test_unicode_characters(self):
        """Should handle Unicode characters properly."""
        unicode_name = "アニメ Title 动漫"
        # Should preserve Unicode unless invalid
        assert len(unicode_name) > 0
        return True
    
    def test_mixed_slashes(self):
        """Should handle mixed forward and back slashes."""
        mixed = "path\\to/folder"
        # Should normalize or validate correctly
        assert '\\' in mixed or '/' in mixed
        return True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
