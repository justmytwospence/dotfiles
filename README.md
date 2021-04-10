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

Different dotfile components should be symlinked with gnu-stow.

# emacs

Add eterm to terminfo database:

```
mkdir $HOME/.terminfo
cp -r /usr/local/share/emacs/*/etc/e $HOME/.terminfo
```
