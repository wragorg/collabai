"""Installer shim regression test (stdlib unittest only). Owner-run: python3 -m unittest discover -s tests -v."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class InstallerShimTests(unittest.TestCase):
    def test_shim_runs_package_module_with_src_on_path(self):
        text = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("python3 -m collabai", text)
        self.assertIn('PYTHONPATH="%s:${PYTHONPATH:-}"', text)
        self.assertNotIn('collabai/__main__.py" "$@"', text)


if __name__ == "__main__":
    unittest.main()
