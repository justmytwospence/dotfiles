# homebrew
eval "$(/opt/homebrew/bin/brew shellenv)"

# pyenv - lazy load (only environment setup, no initialization)
export PYENV_ROOT="$HOME/.pyenv"
export PYENV_VIRTUALENV_VERBOSE_ACTIVATE=0
export PYENV_VIRTUALENV_DISABLE_PROMPT=1

# Add pyenv to path but don't run init commands yet
if [[ -d "$PYENV_ROOT/bin" ]]; then
    path=("$PYENV_ROOT/bin" $path)
fi
