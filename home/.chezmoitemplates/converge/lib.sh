# Shared by every provisioning script (.chezmoiscripts/run_onchange_*). A section is a
# function that checks the real state and acts only when it differs; `run` calls it and
# records a failure without stopping the rest, and the script's tail then exits 1 so chezmoi
# reruns the script on the next apply. Nothing prints unless something changes.
failed=()
have() { command -v "$1" >/dev/null 2>&1; }
step() { printf '==> %s\n' "$*"; }
run() { "$1" || failed+=("${1#converge_}"); }
digest() {
    if have sha256sum; then sha256sum "$@"; else shasum -a 256 "$@"; fi 2>/dev/null | awk '{printf "%s ", $1}'
}
# bin/converge sets DOTFILES_CONVERGE_MANUAL=1: the script runs without an input change,
# so services are only ensured loaded, never reloaded.
inputs_changed() { [ -z "${DOTFILES_CONVERGE_MANUAL:-}" ]; }
# adopted NAME KEY: true when the retired converge stamp for NAME (2026-11-17) recorded
# KEY, i.e. the running service already has this definition. Deletes that stamp either way.
adopted() {
    local dir="$HOME/.local/state/dotfiles/converge" value
    [ -f "$dir/$1" ] || return 1
    value=$(<"$dir/$1")
    rm -f "$dir/$1"
    rmdir "$dir" "${dir%/*}" 2>/dev/null
    [ "$value" = "$2" ]
}
