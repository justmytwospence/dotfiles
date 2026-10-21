# Shared by every converge section. A section is a function that checks the real state
# and acts only when it differs; `run` calls it and records a failure without stopping
# the rest. Nothing prints unless something changes.
STATE="$HOME/.local/state/dotfiles/converge"
failed=()
have() { command -v "$1" >/dev/null 2>&1; }
step() { printf '==> %s\n' "$*"; }
run() { "$1" || failed+=("${1#converge_}"); }
# For steps with no native state to query: stamped NAME KEY is true when NAME last
# converged with KEY; stamp NAME KEY records it.
stamped() { [[ -f $STATE/$1 && $(<"$STATE/$1") == "$2" ]]; }
stamp() { mkdir -p "$STATE" && printf '%s\n' "$2" >"$STATE/$1"; }
digest() {
    if have sha256sum; then sha256sum "$@"; else shasum -a 256 "$@"; fi 2>/dev/null | awk '{printf "%s ", $1}'
}
