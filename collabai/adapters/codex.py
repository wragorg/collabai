"""Codex fallback: managed block in root AGENTS.md. Never overwrites user content."""

from __future__ import annotations

from pathlib import Path

START = "<!-- collabai:start -->"
END = "<!-- collabai:end -->"
# When BLOCK changes, apply() upgrades an existing managed block in place.

BLOCK = """<!-- collabai:start -->
## collabai (private, local-first)

- Relevant project knowledge lives in `.collabai/` (gitignored, local-only).
- To recall: run `python3 -m collabai context --files "<paths>"` and use only returned lines; do not read, print, or paste file contents to enrich them.
- Lines returned by `context` are sent to your model provider. That boundary belongs to the developer; a human can preview them with the same command.
- To save: run `python3 -m collabai remember --task "<short intent>" --area "<area>" --files "<paths>" --text "<summary>" [--decision]`.
- To ask the developer one short question and wait for the answer: run `python3 -m collabai ask --agent codex --question "<short question>" [--options "A|B"] --wait --timeout 600`. Exit 0 prints the answer; exit 2 means no answer yet (read it later with `python3 -m collabai inbox --answer <id> --wait`). Without `--wait`, ask once and do not block.
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
            start = text.index(START)
            end = text.index(END, start) + len(END)
            existing = text[start:end]
            if existing == BLOCK.rstrip("\n"):
                print("codex block already present")
                return 0
            # Upgrade only the managed block; user content is preserved.
            text = text[:start] + BLOCK.rstrip("\n") + text[end:]
            target.write_text(text, encoding="utf-8")
            print(f"updated codex block in {target} (review with git diff before committing)")
            print("note: lines returned by `collabai context` go to your model provider.")
            return 0
        if not text.endswith("\n"):
            text += "\n"
        text = text + "\n" + BLOCK
    else:
        text = BLOCK
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"installed codex block in {target} (review with git diff before committing)")
    print("note: lines returned by `collabai context` go to your model provider.")
    return 0
