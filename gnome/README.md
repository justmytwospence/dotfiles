Restore repositories:

```
sudo cp -r $HOME/dotfiles/gnome/packages/sources.list.d/* /etc/apt/sources.list.d
```

Public keys for these repositories will need to be added manually
at this point (`sudo apt-key adv --keyserver keyserver.ubuntu.com
--recv-keys #####`), before running `sudo apt update`.

Install packages:

```
awk -F'#' '{print $1}' $HOME/dotfiles/gnome/packages/packages.txt | xargs sudo apt install
```

Run stow:

```
stow --no-folding -vv gnome
```

Restore Gnome settings with dconf:

```
dconf load / < $HOME/dotfiles/gnome/dconf/settings.dconf
```
