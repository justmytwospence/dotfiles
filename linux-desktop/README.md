# GNOME settings (extras: linux-desktop)

`settings.dconf` is a `dconf dump /` excerpt, not a chezmoi target. Load it by hand
on a GNOME desktop:

```sh
dconf load / < ~/dotfiles/linux-desktop/settings.dconf
```

The rest of the Linux desktop setup (i3, polybar, rofi, Alacritty, kitty,
terminator, albert, GTK, VS Code, autostart entries, `.Xmodmap`, `remap-keys`) is
ordinary chezmoi targets, written only when `extras` include `linux-desktop`.
