"""Codex fallback: managed block in root AGENTS.md. Never overwrites user content."""

from __future__ import annotations

from pathlib import Path

START = "<!-- collabai:start -->"
END = "<!-- collabai:end -->"

BLOCK = """<!-- collabai:start -->
## collabai (private, local-first)

- Relevant project knowledge lives in `.collabai/` (gitignored, local-only).
- To recall: run `python3 -m collabai context --files "<paths>"` and use only returned lines.
- To save: run `python3 -m collabai remember --task "<short intent>" --area "<area>" --files "<paths>" --text "<summary>" [--decision]`.
- Never paste full transcripts, prompts, secrets, or source contents into memory.
- Task intent stays private unless saved with `--shareable`.
<!-- collabai:end -->
"""


def _target(root: Path) -> Path:
    return root / "AGENTS.md"


def preview(root: Path) -> str:
    target = _target(root)
    current = target.read_text(encoding="utf-8") if target.exists() else "(absent)"
    if len(current) > 2000:
        current = current[:2000] + "\n...(truncated)"
    return f"target: {target}\n--- current ---\n{current}\n--- would ensure block ---\n{BLOCK}"


def apply(root: Path) -> int:
    target = _target(root)
    if target.exists():
        text = target.read_text(encoding="utf-8")
        if START in text and END in text:
            print("codex block already present")
            return 0
        if not text.endswith("\n"):
            text += "\n"
        text = text + "\n" + BLOCK
    else:
        text = BLOCK
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"installed codex block in {target} (review with git diff before committing)")
    return 0
