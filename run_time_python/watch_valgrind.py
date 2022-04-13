# this is code is invoked  from  the function launch_valgrind in ../wrapper_c/dcc_util.c
# valgrind's error message are directed to this code's stdin
#
# This code summarizes any error messages in a form suitable for a novice programmer
# it the in most cases then calls start_gdb to run gdb to print more informatiomn
# valgrind is run with --vgdb=yes


import os, re, sys, signal
from start_gdb import start_gdb, kill_sanitizer2, kill_all
from util import explanation_url
import colors


def watch_valgrind():
    colorize_output = sys.stderr.isatty() or os.environ.get(
        "DCC_COLORIZE_OUTPUT", False
    )
    if colorize_output:
        color = colors.color
    else:
        color = lambda text, color_name: text

    debug_level = int(os.environ.get("DCC_DEBUG", "0"))
    if debug_level > 1:
        print("watch_valgrind() running", file=sys.stderr)
    while read_line(color, debug_level):
        pass
    if debug_level > 1:
        print("watch_valgrind() - exiting", file=sys.stderr)
    sys.exit(0)


def read_line(color, debug_level):
    line = sys.stdin.readline()
    if line:
        if debug_level > 1:
            print("valgrind: ", line, file=sys.stderr, end="")
        return process_line(line, color)
    return 0


# check one line of valgrind output
# return 0 if we should exit


def process_line(line, color):
    error = None
    action = start_gdb

    if "fatal signal" in line:
        # avoid a signal e.g. SIGNALXCPU during valgrind startup
        # being interpreted as a runtime error
        error = ""
        action = kill_sanitizer2
    elif "vgdb me" in line:
        error = "Runtime error: " + color("uninitialized variable accessed.", "red")

    elif "exit_group(status)" in line:
        error = f"""Runtime error: {color('exit value is uninitialized', 'red')}

Main is returning an uninitialized value or exit has been passed an uninitialized value.
"""
        # too late to start gdb as the program is exiting
        # we kill sanitizer2 as it is waiting for gdb
        action = kill_sanitizer2

    elif "clone.S" in line:
        error = f"""Runtime error: {color('invalid parameters to process creation', 'red')}

An error has occurred in process creation.
This is likely an invalid argument to posix_spawn, posix_spawnp or clone.
Check all arguments are initialized.

"""
        # too late to start gdb as the program is exiting
        action = kill_all

    elif "below stack pointer" in line:
        error = f"""Runtime error: {color('access to function variables after function has returned', 'red')}
You have used a pointer to a local variable that no longer exists.
When a function returns its local variables are destroyed.

For more information see: {explanation_url("stack_use_after_return")}'
"""

    elif "Invalid write of size" in line:
        error = f"""Runtime error: {color('invalid assignment.', 'red')}
A huge local array can produce this error.
"""

    elif "Invalid read of size" in line:
        error = f"""Runtime error: {color('invalid memory access.', 'red')}
A common cause of this error is use of invalid FILE * pointer.
"""

    elif "Stack overflow" in line:
        error = f"""Runtime error: {color('stack overflow.', 'red')}
A common cause of this error is infinite recursion.
"""
    elif "loss record" in line:
        line = sys.stdin.readline()
        if "malloc" in line:
            line = sys.stdin.readline()
            m = re.search(r"(\S+)\s*\((.+):(\d+)", line)
            error = "Error: free not called for memory allocated with malloc"
            if m:
                error += (
                    f" in function {m.group(1)} in {m.group(2)} at line {m.group(3)}"
                )
            error += "."
        else:
            error = "Error: memory allocated not de-allocated."
        action = kill_sanitizer2

    if error is not None:
        if error:
            os.environ["DCC_VALGRIND_ERROR"] = error
            print("\n" + error, file=sys.stderr)
            sys.stderr.flush()
        action()
        return 0
    return 1


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(1))
    watch_valgrind()
