"""
Test script for Phase 4: qBittorrent Integration Module

This script validates the qBittorrent API module functionality.
"""
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_qbittorrent_imports():
    """Test that qBittorrent API module imports correctly."""
    print("\n" + "="*60)
    print("Test 1: qBittorrent API Module Imports")
    print("="*60)
    
    try:
        from src import qbittorrent_api
        print("✓ src.qbittorrent_api imported")
        
        from src.qbittorrent_api import (
            QBittorrentClient,
            ping_qbittorrent,
            fetch_categories,
            fetch_feeds,
            fetch_rules,
            APIConnectionError,
            Conflict409Error
        )
        print("✓ All qBittorrent API components imported")
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        assert False, str(e)


def test_client_creation():
    """Test QBittorrentClient instantiation."""
    print("\n" + "="*60)
    print("Test 2: QBittorrentClient Creation")
    print("="*60)
    
    try:
        from src.qbittorrent_api import QBittorrentClient
        
        # Create a client instance (without connecting)
        client = QBittorrentClient(
            protocol='http',
            host='localhost',
            port='8080',
            username='admin',
            password='admin',
            verify_ssl=False,
            timeout=10
        )
        
        print(f"✓ Client created: {client.base_url}")
        print(f"✓ Verify param: {client.verify_param}")
        print(f"✓ Timeout: {client.timeout}s")
        return True
        
    except Exception as e:
        print(f"✗ Client creation failed: {e}")
        assert False, str(e)


def test_api_functions():
    """Test high-level API functions exist."""
    print("\n" + "="*60)
    print("Test 3: API Function Availability")
    print("="*60)
    
    try:
        from src.qbittorrent_api import (
            ping_qbittorrent,
            fetch_categories,
            fetch_feeds,
            fetch_rules
        )
        
        # Check function signatures
        import inspect
        
        funcs = {
            'ping_qbittorrent': ping_qbittorrent,
            'fetch_categories': fetch_categories,
            'fetch_feeds': fetch_feeds,
            'fetch_rules': fetch_rules
        }
        
        for name, func in funcs.items():
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            print(f"✓ {name}({', '.join(params[:5])}...)")
        
        return True
        
    except Exception as e:
        print(f"✗ API function test failed: {e}")
        assert False, str(e)


def test_exception_handling():
    """Test exception classes."""
    print("\n" + "="*60)
    print("Test 4: Exception Classes")
    print("="*60)
    
    try:
        from src.qbittorrent_api import APIConnectionError, Conflict409Error
        from src.constants import QBittorrentError, QBittorrentAuthenticationError
        
        # Test exception creation
        exc1 = APIConnectionError("Connection test")
        exc2 = Conflict409Error("Conflict test")
        exc3 = QBittorrentError("General error test")
        exc4 = QBittorrentAuthenticationError("Auth error test")
        
        print("✓ APIConnectionError created")
        print("✓ Conflict409Error created")
        print("✓ QBittorrentError created")
        print("✓ QBittorrentAuthenticationError created")
        
        return True
        
    except Exception as e:
        print(f"✗ Exception test failed: {e}")
        assert False, str(e)


def test_module_structure():
    """Test module exports and structure."""
    print("\n" + "="*60)
    print("Test 5: Module Structure")
    print("="*60)
    
    try:
        from src import qbittorrent_api
        
        # Check __all__ exports
        if hasattr(qbittorrent_api, '__all__'):
            exports = qbittorrent_api.__all__
            print(f"✓ Module exports {len(exports)} components:")
            for item in exports:
                print(f"  - {item}")
        
        # Check key constants
        constants = [
            'QBT_API_BASE',
            'QBT_AUTH_LOGIN',
            'QBT_APP_VERSION',
            'QBT_TORRENTS_CATEGORIES',
            'QBT_RSS_FEEDS'
        ]
        
        for const in constants:
            if hasattr(qbittorrent_api, const):
                value = getattr(qbittorrent_api, const)
                print(f"✓ {const} = {value}")
        
        return True
        
    except Exception as e:
        print(f"✗ Module structure test failed: {e}")
        assert False, str(e)


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print(" "*15 + "Phase 4: qBittorrent API Module Tests")
    print("="*70)
    
    tests = [
        test_qbittorrent_imports,
        test_client_creation,
        test_api_functions,
        test_exception_handling,
        test_module_structure
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test crashed: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All Phase 4 tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
