"""Channel B: end-to-end smoke test driving the game through its test frontend.

`angband -mtest` is a pseudo-UI: it reads commands on stdin, feeds `key`
commands into the real game loop, and (with `verbose 1`) echoes every screen
write as a `term-text` line. That makes it possible to start the game, create
characters and read the screen back without a terminal.

This covers the 11x9 race/class grid -- every combination the birth code has
to handle -- and checks the engine reports back the character it was asked to
make. It is a smoke test, not a rules test: channel A (the unit harness) is
where interaction rules are verified.
"""

import argparse
import json
import pathlib
import subprocess
import sys

RACES = ["Human", "Half-Elf", "Elf", "Hobbit", "Gnome", "Dwarf", "Half-Orc",
         "Half-Troll", "Dunadan", "High-Elf", "Kobold"]
CLASSES = ["Warrior", "Mage", "Druid", "Priest", "Necromancer", "Paladin",
           "Rogue", "Ranger", "Blackguard"]


def run_one(binary, cwd, race, cls, timeout=30):
    """Birth one character and read back what the engine says it made."""
    script = f"player-birth {race} {cls}\nplayer-race?\nplayer-class?\nquit\n"
    try:
        proc = subprocess.run(
            [binary, "-mtest"],
            input=script, capture_output=True, text=True,
            cwd=cwd, timeout=timeout,
            # Angband refuses to start outside a UTF-8 locale.
            env={"LC_ALL": "C.utf8", "LANG": "C.utf8", "PATH": "/usr/bin:/bin",
                 "HOME": str(pathlib.Path.home())},
        )
    except subprocess.TimeoutExpired:
        return {"race": race, "class": cls, "ok": False,
                "reason": "timeout"}

    out = proc.stdout
    got_race = got_class = None
    for line in out.splitlines():
        if line.startswith("player-race: "):
            got_race = line.split(": ", 1)[1].strip()
        elif line.startswith("player-class: "):
            got_class = line.split(": ", 1)[1].strip()

    ok = (got_race == race and got_class == cls)
    result = {"race": race, "class": cls, "ok": ok,
              "got_race": got_race, "got_class": got_class}
    if not ok:
        result["reason"] = "engine reported a different character"
        result["stdout_tail"] = out.strip().splitlines()[-5:]
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--angband-src", required=True,
                    help="top of the built Angband tree")
    ap.add_argument("--out", required=True, help="JSON results path")
    args = ap.parse_args()

    src = pathlib.Path(args.angband_src).resolve()
    binary = src / "src" / "angband"
    if not binary.is_file():
        sys.exit(f"angband binary not found: {binary}")

    results = []
    for race in RACES:
        for cls in CLASSES:
            results.append(run_one(str(binary), str(src), race, cls))

    failures = [r for r in results if not r["ok"]]

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"total": len(results), "failures": failures, "results": results},
        indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"birth smoke: {len(results) - len(failures)}/{len(results)} ok "
          f"-> {out}")
    for f in failures:
        print(f"  FAIL {f['race']}/{f['class']}: {f.get('reason')}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
