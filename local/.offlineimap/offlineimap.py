#!/usr/bin/python

import re
import os


def get_authinfo_pass(machine, login):
    s = ur"^machine\s+{}\s+login\s+{}\s+password\s+(.+)$".format(machine, login)
    p = re.compile(s, re.MULTILINE)
    authinfo = os.popen("gpg --no-tty --no-mdc-warning -qd ~/.authinfo.gpg").read()
    return re.search(p, authinfo).group(1)
