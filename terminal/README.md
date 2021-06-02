Run stow:

```
stow --no-folding -vv terminal
```

Install packages:

```
awk -F'#' '{print $1}' $HOME/dotfiles/terminal/packages.txt | xargs sudo apt install
```

Set the default shell to zsh:

```
grep -qF `which zsh` /etc/shells || sudo echo `which zsh` >> /etc/shells
chsh -s `which zsh`
```

Restart.

Install zsh plugins:

```
antigen update
```

Install vim plugins:

```
vim +PlugUpgrade +PlugUpdate +quitall
```

Install tmux plugins:

```
$HOME/.tmux/plugins/tpm/scripts/install_plugins.sh
```
