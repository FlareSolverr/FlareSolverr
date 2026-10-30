import os
import shutil
import signal
import stat
import sys
import tempfile
import time
import unittest
from unittest import mock

from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
from selenium.webdriver.common.service import Service
from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver

import sessions
import undetected_chromedriver as uc
import utils

# Stand-in for a stalled Chrome: it ignores SIGTERM, writes into its profile
# and forks a child (like a renderer) that ignores SIGTERM too. The pids are
# written to a file so the test can check that nothing is left behind.
FAKE_BROWSER = """#!{python}
import os, signal, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
profile = [a.split('=', 1)[1] for a in sys.argv if a.startswith('--user-data-dir=')][0]
child = os.fork()
if child == 0:
    while True:
        time.sleep(1)
with open(os.path.join(profile, 'Local State'), 'w') as f:
    f.write('{{}}')
with open({pid_file!r} + '.tmp', 'w') as f:
    f.write('%d %d %s' % (os.getpid(), child, profile))
os.rename({pid_file!r} + '.tmp', {pid_file!r})
while True:
    time.sleep(1)
"""


def _is_alive(pid: int) -> bool:
    try:
        with open('/proc/%d/stat' % pid) as f:
            # a zombie is already dead, it is just waiting for its parent
            return f.read().rsplit(')', 1)[1].split()[0] != 'Z'
    except FileNotFoundError:
        return False
    except OSError:
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@unittest.skipUnless(sys.platform.startswith('linux'), 'requires Linux process groups and /proc')
class TestBrowserCleanupOnStartupFailure(unittest.TestCase):

    def setUp(self):
        self.work_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.work_dir, True)
        self.pid_file = os.path.join(self.work_dir, 'pids')
        self.browser = os.path.join(self.work_dir, 'chrome')
        with open(self.browser, 'w') as f:
            f.write(FAKE_BROWSER.format(python=sys.executable, pid_file=self.pid_file))
        os.chmod(self.browser, stat.S_IRWXU)
        self.leaked = []
        self.addCleanup(self._kill_leftovers)

        # never download or patch a real chromedriver
        patcher = mock.MagicMock(version_main=None, executable_path=self.browser)
        self._patch(mock.patch.object(uc, 'Patcher', return_value=patcher))

    def _patch(self, patcher):
        patcher.start()
        self.addCleanup(patcher.stop)

    def _kill_leftovers(self):
        for pid in self.leaked:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def _start_chrome(self):
        options = uc.ChromeOptions()
        uc.Chrome(options=options, browser_executable_path=self.browser,
                  driver_executable_path=self.browser)

    def _launched_browser(self):
        deadline = time.time() + 10
        while not os.path.exists(self.pid_file):
            if time.time() > deadline:
                self.fail('the fake browser was never started')
            time.sleep(0.05)
        with open(self.pid_file) as f:
            browser_pid, child_pid, profile = f.read().split(' ', 2)
        self.leaked = [int(browser_pid), int(child_pid)]
        return int(browser_pid), int(child_pid), profile

    def _assert_nothing_left(self):
        browser_pid, child_pid, profile = self._launched_browser()
        deadline = time.time() + 15
        while (_is_alive(browser_pid) or _is_alive(child_pid)) and time.time() < deadline:
            time.sleep(0.1)
        self.assertFalse(_is_alive(browser_pid), 'the browser process was left running')
        self.assertFalse(_is_alive(child_pid), 'a child process of the browser was left running')
        self.assertFalse(os.path.exists(profile), 'the temporary profile was not removed')

    def _wait_for_browser(self, *args, **kwargs):
        # let the browser come up before failing, like chromedriver does
        self._launched_browser()

    def test_session_not_created(self):
        # "session not created: cannot connect to chrome" raised by chromedriver
        def new_session(*args, **kwargs):
            self._wait_for_browser()
            raise SessionNotCreatedException('session not created: cannot connect to chrome at 127.0.0.1:1')

        self._patch(mock.patch.object(Service, 'start', autospec=True))
        self._patch(mock.patch.object(RemoteWebDriver, '__init__', side_effect=new_session, autospec=True))
        with self.assertRaises(SessionNotCreatedException):
            self._start_chrome()
        self._assert_nothing_left()

    def test_service_not_started(self):
        # "Can not connect to the Service /app/chromedriver" raised before the session exists
        def start_service(*args, **kwargs):
            self._wait_for_browser()
            raise WebDriverException('Can not connect to the Service /app/chromedriver')

        self._patch(mock.patch.object(Service, 'start', side_effect=start_service, autospec=True))
        with self.assertRaises(WebDriverException):
            self._start_chrome()
        self._assert_nothing_left()


class TestWebDriverCleanup(unittest.TestCase):

    def test_proxy_extension_removed_when_chrome_fails(self):
        created = []

        def create_proxy_extension(proxy):
            created.append(tempfile.mkdtemp())
            return created[0]

        with mock.patch.object(utils, 'create_proxy_extension', side_effect=create_proxy_extension), \
                mock.patch.object(utils, 'get_config_headless', return_value=False), \
                mock.patch.object(utils, 'get_chrome_exe_path', return_value='/usr/bin/chromium'), \
                mock.patch.object(utils, 'get_chrome_major_version', return_value='130'), \
                mock.patch.object(uc, 'Chrome', side_effect=SessionNotCreatedException('session not created')):
            with self.assertRaises(SessionNotCreatedException):
                utils.get_webdriver({'url': 'http://127.0.0.1:8888', 'username': 'user', 'password': 'pass'})
        self.assertEqual(1, len(created))
        self.assertFalse(os.path.exists(created[0]))

    def test_driver_quit_when_setup_after_start_fails(self):
        exists = os.path.exists
        driver = mock.MagicMock()
        driver.patcher.data_path = '/nonexistent/data'
        driver.patcher.exe_name = 'chromedriver'
        driver.patcher.executable_path = '/nonexistent/tmp/chromedriver'
        with mock.patch.object(utils, 'get_config_headless', return_value=False), \
                mock.patch.object(utils, 'get_chrome_exe_path', return_value='/usr/bin/chromium'), \
                mock.patch.object(utils, 'get_chrome_major_version', return_value='130'), \
                mock.patch.object(utils, 'PATCHED_DRIVER_PATH', None), \
                mock.patch.object(uc, 'Chrome', return_value=driver), \
                mock.patch.object(utils.shutil, 'copy', side_effect=OSError('No space left on device')), \
                mock.patch.object(utils.os.path, 'exists', side_effect=lambda p: p != '/app/chromedriver' and exists(p)):
            with self.assertRaises(OSError):
                utils.get_webdriver()
        driver.quit.assert_called_once()

    def test_session_destroy_quits_even_if_close_fails(self):
        driver = mock.MagicMock()
        driver.close.side_effect = WebDriverException('disconnected: not connected to DevTools')
        storage = sessions.SessionsStorage()
        storage.sessions['id'] = sessions.Session('id', driver, None)
        with mock.patch.object(utils, 'PLATFORM_VERSION', 'nt'):
            with self.assertRaises(WebDriverException):
                storage.destroy('id')
        driver.quit.assert_called_once()
        self.assertFalse(storage.exists('id'))


if __name__ == '__main__':
    unittest.main()
