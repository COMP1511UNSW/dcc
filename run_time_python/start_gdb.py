import os, sys, signal, subprocess, time


def start_gdb(gdb_driver_file="drive_gdb.py"):
    signal.signal(signal.SIGINT, lambda *_: kill_all())
    debug_level = int(os.environ.get("DCC_DEBUG", "0"))

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

    if os.path.exists(gdb_driver_file):
        command = [
            "gdb",
            "--nx",
            "--batch",
            "-ex",
            f"python exec(open('{gdb_driver_file}', encoding='utf-8', errors='replace').read())",
            os.environ["DCC_BINARY"],
        ]
    else:
        from embedded_source import embedded_source_drive_gdb_py

        command = [
            "gdb",
            "--nx",
            "--batch",
            "-ex",
            'python exec(r"""' + embedded_source_drive_gdb_py + '""")',
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
    if debug_level > 1:
        print("kill_all()")
    kill_all()


#
# ensure the program compiled with dcc terminates after error
#
def kill_all():
    kill_sanitizer2()
    kill_env("DCC_SANITIZER1_PID")
    kill_env("DCC_PID")
    sys.exit(1)


def kill_sanitizer2(which_signal=None):
    unlink_sanitizer2_executable()
    kill_env("DCC_SANITIZER2_PID", which_signal=which_signal)


def pause_sanitizer1():
    kill_env("DCC_SANITIZER1_PID", which_signal=signal.SIGUSR1)


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
