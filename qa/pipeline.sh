#!/bin/sh
# Run the whole QA pipeline: parse -> generate -> render -> execute -> analyze.
#
# Usage: qa/pipeline.sh [--brands CODE...] [--slays CODE...]
# With no arguments every brand and slay in the gamedata is covered.
#
# Exits non-zero when the engine disagrees with the reference model, so this
# can be used directly as a CI gate.

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${ANGBAND_SRC:-$ROOT/vendor/angband}"

if [ ! -x "$SRC/src/angband" ]; then
	echo "Angband is not built. Run scripts/setup-angband.sh first." >&2
	exit 1
fi

SPEC="$ROOT/specs/gamedata.json"
CASES="$ROOT/test-cases/generated/cases.json"
GEN_C="$ROOT/test-cases/generated/brand-slay.c"
RESULTS="$ROOT/test-cases/generated/results.txt"
REPORT="$ROOT/reports/brand-slay.md"
FINDINGS="$ROOT/reports/brand-slay.json"

echo "== 1/4 item-parser =="
python3 "$ROOT/qa/parser/parse_gamedata.py" \
	--gamedata "$SRC/lib/gamedata" --out "$SPEC"

echo "== 2/4 case-generator =="
python3 "$ROOT/qa/generator/generate_cases.py" \
	--spec "$SPEC" --out "$CASES" "$@"

echo "== 3/4 engine-adapter =="
python3 "$ROOT/qa/runner/render_c_test.py" \
	--cases "$CASES" --spec "$SPEC" --out "$GEN_C"
"$ROOT/qa/runner/run_suite.sh" "$GEN_C" "$RESULTS"

echo "== 4/4 diff-analyzer =="
python3 "$ROOT/qa/analyzer/analyze.py" \
	--cases "$CASES" --results "$RESULTS" \
	--report "$REPORT" --json-out "$FINDINGS"
