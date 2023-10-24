# this is code is invoked  from  the function launch_valgrind in ../wrapper_c/dcc_util.c
# valgrind's error message are directed to this code's stdin
#
# This code summarizes any error messages in a form suitable for a novice programmer
# it the in most cases then calls start_gdb to run gdb to print more informatiomn
# valgrind is run with --vgdb=yes


import os, re, sys, signal
from start_gdb import start_gdb, kill_all, kill
from util import explanation_url
from explain_error import runtime_error_prefix
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
        return process_line(line, color, debug_level)
    return 0


# check one line of valgrind output
# return 0 if we should exit


def process_line(line, color, debug_level):
    runtime_error = ""
    error_text = ""
    call_start_gdb = True
    valgrind_pid = None
    m = re.match(r"^=+(\d+)", line)
    if m:
        valgrind_pid = int(m.group(1))

    if "fatal signal" in line:
        # avoid a signal e.g. SIGNALXCPU during valgrind startup
        # being interpreted as a runtime error
        call_start_gdb = False
    elif "vgdb me" in line:
        runtime_error = "uninitialized variable accessed."
    elif "exit_group(status)" in line:
        runtime_error = "exit value is uninitialized"
        error_text = """
Main is returning an uninitialized value or exit has been passed an uninitialized value.
"""
        # too late to start gdb as the program is exiting
        # we kill sanitizer2 as it is waiting for gdb
        call_start_gdb = False
    elif "clone.S" in line:
        runtime_error = "invalid parameters to process creation"
        error_text = """
An error has occurred in process creation.
This is likely an invalid argument to posix_spawn, posix_spawnp or clone.
Check all arguments are initialized.
"""
        # too late to start gdb as the program has cloned
        call_start_gdb = False
    elif "below stack pointer" in line:
        runtime_error = "access to function variables after function has returned"
        error_text = f"""
You have used a pointer to a local variable that no longer exists.
When a function returns its local variables are destroyed.

For more information see: {explanation_url("stack_use_after_return")}
"""
    elif "Invalid write of size" in line:
        runtime_error = "invalid assignment"
        error_text = """
A huge local array can produce this error.
"""
    elif "Invalid read of size" in line:
        runtime_error = "invalid memory access"
        error_text = """
A common cause of this error is use of an invalid FILE * pointer.
"""
    elif "Stack overflow" in line:
        runtime_error = "stack overflow"
        error_text = """
A common cause of this error is infinite recursion.
"""
    elif "loss record" in line:
        line = sys.stdin.readline()
        if debug_level > 1:
            print("valgrind: ", line, file=sys.stderr, end="")
        runtime_error = ""
        if "malloc" in line:
            line = sys.stdin.readline()
            if debug_level > 1:
                print("valgrind: ", line, file=sys.stderr, end="")
            # crude workaround to stop spurious leak error from lekas
            # cause may leak in library or update needed to valgrind suppression file
            for bad_string in ["LIBC", "fopencookie", ": _", " tsearch "]:
                if bad_string in line:
                    if debug_level > 1:
                        print("ignoring spurious leak", bad_string, file=sys.stderr)
                    return 1

            m = re.search(r"(\S+)\s*\((.+):(\d+)", line)
            error_text = "Error: free not called for memory allocated with malloc"
            if m:
                error_text += (
                    f" in function {m.group(1)} in {m.group(2)} at line {m.group(3)}"
                )
            error_text += "."
        else:
            error_text = "Error: memory allocated not de-allocated."
        call_start_gdb = False
    else:
        return 1

    full_error = runtime_error_prefix(runtime_error, color) + error_text
    if full_error:
        os.environ["DCC_VALGRIND_ERROR"] = full_error
        print("\n" + full_error, file=sys.stderr, flush=True)
    if call_start_gdb:
        start_gdb()
    else:
        if valgrind_pid:
            kill(valgrind_pid)
        kill_all()
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        watch_valgrind()
    except Exception:
        kill_all()
