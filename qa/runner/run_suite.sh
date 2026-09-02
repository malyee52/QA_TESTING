#!/bin/sh
# engine-adapter (part 2): inject the generated C harness into Angband's unit
# test suite, build it, and capture the engine's RESULT lines.
#
# Usage: run_suite.sh <generated.c> <output.txt>
#
# The vendored tree is treated as a scratch build area: the harness is copied
# in and the suite list is patched idempotently, so re-running is safe.

set -e

GEN_C="$1"
OUT="$2"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="${ANGBAND_SRC:-$ROOT/vendor/angband}"
TESTS="$SRC/src/tests"

if [ -z "$GEN_C" ] || [ -z "$OUT" ]; then
	echo "usage: $0 <generated.c> <output.txt>" >&2
	exit 2
fi
if [ ! -d "$TESTS" ]; then
	echo "angband test tree not found at $TESTS; run scripts/setup-angband.sh" >&2
	exit 1
fi

mkdir -p "$TESTS/qa"
cp "$GEN_C" "$TESTS/qa/brand-slay.c"

cat > "$TESTS/qa/suite.mk" << 'MK'
TESTPROGS += \
	qa/brand-slay
MK

# Register the suite with the test Makefile, once.
if ! grep -q "qa/suite.mk" "$TESTS/Makefile"; then
	sed -i 's|^\tartifact/suite.mk \\|\tqa/suite.mk \\\n\tartifact/suite.mk \\|' \
		"$TESTS/Makefile"
	grep -q "qa/suite.mk" "$TESTS/Makefile" || {
		echo "failed to register qa/suite.mk in $TESTS/Makefile" >&2
		exit 1
	}
fi

# Angband refuses to start without a UTF-8 locale.
LC_ALL=C.utf8
LANG=C.utf8
export LC_ALL LANG

make -C "$TESTS" qa/brand-slay.exe >/dev/null

mkdir -p "$(dirname "$OUT")"
# Test cases resolve gamedata through TEST_DEFAULT_PATH, which defaults to
# "./lib/" -- so the binary has to be run from the top of the game tree.
cd "$SRC"
# The harness prints RESULT lines on stdout alongside the suite's own
# pass/fail summary; the analyzer picks out what it needs.
src/tests/qa/brand-slay.exe > "$OUT" 2>&1 || true

echo "captured $(grep -c '^RESULT ' "$OUT" || true) RESULT lines -> $OUT"
