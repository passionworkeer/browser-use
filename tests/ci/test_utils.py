"""Tests for browser_use/skill_cli/utils.py"""

from pathlib import Path
from unittest.mock import patch

from browser_use.skill_cli.utils import (
	get_chrome_profile_path,
	get_chrome_user_data_dirs,
)


def _normalize_path(p: Path) -> str:
	"""Normalize a Path to forward-slash string for cross-platform test comparisons."""
	return p.as_posix()


class TestGetChromeUserDataDirs:
	"""Test get_chrome_user_data_dirs() correctly filters by is_dir()."""

	def test_linux_returns_only_existing_dirs(self):
		"""Only directories that the mocked is_dir reports as existing are returned.

		This test patches Path.is_dir with a tracking function that records all
		candidate paths checked and returns True only for a predefined set of
		Linux Chrome/Chromium user-data directories. The result should include
		only those mocked-as-existing directories.
		"""

		def fake_is_dir(self):
			# Use as_posix() for cross-platform path normalization
			path_str = self.as_posix()
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
		assert '/home/user/.config/BraveSoftware/Brave-Browser' not in result_strs
		assert '/home/user/.config/microsoft-edge' not in result_strs

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
					with patch(
						'browser_use.skill_cli.utils.os.environ.get',
						side_effect=lambda k, d=None: {
							'LOCALAPPDATA': 'C:\\Users\\user\\AppData\\Local',
						}.get(k, d),
					):
						result = get_chrome_user_data_dirs()

		result_strs = [_normalize_path(p) for p in result]
		assert 'C:/Users/user/AppData/Local/Google/Chrome/User Data' in result_strs
		assert 'C:/Users/user/AppData/Local/Chromium/User Data' not in result_strs


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
		"""On Linux with Brave executable, return Brave's own profile path."""
		with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
			result = get_chrome_profile_path(None, executable_path='/usr/bin/brave-browser')
		expected = str(Path.home() / '.config' / 'BraveSoftware' / 'Brave-Browser')
		assert result == expected

	def test_linux_edge_profile_path(self):
		"""On Linux with Microsoft Edge executable, return Edge's own profile path."""
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

	def test_macos_profile_path(self):
		"""On macOS, return the Chrome Application Support directory."""
		with patch('browser_use.skill_cli.utils.platform.system', return_value='Darwin'):
			result = get_chrome_profile_path(None)
		expected = str(Path.home() / 'Library' / 'Application Support' / 'Google' / 'Chrome')
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


class TestFindChromeExecutableLinux:
	"""Test find_chrome_executable() on Linux finds Brave and Edge in addition to Chrome/Chromium."""

	def test_finds_chromium_before_brave(self):
		"""Chrome/Chromium should be preferred over Brave when both are present."""
		with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
			with patch('browser_use.skill_cli.utils.subprocess.run') as mock_run:
				# Simulate chromium found first
				mock_run.side_effect = [
					# google-chrome: not found
					type('MockResult', (), {'returncode': 1})(),
					# google-chrome-stable: not found
					type('MockResult', (), {'returncode': 1})(),
					# chromium: found
					type('MockResult', (), {'returncode': 0, 'stdout': '/usr/bin/chromium'})(),
					# brave-browser: never reached
					type('MockResult', (), {'returncode': 1})(),
				]
				from browser_use.skill_cli.utils import find_chrome_executable

				result = find_chrome_executable()
		assert result == '/usr/bin/chromium'

	def test_finds_brave_when_chrome_not_present(self):
		"""Brave should be found when Chrome/Chromium are not installed."""
		with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
			with patch('browser_use.skill_cli.utils.subprocess.run') as mock_run:
				mock_run.side_effect = [
					type('MockResult', (), {'returncode': 1})(),  # google-chrome
					type('MockResult', (), {'returncode': 1})(),  # google-chrome-stable
					type('MockResult', (), {'returncode': 1})(),  # chromium
					type('MockResult', (), {'returncode': 1})(),  # chromium-browser
					type('MockResult', (), {'returncode': 0, 'stdout': '/usr/bin/brave-browser'})(),  # brave-browser found
				]
				from browser_use.skill_cli.utils import find_chrome_executable

				result = find_chrome_executable()
		assert result == '/usr/bin/brave-browser'

	def test_finds_microsoft_edge(self):
		"""Microsoft Edge should be found when present."""
		with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
			with patch('browser_use.skill_cli.utils.subprocess.run') as mock_run:
				mock_run.side_effect = [
					type('MockResult', (), {'returncode': 1})(),  # google-chrome
					type('MockResult', (), {'returncode': 1})(),  # google-chrome-stable
					type('MockResult', (), {'returncode': 1})(),  # chromium
					type('MockResult', (), {'returncode': 1})(),  # chromium-browser
					type('MockResult', (), {'returncode': 1})(),  # brave-browser
					type('MockResult', (), {'returncode': 0, 'stdout': '/usr/bin/microsoft-edge'})(),  # microsoft-edge found
				]
				from browser_use.skill_cli.utils import find_chrome_executable

				result = find_chrome_executable()
		assert result == '/usr/bin/microsoft-edge'

	def test_returns_none_when_no_browser_found(self):
		"""None should be returned when no browser is found."""
		with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
			with patch('browser_use.skill_cli.utils.subprocess.run') as mock_run:
				mock_run.side_effect = [
					type('MockResult', (), {'returncode': 1})(),
					type('MockResult', (), {'returncode': 1})(),
					type('MockResult', (), {'returncode': 1})(),
					type('MockResult', (), {'returncode': 1})(),
					type('MockResult', (), {'returncode': 1})(),
					type('MockResult', (), {'returncode': 1})(),
				]
				from browser_use.skill_cli.utils import find_chrome_executable

				result = find_chrome_executable()
		assert result is None


