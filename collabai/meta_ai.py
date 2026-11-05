"""Optional Meta AI extras (stdlib only). Off unless a key is present.

Key storage (persistent, most secure stdlib option): a `0600` file in a
`0700` directory outside any repo, `~/.config/collabai/meta.key`
(`$XDG_CONFIG_HOME` respected). `COLLABAI_META_API_KEY` overrides it.
The key is never written into a project `.collabai/`, never logged, and
stripped from launched-agent environments.

Without a key nothing here runs and the harness behaves exactly as v1.
With a key, every AI call prints the model in use. Inputs are collabai
metadata only (tasks, areas, file names, decisions) — never file
contents, transcripts, diffs, or prompts from agent sessions. Output is
shown for the developer to keep or discard; nothing is auto-saved.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "meta-spark-1.3"
API_URL = "https://api.meta.ai/v1/chat/completions"
MAX_OUTPUT = 1000
# The model id and endpoint above are owner-supplied and UNVERIFIED: no
# live smoke call has been owner-pasted yet. Until one passes, Meta AI
# extras are parked — chat() refuses and menu 8 explains — so a
# professional release never presents an unproven endpoint as working.
# Flip to True only with a pasted successful smoke call on record.
META_VERIFIED = False


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
        return model or DEFAULT_MODEL
    except (OSError, ValueError, AttributeError):
        return DEFAULT_MODEL


def _post(url: str, payload: dict, key: str) -> bytes:
    if not url.startswith("https://"):
        raise MetaError("refusing non-HTTPS API URL")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def chat(messages: list[dict], root: Path, poster=None, key: str | None = None) -> str:
    """One chat call. Prints the model in use. Raises MetaError on failure."""
    if not META_VERIFIED:
        raise MetaError(
            "Meta AI extras are parked in this release (model/endpoint "
            "unverified); harness continues without AI"
        )
    api_key = key if key is not None else load_key()
    if not api_key:
        raise MetaError("no Meta key set (run: collabai --meta-key)")
    model = model_for(root)
    print(f"Meta AI via {model} (your key; metadata only, nothing auto-saved)")
    send = poster or _post
    try:
        raw = send(API_URL, {"model": model, "messages": messages}, api_key)
        obj = json.loads(raw.decode("utf-8"))
        text = str(obj["choices"][0]["message"]["content"])
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise MetaError(f"Meta call failed ({exc}); harness continues without AI") from exc
    return text.strip()[:MAX_OUTPUT]


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
        {"role": "system", "content": "Draft one short pair-programming note (max 400 chars) "
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
        {"role": "system", "content": "You are Collab Bot, a cheerful terminal companion. Be brief."},
        {"role": "user", "content": f"{prompts[kind]}\n{_meta_lines(snapshot)}"},
    ]
