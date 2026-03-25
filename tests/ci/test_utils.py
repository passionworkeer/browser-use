"""Tests for browser_use/skill_cli/utils.py"""

import platform
from pathlib import Path
from unittest.mock import patch

import pytest

from browser_use.skill_cli.utils import (
    _get_browser_type,
    get_chrome_profile_path,
    get_chrome_user_data_dirs,
)


def _normalize_path(p: Path) -> str:
    """Normalize a Path to forward-slash string for cross-platform test comparisons."""
    return p.as_posix()


class TestGetChromeUserDataDirs:
    """Test get_chrome_user_data_dirs() correctly filters by is_dir()."""

    def test_linux_returns_only_existing_dirs(self):
        """Only directories that actually exist (is_dir returns True) are returned.

        The key issue this tests resolves: a naive mock that calls self.exists()
        inside the fake is_dir function causes infinite recursion because
        exists() internally uses is_dir(). The correct approach stores the real
        Path.is_dir method and calls it via a side_effect that bypasses the mock.

        Note: the Brave config path is ~/.config/BraveSoftware/Brave-Browser
        (NOT ~/.config/Brave/Brave-Browser). This test verifies both that the
        correct path is checked as a candidate AND that the wrong path is not.
        """
        def fake_is_dir(self):
            # Use as_posix() for cross-platform path normalization
            path_str = self.as_posix()
            # Only google-chrome and chromium exist; BraveSoftware/Brave-Browser
            # and the wrong Brave/Brave-Browser path do not exist
            existing = {
                '/home/user/.config/google-chrome',
                '/home/user/.config/chromium',
            }
            return path_str in existing

        mock_home = Path('/home/user')
        candidates_checked = []

        def tracking_is_dir(self):
            candidates_checked.append(str(self))
            return fake_is_dir(self)

        with patch.object(Path, 'home', return_value=mock_home):
            with patch.object(Path, 'is_dir', tracking_is_dir):
                with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
                    result = get_chrome_user_data_dirs()

        # Verify correct candidates were checked
        normalized_checked = [_normalize_path(Path(c)) for c in candidates_checked]
        assert '/home/user/.config/google-chrome' in normalized_checked
        assert '/home/user/.config/chromium' in normalized_checked
        assert '/home/user/.config/BraveSoftware/Brave-Browser' in normalized_checked
        assert '/home/user/.config/microsoft-edge' in normalized_checked

        # Only existing dirs should be in result
        result_strs = [_normalize_path(p) for p in result]
        assert '/home/user/.config/google-chrome' in result_strs
        assert '/home/user/.config/chromium' in result_strs
        # Correct Brave path not in result (doesn't exist in test)
        assert '/home/user/.config/BraveSoftware/Brave-Browser' not in result_strs
        # Wrong Brave path also not in result (not checked as candidate)
        assert '/home/user/.config/Brave/Brave-Browser' not in result_strs

    def test_linux_brave_software_dir_returned_when_exists(self):
        """When ~/.config/BraveSoftware/Brave-Browser exists, it is included in results."""
        def fake_is_dir(self):
            path_str = self.as_posix()
            existing = {
                '/home/user/.config/google-chrome',
                '/home/user/.config/BraveSoftware/Brave-Browser',
            }
            return path_str in existing

        mock_home = Path('/home/user')

        with patch.object(Path, 'home', return_value=mock_home):
            with patch.object(Path, 'is_dir', fake_is_dir):
                with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
                    result = get_chrome_user_data_dirs()

        result_strs = [_normalize_path(p) for p in result]
        assert '/home/user/.config/google-chrome' in result_strs
        assert '/home/user/.config/BraveSoftware/Brave-Browser' in result_strs
        # Wrong Brave path still not a candidate
        assert '/home/user/.config/Brave/Brave-Browser' not in result_strs

    def test_macos_returns_only_existing_dirs(self):
        """On macOS only existing directories under ~/Library/Application Support are returned."""
        def fake_is_dir(self):
            path_str = self.as_posix()
            existing = {'/home/user/Library/Application Support/Google/Chrome'}
            return path_str in existing

        mock_home = Path('/home/user')

        with patch.object(Path, 'home', return_value=mock_home):
            with patch.object(Path, 'is_dir', fake_is_dir):
                with patch('browser_use.skill_cli.utils.platform.system', return_value='Darwin'):
                    result = get_chrome_user_data_dirs()

        result_strs = [_normalize_path(p) for p in result]
        assert '/home/user/Library/Application Support/Google/Chrome' in result_strs
        assert '/home/user/Library/Application Support/Chromium' not in result_strs

    def test_windows_returns_only_existing_dirs(self):
        """On Windows only existing directories under %LOCALAPPDATA% are returned."""
        def fake_is_dir(self):
            path_str = _normalize_path(self)
            existing = {'C:/Users/user/AppData/Local/Google/Chrome/User Data'}
            return path_str in existing

        mock_home = Path('C:/Users/user')

        with patch.object(Path, 'home', return_value=mock_home):
            with patch.object(Path, 'is_dir', fake_is_dir):
                with patch('browser_use.skill_cli.utils.platform.system', return_value='Windows'):
                    with patch('browser_use.skill_cli.utils.os.environ.get', side_effect=lambda k, d=None: {
                        'LOCALAPPDATA': 'C:\\Users\\user\\AppData\\Local',
                    }.get(k, d)):
                        result = get_chrome_user_data_dirs()

        result_strs = [_normalize_path(p) for p in result]
        assert 'C:/Users/user/AppData/Local/Google/Chrome/User Data' in result_strs
        assert 'C:/Users/user/AppData/Local/Chromium/User Data' not in result_strs


