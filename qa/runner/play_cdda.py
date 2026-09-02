"""Driver for playing Cataclysm: Dark Days Ahead's curses build through a pty.

Unlike Angband's `-mtest` frontend, CDDA has no lock-step test protocol: it
draws straight to a terminal via ncurses. So instead of parsing a trace, this
drives a real pty (via pexpect) and feeds every byte the game writes into a
`pyte` terminal emulator, which reconstructs the on-screen character grid.
Keystrokes are written to the pty's master side exactly as a keyboard would.
"""

import os
import time

import pexpect
import pyte

COLS, ROWS = 80, 24


class Game:
    def __init__(self, binary, userdir=None, cols=COLS, rows=ROWS, timeout=60):
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.Stream(self.screen)

        binary = os.path.abspath(binary)
        cwd = os.path.dirname(binary)
        args = ["--worldsize", "80x24"] if False else []
        if userdir:
            args += ["--userdir", userdir]

        env = dict(os.environ)
        # CDDA falls back to a plain-ASCII line-drawing set without a UTF-8
        # locale; pyte only needs valid UTF-8 text, not a full terminfo, so
        # keep TERM simple.
        env["TERM"] = "xterm"
        env.setdefault("LANG", "C.UTF-8")
        env.setdefault("LC_ALL", "C.UTF-8")

        self.child = pexpect.spawn(
            binary, args=args, cwd=cwd, env=env,
            dimensions=(rows, cols), encoding=None, timeout=timeout,
        )
        self.pump(2.0)

    def pump(self, duration=0.5, chunk=8192):
        """Read whatever the game has written for up to `duration` seconds."""
        end = time.time() + duration
        got_any = False
        while time.time() < end:
            try:
                data = self.child.read_nonblocking(size=chunk, timeout=0.1)
            except pexpect.TIMEOUT:
                if got_any:
                    break
                continue
            except pexpect.EOF:
                break
            if data:
                got_any = True
                self.stream.feed(data.decode("utf-8", errors="replace"))
        return self.screen

    def send(self, s):
        """Send raw bytes/text with no key-name translation."""
        self.child.send(s)

    def key(self, k, settle=0.4):
        """Send one keystroke (a literal char, or 'enter'/'esc'/arrow names)."""
        special = {
            "enter": "\r", "esc": "\x1b", "tab": "\t",
            "up": "\x1b[A", "down": "\x1b[B",
            "right": "\x1b[C", "left": "\x1b[D",
            "space": " ",
        }
        self.send(special.get(k, k))
        return self.pump(settle)

    def keys(self, *ks, settle=0.4):
        for k in ks:
            self.key(k, settle=0.05)
        return self.pump(settle)

    def render(self, border=True):
        lines = [line.rstrip() for line in self.screen.display]
        if not border:
            return "\n".join(lines)
        cols = self.screen.columns
        top = "+" + "-" * cols + "+"
        body = ["|" + line.ljust(cols) + "|" for line in lines]
        return "\n".join([top] + body + [top])

    def text(self):
        return "\n".join(self.screen.display)

    def find(self, needle):
        for y, line in enumerate(self.screen.display):
            if needle in line:
                return y
        return -1

    def alive(self):
        return self.child.isalive()

    def quit(self):
        try:
            if self.child.isalive():
                self.child.terminate(force=True)
        except Exception:
            pass


def main():
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", default="vendor/cataclysm-dda/cataclysm")
    ap.add_argument("--userdir", default=None)
    ap.add_argument("--keys", nargs="*", default=[])
    args = ap.parse_args()

    game = Game(args.binary, userdir=args.userdir)
    if args.keys:
        game.keys(*args.keys)
    print(game.render())
    game.quit()


if __name__ == "__main__":
    main()
