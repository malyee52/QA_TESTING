"""engine-adapter (part 1): render test cases into a C harness.

The harness is a normal member of Angband's unit-test suite, so it links
against the real engine and calls the real improve_attack_modifier(). Rather
than asserting inside C, it *prints* what the engine produced, one line per
case:

    RESULT <case_id> <brand_code|-> <slay_code|-> <verb|-> <multiplier>

Keeping the comparison in Python means a mismatch reports the full expected
vs. actual row instead of just a failed assertion line number.
"""

import argparse
import json
import pathlib

HEADER = r'''/* GENERATED FILE, DO NOT EDIT BY HAND.
 *
 * Regenerate with: python3 qa/runner/render_c_test.py
 *
 * Drives improve_attack_modifier() over a decision-table expansion and prints
 * one RESULT line per case for the QA analyzer to diff against the reference
 * model.
 */

#include "unit-test.h"
#include "unit-test-data.h"
#include "test-utils.h"
#include "init.h"
#include "mon-spell.h"
#include "obj-slays.h"
#include "option.h"
#include "player-birth.h"
#include "player-timed.h"
#include "z-color.h"
#include "z-util.h"
#include "z-virt.h"

int setup_tests(void **state)
{
	set_file_paths();
	init_angband();
#ifdef UNIX
	create_needed_dirs();
#endif
	if (!player_make_simple(NULL, NULL, "QATester")) {
		cleanup_angband();
		return 1;
	}
	return 0;
}

int teardown_tests(void *state)
{
	cleanup_angband();
	return 0;
}

/* Minimal stand-ins for a monster and a weapon. Only the fields the code
 * under test actually reads are populated. */
static struct monster_base qa_base;
static struct monster_race qa_race;
static struct monster qa_mon;
static struct object_base qa_obase;
static struct object_kind qa_kind;
static struct object qa_weapon;

static void qa_reset_monster(void)
{
	static char bname[20] = "blob";
	static char btext[20] = "blob";
	static char rname[20] = "test blob";
	static char rtext[20] = "test blob";

	memset(&qa_base, 0, sizeof(qa_base));
	qa_base.name = bname;
	qa_base.text = btext;
	qa_base.d_char = L'b';
	rf_wipe(qa_base.flags);

	memset(&qa_race, 0, sizeof(qa_race));
	qa_race.name = rname;
	qa_race.text = rtext;
	qa_race.base = &qa_base;
	qa_race.ridx = 1;
	qa_race.avg_hp = 10;
	qa_race.ac = 12;
	qa_race.speed = 110;
	qa_race.level = 1;
	qa_race.rarity = 1;
	qa_race.d_attr = COLOUR_WHITE;
	qa_race.d_char = qa_base.d_char;
	qa_race.max_num = 100;
	rf_wipe(qa_race.flags);
	rsf_wipe(qa_race.spell_flags);

	memset(&qa_mon, 0, sizeof(qa_mon));
	qa_mon.race = &qa_race;
	qa_mon.midx = 1;
	qa_mon.grid = loc(1, 1);
	qa_mon.hp = qa_race.avg_hp;
	qa_mon.maxhp = qa_race.avg_hp;
	qa_mon.mspeed = qa_race.speed;
	qa_mon.cdis = 100;
	rf_wipe(qa_mon.mflag);
}

static void qa_reset_weapon(bool **brands_arr, bool **slays_arr)
{
	static char oname[20] = "weapon";

	memset(&qa_obase, 0, sizeof(qa_obase));
	qa_obase.name = oname;
	qa_obase.tval = 1;
	of_wipe(qa_obase.flags);
	kf_wipe(qa_obase.kind_flags);

	memset(&qa_kind, 0, sizeof(qa_kind));
	qa_kind.name = oname;
	qa_kind.text = oname;
	qa_kind.base = &qa_obase;
	qa_kind.kidx = 1;
	qa_kind.tval = qa_obase.tval;
	qa_kind.sval = 1;
	qa_kind.dd = 1;
	qa_kind.ds = 4;
	qa_kind.weight = 10;
	of_wipe(qa_kind.flags);
	kf_wipe(qa_kind.kind_flags);
	qa_kind.d_attr = COLOUR_WHITE;
	qa_kind.d_char = L'/';
	qa_kind.aware = true;

	memset(&qa_weapon, 0, sizeof(qa_weapon));
	qa_weapon.kind = &qa_kind;
	qa_weapon.oidx = 1;
	qa_weapon.grid = loc(1, 1);
	qa_weapon.tval = qa_kind.tval;
	qa_weapon.sval = qa_kind.sval;
	qa_weapon.dd = qa_kind.dd;
	qa_weapon.ds = qa_kind.ds;
	qa_weapon.number = 1;
	qa_weapon.origin = ORIGIN_DROP_WIZARD;
	qa_weapon.origin_depth = 1;
	of_wipe(qa_weapon.flags);

	memset(*brands_arr, 0, z_info->brand_max * sizeof(**brands_arr));
	memset(*slays_arr, 0, z_info->slay_max * sizeof(**slays_arr));
	qa_weapon.brands = *brands_arr;
	qa_weapon.slays = *slays_arr;
}

/* Look a brand/slay up by its gamedata code so the generated cases stay
 * readable and survive re-ordering of the data files. */
static int qa_brand_index(const char *code)
{
	int i;
	for (i = 1; i < z_info->brand_max; i++)
		if (brands[i].code && streq(brands[i].code, code)) return i;
	return 0;
}

static int qa_slay_index(const char *code)
{
	int i;
	for (i = 1; i < z_info->slay_max; i++)
		if (slays[i].code && streq(slays[i].code, code)) return i;
	return 0;
}

/* improve_attack_modifier() reports which modifier won but not the
 * multiplier it won with, so the multiplier is recomputed here through the
 * engine's own accessor. Without it, a wrong multiplier is only visible when
 * it happens to flip which modifier wins. */
static int qa_multiplier(int b, int s, bool o_combat)
{
	if (b) return get_monster_brand_multiplier(&qa_mon, &brands[b],
		o_combat);
	if (s) return o_combat ? slays[s].o_multiplier : slays[s].multiplier;
	return 1;
}

static void qa_report(const char *id, int b, int s, const char *verb,
		bool touched, bool o_combat)
{
	printf("RESULT %s %s %s %s %d\n", id,
		b ? brands[b].code : "-",
		s ? slays[s].code : "-",
		touched ? verb : "-",
		qa_multiplier(b, s, o_combat));
}

static int qa_run_cases(void *state)
{
	bool *brands_arr = mem_zalloc(z_info->brand_max * sizeof(*brands_arr));
	bool *slays_arr = mem_zalloc(z_info->slay_max * sizeof(*slays_arr));
	int bi = 0, si = 0, b, s;
	char verb[20];

	(void) bi; (void) si;

'''

