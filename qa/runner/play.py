"""Interactive driver for playing Angband through the -mtest frontend.

The test frontend is a lock-step pseudo-UI: every time the game polls for
input it reads exactly one command line from stdin. With `verbose 1` it also
echoes every screen write as `term-text <x> <y> <len> <attr> <string>`, which
is enough to rebuild the 80x24 terminal contents.

That gives a real play loop: push a keystroke, rebuild the screen, decide what
to do next. `version?` is used as a synchronisation barrier -- it makes the
engine print a known line, so the driver knows the keystrokes ahead of it have
been consumed and the screen is settled.
"""

import pathlib
import subprocess
import sys

COLS, ROWS = 80, 24


class Screen:
    """An 80x24 character grid rebuilt from term-* trace lines."""

    def __init__(self):
        self.grid = [[" "] * COLS for _ in range(ROWS)]

    def clear(self):
        self.grid = [[" "] * COLS for _ in range(ROWS)]

    def write(self, x, y, text):
        if not (0 <= y < ROWS):
            return
        for i, ch in enumerate(text):
            if 0 <= x + i < COLS:
                self.grid[y][x + i] = ch

    def wipe(self, x, y, n):
        self.write(x, y, " " * n)

    def render(self, border=True):
        lines = ["".join(row).rstrip() for row in self.grid]
        if not border:
            return "\n".join(lines)
        top = "+" + "-" * COLS + "+"
        body = ["|" + line.ljust(COLS) + "|" for line in lines]
        return "\n".join([top] + body + [top])

    def find(self, needle):
        """Row index containing `needle`, or -1."""
        for y, row in enumerate(self.grid):
            if needle in "".join(row):
                return y
        return -1

    def text(self):
        return "\n".join("".join(row) for row in self.grid)


class Game:
    def __init__(self, angband_src, verbose_trace=False):
        src = pathlib.Path(angband_src).resolve()
        self.binary = src / "src" / "angband"
        if not self.binary.is_file():
            raise SystemExit(f"angband binary not found: {self.binary}")

        self.screen = Screen()
        self.verbose_trace = verbose_trace
        self.sync_count = 0

        self.proc = subprocess.Popen(
            # The engine's stdout is a pipe here, so libc would block-buffer
            # its trace output and the driver would deadlock waiting on a
            # barrier that is still sitting in the child's buffer.
            ["stdbuf", "-o0", "-e0", str(self.binary), "-mtest"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
            # The frontend renders wide chars through wcstombs(), which can
            # emit bytes that are not valid UTF-8 (e.g. latin-1 punctuation
            # in the tombstone art). Never let that kill the play session.
            errors="replace",
            cwd=str(src),
            # Angband refuses to start outside a UTF-8 locale.
            env={"LC_ALL": "C.utf8", "LANG": "C.utf8",
                 "PATH": "/usr/bin:/bin", "HOME": str(pathlib.Path.home())},
        )
        self._send("verbose 1")

    def _send(self, line):
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def _apply(self, line):
        """Fold one trace line into the screen model."""
        if line.startswith("term-text "):
            # term-text <x> <y> <len> <attr> <string>; the string itself may
            # contain spaces, so only the first five fields are split off.
            parts = line.split(" ", 5)
            if len(parts) < 6:
                return
            try:
                x, y = int(parts[1]), int(parts[2])
            except ValueError:
                return
            self.screen.write(x, y, parts[5])
        elif line.startswith("term-wipe "):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    self.screen.wipe(int(parts[1]), int(parts[2]),
                                     int(parts[3]))
                except ValueError:
                    pass
        elif line.startswith("term-xtra-clear"):
            self.screen.clear()

    def keys(self, *keys, settle=10):
        """Send keystrokes and wait for the screen to stop changing.

        A `key` command only *stores* the keystroke; the engine pushes it on
        its next poll and redraws some polls later. So a single barrier
        returns a screen from before the key took effect. Instead, keep
        stepping the engine until the screen holds still.
        """
        for k in keys:
            self._send(f"key {k}")
        return self.settle(settle)

    def settle(self, rounds=10, stable_for=2, minimum=4):
        """Step the engine until the screen is unchanged `stable_for` times.

        `minimum` guards against stopping before the engine has even started
        redrawing: a keystroke typically takes two or three polls to reach the
        screen, and those first polls look deceptively "stable".
        """
        previous = self.screen.text()
        unchanged = 0
        for step in range(rounds):
            self.sync()
            current = self.screen.text()
            if current == previous:
                unchanged += 1
                if step + 1 >= minimum and unchanged >= stable_for:
                    break
            else:
                unchanged = 0
                previous = current
        return self.screen

    def sync(self):
        """Barrier: read trace output until the engine answers version?."""
        self.sync_count += 1
        self._send("version?")
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("engine exited unexpectedly")
            line = line.rstrip("\n")
            if self.verbose_trace:
                print("  trace:", line, file=sys.stderr)
            self._apply(line)
            if line.startswith("cmd-version:"):
                return self.screen

    def messages(self):
        """Text of the message line at the top of the screen."""
        return "".join(self.screen.grid[0]).strip()

    def clear_more(self, limit=20):
        """Dismiss any stacked -more- prompts, returning what they said.

        The engine pauses on -more- until a key is pressed, so an unattended
        driver deadlocks on them. Collect the text before dismissing so no
        message is lost.
        """
        seen = []
        for _ in range(limit):
            msg = self.messages()
            if "-more-" not in msg:
                break
            seen.append(msg.replace("-more-", "").strip())
            self.keys("enter")
        return seen

    def status(self):
        """Parse the sidebar/status line into a small dict."""
        text = self.screen.text().split("\n")
        info = {}
        for row in text:
            stripped = row.strip()
            if stripped.startswith("HP "):
                info["hp"] = stripped[3:].strip()
            elif stripped.startswith("LEVEL "):
                info["level"] = stripped[6:].strip()
        # The bottom line carries the depth readout.
        info["depth"] = text[22].strip() if len(text) > 22 else ""
        return info

    def command(self, cmd):
        """Send a raw test-frontend command (e.g. player-race?)."""
        self._send(cmd)
        return self.sync()

    def quit(self):
        try:
            self._send("quit")
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--angband-src", default="vendor/angband")
    ap.add_argument("--keys", nargs="*", default=[],
                    help="keystrokes to send after boot")
    args = ap.parse_args()

    game = Game(args.angband_src)
    game.sync()
    if args.keys:
        game.keys(*args.keys)
    print(game.screen.render())
    game.quit()


if __name__ == "__main__":
    main()
