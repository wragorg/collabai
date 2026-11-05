"""Claude Code adapter PoC: merge a SessionStart hook into settings.local.json.

Never touches settings.json (shared). Preserves existing hooks.
Hook calls `collabai context` with no args; empty output costs 0 tokens.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LOCAL_SETTINGS = Path(".claude/settings.local.json")
HOOK_COMMAND = "python3 -m collabai context"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def planned_hook() -> dict:
    return {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": HOOK_COMMAND}],
                }
            ]
        }
    }


def preview(root: Path) -> str:
    current = _load(root / LOCAL_SETTINGS)
    return json.dumps({"current": current, "would_add": planned_hook()}, indent=2)


def apply(root: Path) -> int:
    target = root / LOCAL_SETTINGS
    data = _load(target)
    hooks = data.setdefault("hooks", {})
    starts = hooks.setdefault("SessionStart", [])
    for entry in starts:
        for hook in entry.get("hooks", []):
            if hook.get("command") == HOOK_COMMAND:
                print("hook already present")
                print("note: lines returned by `collabai context` go to your model provider.")
                return 0
    starts.append({"matcher": "*", "hooks": [{"type": "command", "command": HOOK_COMMAND}]})
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"installed SessionStart hook in {target} (private, uncommitted)")
    print("note: lines returned by `collabai context` go to your model provider; "
          'preview with: collabai context --files "<paths>"')
    return 0
