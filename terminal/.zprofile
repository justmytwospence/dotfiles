# homebrew
eval "$(/opt/homebrew/bin/brew shellenv)"

# pyenv
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# pyenv-virtualenv
eval "$(pyenv virtualenv-init -)"
export PYENV_VIRTUALENV_VERBOSE_ACTIVATE=0
export PYENV_VIRTUALENV_DISABLE_PROMPT=1
