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
# What --tree scans:
#   - tracked text files
#   - untracked files that are not git-ignored (text and binary),
#     reported as "untracked: <path>"; they are the next candidates
#     for "git add"
# What --tree does NOT scan:
#   - tracked binary files (git grep -I skips them, for example the
#     PNGs under docs/screens; a test keeps those free of metadata)
#   - git-ignored files (they cannot be committed by accident)
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
  # Untracked, not ignored files: not in the index yet, so git grep
  # does not see them. The denylist itself is never reported.
  while IFS= read -r -d '' f; do
    [ -f "$f" ] || continue
    [ "$f" -ef "$DENYLIST" ] && continue
    if grep -q -i -F -f "$DENYLIST" -- "$f" 2>/dev/null; then
      hit "untracked: $f"
    fi
  done < <(git ls-files --others --exclude-standard -z -- . ':!.planning')
else
  if [ "$HAVE_LIST" -eq 1 ]; then
    # (1) file contents of every commit
    while IFS= read -r rev; do
      while IFS= read -r line; do
        [ -n "$line" ] && hit "$line"
      done < <(git grep -I -i -F -l -f "$DENYLIST" "$rev" || true)
    done < <(git rev-list --all)

    # (2) commit metadata and messages: hashes only.
    # One commit per iteration, so a hit can only ever report the hash
    # and never a word of the message. grep reads all input (no -q) so
    # that git never sees a closed pipe under pipefail.
    while IFS= read -r h; do
      [ -n "$h" ] || continue
      if git show -s --format='%an <%ae> %cn <%ce>%n%B' "$h" \
          | grep -i -F -f "$DENYLIST" >/dev/null; then
        hit "commit-message/author: $h"
      fi
    done < <(git rev-list --all)

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
