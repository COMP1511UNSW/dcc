# this is code is invoked  from  the function launch_valgrind in ../wrapper_c/dcc_util.c
# valgrind's error message are directed to this code's stdin
#
# This code summarizes any error messages in a form suitable for a novice programmer
# it the in most cases then calls start_gdb to run gdb to print more informatiomn
# valgrind is run with --vgdb=yes


import io, os, re, sys, signal
from start_gdb import start_gdb, kill_all, kill, kill_env
from util import debug_level_from_environment, explanation_url
from explain_error import runtime_error_prefix, ASAN_EXPLANATIONS
import colors


# a line of valgrind output which starts a report rather than continuing one
VALGRIND_REPORT_RE = re.compile(r"^==\d+== [A-Z]")

# the stack frames valgrind prints beneath a report, which its purely
# informational messages do not have
VALGRIND_STACK_FRAME_RE = re.compile(r"^==\d+==\s+(at|by) 0x")

# lines valgrind prints which are not reporting an error
VALGRIND_NOT_AN_ERROR = (
    "TO DEBUG THIS PROCESS",
    "For lists of detected and suppressed errors",
    "ERROR SUMMARY",
    "HEAP SUMMARY",
    "LEAK SUMMARY",
    "All heap blocks were freed",
    "in use at exit",
    "total heap usage",
    "Command:",
    "Copyright",
    "Using Valgrind",
    "Memcheck,",
)

# a report valgrind made which dcc did not recognise, and whether valgrind
# printed a stack trace beneath it, which only a real error has
unrecognised_output: list = []
unrecognised_has_stack_frames = [False]


def watch_valgrind():
    colorize_output = sys.stderr.isatty() or os.environ.get(
        "DCC_COLORIZE_OUTPUT", False
    )
    if colorize_output:
        color = colors.color
    else:
        color = lambda text, color_name: text

    # valgrind echoes the binary's pathname, which need not be valid UTF-8,
    # and an exception here leaves the program waiting for a debugger forever
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, errors="replace")

    debug_level = debug_level_from_environment()
    if debug_level > 1:
        print("watch_valgrind() running", file=sys.stderr)
    while read_line(color, debug_level):
        pass
    report_unrecognised_output(color)
    if debug_level > 1:
        print("watch_valgrind() - exiting", file=sys.stderr)
    sys.exit(0)


def note_unrecognised_line(line):
    """remember a report from valgrind which dcc has no explanation for"""
    if unrecognised_output and VALGRIND_STACK_FRAME_RE.match(line):
        unrecognised_has_stack_frames[0] = True
    if not VALGRIND_REPORT_RE.match(line):
        return
    if any(text in line for text in VALGRIND_NOT_AN_ERROR):
        return
    if len(unrecognised_output) < 20:
        unrecognised_output.append(line)


def report_unrecognised_output(color):
    """
    report an error valgrind found which dcc has no explanation for

    Without this a valgrind message dcc does not know about is discarded and
    the program exits as if it were correct, so a valgrind release which
    renames a message would silently switch off that kind of checking.
    """
    if not unrecognised_output or not unrecognised_has_stack_frames[0]:
        # valgrind prints informational messages too, and only a real error
        # report has a stack trace beneath it
        return
    error = runtime_error_prefix("error detected by valgrind", color)
    print("\n" + error, file=sys.stderr)
    print(
        "dcc does not have an explanation for this error."
        " This is what valgrind reported:\n",
        file=sys.stderr,
    )
    for line in unrecognised_output:
        print("   ", line.rstrip(), file=sys.stderr)
    print(file=sys.stderr, flush=True)
    kill_env("DCC_SANITIZER1_PID", which_signal=signal.SIGUSR1)
    kill_all()


def read_line(color, debug_level):
    line = read_valgrind_line(debug_level)
    if line:
        return process_line(line, color, debug_level)
    return 0


def read_valgrind_line(debug_level):
    line = sys.stdin.readline()
    if line and debug_level > 1:
        print("valgrind: ", line, file=sys.stderr, end="")
    return line


def read_address_description(debug_level):
    """
    return valgrind's description of the memory an invalid read or write
    touched, which it prints beneath the report's stack frames, e.g.
    "Address 0x4a6005c is 12 bytes after a block of size 16 alloc'd",
    and the stack valgrind prints under that description, which is where
    the block was allocated or freed
    """
    description = ""
    frames = ""
    # bounded so a truncated report can not leave this reading forever
    for _ in range(64):
        line = read_valgrind_line(debug_level)
        m = re.match(r"^==\d+==\s+(\S.*?)\s*$", line)
        if not m:
            break
        if VALGRIND_STACK_FRAME_RE.match(line):
            if description:
                frames += m.group(1) + "\n"
            continue
        if frames:
            break
        if description:
            description += " " + m.group(1)
        elif m.group(1).startswith("Address "):
            description = m.group(1)
        else:
            break
    return description, frames


