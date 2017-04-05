c = get_config()

# https://github.com/rossant/ipycache
c.CacheMagics.cachedir = "./cache"

c.AliasManager.user_aliases = [
    ("l", "ls -al"),
]

c.TerminalInteractiveShell.banner1 = u""
c.TerminalInteractiveShell.separate_in = u""
