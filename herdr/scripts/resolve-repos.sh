#!/bin/bash
# Resolve which herdr workspace list is in effect, and optionally print it.
#
# Resolution order — first hit wins, and it wins outright. Lists are never
# merged, so a machine-local list shows only the repos it names:
#
#   1. $HERDR_REPOS                      explicit override (any path)
#   2. ~/.config/herdr/repos.local.yaml  machine-local list, untracked. Work
#                                        repos go here so they stay out of the
#                                        public repo.
#   3. <repo>/herdr/spreader.yaml        the committed personal list
#
# Usage:
#   resolve-repos.sh              print the path of the active list
#   resolve-repos.sh --entries    print "label<TAB>root" per workspace, ~ expanded
#   resolve-repos.sh --source     print a one-word provenance: env|local|repo
#
# $HERDR_REPOS set to a path that does not exist is an error, not a fallthrough —
# a typo there should be loud rather than silently reverting to the personal list.
set -uo pipefail

MODE="path"
case "${1:-}" in
  "")         ;;
  --entries)  MODE="entries" ;;
  --source)   MODE="source" ;;
  --path)     MODE="path" ;;
  *) echo "resolve-repos: unknown argument: $1" >&2; exit 2 ;;
esac

# Real path of this script, following symlinks, so the repo copy of spreader.yaml
# is still findable if we are ever invoked through a symlink.
# Not `readlink -f`: absent from older BSD userlands.
self="${BASH_SOURCE[0]}"
while [ -L "$self" ]; do
  link=$(readlink "$self")
  case "$link" in
    /*) self="$link" ;;
    *)  self="$(dirname "$self")/$link" ;;
  esac
done
SCRIPTS_DIR="$(cd "$(dirname "$self")" && pwd)"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/herdr"
LOCAL_LIST="$CONFIG_DIR/repos.local.yaml"
REPO_LIST="$SCRIPTS_DIR/../spreader.yaml"

if [ -n "${HERDR_REPOS:-}" ]; then
  if [ ! -f "$HERDR_REPOS" ]; then
    echo "resolve-repos: \$HERDR_REPOS='$HERDR_REPOS' is not a file" >&2
    exit 1
  fi
  LIST="$HERDR_REPOS"; SOURCE="env"
elif [ -f "$LOCAL_LIST" ]; then
  LIST="$LOCAL_LIST"; SOURCE="local"
elif [ -f "$REPO_LIST" ]; then
  LIST="$REPO_LIST"; SOURCE="repo"
else
  echo "resolve-repos: no workspace list found (tried \$HERDR_REPOS, $LOCAL_LIST, $REPO_LIST)" >&2
  exit 1
fi

# Absolute, symlink-free path so callers can print it unambiguously.
LIST="$(cd "$(dirname "$LIST")" && pwd)/$(basename "$LIST")"

case "$MODE" in
  path)   printf '%s\n' "$LIST" ;;
  source) printf '%s\n' "$SOURCE" ;;
  entries)
    # The list shape is fixed (see gen-spreader.sh): a `- name:` line followed by
    # a `root:` line per workspace. A hand-rolled parse keeps this dependency-free
    # — no yq, no python yaml — which is the whole point of the fallback path.
    awk '
      match($0, /^[[:space:]]*-[[:space:]]+name:[[:space:]]*/) {
        name = substr($0, RSTART + RLENGTH)
        gsub(/^"|"$/, "", name); gsub(/[[:space:]]+$/, "", name)
        next
      }
      match($0, /^[[:space:]]+root:[[:space:]]*/) {
        root = substr($0, RSTART + RLENGTH)
        gsub(/^"|"$/, "", root); gsub(/[[:space:]]+$/, "", root)
        if (name != "" && root != "") { print name "\t" root }
        name = ""; root = ""
        next
      }
    ' "$LIST" | while IFS=$'\t' read -r label root; do
      printf '%s\t%s\n' "$label" "${root/#\~/$HOME}"
    done
    ;;
esac
