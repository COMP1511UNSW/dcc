# miscellaneous code used at both compile & run-time

import os

EXPLANATION_BASE_URL = "https://comp1511unsw.github.io/dcc/"


def explanation_url(page):
    return EXPLANATION_BASE_URL + page + ".html"


def search_path(program, cwd=None):
    """
    return absolute pathname for first instance of program in $PATH, None otherwise
    if cwd supplied use it as current working firectory
    """
    path = os.environ.get("PATH", "/bin:/usr/bin:/usr/local/bin:.")
    for directory in path.split(os.pathsep):
        if cwd and not os.path.isabs(directory):
            directory = os.path.join(cwd, directory)
        pathname = os.path.join(directory, program)
        if os.path.isfile(pathname) and os.access(pathname, os.X_OK):
            return pathname
    return None
