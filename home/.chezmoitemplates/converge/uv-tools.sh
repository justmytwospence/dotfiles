{{- if or (hasPrefix "mac-" .host) (has .host (list "nuc" "agentbox-box")) }}
# uv tool receipts (lib/uv_tools.py, docs/cooldown.md): tools that use a package I maintain
# exempt it in their receipt, a per-package cutoff older than the cooldown (a lapsed
# fast-forward) is dropped with its pin, and the retired 2999 sentinels leave every receipt.
# Reinstalls rewrite the receipt only; nothing is upgraded. Silent when converged.
converge_uv_tools() {
    have uv || return 0
    python3 -B {{ joinPath .chezmoi.sourceDir "lib/uv_tools.py" | quote }} --maintained {{ join "," .cooldownExempt.uv | squote }}
}
run converge_uv_tools
{{- end }}