class TestGetBrowserType:
    """Test _get_browser_type() correctly classifies browsers."""

    def test_none_returns_chrome(self):
        assert _get_browser_type(None) == 'chrome'

    def test_chromium_returns_chromium(self):
        assert _get_browser_type('/usr/bin/chromium') == 'chromium'
        assert _get_browser_type('/usr/bin/chromium-browser') == 'chromium'

    def test_google_chrome_returns_chrome(self):
        assert _get_browser_type('/usr/bin/google-chrome') == 'chrome'
        assert _get_browser_type('/usr/bin/google-chrome-stable') == 'chrome'

    def test_brave_returns_brave(self):
        assert _get_browser_type('/usr/bin/brave-browser') == 'brave'

    def test_edge_returns_edge(self):
        assert _get_browser_type('/usr/bin/microsoft-edge') == 'edge'

    def test_windows_chrome_returns_chrome(self):
        assert _get_browser_type('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe') == 'chrome'

    def test_windows_chromium_returns_chromium(self):
        assert _get_browser_type('C:\\Program Files\\Chromium\\Application\\chrome.exe') == 'chromium'

    def test_windows_brave_returns_brave(self):
        assert _get_browser_type('C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe') == 'brave'

    def test_windows_edge_returns_edge(self):
        assert _get_browser_type('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe') == 'edge'

    def test_macos_chrome_returns_chrome(self):
        assert _get_browser_type('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome') == 'chrome'

    def test_macos_chromium_returns_chromium(self):
        assert _get_browser_type('/Applications/Chromium.app/Contents/MacOS/Chromium') == 'chromium'

    def test_macos_brave_returns_brave(self):
        assert _get_browser_type('/Applications/Brave Browser.app/Contents/MacOS/Brave Browser') == 'brave'

    def test_macos_edge_returns_edge(self):
        assert _get_browser_type('/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge') == 'edge'


