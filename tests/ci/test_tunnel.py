"""Tests for tunnel module - cloudflared binary management."""

from unittest.mock import MagicMock, patch

import pytest

from browser_use.skill_cli.tunnel import TunnelManager, get_tunnel_manager


@pytest.fixture
def tunnel_manager():
	"""Create a fresh TunnelManager instance for testing."""
	return TunnelManager()


def test_tunnel_manager_system_cloudflared(tunnel_manager):
	"""Test that system cloudflared is found."""
	with patch('shutil.which', return_value='/usr/local/bin/cloudflared'):
		binary_path = tunnel_manager.get_binary_path()
		assert binary_path == '/usr/local/bin/cloudflared'


def test_tunnel_manager_caches_result(tunnel_manager):
	"""Test that binary path is cached after first call."""
	with patch('shutil.which', return_value='/usr/local/bin/cloudflared'):
		path1 = tunnel_manager.get_binary_path()
		# Reset shutil.which to ensure it's not called again
		with patch('shutil.which', side_effect=Exception('Should be cached')):
			path2 = tunnel_manager.get_binary_path()
		assert path1 == path2


def test_tunnel_manager_not_installed(tunnel_manager):
	"""Test that RuntimeError is raised when cloudflared not found."""
	with patch('shutil.which', return_value=None):
		with pytest.raises(RuntimeError) as exc_info:
			tunnel_manager.get_binary_path()
		assert 'cloudflared not installed' in str(exc_info.value)


def test_tunnel_manager_is_available_cached(tunnel_manager):
	"""Test is_available check with cached binary path."""
	tunnel_manager._binary_path = '/usr/local/bin/cloudflared'
	assert tunnel_manager.is_available() is True


def test_tunnel_manager_is_available_system(tunnel_manager):
	"""Test is_available check finds system cloudflared."""
	with patch('shutil.which', return_value='/usr/local/bin/cloudflared'):
		assert tunnel_manager.is_available() is True


def test_tunnel_manager_is_available_not_found(tunnel_manager):
	"""Test is_available when cloudflared not found."""
	with patch('shutil.which', return_value=None):
		assert tunnel_manager.is_available() is False


def test_tunnel_manager_status_installed(tunnel_manager):
	"""Test get_status returns correct info when cloudflared installed."""
	with patch('shutil.which', return_value='/usr/local/bin/cloudflared'):
		status = tunnel_manager.get_status()
		assert status['available'] is True
		assert status['source'] == 'system'
		assert status['path'] == '/usr/local/bin/cloudflared'


def test_tunnel_manager_status_not_found(tunnel_manager):
	"""Test get_status when cloudflared not found."""
	with patch('shutil.which', return_value=None):
		status = tunnel_manager.get_status()
		assert status['available'] is False
		assert status['source'] is None
		assert 'not installed' in status['note']


def test_get_tunnel_manager_singleton():
	"""Test that get_tunnel_manager returns a singleton."""
	# Reset the global singleton
	import browser_use.skill_cli.tunnel as tunnel_module

	tunnel_module._tunnel_manager = None

	mgr1 = get_tunnel_manager()
	mgr2 = get_tunnel_manager()
	assert mgr1 is mgr2


# =============================================================================
# Tests for _kill_process
# =============================================================================
import sys


