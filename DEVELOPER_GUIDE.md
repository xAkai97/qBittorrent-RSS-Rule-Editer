# Developer Guide

## Getting Started

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Git
- Text editor or IDE (VS Code recommended)

### Initial Setup

1. **Clone the Repository**
   ```powershell
   git clone https://github.com/xAkai97/qBittorrent-RSS-Rule-Editer.git
   cd qBittorrent-RSS-Rule-Editer
   ```

2. **Create Virtual Environment**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate
   ```

3. **Install Development Dependencies**
   ```powershell
   pip install -r requirements.txt
   pytest  # Verify test setup
   ```

4. **Run the Application**
   ```powershell
   python main.py
   ```

## Project Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed information on:
- Module structure and responsibilities
- Data flow diagrams
- Design patterns used
- Testing architecture

## Coding Standards

### Code Style
- Follow **PEP 8** guidelines
- Line length: 100 characters maximum
- Use 4 spaces for indentation (no tabs)
- Use descriptive variable and function names

### Type Hints
- Use type hints for function parameters and return values
- Example:
  ```python
  def fetch_rules(
      protocol: str,
      host: str,
      port: str,
      username: str,
      password: str,
      verify_ssl: bool = True,
      timeout: int = 10
  ) -> Tuple[bool, Union[str, Dict]]:
      """Fetch RSS rules from qBittorrent."""
  ```

### Docstrings
- Use triple-quoted docstrings for modules, classes, and functions
- Follow **Google-style** format:
  ```python
  def validate_rule(rule: RSSRule) -> bool:
      """Validate RSS rule structure and content.
      
      Args:
          rule: The RSSRule object to validate.
          
      Returns:
          True if valid, False otherwise.
          
      Raises:
          ValidationError: If critical fields are missing.
      """
  ```

### Naming Conventions
- **Functions:** `snake_case` (e.g., `fetch_categories`)
- **Classes:** `PascalCase` (e.g., `QBittorrentClient`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `DEFAULT_TIMEOUT`)
- **Private methods:** `_leading_underscore` (e.g., `_connect_with_requests`)

### Import Organization
```python
# 1. Standard library imports
import json
import logging
from typing import Dict, List, Tuple

# 2. Third-party imports
import requests
from dataclasses import dataclass

# 3. Local imports
from src.constants import QBittorrentError
from src.config import load_config
```

## Testing

### Running Tests

**Run all tests:**
```powershell
pytest -v
```

**Run specific test file:**
```powershell
pytest tests/test_rss_rules.py -v
```

**Run specific test function:**
```powershell
pytest tests/test_rss_rules.py::test_rss_rule_creation -v
```

**Run with coverage report:**
```powershell
pytest --cov=src --cov-report=html
```

### Writing Tests

#### Test File Structure
```python
import unittest
from unittest.mock import patch, MagicMock
from src.module_name import function_or_class


