# Resolve the enabled family slots offline from Pi's last-known catalog.
converge_pi_models() {
    python3 -B - "$HOME/.pi/agent/settings.json" '{{ .chezmoi.sourceDir }}/private_dot_pi/private_agent/settings.managed.json' "$HOME/.pi/agent/models-store.json" '{{ .chezmoi.sourceDir }}/lib' <<'PY'
import sys
sys.path.insert(0, sys.argv[4])
from agent_settings import converge_pi_enabled_models
converge_pi_enabled_models(*sys.argv[1:4])
PY
}
run converge_pi_models