class TestKillProcessWindows:
	"""Tests for _kill_process on Windows.

	These tests patch ctypes.windll (with create=True so they work on non-Windows)
	and sys.platform to exercise the Windows code path in CI without skipping.
	time.sleep is also mocked to avoid test slowness from retry loops.
	"""

	@staticmethod
	def test_kill_process_windows_success_exits_immediately():
		"""Test Windows path: TerminateProcess succeeds and process exits immediately."""
		import ctypes

		from browser_use.skill_cli.tunnel import _kill_process

		mock_handle = MagicMock()
		mock_kernel32 = MagicMock()
		mock_kernel32.OpenProcess.return_value = mock_handle
		mock_kernel32.TerminateProcess.return_value = True
		mock_windll = MagicMock()
		mock_windll.kernel32 = mock_kernel32

		with patch.object(ctypes, 'windll', mock_windll, create=True):
			with patch('browser_use.skill_cli.tunnel.sys.platform', 'win32'):
				with patch('browser_use.skill_cli.tunnel.time.sleep'):
					with patch('browser_use.skill_cli.tunnel._is_process_alive', return_value=False):
						result = _kill_process(1234)

		assert result is True
		mock_kernel32.OpenProcess.assert_called_once_with(0x0001, False, 1234)
		mock_kernel32.TerminateProcess.assert_called_once_with(mock_handle, 1)
		mock_kernel32.CloseHandle.assert_called_once_with(mock_handle)

	@staticmethod
	def test_kill_process_windows_success_waits_for_exit():
		"""Test Windows path: TerminateProcess succeeds but process requires waiting."""
		import ctypes

		from browser_use.skill_cli.tunnel import _kill_process

		mock_handle = MagicMock()
		mock_kernel32 = MagicMock()
		mock_kernel32.OpenProcess.return_value = mock_handle
		mock_kernel32.TerminateProcess.return_value = True
		mock_windll = MagicMock()
		mock_windll.kernel32 = mock_kernel32

		# Process still alive for first 3 checks, then exits
		call_count = [0]

		def fake_is_alive(pid):
			call_count[0] += 1
			return call_count[0] <= 3

		with patch.object(ctypes, 'windll', mock_windll, create=True):
			with patch('browser_use.skill_cli.tunnel.sys.platform', 'win32'):
				with patch('browser_use.skill_cli.tunnel.time.sleep'):
					with patch('browser_use.skill_cli.tunnel._is_process_alive', side_effect=fake_is_alive):
						result = _kill_process(1234)

		assert result is True
		assert call_count[0] == 4  # 3 alive checks + 1 exit
		mock_kernel32.CloseHandle.assert_called_once_with(mock_handle)

	@staticmethod
	def test_kill_process_windows_open_process_returns_null():
		"""Test Windows path: OpenProcess returns NULL handle (process not found)."""
		import ctypes

		from browser_use.skill_cli.tunnel import _kill_process

		mock_kernel32 = MagicMock()
		mock_kernel32.OpenProcess.return_value = None
		mock_windll = MagicMock()
		mock_windll.kernel32 = mock_kernel32

		with patch.object(ctypes, 'windll', mock_windll, create=True):
			with patch('browser_use.skill_cli.tunnel.sys.platform', 'win32'):
				with patch('browser_use.skill_cli.tunnel.time.sleep'):
					result = _kill_process(9999)

		assert result is False
		mock_kernel32.OpenProcess.assert_called_once()

	@staticmethod
	def test_kill_process_windows_terminate_fails():
		"""Test Windows path: TerminateProcess returns False."""
		import ctypes

		from browser_use.skill_cli.tunnel import _kill_process

		mock_handle = MagicMock()
		mock_kernel32 = MagicMock()
		mock_kernel32.OpenProcess.return_value = mock_handle
		mock_kernel32.TerminateProcess.return_value = False
		mock_windll = MagicMock()
		mock_windll.kernel32 = mock_kernel32

		with patch.object(ctypes, 'windll', mock_windll, create=True):
			with patch('browser_use.skill_cli.tunnel.sys.platform', 'win32'):
				with patch('browser_use.skill_cli.tunnel.time.sleep'):
					result = _kill_process(1234)

		assert result is False
		mock_kernel32.CloseHandle.assert_called_once_with(mock_handle)


class TestKillProcessUnix:
	"""Tests for _kill_process on Unix (non-Windows)."""

	def test_kill_process_unix_sigterm_kills_immediately(self):
		"""Test Unix path: SIGTERM kills process immediately."""
		from browser_use.skill_cli.tunnel import _kill_process

		original_platform = sys.platform

		try:
			sys.platform = 'linux'

			with patch('os.kill') as mock_kill:
				with patch('browser_use.skill_cli.tunnel._is_process_alive') as mock_is_alive:
					mock_is_alive.return_value = False  # Process exits immediately

					result = _kill_process(1234)

			assert result is True
			mock_kill.assert_called_once_with(1234, 15)  # 15 = SIGTERM
			assert mock_is_alive.call_count == 1
		finally:
			sys.platform = original_platform

	def test_kill_process_unix_sigkill_after_grace_period(self):
		"""Test Unix path: SIGKILL sent after SIGTERM grace period expires."""
		from browser_use.skill_cli.tunnel import _kill_process

		original_platform = sys.platform

		try:
			sys.platform = 'linux'

			call_count = [0]

			def fake_is_alive(pid):
				call_count[0] += 1
				return True  # Always alive

			with patch('os.kill') as mock_kill:
				with patch('browser_use.skill_cli.tunnel.time.sleep'):
					with patch('browser_use.skill_cli.tunnel._is_process_alive', side_effect=fake_is_alive):
						result = _kill_process(1234)

			assert result is True
			# Should have sent SIGTERM first, then SIGKILL after 10 sleeps
			assert mock_kill.call_count == 2
			mock_kill.assert_any_call(1234, 15)  # SIGTERM
			mock_kill.assert_any_call(1234, 9)  # SIGKILL
			assert call_count[0] == 10  # 10 alive checks during grace period (then SIGKILL)
		finally:
			sys.platform = original_platform

	def test_kill_process_unix_process_not_found(self):
		"""Test Unix path: ProcessLookupError when process doesn't exist."""
		from browser_use.skill_cli.tunnel import _kill_process

		original_platform = sys.platform

		try:
			sys.platform = 'linux'

			with patch('os.kill', side_effect=ProcessLookupError('No such process')):
				result = _kill_process(9999)

			assert result is False
		finally:
			sys.platform = original_platform
