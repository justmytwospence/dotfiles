Run stow:

```
stow --no-folding terminal
```

Install packages:

```
xargs -a $HOME/dotfiles/terminal/.config/apt/terminal-packages.txt sudo apt install
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
