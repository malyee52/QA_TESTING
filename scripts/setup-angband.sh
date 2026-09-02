#!/bin/sh
# Fetch and build Angband with the headless test frontend enabled.
#
# Produces:
#   vendor/angband/src/angband       - game binary with -mtest pseudo-UI
#   vendor/angband/src/tests/        - unit test harness (make tests)
#
# Idempotent: skips work that is already done.

set -e

REPO_URL="${ANGBAND_REPO:-https://github.com/angband/angband.git}"
REPO_REV="${ANGBAND_REV:-master}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/vendor/angband"

log() { printf '[setup] %s\n' "$1"; }

if [ ! -d "$SRC/.git" ]; then
	log "cloning $REPO_URL ($REPO_REV)"
	mkdir -p "$ROOT/vendor"
	git clone --depth 1 --branch "$REPO_REV" "$REPO_URL" "$SRC"
else
	log "reusing existing clone at $SRC"
fi

cd "$SRC"

if [ ! -f configure ]; then
	log "running autogen.sh"
	./autogen.sh
fi

if [ ! -f config.status ]; then
	# Only the test frontend is needed; graphical frontends are skipped so the
	# build works on a headless box with no X11/SDL/curses dev packages.
	log "configuring (test frontend only)"
	./configure --enable-test \
		--disable-curses --disable-x11 --disable-sdl --disable-sdl2
fi

log "building game binary"
make -j"$(nproc 2>/dev/null || echo 2)"

# run-tests and the game itself look for gamedata under the install prefix,
# so an install step is required before anything can be executed.
log "installing gamedata"
make install

log "done: $SRC/src/angband"
