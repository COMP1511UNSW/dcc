import os, re
from util import dprint


def set_interface(interface):
    global gdb
    gdb = interface


def gdb_attach():
    pid = int(os.environ.get("DCC_PID"))
    if "DCC_VALGRIND_ERROR" in os.environ:
        dprint(2, "attaching gdb to valgrind", pid)
        gdb.execute(f"target remote | vgdb --pid={pid}")
    else:
        dprint(2, "attaching gdb to ", pid)
        gdb.execute(f"attach {pid}")
    dprint(3, "gdb_attach() returning")


def gdb_evaluate(expression):
    dprint(
        3,
        "gdb_evaluate:",
        expression,
    )
    value = gdb_execute(f"print {expression}")
    value = re.sub(r"^[^=]*=\s*", "", value).strip()
    dprint(
        3,
        "->",
        value,
    )
    return value.strip()


def gdb_execute(command):
    dprint(3, "gdb.execute:", command)
    try:
        s = gdb.execute(command, to_string=True)
    except gdb.error as e:
        dprint(3, "gdb.execute", e)
        s = ""
    dprint(3, "gdb.execute:", "->", s)
    return s


def gdb_flush():
    dprint(3, "gdb.flush")
    gdb.flush(gdb.STDOUT)
    gdb.flush(gdb.STDERR)
