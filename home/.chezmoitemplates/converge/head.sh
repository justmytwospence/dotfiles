#!/bin/bash
set -uo pipefail
{{ template "script-path.sh" . }}
{{ template "converge/lib.sh" . }}
