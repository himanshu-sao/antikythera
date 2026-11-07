#!/bin/bash
# Back up the Antikythera data directory (automation-ideas/) to a timestamped tar.gz.
#
# Usage:
#   scripts/backup_data.sh [SOURCE_DIR]
#
#   SOURCE_DIR                 directory to back up (default: <repo>/automation-ideas)
#   ANTIKYTHERA_BACKUP_DIR     where archives go (default: $HOME/antikythera-backups)
#   ANTIKYTHERA_BACKUP_KEEP    how many newest archives to keep (default: 14)
#
# Output: <backup dir>/automation-ideas-<UTC YYYYmmddTHHMMSSZ>.tar.gz, mode 0600.
#
# Notes
#   - Dotfiles are included on purpose (.vault.key is needed to read the vault).
#   - Only *.lock files are excluded. *.corrupt-* copies are kept.
#   - The archive holds secrets: the backup directory is created 0700 and the archive 0600.
#     Do not copy it anywhere less protected than the data directory itself.
#   - Safe under cron: no prompts, exits non-zero with a message on any failure, writes the
#     archive to a temporary name and renames it only when complete, and only ever deletes
#     files that match its own archive name pattern inside the backup directory.
#   - Example crontab (daily 02:30):  30 2 * * * /path/to/antikythera/scripts/backup_data.sh
#
# Exit codes: 0 ok, 1 usage/config error, 2 source missing, 3 archive failure.

set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

SRC="${1:-$REPO_DIR/automation-ideas}"
BACKUP_DIR="${ANTIKYTHERA_BACKUP_DIR:-$HOME/antikythera-backups}"
KEEP="${ANTIKYTHERA_BACKUP_KEEP:-14}"
PREFIX="automation-ideas-"
SUFFIX=".tar.gz"

die() {
  local code="$1"; shift
  echo "backup_data: $*" >&2
  exit "$code"
}

[ "$#" -le 1 ] || die 1 "usage: $0 [SOURCE_DIR]"

# An empty ANTIKYTHERA_BACKUP_KEEP falls back to the default (14), like an unset one.
case "$KEEP" in
  *[!0-9]*) die 1 "ANTIKYTHERA_BACKUP_KEEP must be a positive integer" ;;
esac
[ "$KEEP" -ge 1 ] || die 1 "ANTIKYTHERA_BACKUP_KEEP must be at least 1"

[ -n "$BACKUP_DIR" ] || die 1 "ANTIKYTHERA_BACKUP_DIR is empty"
[ -d "$SRC" ] || die 2 "source directory not found: $SRC"

# Resolve to absolute paths so the "backup dir inside source" check is reliable.
SRC="$(cd "$SRC" && pwd -P)"
if [ ! -d "$BACKUP_DIR" ]; then
  mkdir -p "$BACKUP_DIR"
  chmod 700 "$BACKUP_DIR"   # only a directory we create gets tightened
fi
BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd -P)"

case "$BACKUP_DIR/" in
  "$SRC"/*) die 1 "backup directory must not be inside the source directory" ;;
esac

# The name is the UTC start time to the second. Two runs in the same second must not
# collide and must not get a suffix: "-1" sorts BEFORE ".tar.gz", which would make the newer
# archive look older to rotation. If the name is taken, wait for the clock to advance.
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FINAL="$BACKUP_DIR/${PREFIX}${STAMP}${SUFFIX}"
waited=0
while [ -e "$FINAL" ]; do
  [ "$waited" -lt 10 ] || die 3 "could not get a free archive name for $STAMP"
  sleep 1
  waited=$((waited + 1))
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  FINAL="$BACKUP_DIR/${PREFIX}${STAMP}${SUFFIX}"
done
TMP="$(mktemp "$BACKUP_DIR/.${PREFIX}partial.XXXXXX")"
trap 'rm -f "$TMP"' EXIT

# Archive the directory's contents (entries are ./<name>, so restore with: tar -C DEST -xzf).
# "." includes dotfiles; --exclude drops lock files only. COPYFILE_DISABLE stops macOS bsdtar
# from adding AppleDouble "._" metadata entries (GNU tar ignores it).
if ! COPYFILE_DISABLE=1 tar -czf "$TMP" --exclude='*.lock' -C "$SRC" . ; then
  die 3 "tar failed for $SRC"
fi

chmod 600 "$TMP"
# Verify the archive is readable before it replaces anything.
tar -tzf "$TMP" >/dev/null || die 3 "archive verification failed"
mv "$TMP" "$FINAL"
trap - EXIT
echo "backup_data: wrote $FINAL"

# Rotation: keep the newest KEEP archives. Names sort chronologically because the stamp is
# fixed-width UTC, so a lexical sort is a time sort. Only our own name pattern is touched.
count=0
while IFS= read -r f; do
  count=$((count + 1))
  if [ "$count" -gt "$KEEP" ]; then
    rm -f -- "$f"
    echo "backup_data: removed old backup $(basename "$f")"
  fi
done < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name "${PREFIX}*${SUFFIX}" | sort -r)
