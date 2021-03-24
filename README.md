# Setup

Clone this repo:

```
git clone git://github.com/justmytwospence/dotfiles.git $HOME/dotfiles
```

Generate SSH key:

```
ssh-keygen -t rsa -b 4096 -C "github@spencerboucher.com"
```

Now, [add the public key to GitHub](https://github.com/settings/keys).

Initialize submodules:

```
(cd $HOME/dotfiles && git submodule init && git submodule update)
```

# ubuntu-gnome

Restore repositories:

```
sudo cp -r $HOME/dotfiles/ubuntu-gnome/.config/apt/sources.list.d/* /etc/apt/sources.list.d
```

Public keys for these repositories will need to be added manually at this point (`sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys #####`), before running `sudo apt update`.

Install packages:

```
xargs -a $HOME/dotfiles/ubuntu-gnome/.config/apt/packages.txt sudo apt install
```

Stow:

```
stow ubuntu-gnome --dir $HOME/dotfiles --no-folding
```

Restore Gnome settings with dconf:

```
dconf load / < $HOME/dotfiles/ubuntu-gnome/.config/dconf/settings.dconf
```

Enable systemd services:

```
systemctl --user enable emacs.service
```

Set default browser to Firefox:

```
sudo update-alternatives --set x-www-browser $(which firefox)
xdg-settings set default-web-browser firefox.desktop
```

# osx

Install Homebrew:

```
/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
```

Install GNU stow:

```
brew install stow
stow osx --dir $HOME/dotfiles --no-folding
```

Install Homebrew packages:

```
brew bundle --global
```

# terminal

```
stow common --dir $HOME/dotfiles --no-folding
```

Set the default shell to zsh:

```
grep -qF `which zsh` /etc/shells || sudo echo `which zsh` >> /etc/shells
chsh -s `which zsh`
```

Restart.

Set base16 shell theme:

```
base16_tomorrow-night
```

Install zsh plugins:

```
zplug install
```

Install Vim plugins:

```
vim +PlugUpgrade +PlugUpdate +quitall
```

Install tmux plugins:

```
$HOME/.tmux/plugins/tpm/scripts/install_plugins.sh
```

# ubuntu-gnome

```
stow local --dir $HOME/ubuntu-gnome --no-folding
```

# jupyter

Install Jupyter:

```
pip3 install jupyter jupyter_contrib_nbextensions
jupyter contrib nbextension install --user
```

# emacs

```
stow local --dir $HOME/emacs --no-folding
```

Add eterm to terminfo database:

```
mkdir $HOME/.terminfo
cp -r /usr/local/share/emacs/*/etc/e $HOME/.terminfo
```
