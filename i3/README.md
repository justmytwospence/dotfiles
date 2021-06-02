Run stow:

```
stow --no-folding -vv i3
```

Install packages:

```
awk -F'#' '{print $1}' $HOME/dotfiles/i3/packages.txt | xargs sudo apt install
```