FOOTER = r'''
	mem_free(slays_arr);
	mem_free(brands_arr);
	ok;
}

const char *suite_name = "qa/brand-slay";
struct test tests[] = {
	{ "generated-cases", qa_run_cases },
	{ NULL, NULL }
};
'''


def c_bool(value):
    return "true" if value else "false"


def render_case(case, brands, slays):
    """Emit the C block that sets up and runs one decision-table row."""
    lines = []
    cid = case["id"]
    lines.append(f'\t/* {cid}: brand={case["brand"]} slay={case["slay"]} '
                 f'resists={case["mon_resists"]} vuln={case["mon_vulnerable"]} '
                 f'matches={case["mon_matches_slay"]} '
                 f'o_combat={case["o_combat"]} range={case["range"]} */')
    lines.append("\tqa_reset_monster();")
    lines.append("\tqa_reset_weapon(&brands_arr, &slays_arr);")

    brand = brands.get(case["brand"])
    slay = slays.get(case["slay"])

    if brand:
        lines.append(f'\tbi = qa_brand_index("{brand["code"]}");')
        lines.append("\tif (bi) brands_arr[bi] = true;")
        # The monster's resistance / vulnerability is expressed through the
        # very flags the brand names, so read them off the brand record.
        if case["mon_resists"] and brand["resist_flag"]:
            lines.append(
                f'\trf_on(qa_race.flags, RF_{brand["resist_flag"]});')
        if case["mon_vulnerable"] and brand["vuln_flag"]:
            lines.append(
                f'\trf_on(qa_race.flags, RF_{brand["vuln_flag"]});')

    if slay:
        lines.append(f'\tsi = qa_slay_index("{slay["code"]}");')
        lines.append("\tif (si) slays_arr[si] = true;")
        if case["mon_matches_slay"]:
            if slay["race_flag"]:
                lines.append(
                    f'\trf_on(qa_race.flags, RF_{slay["race_flag"]});')
            elif slay["base"]:
                # Base-matched slays compare the monster base by name.
                lines.append(f'\tqa_base.name = "{slay["base"]}";')

    lines.append(f'\tplayer->opts.opt[OPT_birth_percent_damage] = '
                 f'{c_bool(case["o_combat"])};')
    lines.append("\tb = 0;")
    lines.append("\ts = 0;")
    # "hit" is the engine's default verb; if it survives, no modifier fired.
    lines.append('\tmy_strcpy(verb, "hit", sizeof(verb));')
    lines.append(f'\timprove_attack_modifier(player, &qa_weapon, &qa_mon, '
                 f'&b, &s, verb, {c_bool(case["range"])});')
    lines.append(f'\tqa_report("{cid}", b, s, verb, !streq(verb, "hit"), '
                 f'{c_bool(case["o_combat"])});')
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True, help="C file to write")
    args = ap.parse_args()

    cases = json.loads(pathlib.Path(args.cases).read_text(encoding="utf-8"))
    spec = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
    brands = {b["code"]: b for b in spec["brands"]}
    slays = {s["code"]: s for s in spec["slays"]}

    body = "\n".join(render_case(c, brands, slays) for c in cases)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(HEADER + body + FOOTER, encoding="utf-8")
    print(f"rendered {len(cases)} cases -> {out}")


if __name__ == "__main__":
    main()
