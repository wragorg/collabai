"""Two tiny waiting games (stdlib only, pure logic + line-based play).

Snake is turn-based (w/a/s/d + Enter per move) so it works in any
terminal and stays testable. Typing sprint scores one sentence. Best
scores live in `.collabai/games.json` (`0600`, metadata only). If an
agent question arrives, the game pauses and hands control back.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path

SENTENCES = [
    "the quick brown fox jumps over the lazy dog",
    "ship small changes and talk to your pair often",
    "decisions are cheap when everyone can find them",
    "a clean diff tells its own story in review",
]


class SnakeGame:
    def __init__(self, width: int = 12, height: int = 8, seed: int = 0):
        self.width, self.height = width, height
        self.rng = random.Random(seed)
        self.snake: list[tuple[int, int]] = [(width // 2, height // 2)]
        self.direction = (1, 0)
        self.food = self._place()
        self.score = 0
        self.alive = True

    def _place(self) -> tuple[int, int]:
        while True:
            cell = (self.rng.randrange(self.width), self.rng.randrange(self.height))
            if cell not in self.snake:
                return cell

    def turn(self, key: str) -> None:
        moves = {"w": (0, -1), "s": (0, 1), "a": (-1, 0), "d": (1, 0)}
        nxt = moves.get((key or "").strip().lower()[:1])
        if nxt is not None and (nxt[0] + self.direction[0], nxt[1] + self.direction[1]) != (0, 0):
            self.direction = nxt

    def step(self) -> None:
        if not self.alive:
            return
        head = (self.snake[0][0] + self.direction[0], self.snake[0][1] + self.direction[1])
        if not (0 <= head[0] < self.width and 0 <= head[1] < self.height) or head in self.snake:
            self.alive = False
            return
        self.snake.insert(0, head)
        if head == self.food:
            self.score += 1
            self.food = self._place()
        else:
            self.snake.pop()

    def render(self) -> str:
        rows = []
        for y in range(self.height):
            row = ""
            for x in range(self.width):
                if (x, y) == self.snake[0]:
                    row += "@"
                elif (x, y) in self.snake:
                    row += "o"
                elif (x, y) == self.food:
                    row += "*"
                else:
                    row += "."
            rows.append(row)
        return "\n".join(rows)


def score_typing(target: str, typed: str, seconds: float) -> dict:
    seconds = max(seconds, 0.01)
    correct = sum(1 for a, b in zip(target, typed) if a == b)
    accuracy = correct / max(len(target), 1)
    wpm = (len(typed) / 5.0) / (seconds / 60.0)
    return {"wpm": round(wpm, 1), "accuracy": round(accuracy, 2),
            "score": int(wpm * accuracy)}


def load_scores(root: Path) -> dict:
    try:
        obj = json.loads((root / ".collabai" / "games.json").read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError):
        return {}


def save_score(root: Path, game: str, score: int) -> int:
    scores = load_scores(root)
    best = max(int(scores.get(game, 0)), int(score))
    scores[game] = best
    path = root / ".collabai" / "games.json"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError as exc:
        print(f"warning: could not lock down {path}: {exc}", file=sys.stderr)
    return best


def play_snake(input_fn, pending_fn=None, seed: int | None = None) -> int:
    game = SnakeGame(seed=seed if seed is not None else int(time.time()) % 10000)
    print("Snake: w/a/s/d + Enter moves, q quits. Eating * grows you.")
    while game.alive:
        if pending_fn is not None and pending_fn() > 0:
            print("paused: an agent needs you. Game over for now.")
            return game.score
        print(game.render())
        try:
            key = str(input_fn("move> ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return game.score
        if key == "q":
            return game.score
        game.turn(key)
        game.step()
    print(game.render())
    print(f"snake down. score {game.score}")
    return game.score


def play_typing(input_fn, pending_fn=None, sentence: str | None = None,
                clock=None) -> dict:
    target = sentence or SENTENCES[int(time.time()) % len(SENTENCES)]
    print("Typing sprint: type this exactly, then Enter:")
    print(f"  {target}")
    timer = clock or time.monotonic
    start = timer()
    try:
        typed = str(input_fn("type> "))
    except (EOFError, KeyboardInterrupt):
        return {"wpm": 0.0, "accuracy": 0.0, "score": 0}
    result = score_typing(target, typed, timer() - start)
    print(f"{result['wpm']} wpm, {int(result['accuracy'] * 100)}% accurate, score {result['score']}")
    if pending_fn is not None and pending_fn() > 0:
        print("an agent needs you: check menu 9 (Inbox).")
    return result
