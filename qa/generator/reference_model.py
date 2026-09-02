"""Independent reference model for Angband's brand/slay resolution.

Deliberately written from the *declared* rules in docs/domain-mapping.md and
the gamedata files -- not from obj-slays.c. The pipeline compares this model
against the real engine, so any place the two disagree is a finding worth a
human look. Mirroring the C code here would make the whole exercise circular.
"""


def brand_multiplier(brand, resists, vulnerable, o_combat):
    """Effective multiplier a brand contributes, or None if it cannot apply.

    Rule 1: a resisted brand does not apply at all.
    Rule 2: a vulnerable monster doubles the brand's *extra* damage.
    """
    if resists:
        return None

    mult = brand["o_multiplier"] if o_combat else brand["multiplier"]

    if vulnerable and brand["vuln_flag"]:
        if o_combat:
            # In O-combat the multiplier is a percentage where 10 is "normal",
            # so only the amount above 10 is doubled.
            mult = 2 * (mult - 10) + 10
        else:
            mult = mult * 2

    return mult


def slay_multiplier(slay, matches, o_combat):
    """Effective multiplier a slay contributes, or None if it cannot apply.

    Rule 3: a slay only applies to monsters of the targeted kind.
    """
    if not matches:
        return None
    return slay["o_multiplier"] if o_combat else slay["multiplier"]


def brand_verb(brand, is_range):
    """Rule 6: ranged brand verbs take a trailing 's'."""
    verb = brand["verb"]
    return verb + "s" if is_range else verb


def slay_verb(slay, is_range):
    return slay["range_verb"] if is_range else slay["melee_verb"]


def resolve(case, brand=None, slay=None):
    """Predict what improve_attack_modifier() should produce for a case.

    Returns a dict with the modifier the engine is expected to pick.
    `brand_used` / `slay_used` are the codes (or None); the engine reports
    indices, which the analyzer maps back to codes before comparing.
    """
    o_combat = case["o_combat"]
    is_range = case["range"]

    # Baseline: no modifier beats a plain, unmodified hit.
    best_mult = 1
    result = {"brand_used": None, "slay_used": None, "verb": None,
              "multiplier": best_mult}

    # Rule 5: brands are evaluated first, so on a tie the brand is kept.
    if brand is not None:
        mult = brand_multiplier(brand, case["mon_resists"],
                                case["mon_vulnerable"], o_combat)
        if mult is not None and mult > best_mult:
            best_mult = mult
            result = {"brand_used": brand["code"], "slay_used": None,
                      "verb": brand_verb(brand, is_range),
                      "multiplier": mult}

    if slay is not None:
        mult = slay_multiplier(slay, case["mon_matches_slay"], o_combat)
        # Rule 4 + 5: strictly greater, so a tie leaves the brand in place.
        if mult is not None and mult > best_mult:
            best_mult = mult
            result = {"brand_used": None, "slay_used": slay["code"],
                      "verb": slay_verb(slay, is_range),
                      "multiplier": mult}

    return result
