"""Dry tests for editor_ctl setup subcommand (no clone, no servers)."""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import editor_ctl


class TestSetupCommand(unittest.TestCase):
    def test_setup_constants(self):
        self.assertTrue(editor_ctl.REPO_CLONE_URL.endswith("CYD_TD_Controller.git"))
        self.assertEqual(editor_ctl.CLONE_DIRNAME, "CYD_TD_Controller")

    def test_setup_returns_json_with_ok(self):
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            [sys.executable, os.path.join(repo, "editor_ctl.py"), "setup"],
            capture_output=True,
            text=True,
            cwd=repo,
            check=False,
            timeout=600,
        )
        data = json.loads(result.stdout.strip())
        self.assertIn("ok", data)
        self.assertIn("setup_ready", data)
        self.assertIn("missing", data)
        self.assertFalse(data.get("cloned"))
        # setup must not start servers; running may be true if already up from a prior session


if __name__ == "__main__":
    unittest.main()
