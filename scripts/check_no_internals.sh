#!/bin/bash
set -euo pipefail

# ============================================================
# Scan a git repository for strings that must not be published.
# ============================================================
# The strings come from a local, git-ignored denylist (one
# literal per line, matched case-insensitively as fixed strings).
# The script prints locations (paths, hashes, counts) only,
# never the matched text.
#
# Usage:
#   scripts/check_no_internals.sh [--tree|--history] [--require-denylist]
#
# Environment:
#   INTERNALS_DENYLIST  path to the denylist
#                       (default: <repo root>/.internals-denylist)
#
# Exit codes: 0 clean (or skipped), 1 hits, 2 denylist required but missing
# ============================================================

MODE="tree"
REQUIRE=0
for arg in "$@"; do
  case "$arg" in
    --tree) MODE="tree" ;;
    --history) MODE="history" ;;
    --require-denylist) REQUIRE=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 64 ;;
  esac
done

TOP="$(git rev-parse --show-toplevel)"
cd "$TOP"
DENYLIST="${INTERNALS_DENYLIST:-$TOP/.internals-denylist}"

HAVE_LIST=1
if [ ! -s "$DENYLIST" ]; then
  HAVE_LIST=0
  if [ "$REQUIRE" -eq 1 ]; then
    echo "ERROR: denylist missing or empty" >&2
    exit 2
  fi
  if [ "$MODE" = "tree" ]; then
    echo "SKIPPED: no denylist"
    exit 0
  fi
fi

HITS=0
hit() { echo "$1"; HITS=$((HITS + 1)); }

if [ "$MODE" = "tree" ]; then
  while IFS= read -r f; do
    [ -n "$f" ] && hit "$f"
  done < <(git grep -I -i -F -l -f "$DENYLIST" -- . ':!.planning' || true)
else
  if [ "$HAVE_LIST" -eq 1 ]; then
    # (1) file contents of every commit
    while IFS= read -r rev; do
      while IFS= read -r line; do
        [ -n "$line" ] && hit "$line"
      done < <(git grep -I -i -F -l -f "$DENYLIST" "$rev" || true)
    done < <(git rev-list --all)

    # (2) commit metadata and messages: hashes only
    while IFS= read -r h; do
      [ -n "$h" ] && hit "commit-message/author: $h"
    done < <(
      git log --all --format='%x01%H %an <%ae> %cn <%ce>%n%B' \
        | awk 'BEGIN{RS="\001"} NR>1 {print}' \
        | while IFS= read -r rec; do
            hash="${rec%% *}"
            if printf '%s' "$rec" | grep -q -i -F -f "$DENYLIST"; then
              echo "$hash"
            fi
          done
    )

    # (3) tags: names only
    while IFS= read -r t; do
      if git for-each-ref "$t" --format='%(taggername) %(taggeremail) %(contents)' \
          | grep -q -i -F -f "$DENYLIST"; then
        hit "tag: $t"
      fi
    done < <(git for-each-ref refs/tags --format='%(refname)')
  fi

  # (4) built-in checks that need no denylist
  PLAN_HASHES="$(git log --all --format='%x01%H %B' | awk 'BEGIN{RS="\001"} tolower($0) ~ /\.planning/ {print substr($1,1,12)}' | sort -u || true)"
  if [ -n "$PLAN_HASHES" ]; then
    n="$(printf '%s\n' "$PLAN_HASHES" | wc -l | tr -d ' ')"
    echo "messages mentioning the planning directory: $n"
    printf '%s\n' "$PLAN_HASHES"
    HITS=$((HITS + n))
  fi
  n="$(git rev-list --objects --all | grep -c -E '(^| )(\.planning/|docs/screen-[^/]*\.png|display/)' || true)"
  if [ "${n:-0}" -gt 0 ]; then
    echo "objects under purged paths: $n"
    HITS=$((HITS + n))
  fi
fi

if [ "$HITS" -eq 0 ]; then
  echo "CLEAN"
  exit 0
fi
echo "HITS: $HITS"
exit 1
