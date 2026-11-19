#!/usr/bin/env bash
set -euo pipefail

case "${1:---check}" in
  --check|--apply) mode=${1:---check} ;;
  *) printf 'Usage: %s [--check|--apply]\n' "$0" >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || exit 2

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "${LOCI_WORKSPACE:-/home/loci/loci-memory-engine}"

check_clean() {
  local status
  if [[ $(git symbolic-ref --quiet --short HEAD) != main ]]; then
    printf 'Refusing synchronization outside the main branch.\n' >&2
    exit 1
  fi
  status=$(git status --porcelain=v1 --untracked-files=all)
  if [[ -n $status ]]; then
    printf 'Refusing synchronization with staged, unstaged, or untracked work.\n' >&2
    exit 1
  fi
}

check_clean
git fetch --quiet --no-tags --no-auto-maintenance origin refs/heads/main:refs/remotes/origin/main
target=$(git rev-parse --verify refs/remotes/origin/main^{commit})
current=$(git rev-parse --verify HEAD)
if ! git merge-base --is-ancestor "$current" "$target"; then
  printf 'Refusing synchronization because local main is ahead of or diverged from origin.\n' >&2
  exit 1
fi
expected=$(git show "$target:manifest.sha256")
if [[ ! $expected =~ ^[[:xdigit:]]{64}$ ]] ||
   [[ $(python3 "$script_dir/scripts/engine_manifest.py" "$target") != "$expected" ]]; then
  printf 'Refusing synchronization because the target engine manifest is invalid.\n' >&2
  exit 1
fi
if [[ $mode == --check || $current == "$target" ]]; then
  printf 'Verified synchronization target %s.\n' "$target"
  exit 0
fi
check_clean
git -c core.hooksPath=/dev/null merge --ff-only --no-overwrite-ignore "$target"
printf 'Fast-forwarded to %s. Services require separate authorization.\n' "$target"
