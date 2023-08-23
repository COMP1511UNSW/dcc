import os, platform, sys, signal, traceback
import colors, gdb_interface, explain_error, util

#
# Code below is executed from gdb.
# It prints details of the program state likely to be of interest to
# a beginner programmer
#

# workaround - avoid warning message from analysers
if 0:
    gdb = None


def drive_gdb():
    output_stream = os.fdopen(3, "w", encoding="utf-8", errors="replace")
    util.set_debug_level()
    util.set_debug_stream(output_stream)
    windows_subsystem_for_linux = "microsoft" in platform.uname()[3].lower()
    colorize_output = output_stream.isatty() or os.environ.get(
        "DCC_COLORIZE_OUTPUT", False
    )
    if colorize_output:
        color = colors.color
    else:
        color = lambda text, *args, **kwargs: text
    # 	signal.signal(signal.SIGINT, interrupt_handler)

    try:
        gdb_interface.set_interface(gdb)
        gdb_interface.gdb_attach()
        pid = os.environ.get("DCC_PID", "")
        sanitizer2_pid = os.environ.get("DCC_SANITIZER2_PID", "")
        sanitizer1_pid = os.environ.get("DCC_SANITIZER1_PID", "")
        if pid and sanitizer2_pid and sanitizer1_pid:
            if pid == sanitizer2_pid:
                os.kill(int(sanitizer1_pid), signal.SIGUSR1)
        explain_error.explain_error(output_stream, color)
    except gdb.error as e:
        if "ptrace" in str(e).lower() and os.path.exists("/.dockerenv"):
            print(
                "\ndcc : can not provide information about variables because docker not run with --cap-add=SYS_PTRACE\n",
                file=output_stream,
            )
        elif util.get_debug_level():
            traceback.print_exc(file=output_stream)
        sys.exit(1)
    except Exception:
        if util.get_debug_level():
            traceback.print_exc(file=output_stream)
        sys.exit(1)

    output_stream.flush()
    # __dcc_error_exit hangs for unknown reason on WSL
    if not windows_subsystem_for_linux:
        gdb_interface.gdb_execute("call (void)__dcc_error_exit()")
    # 	kill_all()
    gdb_interface.gdb_execute("quit")


if __name__ == "__main__":
    drive_gdb()
