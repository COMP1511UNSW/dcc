import os, re
from util import dprint


def set_interface(interface):
    global gdb
    gdb = interface


def gdb_attach():
    gdb.execute("set exec-file-mismatch off")
    pid = int(os.environ.get("DCC_PID"))
    if "DCC_VALGRIND_ERROR" in os.environ or "DCC_VALGRIND_RUNNING" in os.environ  :
        dprint(2, "attaching gdb to valgrind", pid)
        gdb.execute(f"target remote | vgdb --pid={pid}")
    else:
        dprint(2, "attaching gdb to ", pid)
        gdb.execute(f"attach {pid}")
    dprint(3, "gdb_attach() returning")


# most uses can be replaced by gdb_eval
def gdb_evaluate(expression):
    dprint(3, "gdb_evaluate:", expression)
    value = gdb_execute(f"print {expression}")
    value = re.sub(r"^[^=]*=\s*", "", value).strip()
    dprint(3, "->", value)
    return value.strip()


def gdb_eval(expression):
    dprint(3, "gdb_eval:", expression)
    try:
        value = gdb.parse_and_eval(expression)
        dprint(3, "->", value)
    except gdb.error as e:
        dprint(3, e)
        value = None
    return value


def gdb_set_frame(level):
    gdb_execute(f"frame {level}")


# only in recent gdb versions
def gdb_get_frame():
    dprint(3, "gdb.selected_frame")
    try:
        return gdb.selected_frame().level()
    except gdb.error as e:
        dprint(3, "gdb.selected_frame", e)
        return 0


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


def gdb_get_byte_array(array, length):
    try:
        gdb_array = gdb_eval(array)
        return bytearray((256 + int(gdb_array[i])) % 256 for i in range(length))
    except (IndexError, ValueError, TypeError, gdb.error):
        return b''
