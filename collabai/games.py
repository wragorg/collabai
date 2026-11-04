"""One waiting game: Snake (stdlib only, pure logic + curses layer).

On a real terminal Snake runs in place under curses: it moves on its
own clock, turns on single keypresses (arrows or w/a/s/d, no Enter),
speeds up as it eats, and ends on a game-over screen (r restarts,
q quits). Without a TTY it falls back to line-at-a-time play so
scripts and tests work. Best score lives in `.collabai/games.json`
(`0600`, metadata only). If an agent question arrives, the game
pauses and hands control back.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path

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


def _live_terminal(input_fn) -> bool:
    if input_fn is not input:
        return False
    try:
        import termios  # noqa: F401

        return bool(sys.stdin.isatty())
    except (ImportError, OSError, AttributeError):
        return False


def _play_snake_curses(game: SnakeGame, pending_fn=None) -> int:
    """In-place Snake under curses: the stdlib way to do terminal games.

    curses owns the screen and keyboard (arrow keys included), restores
    the terminal on every exit path, and getch() with a timeout is the
    game clock — no manual termios, escape parsing, or Enter per move.
    """
    import curses

    keys = {
        curses.KEY_UP: "w", curses.KEY_DOWN: "s",
        curses.KEY_LEFT: "a", curses.KEY_RIGHT: "d",
        ord("w"): "w", ord("s"): "s", ord("a"): "a", ord("d"): "d",
        ord("W"): "w", ord("S"): "s", ord("A"): "a", ord("D"): "d",
    }
    result = {"score": 0}

    def _draw(stdscr, headline: str) -> None:
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()
        if max_y < game.height + 4 or max_x < game.width + 2:
            stdscr.addstr(0, 0, "terminal too small for Snake; resize or press q")
            stdscr.refresh()
            return
        stdscr.addstr(0, 0, headline[: max_x - 1])
        for x in range(game.width + 2):
            stdscr.addch(1, x, "#")
            stdscr.addch(game.height + 2, x, "#")
        for y in range(game.height):
            stdscr.addch(y + 2, 0, "#")
            stdscr.addch(y + 2, game.width + 1, "#")
            for x in range(game.width):
                cell = (x, y)
                ch = "@" if cell == game.snake[0] else "o" if cell in game.snake else "*" if cell == game.food else " "
                if ch != " ":
                    stdscr.addch(y + 2, x + 1, ch)
        stdscr.refresh()

    def _main(stdscr) -> None:
        curses.curs_set(0)
        stdscr.keypad(True)
        while True:  # one run per iteration; r restarts from game over
            run = SnakeGame(width=game.width, height=game.height,
                            seed=int(time.time()) % 100000)
            paused = False
            while run.alive:
                if pending_fn is not None and pending_fn() > 0:
                    _draw(stdscr, "PAUSED: an agent needs you. Press any key: menu 2 (Inbox).")
                    stdscr.timeout(-1)
                    stdscr.getch()
                    result["score"] = max(result["score"], run.score)
                    return
                stdscr.timeout(max(65, 150 - run.score * 6))
                _draw(stdscr, f"SNAKE  score {run.score}  length {len(run.snake)}  "
                              "arrows/wasd steer  p pause  q quit")
                key = stdscr.getch()
                if key in (ord("q"), ord("Q")):
                    result["score"] = max(result["score"], run.score)
                    return
                if key in (ord("p"), ord("P")):
                    _draw(stdscr, "PAUSED. Press p to resume, q to quit.")
                    stdscr.timeout(-1)
                    key = stdscr.getch()
                    while key not in (ord("p"), ord("P"), ord("q"), ord("Q")):
                        key = stdscr.getch()
                    if key in (ord("q"), ord("Q")):
                        result["score"] = max(result["score"], run.score)
                        return
                    continue
                if key in keys:
                    run.turn(keys[key])
                run.step()
            result["score"] = max(result["score"], run.score)
            _draw(stdscr, f"GAME OVER  score {run.score}.  r = play again, q = back to collabai")
            stdscr.timeout(-1)
            key = stdscr.getch()
            if key not in (ord("r"), ord("R")):
                return

    curses.wrapper(_main)
    return int(result["score"])


def play_snake(input_fn=input, pending_fn=None, seed: int | None = None) -> int:
    if _live_terminal(input_fn):
        board = SnakeGame(width=26, height=14,
                          seed=seed if seed is not None else int(time.time()) % 10000)
        try:
            return _play_snake_curses(board, pending_fn)
        except Exception as exc:  # curses unavailable/broken: fall back, never crash the harness
            print(f"interactive Snake unavailable ({exc}); line mode instead.")
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