class TestGetChromeProfilePath:
    """Test get_chrome_profile_path() with the executable_path parameter on Linux."""

    def test_linux_chromium_profile_path(self):
        """On Linux with Chromium executable, return the Chromium profile path."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
            result = get_chrome_profile_path(None, executable_path='/usr/bin/chromium')
        expected = str(Path.home() / '.config' / 'chromium')
        assert result == expected

    def test_linux_chromium_browser_profile_path(self):
        """On Linux with chromium-browser executable, return the Chromium profile path."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
            result = get_chrome_profile_path(None, executable_path='/usr/bin/chromium-browser')
        expected = str(Path.home() / '.config' / 'chromium')
        assert result == expected

    def test_linux_google_chrome_profile_path(self):
        """On Linux with google-chrome executable, return the Google Chrome profile path."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
            result = get_chrome_profile_path(None, executable_path='/usr/bin/google-chrome')
        expected = str(Path.home() / '.config' / 'google-chrome')
        assert result == expected

    def test_linux_brave_profile_path(self):
        """On Linux with Brave executable, return the Brave profile path."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
            result = get_chrome_profile_path(None, executable_path='/usr/bin/brave-browser')
        expected = str(Path.home() / '.config' / 'BraveSoftware' / 'Brave-Browser')
        assert result == expected

    def test_linux_edge_profile_path(self):
        """On Linux with Edge executable, return the Edge profile path."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
            result = get_chrome_profile_path(None, executable_path='/usr/bin/microsoft-edge')
        expected = str(Path.home() / '.config' / 'microsoft-edge')
        assert result == expected

    def test_linux_no_executable_path_defaults_to_chrome(self):
        """On Linux with no executable_path, default to Google Chrome profile path."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
            result = get_chrome_profile_path(None, executable_path=None)
        expected = str(Path.home() / '.config' / 'google-chrome')
        assert result == expected

    def test_macos_brave_profile_path(self):
        """On macOS with Brave executable, return the Brave Application Support directory."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Darwin'):
            result = get_chrome_profile_path(None, executable_path='/Applications/Brave Browser.app/Contents/MacOS/Brave Browser')
        expected = str(Path.home() / 'Library' / 'Application Support' / 'BraveSoftware' / 'Brave-Browser')
        assert result == expected

    def test_macos_edge_profile_path(self):
        """On macOS with Edge executable, return the Edge Application Support directory."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Darwin'):
            result = get_chrome_profile_path(None, executable_path='/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge')
        expected = str(Path.home() / 'Library' / 'Application Support' / 'Microsoft Edge')
        assert result == expected

    def test_macos_chromium_profile_path(self):
        """On macOS with Chromium executable, return the Chromium Application Support directory."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Darwin'):
            result = get_chrome_profile_path(None, executable_path='/Applications/Chromium.app/Contents/MacOS/Chromium')
        expected = str(Path.home() / 'Library' / 'Application Support' / 'Chromium')
        assert result == expected

    def test_macos_profile_path(self):
        """On macOS, return the Chrome Application Support directory."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Darwin'):
            result = get_chrome_profile_path(None)
        expected = str(Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome')
        assert result == expected

    def test_windows_brave_profile_path(self):
        """On Windows with Brave executable, return the Brave User Data directory."""
        import os
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Windows'):
            result = get_chrome_profile_path(None, executable_path='C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe')
        local_app_data = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))
        expected = str(Path(local_app_data) / 'BraveSoftware' / 'Brave-Browser' / 'User Data')
        assert result == expected

    def test_windows_edge_profile_path(self):
        """On Windows with Edge executable, return the Edge User Data directory."""
        import os
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Windows'):
            result = get_chrome_profile_path(None, executable_path='C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe')
        local_app_data = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))
        expected = str(Path(local_app_data) / 'Microsoft' / 'Edge' / 'User Data')
        assert result == expected

    def test_windows_chromium_profile_path(self):
        """On Windows with Chromium executable, return the Chromium User Data directory."""
        import os
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Windows'):
            result = get_chrome_profile_path(None, executable_path='C:\\Program Files\\Chromium\\Application\\chrome.exe')
        local_app_data = os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))
        expected = str(Path(local_app_data) / 'Chromium' / 'User Data')
        assert result == expected

    def test_windows_profile_path(self):
        """On Windows, return the Chrome User Data directory under %LOCALAPPDATA%."""
        import os
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Windows'):
            result = get_chrome_profile_path(None)
        expected = os.path.expandvars(r'%LocalAppData%\Google\Chrome\User Data')
        assert result == expected

    def test_named_profile_returns_profile_name(self):
        """When a profile name is given, return it directly (Chrome uses it as subdirectory)."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
            result = get_chrome_profile_path('work-profile')
        assert result == 'work-profile'

    def test_named_profile_macos(self):
        """On macOS, named profile returns the profile name directly."""
        with patch('browser_use.skill_cli.utils.platform.system', return_value='Darwin'):
            result = get_chrome_profile_path('my-profile')
        assert result == 'my-profile'


class TestListChromeProfiles:
    """Test list_chrome_profiles() with executable_path parameter on Linux.

    These tests verify that profile listing uses the correct user-data directory
    based on the detected browser executable, rather than defaulting to Chrome.
    """

    def test_linux_chromium_uses_correct_profile_dir(self):
        """On Linux with Chromium executable, list_chrome_profiles reads from ~/.config/chromium."""
        from browser_use.skill_cli.utils import list_chrome_profiles

        chromium_user_data = '/home/user/.config/chromium'
        chromium_local_state = f'{chromium_user_data}/Local State'
        fake_local_state = {
            'profile': {
                'info_cache': {
                    'Default': {'name': 'Person 1'},
                    'Profile 1': {'name': 'Work'},
                }
            }
        }

        orig_exists = Path.exists

        def fake_exists(self):
            return self.as_posix() == chromium_local_state

        orig_open = open

        def fake_open(path, *args, **kwargs):
            path_str = path.as_posix() if hasattr(path, 'as_posix') else str(path)
            if path_str == chromium_local_state:
                import io
                import json as json_mod
                return io.StringIO(json_mod.dumps(fake_local_state))
            return orig_open(path, *args, **kwargs)

        with patch.object(Path, 'exists', fake_exists):
            with patch('builtins.open', fake_open):
                with patch('browser_use.skill_cli.utils.get_chrome_profile_path', return_value=chromium_user_data):
                    result = list_chrome_profiles(executable_path='/usr/bin/chromium')

        assert len(result) == 2
        assert result[0]['directory'] == 'Default'
        assert result[1]['directory'] == 'Profile 1'

    def test_linux_brave_uses_correct_profile_dir(self):
        """On Linux with Brave executable, list_chrome_profiles reads from ~/.config/BraveSoftware/Brave-Browser."""
        from browser_use.skill_cli.utils import list_chrome_profiles

        brave_user_data = '/home/user/.config/BraveSoftware/Brave-Browser'
        brave_local_state = f'{brave_user_data}/Local State'
        fake_local_state = {
            'profile': {
                'info_cache': {
                    'Default': {'name': 'Person 1'},
                    'Profile 1': {'name': 'Brave Profile'},
                }
            }
        }

        orig_exists = Path.exists
        orig_open = open

        def fake_exists(self):
            return self.as_posix() == brave_local_state

        def fake_open(path, *args, **kwargs):
            path_str = path.as_posix() if hasattr(path, 'as_posix') else str(path)
            if path_str == brave_local_state:
                import io
                import json as json_mod
                return io.StringIO(json_mod.dumps(fake_local_state))
            return orig_open(path, *args, **kwargs)

        with patch.object(Path, 'exists', fake_exists):
            with patch('builtins.open', fake_open):
                with patch('browser_use.skill_cli.utils.get_chrome_profile_path', return_value=brave_user_data):
                    result = list_chrome_profiles(executable_path='/usr/bin/brave-browser')

        assert len(result) == 2

    def test_linux_edge_uses_correct_profile_dir(self):
        """On Linux with Edge executable, list_chrome_profiles reads from ~/.config/microsoft-edge."""
        from browser_use.skill_cli.utils import list_chrome_profiles

        edge_user_data = '/home/user/.config/microsoft-edge'
        edge_local_state = f'{edge_user_data}/Local State'
        fake_local_state = {
            'profile': {
                'info_cache': {
                    'Default': {'name': 'Person 1'},
                }
            }
        }

        orig_exists = Path.exists
        orig_open = open

        def fake_exists(self):
            return self.as_posix() == edge_local_state

        def fake_open(path, *args, **kwargs):
            path_str = path.as_posix() if hasattr(path, 'as_posix') else str(path)
            if path_str == edge_local_state:
                import io
                import json as json_mod
                return io.StringIO(json_mod.dumps(fake_local_state))
            return orig_open(path, *args, **kwargs)

        with patch.object(Path, 'exists', fake_exists):
            with patch('builtins.open', fake_open):
                with patch('browser_use.skill_cli.utils.get_chrome_profile_path', return_value=edge_user_data):
                    result = list_chrome_profiles(executable_path='/usr/bin/microsoft-edge')

        assert len(result) == 1

    def test_linux_chrome_uses_google_chrome_dir(self):
        """On Linux with Google Chrome executable, list_chrome_profiles reads from ~/.config/google-chrome."""
        from browser_use.skill_cli.utils import list_chrome_profiles

        chrome_user_data = '/home/user/.config/google-chrome'
        chrome_local_state = f'{chrome_user_data}/Local State'
        fake_local_state = {
            'profile': {
                'info_cache': {
                    'Default': {'name': 'Person 1'},
                }
            }
        }

        orig_exists = Path.exists
        orig_open = open

        def fake_exists(self):
            return self.as_posix() == chrome_local_state

        def fake_open(path, *args, **kwargs):
            path_str = path.as_posix() if hasattr(path, 'as_posix') else str(path)
            if path_str == chrome_local_state:
                import io
                import json as json_mod
                return io.StringIO(json_mod.dumps(fake_local_state))
            return orig_open(path, *args, **kwargs)

        with patch.object(Path, 'exists', fake_exists):
            with patch('builtins.open', fake_open):
                with patch('browser_use.skill_cli.utils.get_chrome_profile_path', return_value=chrome_user_data):
                    result = list_chrome_profiles(executable_path='/usr/bin/google-chrome')

        assert len(result) == 1

    def test_explicit_user_data_dir_overrides_executable_path(self):
        """When user_data_dir is provided, it is used regardless of executable_path."""
        from browser_use.skill_cli.utils import list_chrome_profiles

        explicit_dir = '/custom/path/Chrome/User Data'
        explicit_local_state = f'{explicit_dir}/Local State'
        fake_local_state = {
            'profile': {
                'info_cache': {
                    'Default': {'name': 'Custom'},
                    'Profile 1': {'name': 'Work'},
                }
            }
        }

        orig_exists = Path.exists
        orig_open = open

        def fake_exists(self):
            return self.as_posix() == explicit_local_state

        def fake_open(path, *args, **kwargs):
            path_str = path.as_posix() if hasattr(path, 'as_posix') else str(path)
            if path_str == explicit_local_state:
                import io
                import json as json_mod
                return io.StringIO(json_mod.dumps(fake_local_state))
            return orig_open(path, *args, **kwargs)

        with patch.object(Path, 'exists', fake_exists):
            with patch('builtins.open', fake_open):
                # Chromium path passed but explicit dir should be used instead
                result = list_chrome_profiles(
                    user_data_dir=explicit_dir,
                    executable_path='/usr/bin/chromium',
                )

        assert len(result) == 2

    def test_no_local_state_returns_empty(self):
        """When Local State does not exist, list_chrome_profiles returns an empty list."""
        from browser_use.skill_cli.utils import list_chrome_profiles

        def always_false(self):
            return False

        with patch.object(Path, 'exists', always_false):
            with patch('browser_use.skill_cli.utils.get_chrome_profile_path', return_value='/home/user/.config/chromium'):
                result = list_chrome_profiles(executable_path='/usr/bin/chromium')

        assert result == []

    def test_browser_session_list_chrome_profiles_auto_detect(self):
        """BrowserSession.list_chrome_profiles auto-detects executable when neither arg is given."""
        from browser_use.browser.session import BrowserSession

        chrome_user_data = '/home/user/.config/google-chrome'
        chrome_local_state = f'{chrome_user_data}/Local State'
        fake_local_state = {
            'profile': {
                'info_cache': {
                    'Default': {'name': 'Person 1'},
                }
            }
        }

        orig_exists = Path.exists
        orig_open = open

        def fake_exists(self):
            return self.as_posix() == chrome_local_state

        def fake_open(path, *args, **kwargs):
            path_str = path.as_posix() if hasattr(path, 'as_posix') else str(path)
            if path_str == chrome_local_state:
                import io
                import json as json_mod
                return io.StringIO(json_mod.dumps(fake_local_state))
            return orig_open(path, *args, **kwargs)

        with patch.object(Path, 'exists', fake_exists):
            with patch('builtins.open', fake_open):
                with patch('browser_use.skill_cli.utils.find_chrome_executable', return_value='/usr/bin/google-chrome'):
                    with patch('browser_use.skill_cli.utils.get_chrome_profile_path', return_value=chrome_user_data):
                        result = BrowserSession.list_chrome_profiles()

        assert len(result) == 1
        assert result[0]['directory'] == 'Default'

    def test_browser_session_list_chrome_profiles_with_executable_path(self):
        """BrowserSession.list_chrome_profiles with executable_path bypasses auto-detection."""
        from browser_use.browser.session import BrowserSession

        chromium_user_data = '/home/user/.config/chromium'
        chromium_local_state = f'{chromium_user_data}/Local State'
        fake_local_state = {
            'profile': {
                'info_cache': {
                    'Default': {'name': 'Person 1'},
                    'Profile 1': {'name': 'Work'},
                }
            }
        }

        orig_exists = Path.exists
        orig_open = open

        def fake_exists(self):
            return self.as_posix() == chromium_local_state

        def fake_open(path, *args, **kwargs):
            path_str = path.as_posix() if hasattr(path, 'as_posix') else str(path)
            if path_str == chromium_local_state:
                import io
                import json as json_mod
                return io.StringIO(json_mod.dumps(fake_local_state))
            return orig_open(path, *args, **kwargs)

        with patch.object(Path, 'exists', fake_exists):
            with patch('builtins.open', fake_open):
                # Pass executable_path directly — should NOT call find_chrome_executable
                with patch('browser_use.skill_cli.utils.find_chrome_executable') as mock_find:
                    with patch('browser_use.skill_cli.utils.get_chrome_profile_path', return_value=chromium_user_data):
                        result = BrowserSession.list_chrome_profiles(executable_path='/usr/bin/chromium')

        mock_find.assert_not_called()
        assert len(result) == 2