class TestListChromeProfiles:
	"""Test list_chrome_profiles() with executable_path=None (backward-compat) and with executable_path set."""

	def test_none_executable_reads_chrome_dir(self, tmp_path):
		"""When executable_path is None, list_chrome_profiles reads google-chrome directory."""
		from browser_use.skill_cli.utils import list_chrome_profiles

		# Create a fake Local State file under the default chrome dir
		chrome_dir = tmp_path / '.config' / 'google-chrome'
		chrome_dir.mkdir(parents=True)
		local_state = chrome_dir / 'Local State'
		local_state.write_text('{"profile":{"info_cache":{"Default":{"name":"Person 1"}}}}')

		with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
			with patch('browser_use.skill_cli.utils.get_chrome_profile_path') as mock_get_path:
				# When executable_path=None, get_chrome_profile_path returns google-chrome dir
				mock_get_path.return_value = str(chrome_dir)
				profiles = list_chrome_profiles(None)

		assert len(profiles) == 1
		assert profiles[0]['directory'] == 'Default'
		assert profiles[0]['name'] == 'Person 1'

	def test_chromium_executable_reads_chromium_dir(self, tmp_path):
		"""When executable_path points to Chromium, list_chrome_profiles reads chromium directory."""
		from browser_use.skill_cli.utils import list_chrome_profiles

		# Create a fake Local State file under the chromium dir
		chromium_dir = tmp_path / '.config' / 'chromium'
		chromium_dir.mkdir(parents=True)
		local_state = chromium_dir / 'Local State'
		local_state.write_text('{"profile":{"info_cache":{"Profile 1":{"name":"Work"}}}}')

		mock_home = tmp_path
		with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
			with patch.object(Path, 'home', return_value=mock_home):
				profiles = list_chrome_profiles('/usr/bin/chromium')

		assert len(profiles) == 1
		assert profiles[0]['directory'] == 'Profile 1'
		assert profiles[0]['name'] == 'Work'

	def test_missing_local_state_returns_empty(self):
		"""When Local State is missing, list_chrome_profiles returns an empty list."""
		from browser_use.skill_cli.utils import list_chrome_profiles

		# No Local State file anywhere
		with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
			with patch('browser_use.skill_cli.utils.get_chrome_profile_path') as mock_get_path:
				mock_get_path.return_value = '/nonexistent'
				profiles = list_chrome_profiles(None)

		assert profiles == []

	def test_brave_executable_reads_brave_dir(self, tmp_path):
		"""When executable_path points to Brave, list_chrome_profiles reads Brave's directory."""
		from browser_use.skill_cli.utils import list_chrome_profiles

		# Create a fake Local State file under the Brave directory
		brave_dir = tmp_path / '.config' / 'BraveSoftware' / 'Brave-Browser'
		brave_dir.mkdir(parents=True)
		local_state = brave_dir / 'Local State'
		local_state.write_text('{"profile":{"info_cache":{"Default":{"name":"Brave User"}}}}')

		mock_home = tmp_path
		with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
			with patch.object(Path, 'home', return_value=mock_home):
				profiles = list_chrome_profiles('/usr/bin/brave-browser')

		assert len(profiles) == 1
		assert profiles[0]['directory'] == 'Default'
		assert profiles[0]['name'] == 'Brave User'

	def test_edge_executable_reads_edge_dir(self, tmp_path):
		"""When executable_path points to Microsoft Edge, list_chrome_profiles reads Edge's directory."""
		from browser_use.skill_cli.utils import list_chrome_profiles

		# Create a fake Local State file under the Edge directory
		edge_dir = tmp_path / '.config' / 'microsoft-edge'
		edge_dir.mkdir(parents=True)
		local_state = edge_dir / 'Local State'
		local_state.write_text('{"profile":{"info_cache":{"Profile 1":{"name":"Work"}}}}')

		mock_home = tmp_path
		with patch('browser_use.skill_cli.utils.platform.system', return_value='Linux'):
			with patch.object(Path, 'home', return_value=mock_home):
				profiles = list_chrome_profiles('/usr/bin/microsoft-edge')

		assert len(profiles) == 1
		assert profiles[0]['directory'] == 'Profile 1'
		assert profiles[0]['name'] == 'Work'