def explain_invalid_access(description, frames, default_error, color):
    """
    explain an invalid read or write using valgrind's description of the
    memory touched

    The explanation is the one dcc gives when AddressSanitizer reports the
    same fault, so the sanitizers do not disagree about a program.  If
    valgrind has not said what the memory was, neither can dcc: naming a
    cause the program does not contain sends a novice to the wrong place.
    """
    hint = ""
    if re.search(r"block of size \d+ free'd", description):
        error = "use after free"
        # the block a FILE * points to is freed by fclose, and a student
        # who has called no free at all needs to be told that
        if "fclose" in frames:
            hint = "\nA FILE * can not be used after fclose has been called on it.\n"
    elif re.search(r"block of size \d+ alloc'd", description):
        error = "malloc buffer overflow"
    elif "below stack pointer" in description:
        error = "stack use after return"
    else:
        return default_error, ""
    for substring, explanation in ASAN_EXPLANATIONS:
        if substring in error.lower():
            prefix = color("dcc explanation: ", "cyan")
            return error, "\n" + prefix + explanation.rstrip("\n") + "\n" + hint
    return error, hint


def leak_allocation_location(line, debug_level):
    """
    return the match for the frame of a leaked allocation in the student's code

    valgrind reports the frame which called malloc, but for e.g. getline or
    strdup that frame is inside libc and names a file the student has never
    seen, so the frames are walked outwards to the first one whose source
    file dcc can find.  If no frame's source file can be found the innermost
    frame is returned, which is what dcc reported before the walk existed -
    moving the location outwards would be a confidently wrong answer.
    """
    innermost = None
    for _ in range(64):
        m = re.search(r"(\S+)\s*\((.+):(\d+)", line)
        if m:
            innermost = innermost or m
            if is_program_source_file(m.group(2)):
                return m
        line = read_valgrind_line(debug_level)
        if not VALGRIND_STACK_FRAME_RE.match(line):
            break
    return innermost


def is_program_source_file(filename):
    """return True if filename looks like a source file of the program"""
    # this code runs in a temporary directory and valgrind prints a bare
    # basename, so it is looked for beside the program's binary as well as in
    # the directory the program was run from
    directories = [os.environ.get("DCC_PWD", "")]
    binary = os.environ.get("DCC_BINARY")
    # DCC_UNLINK is the copy of the program dcc made in /tmp to run as
    # sanitizer2, whose directory is not the student's
    if binary and binary != os.environ.get("DCC_UNLINK"):
        directories.append(os.path.dirname(binary))
    return any(os.path.exists(os.path.join(d, filename)) for d in directories)


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
        description, frames = read_address_description(debug_level)
        runtime_error, error_text = explain_invalid_access(
            description, frames, "invalid assignment", color
        )
    elif "Invalid read of size" in line:
        description, frames = read_address_description(debug_level)
        runtime_error, error_text = explain_invalid_access(
            description, frames, "invalid memory access", color
        )
    elif "Stack overflow" in line:
        runtime_error = "stack overflow"
        error_text = """
A common cause of this error is infinite recursion.
"""
    elif "loss record" in line:
        line = read_valgrind_line(debug_level)
        runtime_error = ""
        if "malloc" in line:
            line = read_valgrind_line(debug_level)
            # crude workaround to stop spurious leak error from lekas
            # cause may leak in library or update needed to valgrind suppression file
            for bad_string in ["LIBC", "fopencookie", " tsearch "]:
                if bad_string in line:
                    if debug_level > 1:
                        print("ignoring spurious leak", bad_string, file=sys.stderr)
                    return 1

            # a name beginning with an underscore is usually a library internal
            # such as _IO_file_doallocate, but a student may write a function
            # called _helper, so what decides is whether the frame names a file
            # of theirs rather than the name itself
            if ": _" in line:
                frame = re.search(r"(\S+)\s*\((.+):(\d+)", line)
                if not frame or not is_program_source_file(frame.group(2)):
                    if debug_level > 1:
                        print("ignoring spurious leak : _", file=sys.stderr)
                    return 1

            m = leak_allocation_location(line, debug_level)
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
        note_unrecognised_line(line)
        return 1

    full_error = runtime_error_prefix(runtime_error, color) + error_text
    if full_error:
        os.environ["DCC_VALGRIND_ERROR"] = full_error
        print("\n" + full_error, file=sys.stderr, flush=True)
    if call_start_gdb:
        start_gdb()
    else:
        if full_error:
            # tell the other process an error was found, so that a program
            # whose only error is reported here does not exit successfully
            kill_env("DCC_SANITIZER1_PID", which_signal=signal.SIGUSR1)
        if valgrind_pid:
            kill(valgrind_pid)
        kill_all()
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        watch_valgrind()
    except Exception:
        # the program is stopped waiting for the debugger this code starts,
        # so it must be killed rather than left to exit itself
        kill_all(kill_program=True)
