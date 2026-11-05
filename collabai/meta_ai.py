"""Optional Meta AI extras (stdlib only). Off unless a key is present.

Key storage (persistent, most secure stdlib option): a `0600` file in a
`0700` directory outside any repo, `~/.config/collabai/meta.key`
(`$XDG_CONFIG_HOME` respected). `COLLABAI_META_API_KEY` overrides it.
The key is never written into a project `.collabai/`, never logged, and
stripped from launched-agent environments.

Without a key nothing here runs and the harness behaves exactly as v1.
With a key, every AI call prints the model in use. The one-shot extras
use collabai metadata only (tasks, areas, file names, decisions). The
menu-8 chat loop sends only what the developer types at its prompt —
never file contents, transcripts, diffs, or prompts from agent
sessions. Output is shown for the developer to keep or discard;
nothing is auto-saved and chat history is never written to disk.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Verified against Meta's official Model API docs (dev.meta.ai/docs/models):
# the model id is muse-spark-1.3 (the earlier meta-spark-1.3 never existed
# and made every call fail). Endpoint is the documented Chat Completions URL.
DEFAULT_MODEL = "muse-spark-1.3"
LEGACY_MODEL = "meta-spark-1.3"
API_URL = "https://api.meta.ai/v1/chat/completions"
MAX_OUTPUT = 1000
# Verified live: owner-pasted `collabai --meta-test` returned
# "meta-test: ok (ready)" with this model and endpoint, so menu 8 is
# unparked. If the model/endpoint ever changes, set this back to False
# until a new pasted smoke call passes.
META_VERIFIED = True


class MetaError(RuntimeError):
    pass


def key_path(home: Path | None = None) -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else (home or Path.home()) / ".config"
    return base / "collabai" / "meta.key"


def store_key(key: str, home: Path | None = None) -> Path:
    key = (key or "").strip()
    if not key or any(ch.isspace() for ch in key):
        raise ValueError("key is empty or contains whitespace; not stored")
    path = key_path(home)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError as exc:
        print(f"warning: could not lock down {path.parent}: {exc}", file=sys.stderr)
    path.write_text(key + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        print(f"warning: could not lock down {path}: {exc}", file=sys.stderr)
    return path


def delete_key(home: Path | None = None) -> bool:
    path = key_path(home)
    if path.exists():
        path.unlink()
        return True
    return False


def load_key(home: Path | None = None) -> str | None:
    env = os.environ.get("COLLABAI_META_API_KEY", "").strip()
    if env:
        return env
    path = key_path(home)
    try:
        key = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return key or None


def model_for(root: Path) -> str:
    try:
        cfg = json.loads((root / ".collabai" / "config.json").read_text(encoding="utf-8"))
        model = str(cfg.get("inference", {}).get("model", "")).strip()
    except (OSError, ValueError, AttributeError):
        return DEFAULT_MODEL
    if not model or model == LEGACY_MODEL:
        # Migrate the never-valid legacy id instead of failing every call.
        return DEFAULT_MODEL
    return model


def _describe_ssl_error(exc: Exception) -> str:
    return (
        "TLS certificate verification failed: this Python has no CA "
        "bundle (common on macOS python.org installs). Run the "
        "'Install Certificates.command' shipped with your Python, or "
        f"set SSL_CERT_FILE to a CA bundle, then try again ({exc})")


def _describe_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")[:200].strip()
    except Exception:
        body = ""
    detail = f": {body}" if body else ""
    if exc.code == 401:
        return (f"Meta API key rejected (HTTP 401){detail}. Store a Model API "
                "key (starts with LLM_) with: collabai --meta-key")
    if exc.code in (400, 404):
        return (f"Meta rejected the request (HTTP {exc.code}){detail}. "
                f"Model in use: {DEFAULT_MODEL}")
    if exc.code == 429:
        return f"Meta rate limit hit (HTTP 429){detail}. Wait and try again."
    return f"Meta call failed (HTTP {exc.code}){detail}"


# CA bundles Python may not find by default. macOS ships /etc/ssl/cert.pem
# but python.org Pythons ignore it until "Install Certificates" runs, and
# judges/users should never have to set SSL_CERT_FILE by hand. Verification
# is always on; we only point OpenSSL at a bundle that already exists.
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


def _is_ssl_error(exc: BaseException) -> bool:
    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    return isinstance(exc, urllib.error.URLError) and isinstance(
        exc.reason, ssl.SSLCertVerificationError)


def _fetch_bytes(req: urllib.request.Request, context=None) -> bytes:
    try:
        with urllib.request.urlopen(req, timeout=30, context=context) as resp:
            return resp.read()
    except (ssl.SSLCertVerificationError, urllib.error.URLError) as exc:
        if context is not None or not _is_ssl_error(exc):
            raise
        cafile = _fallback_cafile()
        if cafile is None:
            raise
        ctx = ssl.create_default_context(cafile=cafile)
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            return resp.read()


def _post(url: str, payload: dict, key: str) -> bytes:
    if not url.startswith("https://"):
        raise MetaError("refusing non-HTTPS API URL")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    return _fetch_bytes(req)


def chat(messages: list[dict], root: Path, poster=None, key: str | None = None) -> str:
    """One chat call. Prints the model in use. Raises MetaError on failure."""
    return _chat(messages, root, poster=poster, key=key, bypass_parked=False)


def smoke_test(root: Path, poster=None, key: str | None = None) -> str:
    """One minimal live call to prove key + model + endpoint. Bypasses the park.

    This is the gate for flipping META_VERIFIED: it exists so the owner
    can produce the proof on their own machine with `collabai --meta-test`.
    """
    return _chat(
        [{"role": "user", "content": "Reply with the single word: ready"}],
        root, poster=poster, key=key, bypass_parked=True,
    )


def _chat(messages: list[dict], root: Path, poster=None, key: str | None = None,
          bypass_parked: bool = False) -> str:
    if not META_VERIFIED and not bypass_parked:
        raise MetaError(
            "Meta AI extras are parked until a live smoke call passes "
            "(run: collabai --meta-test); harness continues without AI"
        )
    api_key = key if key is not None else load_key()
    if not api_key:
        raise MetaError("no Meta key set (run: collabai --meta-key)")
    model = model_for(root)
    print(f"Meta AI via {model} (your key; nothing auto-saved)")
    send = poster or _post
    try:
        raw = send(API_URL, {"model": model, "messages": messages}, api_key)
        obj = json.loads(raw.decode("utf-8"))
        text = str(obj["choices"][0]["message"]["content"] or "")
    except MetaError:
        raise
    except urllib.error.HTTPError as exc:
        raise MetaError(_describe_http_error(exc)) from exc
    except ssl.SSLCertVerificationError as exc:
        raise MetaError(_describe_ssl_error(exc)) from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise MetaError(_describe_ssl_error(exc.reason)) from exc
        raise MetaError(
            f"Meta call failed (network: {exc.reason}); harness continues "
            "without AI") from exc
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        if "timed out" in str(exc).lower() or "timeout" in str(exc).lower():
            raise MetaError("Meta call timed out; check the network and try again") from exc
        raise MetaError(f"Meta call failed ({exc}); harness continues without AI") from exc
    text = text.strip()
    if not text:
        raise MetaError(
            "Meta returned an empty reply (reasoning may have used the "
            "output budget); ask again")
    return text[:MAX_OUTPUT]


def _meta_lines(snapshot: dict) -> str:
    agents = "; ".join(
        f"{a.get('agent')} in {a.get('area') or '?'}: {a.get('task')}"
        for a in snapshot.get("agents", [])
    ) or "no sessions"
    decisions = "; ".join(str(d.get("text", "")) for d in snapshot.get("decisions", [])[:3]) or "none"
    overlaps = ", ".join(sorted(snapshot.get("overlaps", {}))) or "none"
    return f"sessions: {agents}\ndecisions: {decisions}\noverlaps: {overlaps}"


def draft_note_messages(files: list[str], hint: str) -> list[dict]:
    return [
        {"role": "developer", "content": "Draft one short pair-programming note (max 400 chars) "
                                         "from file names and a hint only. No code."},
        {"role": "user", "content": f"files: {', '.join(files) or 'none'}\nhint: {hint}"},
    ]


def fun_messages(kind: str, snapshot: dict) -> list[dict]:
    prompts = {
        "overlap": "Explain this possible work overlap in two friendly sentences and suggest who talks first.",
        "fortune": "Give one short, playful fortune-cookie line for this pair-programming team. One sentence.",
        "standup": "Write a one-line standup update from this metadata. One sentence.",
        "celebrate": "Write one short celebration line for a finished task. One sentence.",
    }
    return [
        {"role": "developer", "content": "You are Collab Bot, a cheerful terminal companion. Be brief."},
        {"role": "user", "content": f"{prompts[kind]}\n{_meta_lines(snapshot)}"},
    ]
