"""Windows list_ports fallback: venv subprocess when host Python lacks pyserial."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server


class TestListPortsWindowsFallback(unittest.TestCase):
    def test_venv_subprocess_runs_when_pyserial_missing_on_host(self):
        if not server._venv_python_path():
            self.skipTest(".venv python not present")

        with mock.patch.object(server, "_comports_via_pyserial", side_effect=ImportError("no pyserial")):
            with mock.patch.object(server, "_comports_via_venv_site_packages", return_value=None):
                ports = server._list_ports_windows()

        self.assertIsInstance(ports, list)

    def test_venv_subprocess_helper_direct(self):
        if not server._venv_python_path():
            self.skipTest(".venv python not present")

        ports = server._comports_via_venv_subprocess()
        self.assertIsNotNone(ports)
        self.assertIsInstance(ports, list)


if __name__ == "__main__":
    unittest.main()
