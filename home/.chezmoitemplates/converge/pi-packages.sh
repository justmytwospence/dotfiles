# Pi packages from settings.managed.json: a Git package checked out at its pinned commit,
# an npm package installed (at its pinned version, if any). `pi update <source>` installs
# a missing package or moves a checkout to its pin without touching settings.json; Pi
# itself and unpinned npm packages are never upgraded here. npm packages dropped from
# the settings are uninstalled.
converge_pi_packages() {
    have pi || return 0
    local dir="$HOME/.pi/agent" rc=0
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
{{- range (include "private_dot_pi/private_agent/settings.managed.json" | fromJson).packages }}
{{- $source := . }}
{{- if kindIs "map" . }}{{ $source = .source }}{{ end }}
{{- if hasPrefix "git:" $source }}
{{- $parts := splitList "@" (trimPrefix "git:" $source) }}
{{- $ref := "?*" }}{{ if gt (len $parts) 1 }}{{ $ref = index $parts 1 }}{{ end }}
    [[ $(git -C "$dir/git/{{ index $parts 0 }}" rev-parse HEAD 2>/dev/null) == {{ $ref }} ]] ||
        { step "pi {{ $source }}"; pi update {{ $source | quote }} </dev/null || rc=1; }
{{- else if hasPrefix "npm:" $source }}
{{- $spec := trimPrefix "npm:" $source }}
{{- $name := regexReplaceAll "^(@?[^@]+)(@.*)?$" $spec "${1}" }}
{{- $version := regexReplaceAll "^@?[^@]+@?" $spec "" }}
    grep -qs '"version": *"{{ $version | default "[^\"]*" }}"' "$dir/npm/node_modules/{{ $name }}/package.json" ||
        { step "pi {{ $source }}"; pi update {{ $source | quote }} </dev/null || rc=1; }
{{- end }}
{{- end }}
    return $rc
}
run converge_pi_packages
