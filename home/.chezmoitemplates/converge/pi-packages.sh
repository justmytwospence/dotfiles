# Pi packages from settings.managed.json: a Git package checked out at its pinned commit
# (a tag pin's commit comes from .chezmoidata/pi_tag_commits.json),
# an npm package installed (at its pinned version, if any). `pi update <source>` installs
# a missing Git package or moves a checkout to its pin without touching settings.json.
# npm packages go through `pi install <source>`: `pi update` leaves an installed npm
# package on its old version when the pin changes (pi 1.4.0), while `pi install` of the
# entry settings.json already holds installs that version and leaves settings.json as
# is. Pi itself and unpinned npm packages are never upgraded here. npm packages and Git
# checkouts dropped from the settings are removed (a checkout with uncommitted or unpushed
# work is reported and kept).
converge_pi_packages() {
    have pi || return 0
    local dir="$HOME/.pi/agent" rc=0 updated=0
    # npm packages no longer in settings.json: pi stops loading a package dropped from
    # `packages` but leaves it installed in ~/.pi/agent/npm.
    local pi_npm="$dir/npm" extra
    if [ -f "$pi_npm/package.json" ] && [ -f "$dir/settings.json" ] && command -v npm >/dev/null 2>&1; then
        extra=$(python3 - "$pi_npm/package.json" "$dir/settings.json" <<'PY'
import json, sys
def name(spec):
    spec = spec[4:]
    at = spec.find("@", 1)
    return spec if at < 0 else spec[:at]
installed = json.load(open(sys.argv[1])).get("dependencies", {})
# A package entry is a source string or an object with a `source` (filtered resources).
sources = [p.get("source") if isinstance(p, dict) else p
           for p in json.load(open(sys.argv[2])).get("packages", [])]
wanted = {name(s) for s in sources if isinstance(s, str) and s.startswith("npm:")}
print(" ".join(sorted(set(installed) - wanted)))
PY
)
        if [ -n "$extra" ]; then
            step "pi: uninstall npm packages no longer configured: $extra"
            # shellcheck disable=SC2086  # a word list of package names
            npm --prefix "$pi_npm" uninstall --legacy-peer-deps --no-audit --no-fund $extra >/dev/null 2>&1 || rc=1
        fi
    fi
    # Git checkouts of packages no longer in settings.json: pi stops loading them but leaves
    # them under ~/.pi/agent/git. A checkout holding work that exists nowhere else stays.
    local wanted checkout rel
    if [ -f "$dir/settings.json" ] && [ -d "$dir/git" ]; then
        wanted=$(python3 - "$dir/settings.json" <<'PY'
import json, re, sys
sources = [p.get("source") if isinstance(p, dict) else p
           for p in json.load(open(sys.argv[1])).get("packages", [])]
for s in sources:
    if isinstance(s, str) and s.startswith("git:"):
        spec = re.sub(r"^git:(https?://)?", "", s).split("@")[0]
        print(spec[:-4] if spec.endswith(".git") else spec)
PY
) || return 1
        for checkout in "$dir"/git/*/*/*; do
            [ -e "$checkout/.git" ] || continue
            rel=${checkout#"$dir/git/"}
            grep -qxF "$rel" <<<"$wanted" && continue
            # package-lock.json is rewritten by pi's own npm install, so it is not work.
            if [ -n "$(git -C "$checkout" status --porcelain -- . ':(exclude)package-lock.json' 2>/dev/null)" ] ||
                [ -n "$(git -C "$checkout" log --branches --not --remotes --oneline -1 2>/dev/null)" ]; then
                echo "pi: $checkout is no longer configured but has local work; remove it by hand" >&2
                continue
            fi
            step "pi: remove unconfigured checkout $rel"
            rm -rf "$checkout" || rc=1
        done
    fi
{{- range (include "private_dot_pi/private_agent/settings.managed.json" | fromJson).packages }}
{{- $source := . }}
{{- if kindIs "map" . }}{{ $source = .source }}{{ end }}
{{- if hasPrefix "git:" $source }}
{{- $parts := splitList "@" (trimPrefix "git:" $source) }}
{{- $ref := "?*" }}{{ if gt (len $parts) 1 }}{{ $ref = index $parts 1 }}{{ end }}
{{- $commit := $ref }}
{{- if and (gt (len $parts) 1) (not (regexMatch "^[0-9a-f]{40}$" $ref)) }}
{{- $commit = index $.piTagCommits $source }}
{{- if not $commit }}{{ fail (printf "%s: tag pin without a commit in .chezmoidata/pi_tag_commits.json" $source) }}{{ end }}
{{- end }}
    [[ $(git -C "$dir/git/{{ index $parts 0 }}" rev-parse HEAD 2>/dev/null) == {{ $commit }} ]] ||
        { step "pi {{ $source }}"; pi update {{ $source | quote }} </dev/null && updated=1 || rc=1; }
{{- else if hasPrefix "npm:" $source }}
{{- $spec := trimPrefix "npm:" $source }}
{{- $name := regexReplaceAll "^(@?[^@]+)(@.*)?$" $spec "${1}" }}
{{- $version := regexReplaceAll "^@?[^@]+@?" $spec "" }}
    grep -qs '"version": *"{{ $version | default "[^\"]*" }}"' "$dir/npm/node_modules/{{ $name }}/package.json" ||
        { step "pi {{ $source }}"; pi install {{ $source | quote }} </dev/null && updated=1 || rc=1; }
{{- end }}
{{- end }}
    # Ask running Pi sessions to reload onto what was installed (pi-reload-all watches this
    # file; each session reloads once its turn ends and its editor is empty).
    if [ "$updated" = 1 ]; then
        step "pi: ask running sessions to reload"
        printf '{"id":"converge-%s-%s","at":%s000,"origin":"%s"}' "$(date +%s)" "$$" "$(date +%s)" "$(hostname -s)" >"$dir/reload-request.tmp" &&
            mv "$dir/reload-request.tmp" "$dir/reload-request" || rc=1
    fi
    return $rc
}
run converge_pi_packages
