# Pi packages from settings.managed.json: a Git package checked out at its pinned commit,
# an npm package installed (at its pinned version, if any). `pi update <source>` installs
# a missing package or moves a checkout to its pin without touching settings.json; Pi
# itself and unpinned npm packages are never upgraded here.
converge_pi_packages() {
    have pi || return 0
    local dir="$HOME/.pi/agent" rc=0
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
