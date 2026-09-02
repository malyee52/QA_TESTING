"""item-parser: turn Angband's declarative gamedata into structured QA specs.

Angband keeps brands, slays and monster bases in flat `key:value` record files
under lib/gamedata/. Records are separated by blank lines and the first key of
a record is its identity (`code:` for brands/slays, `name:` for monster bases).

The output is a single JSON document consumed by the case generator, so the
rest of the pipeline never has to know the on-disk format.
"""

import argparse
import json
import pathlib
import sys

# Keys whose values are integers rather than strings.
INT_KEYS = {"multiplier", "o-multiplier", "power"}

# Keys that may legitimately appear more than once in one record.
MULTI_KEYS = {"flags", "flags-off", "desc"}


def parse_records(path, id_key):
    """Parse a gamedata file into a list of dicts, one per record.

    A record starts at its `id_key` line and runs until the next one. Comments
    (`#`) and blank lines are skipped, so blank-line separation is not relied
    upon -- some files omit it.
    """
    records = []
    current = None

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if key == id_key:
            current = {id_key: value}
            records.append(current)
            continue

        if current is None:
            # Stray key before any record header; ignore rather than guess.
            continue

        if key in INT_KEYS:
            try:
                value = int(value)
            except ValueError:
                pass

        if key in MULTI_KEYS:
            current.setdefault(key, []).append(value)
        else:
            current[key] = value

    return records


def normalise_brand(rec):
    return {
        "code": rec["code"],
        "name": rec.get("name"),
        "verb": rec.get("verb"),
        "multiplier": rec.get("multiplier"),
        "o_multiplier": rec.get("o-multiplier"),
        "resist_flag": rec.get("resist-flag"),
        "vuln_flag": rec.get("vuln-flag"),
    }


def normalise_slay(rec):
    return {
        "code": rec["code"],
        "name": rec.get("name"),
        "race_flag": rec.get("race-flag"),
        "base": rec.get("base"),
        "multiplier": rec.get("multiplier"),
        "o_multiplier": rec.get("o-multiplier"),
        "melee_verb": rec.get("melee-verb"),
        "range_verb": rec.get("range-verb"),
    }


def normalise_base(rec):
    return {
        "name": rec["name"],
        "glyph": rec.get("glyph"),
        "flags": rec.get("flags", []),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gamedata", required=True,
                    help="path to vendor/angband/lib/gamedata")
    ap.add_argument("--out", required=True, help="output JSON path")
    args = ap.parse_args()

    gamedata = pathlib.Path(args.gamedata)
    if not gamedata.is_dir():
        sys.exit(f"gamedata directory not found: {gamedata}")

    sources = {
        "brands": (gamedata / "brand.txt", "code", normalise_brand),
        "slays": (gamedata / "slay.txt", "code", normalise_slay),
        "monster_bases": (gamedata / "monster_base.txt", "name",
                          normalise_base),
    }

    spec = {}
    for section, (path, id_key, normalise) in sources.items():
        if not path.exists():
            sys.exit(f"missing gamedata file: {path}")
        spec[section] = [normalise(r) for r in parse_records(path, id_key)]

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    for section, items in spec.items():
        print(f"{section}: {len(items)}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
