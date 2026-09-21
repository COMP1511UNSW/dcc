import os, sys, signal, subprocess, time
from util import debug_level_from_environment


def start_gdb(gdb_driver_file="drive_gdb.py"):
    signal.signal(signal.SIGINT, lambda *_: kill_all())
    debug_level = debug_level_from_environment()

    #
    # if a run-time error has occurred in sanitizer1 kill sanitizer2 now to avoid dupicate error
    # sanitizer2 will sanitizer1 if it starts gdb successfully
    #
    pid = os.environ.get("DCC_PID", "")
    sanitizer2_pid = os.environ.get("DCC_SANITIZER2_PID", "")
    sanitizer1_pid = os.environ.get("DCC_SANITIZER1_PID", "")
    if pid and sanitizer2_pid and sanitizer1_pid:
        if pid == sanitizer1_pid:
            kill_sanitizer2()

    if "DCC_BINARY" not in os.environ:
        # the program stopped before it could record its pathname,
        # e.g. a stack overflow while the run-time support was starting
        if debug_level:
            print("start_gdb: DCC_BINARY not set", file=sys.stderr)
        kill_sanitizer2()
        kill_env("DCC_PID", which_signal=signal.SIGPIPE)
        sys.exit(1)

    if debug_level > 1:
        print("start_gdb: ", end="")
        print(
            " ".join(
                f"{k}={os.environ.get(k, '')}"
                for k in "DCC_PID DCC_SANITIZER1_PID DCC_SANITIZER2_PID DCC_BINARY".split()
            )
        )

    for key in os.environ:
        if key.startswith("PYTHON"):
            del os.environ[key]

    # gdb seems to need this for imports to work
    os.environ["PYTHONPATH"] = "."
    os.environ["DCC_RUN_INSIDE_GDB"] = "true"
    os.environ[
        "PATH"
    ] = "/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:" + os.environ.get("PATH", "")
    os.environ[
        "LC_ALL"
    ] = "C"  # stop invalid utf-8  throwing Python exception with gdb - still needed?

    command = [
        "gdb",
        "--nx",
        "--batch",
        "-ex",
        f"python exec(open('{gdb_driver_file}', encoding='utf-8', errors='replace').read())",
        os.environ["DCC_BINARY"],
    ]

    if debug_level > 1:
        print("running:", command)

    # gdb puts confusing messages on stderr & stdout  so send these to /dev/null
    # and use file descriptor 3 for our messages
    os.dup2(2, 3)
    # pylint: disable=consider-using-with
    try:
        if debug_level > 1:
            p = subprocess.Popen(command, stdin=subprocess.DEVNULL, close_fds=False)
        else:
            p = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=False,
            )
        p.communicate()
    except OSError:
        print(
            "\ngdb not available to print program location and variable values\n",
            file=sys.stderr,
        )
        kill_all(kill_program=True)
    if debug_level > 1:
        print("kill_all()")
    # a gdb which failed has not told the program to exit, and under valgrind
    # it is stopped waiting for a debugger, so it would wait forever
    kill_all(kill_program=p.returncode != 0)


#
# ensure the program compiled with dcc terminates after error
#
def kill_all(kill_program=False):
    kill_sanitizer2()
    kill_env("DCC_SANITIZER1_PID")
    if kill_program or not program_stops_itself():
        kill_env("DCC_PID")
    sys.exit(1)


def program_stops_itself():
    """
    return True if the program will terminate without being killed

    When valgrind is the only sanitizer the program is the valgrind process,
    which does not die promptly from the signal used to stop the other
    sanitizers, so it would be killed instead and the shell would report
    "Killed".  It runs __dcc_error_exit itself once this code has finished.
    """
    return os.environ.get("DCC_SANITIZER", "") == "VALGRIND" and (
        "DCC_SANITIZER2_PID" not in os.environ
    )


def kill_sanitizer2(which_signal=None):
    unlink_sanitizer2_executable()
    kill_env("DCC_SANITIZER2_PID", which_signal=which_signal)


def kill_env(environment_variable_name, which_signal=None):
    if environment_variable_name in os.environ:
        try:
            kill(int(os.environ[environment_variable_name]), which_signal=which_signal)
        except ValueError:
            pass


def kill(pid, which_signal=None):
    # print('killing', pid)
    try:
        if which_signal is None:
            # in some circumstance SIGPIPE can avoid killed message
            # also allows cleanup of temporaries
            os.kill(pid, signal.SIGPIPE)
            # allow process hopefully enough time to handle SIGPIPE
            # then send SIGKILL to make sure process terminates
            time.sleep(0.25)
            os.kill(pid, signal.SIGKILL)
        else:
            os.kill(pid, which_signal)
    except ProcessLookupError:
        pass


def unlink_sanitizer2_executable():
    if "DCC_UNLINK" in os.environ:
        try:
            os.unlink(os.environ["DCC_UNLINK"])
        except OSError:
            pass


if __name__ == "__main__":
    start_gdb()
