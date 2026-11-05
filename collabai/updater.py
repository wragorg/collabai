"""Self-update / full uninstall for installed copies (stdlib only).

`collabai --update` downloads a release tarball and its `.sha256` over
HTTPS only, verifies the checksum fail-closed before extracting (same
contract as install.sh), swaps the version directory under
`~/.local/share/`, and rewrites the `~/.local/bin/collabai` shim. The old
version directory and shim are restored if anything fails mid-swap.

`collabai --uninstall` asks separately about the shim, the installed
version directories, and private `.collabai/` state in the current
project, then removes only what was approved. The plain `uninstall`
subcommand still removes private state only.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import ssl
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

OWNER = "wragorg"
REPO = "collabai"
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def parse_version(text: str) -> tuple[int, int, int]:
    raw = str(text or "").strip().lstrip("v")
    if not _VERSION_RE.match(raw):
        raise ValueError(f"bad version: {text!r} (want X.Y.Z)")
    major, minor, patch = raw.split(".")
    return int(major), int(minor), int(patch)


def release_urls(version: str) -> tuple[str, str]:
    parse_version(version)
    base = (
        f"https://github.com/{OWNER}/{REPO}/releases/download/"
        f"v{version}/collabai-{version}.tar.gz"
    )
    return base, base + ".sha256"


# Same CA fallback as meta_ai: point OpenSSL at a bundle that already
# exists on the machine (macOS ships /etc/ssl/cert.pem). Verification on.
_CAFILE_CANDIDATES = (
    "/etc/ssl/cert.pem",
    "/etc/ssl/certs/ca-certificates.crt",
    "/opt/homebrew/etc/ca-certificates/cert.pem",
    "/usr/local/etc/ca-certificates/cert.pem",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/usr/local/etc/openssl@3/cert.pem",
)


def _fallback_cafile() -> str | None:
    env = os.environ.get("SSL_CERT_FILE", "").strip()
    if env and Path(env).exists():
        return env
    for cand in _CAFILE_CANDIDATES:
        if Path(cand).exists():
            return cand
    try:
        import certifi

        return certifi.where()
    except Exception:
        return None


def _fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-HTTPS URL: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "collabai-updater"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as exc:
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        if not isinstance(reason, ssl.SSLCertVerificationError):
            raise
        cafile = _fallback_cafile()
        if cafile is None:
            raise
        ctx = ssl.create_default_context(cafile=cafile)
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return resp.read()


def latest_version(fetcher=None) -> str:
    fetch = fetcher or _fetch
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
    obj = json.loads(fetch(url).decode("utf-8"))
    tag = str(obj.get("tag_name", "")).strip()
    parse_version(tag)
    return tag.lstrip("v")


def expected_sha(sha_text: bytes) -> str:
    token = sha_text.decode("utf-8", errors="replace").split()[0].lower() if sha_text.split() else ""
    if not _SHA_RE.match(token):
        raise ValueError("checksum file did not start with a sha256 hex digest")
    return token


def sha_ok(data: bytes, want: str) -> bool:
    return hashlib.sha256(data).hexdigest() == want


def extract_safely(tar_bytes: bytes, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
        for member in tar.getmembers():
            name = member.name
            if member.issym() or member.islnk():
                raise ValueError(f"refusing link in release tarball: {name}")
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError(f"refusing unsafe path in release tarball: {name}")
        tar.extractall(dest)  # members already validated above


def _shim_text(src: Path) -> str:
    return f'#!/bin/sh\nPYTHONPATH="{src}:${{PYTHONPATH:-}}" exec python3 -m collabai "$@"\n'


def install_version(version: str, home: Path | None = None, fetcher=None) -> Path:
    """Download, verify, and install `version`. Returns the version dir."""
    parse_version(version)
    fetch = fetcher or _fetch
    home = home or Path.home()
    prefix = home / ".local"
    src = prefix / "share" / f"collabai-{version}"
    shim = prefix / "bin" / "collabai"
    tar_url, sha_url = release_urls(version)
    print(f"downloading {tar_url}")
    tar_bytes = fetch(tar_url)
    print(f"downloading {sha_url}")
    want = expected_sha(fetch(sha_url))
    print("verifying checksum")
    if not sha_ok(tar_bytes, want):
        raise ValueError("checksum mismatch; refusing to install")
    old_shim = shim.read_text(encoding="utf-8") if shim.exists() else None
    backup: Path | None = None
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "extract"
        extract_safely(tar_bytes, stage)
        if not (stage / "collabai" / "__main__.py").exists():
            raise ValueError("tarball layout wrong: collabai/__main__.py missing")
        (prefix / "share").mkdir(parents=True, exist_ok=True)
        (prefix / "bin").mkdir(parents=True, exist_ok=True)
        try:
            if src.exists():
                backup = prefix / "share" / f"collabai-{version}.old"
                if backup.exists():
                    shutil.rmtree(backup)
                src.rename(backup)
            shutil.move(str(stage), str(src))
            shim.write_text(_shim_text(src), encoding="utf-8")
            shim.chmod(0o755)
        except OSError:
            if backup is not None and backup.exists():
                if src.exists():
                    shutil.rmtree(src, ignore_errors=True)
                backup.rename(src)
            if old_shim is not None:
                shim.write_text(old_shim, encoding="utf-8")
            elif shim.exists():
                shim.unlink()
            raise
    if backup is not None and backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    return src


def run_update(to: str | None = None, fetcher=None) -> int:
    from . import __version__

    try:
        target = to.lstrip("v") if to else latest_version(fetcher)
        parse_version(target)
    except (ValueError, OSError, KeyError) as exc:
        print(f"update failed: {exc}", file=sys.stderr)
        return 1
    if parse_version(target) == parse_version(__version__):
        print(f"already at {__version__}")
        return 0
    if parse_version(target) < parse_version(__version__):
        print(f"refusing downgrade: {__version__} -> {target}", file=sys.stderr)
        return 1
    print(f"updating collabai {__version__} -> {target}")
    try:
        src = install_version(target, fetcher=fetcher)
    except (ValueError, OSError, tarfile.TarError) as exc:
        print(f"update failed: {exc}", file=sys.stderr)
        return 1
    print(f"installed {target} to {src}")
    print("run: collabai --version  (ensure ~/.local/bin is on PATH)")
    return 0


def _yes(input_fn, label: str) -> bool:
    try:
        return str(input_fn(label)).strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def run_uninstall_full(root: Path, home: Path | None = None, input_fn=input) -> int:
    home = home or Path.home()
    prefix = home / ".local"
    shim = prefix / "bin" / "collabai"
    versions = sorted((prefix / "share").glob("collabai-*")) if (prefix / "share").exists() else []
    versions = [p for p in versions if p.is_dir() and not p.name.endswith(".old")]
    state = root / ".collabai"
    removed: list[str] = []
    if shim.exists() and _yes(input_fn, f"remove shim {shim}? [y/N] "):
        shim.unlink()
        removed.append("shim")
    if versions and _yes(
        input_fn, f"remove {len(versions)} installed version dir(s) under {prefix / 'share'}? [y/N] "
    ):
        for path in versions:
            shutil.rmtree(path, ignore_errors=True)
        removed.append("installed versions")
    if state.exists() and _yes(input_fn, f"remove private state {state}? [y/N] "):
        shutil.rmtree(state)
        removed.append("private state")
    print("removed: " + (", ".join(removed) if removed else "nothing (everything kept)"))
    print("tracked project files untouched.")
    return 0
