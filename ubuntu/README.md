Restore repositories:

```
sudo cp -r $HOME/dotfiles/ubuntu/packages/sources.list.d/* /etc/apt/sources.list.d
```

Public keys for these repositories will need to be added manually
at this point (`sudo apt-key adv --keyserver keyserver.ubuntu.com
--recv-keys #####`), before running `sudo apt update`.

Install packages:

```
awk -F'#' '{print $1}' $HOME/dotfiles/ubuntu/packages/packages.txt | xargs sudo apt install
```

Run stow:

```
stow --no-folding -vv ubuntu
```

Enable systemd services:

```
systemctl --user enable emacs
systemctl --user enable terminator
```

Set default browser to Firefox:

```
sudo update-alternatives --set x-www-browser $(which firefox)
xdg-settings set default-web-browser firefox.desktop
```
