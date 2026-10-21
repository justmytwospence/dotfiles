c = get_config()

c.InteractiveShellApp.pylab_import_all = True
c.TerminalInteractiveShell.banner1 = u""
c.TerminalInteractiveShell.editing_mode = u"vi"
c.TerminalInteractiveShell.separate_in = u""

# https://github.com/rossant/ipycache
c.CacheMagics.cachedir = "./cache"

c.AliasManager.user_aliases = [
    ("l", "ls -al"),
]
