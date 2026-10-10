#!/usr/bin/env bash
# Cross-platform Python launcher for AI log hooks.
# Tries python3 → python → py -3 on PATH; on Windows, falls back to common
# Python install locations because Git Bash launched by some hooks gets a
# stripped PATH that omits the Windows Python directory.
# Designed to be sourced or called as: bash scripts/_pyrun.sh <script> [args...]
#
# Exits 0 silently if no Python is found — hooks must never block the AI tool.
set -u

# A command can exist on PATH but still be a broken Windows Store execution
# alias. Probe that it starts a real interpreter before selecting it.
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then
  exec python3 "$@"
elif command -v python >/dev/null 2>&1 && python -c 'import sys' >/dev/null 2>&1; then
  exec python "$@"
elif command -v py >/dev/null 2>&1 && py -3 -c 'import sys' >/dev/null 2>&1; then
  exec py -3 "$@"
fi

# PATH lookup can resolve to a Store alias, or Git Bash may start with a
# stripped PATH. Probe standard Windows installs and the bundled Codex runtime.
shopt -s nullglob 2>/dev/null || true
for cand in \
  /c/Users/*/AppData/Local/Programs/Python/Python*/python.exe \
  /c/Users/*/.cache/codex-runtimes/*/dependencies/python/python.exe \
  "/c/Program Files/Python"*/python.exe \
  "/c/Program Files (x86)/Python"*/python.exe \
  /c/Python*/python.exe; do
  if [ -x "$cand" ] && "$cand" -c 'import sys' >/dev/null 2>&1; then
    exec "$cand" "$@"
  fi
done
shopt -u nullglob 2>/dev/null || true

exit 0
