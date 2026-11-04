"""Self-update / full-uninstall tests (stdlib unittest, no network).

Owner-run: python3 -m unittest discover -s tests -v
All downloads are faked in memory; the checksum mismatch case must fail
closed and install nothing.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from collabai.updater import (
    expected_sha,
    install_version,
    parse_version,
    release_urls,
    run_uninstall_full,
    sha_ok,
)


def _tar_bytes(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _fetcher(tar_bytes: bytes):
    def fetch(url: str) -> bytes:
        if url.endswith(".sha256"):
            return f"{hashlib.sha256(tar_bytes).hexdigest()}  collabai.tar.gz\n".encode()
        return tar_bytes

    return fetch


class VersionTests(unittest.TestCase):
    def test_parse_and_compare(self):
        self.assertEqual(parse_version("v2.0.0"), (2, 0, 0))
        self.assertGreater(parse_version("2.0.1"), parse_version("2.0.0"))
        with self.assertRaises(ValueError):
            parse_version("2.0")
        with self.assertRaises(ValueError):
            parse_version("latest")

    def test_release_urls_https_only(self):
        tar_url, sha_url = release_urls("2.0.0")
        self.assertTrue(tar_url.startswith("https://github.com/wragorg/collabai/"))
        self.assertEqual(sha_url, tar_url + ".sha256")
        with self.assertRaises(ValueError):
            release_urls("../evil")


class InstallTests(unittest.TestCase):
    def test_install_writes_verified_shim(self):
        tar_bytes = _tar_bytes(
            {"collabai/__main__.py": "# entry\n", "collabai/__init__.py": "# pkg\n"}
        )
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            src = install_version("9.9.9", home=home, fetcher=_fetcher(tar_bytes))
            self.assertTrue((src / "collabai" / "__main__.py").exists())
            shim = home / ".local" / "bin" / "collabai"
            self.assertIn(str(src), shim.read_text(encoding="utf-8"))
            self.assertIn("python3 -m collabai", shim.read_text(encoding="utf-8"))

    def test_checksum_mismatch_installs_nothing(self):
        tar_bytes = _tar_bytes({"collabai/__main__.py": "# entry\n"})
        bad = _fetcher(tar_bytes)

        def lying_fetch(url: str) -> bytes:
            if url.endswith(".sha256"):
                return ("0" * 64 + "  collabai.tar.gz\n").encode()
            return bad(url)

        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            with self.assertRaises(ValueError):
                install_version("9.9.9", home=home, fetcher=lying_fetch)
            self.assertFalse((home / ".local" / "share" / "collabai-9.9.9").exists())
            self.assertFalse((home / ".local" / "bin" / "collabai").exists())

    def test_sha_helpers(self):
        data = b"payload"
        digest = hashlib.sha256(data).hexdigest()
        self.assertEqual(expected_sha(f"{digest}  file\n".encode()), digest)
        self.assertTrue(sha_ok(data, digest))
        self.assertFalse(sha_ok(data, "0" * 64))
        with self.assertRaises(ValueError):
            expected_sha(b"not-a-digest")


class UninstallTests(unittest.TestCase):
    def test_uninstall_asks_separately(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            home, root = base / "home", base / "proj"
            shim = home / ".local" / "bin" / "collabai"
            shim.parent.mkdir(parents=True)
            shim.write_text("#!/bin/sh\n", encoding="utf-8")
            version_dir = home / ".local" / "share" / "collabai-2.0.0"
            version_dir.mkdir(parents=True)
            state = root / ".collabai"
            state.mkdir(parents=True)
            answers = iter(["y", "n", "y"])  # shim yes, versions no, state yes
            code = run_uninstall_full(root, home=home, input_fn=lambda _label: next(answers))
            self.assertEqual(code, 0)
            self.assertFalse(shim.exists())
            self.assertTrue(version_dir.exists())
            self.assertFalse(state.exists())


if __name__ == "__main__":
    unittest.main()