class TestFunctionality(unittest.TestCase):
    """Test suite for specific functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        pass
    
    def tearDown(self):
        """Clean up after tests."""
        pass
    
    def test_successful_case(self):
        """Test happy path."""
        result = function_under_test()
        self.assertEqual(result, expected_value)
    
    def test_error_case(self):
        """Test error handling."""
        with self.assertRaises(ExpectedException):
            function_that_raises()
    
    @patch('src.module.external_function')
    def test_with_mock(self, mock_func):
        """Test with mocked dependencies."""
        mock_func.return_value = test_value
        result = function_under_test()
        self.assertEqual(result, expected_value)


if __name__ == '__main__':
    unittest.main()
```

#### Best Practices
- **One assertion per test** (preferably)
- **Clear test names** that describe what's being tested
- **Use descriptive assertions** with messages
- **Mock external dependencies** (APIs, file system, database)
- **Test edge cases** (empty input, None values, invalid data)
- **Test error conditions** (exceptions, timeouts, invalid states)

#### Test Categories

| Category | Location | Count | Purpose |
|----------|----------|-------|---------|
| Unit | `test_modules.py` | 6 | Test individual modules |
| Integration | `test_integration.py` | 10 | Test module interactions |
| Edge Cases | `test_import_export_edge_cases.py` | 21 | Test boundary conditions |
| Business Logic | `test_rss_rules.py` | 9 | Test rule operations |
| Data Filtering | `test_filtering.py` | 18 | Test utility functions |
| API | `test_qbittorrent_api.py` | 5 | Test qBittorrent client |
| API Errors | `test_qbittorrent_api_errors.py` | 25 | Test error handling |
| GUI | `test_gui_components.py` | 15 | Test GUI components (mocked) |

### Test Fixtures

Common test fixtures used throughout the test suite:

```python
# Valid RSSRule object
valid_rule = RSSRule(
    ruleName="Test Rule",
    mustContain="720p",
    savePath="/downloads/anime",
    enabled=True
)

# Valid configuration
config = {
    'protocol': 'http',
    'host': 'localhost',
    'port': '8080',
    'username': 'admin',
    'password': 'password',
    'verify_ssl': False
}

# Mock qBittorrent client
mock_client = MagicMock()
mock_client.connect.return_value = True
mock_client.get_rules.return_value = {'rule1': {...}}
```

## Adding Features

### Feature Development Workflow

1. **Create Feature Branch**
   ```powershell
   git checkout -b feature/description
   ```

2. **Write Tests First** (TDD approach)
   - Create test file or add tests to existing file
   - Tests should fail initially
   - Run: `pytest tests/test_*.py -v`

3. **Implement Feature**
   - Follow coding standards above
   - Add docstrings and comments
   - Keep changes focused and atomic

4. **Run All Tests**
   ```powershell
   pytest -v
   ```

5. **Update Documentation**
   - Update ARCHITECTURE.md if structure changes
   - Update README.md if user-facing changes
   - Add code comments for complex logic

6. **Commit Changes**
   ```powershell
   git add .
   git commit -m "Add feature: description"
   ```

### Common Development Tasks

#### Adding a New API Integration

1. Create `src/new_api.py` with:
   - Module docstring explaining purpose
   - Class for API client (e.g., `NewAPIClient`)
   - Methods for API operations
   - Error handling for network failures

2. Add tests in `tests/test_new_api.py`:
   - Mock HTTP requests
   - Test successful operations
   - Test error conditions
   - Test caching (if applicable)

3. Integrate in GUI:
   - Update `gui/dialogs.py` if adding settings
   - Update `gui/main_window.py` if adding UI
   - Update `app_state.py` if adding state

#### Adding a New GUI Component

1. Create widget in `src/gui/widgets.py`:
   - Use Tkinter standard widgets where possible
   - Add docstrings with usage example
   - Support customization via parameters

2. Create tests in `tests/test_gui_components.py`:
   - Mock Tkinter components
   - Test initialization
   - Test interactions
   - Test state changes

3. Integrate in main window:
   - Add widget to `gui/main_window.py`
   - Update layout manager (grid/pack)
   - Bind events if needed
   - Connect to app_state

#### Adding Configuration Options

1. Add to `src/constants.py`:
   - Define option key and default value
   - Add documentation comment

2. Update `src/config.py`:
   - Add getter method
   - Handle missing values gracefully

3. Add UI in `gui/dialogs.py`:
   - Create settings dialog entry
   - Validate user input
   - Save to config.ini

4. Add tests:
   - Test default values
   - Test saving/loading
   - Test invalid values

## Debugging

### Logging

The application uses Python's built-in logging module:

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Detailed information for debugging")
logger.info("General informational message")
logger.warning("Warning message")
logger.error("Error occurred", exc_info=True)
```

**View logs:**
```powershell
# Real-time tail
Get-Content qbt_editor.log -Tail 50 -Wait

# Or open in editor
code qbt_editor.log
```

### Common Issues

#### Import Errors
- **Error:** `ModuleNotFoundError: No module named 'src'`
- **Solution:** Run from project root directory: `cd /path/to/qBittorrent-RSS-Rule-Editer`

#### Tkinter Not Found
- **Error:** `ModuleNotFoundError: No module named 'tkinter'`
- **Windows:** Usually included with Python; reinstall Python
- **Linux:** `sudo apt-get install python3-tk`
- **macOS:** `brew install python-tk@3.x`

#### Virtual Environment Issues
- **Error:** `The specified module could not be found`
- **Solution:** Reactivate venv: `.\.venv\Scripts\Activate`

#### Test Failures
- **Issue:** Tests failing after code changes
- **Debug steps:**
  1. Run single failing test: `pytest tests/file.py::test_name -v`
  2. Add print statements or use `pdb.set_trace()`
  3. Check mock return values match actual API

### Interactive Debugging

Using `pdb` (Python Debugger):

```python
import pdb

# Set breakpoint
pdb.set_trace()

# Or use built-in breakpoint (Python 3.7+)
breakpoint()
```

**Common pdb commands:**
- `n` - next line
- `s` - step into
- `c` - continue
- `p variable` - print variable
- `l` - list current code
- `q` - quit debugger

## Performance Profiling

### Profile Startup Time
```powershell
python -m cProfile -s cumtime main.py
```

### Profile Memory Usage
```powershell
pip install memory-profiler
python -m memory_profiler main.py
```

### Profile Specific Function
```python
from cProfile import Profile
from pstats import Stats

profiler = Profile()
profiler.enable()
expensive_function()
profiler.disable()
stats = Stats(profiler)
stats.sort_stats('cumtime')
stats.print_stats(10)
```

## Release Process

### Version Numbering
- Follow **Semantic Versioning**: MAJOR.MINOR.PATCH
- Example: 1.2.3 (Major: 1, Minor: 2, Patch: 3)

### Release Checklist
- [ ] Update version in `src/constants.py`
- [ ] Update CHANGELOG (if exists)
- [ ] Run full test suite: `pytest -v`
- [ ] Update README.md if needed
- [ ] Create git tag: `git tag v1.2.3`
- [ ] Push changes and tag: `git push origin main --tags`

## Code Review Checklist

When reviewing PRs, check for:
- [ ] Code follows PEP 8 style guide
- [ ] Type hints present for functions
- [ ] Docstrings complete and accurate
- [ ] Tests written for new functionality
- [ ] All tests passing
- [ ] No hardcoded values (use constants)
- [ ] Error handling implemented
- [ ] Logging added where appropriate
- [ ] No security vulnerabilities
- [ ] Documentation updated

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/name`
3. Make changes following this guide
4. Write/update tests
5. Update documentation
6. Submit pull request with description

## Resources

- [Python Style Guide (PEP 8)](https://www.python.org/dev/peps/pep-0008/)
- [Type Hints (PEP 484)](https://www.python.org/dev/peps/pep-0484/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Tkinter Documentation](https://docs.python.org/3/library/tkinter.html)
- [Requests Library](https://requests.readthedocs.io/)

## Getting Help

- Check existing issues on GitHub
- Review code comments and docstrings
- See ARCHITECTURE.md for design details
- Check test files for usage examples
