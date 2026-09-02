"""case-generator: expand the decision table into concrete test cases.

Each case pairs one weapon configuration (a brand and/or a slay) with one
monster configuration (resists / vulnerable / matches the slay) under one
combat mode and attack range, plus the expected outcome from the independent
reference model.

Impossible rows are pruned rather than generated: a brand with no vuln-flag
can never meet a vulnerable monster, and "matches the slay" is meaningless
with no slay equipped. Generating them would inflate the case count with rows
whose expectation is trivially "no change" -- the over-generation problem the
design doc warns about.
"""

import argparse
import itertools
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import reference_model  # noqa: E402


def build_cases(spec, brand_codes=None, slay_codes=None):
    brands = {b["code"]: b for b in spec["brands"]}
    slays = {s["code"]: s for s in spec["slays"]}

    if brand_codes:
        brands = {c: brands[c] for c in brand_codes if c in brands}
    if slay_codes:
        slays = {c: slays[c] for c in slay_codes if c in slays}

    cases = []
    combos = itertools.product(
        [None] + sorted(brands),
        [None] + sorted(slays),
        [False, True],   # mon_resists
        [False, True],   # mon_vulnerable
        [False, True],   # mon_matches_slay
        [False, True],   # o_combat
        [False, True],   # range
    )

    for bcode, scode, resists, vuln, matches, o_combat, is_range in combos:
        brand = brands.get(bcode)
        slay = slays.get(scode)

        # Prune rows that cannot exist in the game.
        if brand is None and (resists or vuln):
            continue          # nothing to resist or be vulnerable to
        if brand is not None and vuln and not brand["vuln_flag"]:
            continue          # this element has no vulnerability flag at all
        if slay is None and matches:
            continue          # no slay to match against
        if brand is None and slay is None:
            continue          # bare weapon; nothing to resolve

        case = {
            "brand": bcode,
            "slay": scode,
            "mon_resists": resists,
            "mon_vulnerable": vuln,
            "mon_matches_slay": matches,
            "o_combat": o_combat,
            "range": is_range,
        }
        case["id"] = "case_%04d" % len(cases)
        case["expected"] = reference_model.resolve(case, brand, slay)
        cases.append(case)

    return cases


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", required=True, help="specs/gamedata.json")
    ap.add_argument("--out", required=True, help="output cases JSON")
    ap.add_argument("--brands", nargs="*",
                    help="limit to these brand codes (default: all)")
    ap.add_argument("--slays", nargs="*",
                    help="limit to these slay codes (default: all)")
    args = ap.parse_args()

    spec = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
    cases = build_cases(spec, args.brands, args.slays)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    print(f"generated {len(cases)} cases -> {out}")


if __name__ == "__main__":
    main()
