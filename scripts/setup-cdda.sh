#!/bin/sh
# Fetch and build Cataclysm: Dark Days Ahead with the curses (terminal) interface.
#
# Produces:
#   vendor/cataclysm-dda/cataclysm   - curses game binary, no tiles/SDL/sound
#
# Idempotent: skips work that is already done.

set -e

REPO_URL="${CDDA_REPO:-https://github.com/CleverRaven/cataclysm-dda}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/vendor/cataclysm-dda"

log() { printf '[setup] %s\n' "$1"; }

if [ ! -d "$SRC/.git" ]; then
	log "cloning $REPO_URL"
	mkdir -p "$ROOT/vendor"
	# LFS objects aren't needed to build the curses binary; skip the smudge
	# filter so a clone doesn't fail on repos that require LFS credentials.
	GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 "$REPO_URL" "$SRC"
else
	log "reusing existing clone at $SRC"
fi

cd "$SRC"

if [ ! -x cataclysm ]; then
	# TILES=0 SOUND=0 drop the SDL2 dependency (headless box, no display);
	# LOCALIZE=0 drops the gettext runtime requirement. CCACHE speeds up
	# rebuilds after a `git pull`.
	log "building curses binary (this takes a while)"
	make -j"$(nproc 2>/dev/null || echo 2)" \
		RELEASE=1 TILES=0 SOUND=0 LOCALIZE=0 CCACHE=1
else
	log "reusing existing binary at $SRC/cataclysm"
fi

log "done: $SRC/cataclysm"
