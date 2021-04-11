Restore repositories:

```
sudo cp -r $HOME/dotfiles/ubuntu-gnome/packages/sources.list.d/* /etc/apt/sources.list.d
```

Public keys for these repositories will need to be added manually
at this point (`sudo apt-key adv --keyserver keyserver.ubuntu.com
--recv-keys #####`), before running `sudo apt update`.

Install packages:

```
xargs -a $HOME/dotfiles/ubuntu-gnome/packages/packages.txt sudo apt install
```

Run stow:

```
stow --no-folding -vv ubuntu-gnome
```

Restore Gnome settings with dconf:

```
dconf load / < $HOME/dotfiles/ubuntu-gnome/dconf/settings.dconf
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

