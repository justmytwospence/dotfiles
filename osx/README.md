Install Homebrew:

```
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

Install and run GNU stow:

```
brew install stow
stow osx --dir $HOME/dotfiles --no-folding
```

Install Homebrew packages:

```
brew bundle --global
```
