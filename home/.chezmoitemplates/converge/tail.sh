if ((${#failed[@]})); then
    echo "converge: failed: ${failed[*]}" >&2
    exit 1
fi
