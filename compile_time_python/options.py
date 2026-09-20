import io, os, platform, re, shlex, subprocess, sys, tarfile
from version import VERSION
from util import debug_level_from_environment, search_path


# on some platforms -Wno-unused-result is needed
# to avoid warnings about scanf's return value being ignored and
# novice programmers will often be told to ignore scanf's return value
# when writing their first programs

COMMON_WARNING_ARGS = """
    -Wall
    -Wno-unused
    -Wunused-variable
    -Wunused-value
    -Wno-unused-result
    -Wshadow
    """.split()

COMMON_COMPILER_ARGS = COMMON_WARNING_ARGS + "-g".split()

# specifying dwarf-4 avoids warnings & errors from valgrind on Debian bookworm & trixie
CLANG_ONLY_ARGS = """
    -gdwarf-4
    -Wunused-comparison
    -fno-omit-frame-pointer
    -fno-common
    -funwind-tables
    -fno-optimize-sibling-calls
    -Qunused-arguments
    -Wno-unused-parameter
    """.split()

IMPLICIT_LINKER_ARGS = "-lm".split()

COMPILE_HELPER_BASENAME = "dcc-compile-helper"

USAGE = """\
Usage: {program} [options] [clang-options] <source-files>

Compile C programs with clang, adding run-time error checking and
explanations of errors suitable for novice programmers.

Options:
  -fsanitize=<list>        address, memory or valgrind, optionally with undefined,
                           comma-separated (default: address and valgrind,
                           or address and memory if valgrind is not installed)
  --memory, --valgrind     deprecated: same as -fsanitize=memory or -fsanitize=valgrind
  --leak-check             report memory leaks when the program exits
  --no-explanations        do not add explanations to compiler messages
  --use-after-return       detect use of a local variable after its function returns
  --suppressions=<file>    valgrind suppressions file
  --c-compiler=<compiler>  compiler to run (default: clang, or clang++ for C++)
  --compile_helper=<program>
                           run <program> after a compiler warning or error
  --compile_logger=<program>
                           run <program> after every compilation
  --embedded_environment_variable=<name>=<value>
                           set <name> in the environment of the compiled program
  --shared-libasan, --no-shared-libasan
                           link AddressSanitizer as a shared library, or not
  --valgrind-fix-posix-spawn, --no-valgrind-fix-posix-spawn
                           work around posix_spawn under valgrind, or not
  --ifdef-main             rename main with a macro instead of linker wrapping
  --use-funopen            use funopen instead of fopencookie
  -o <file>                write the executable to <file> (default: a.out)
  -v, --version            print the dcc version and exit
  --help                   print this message and exit

All other options are passed to clang.

Environment variables:
  DCC_DEBUG                level of debugging output (default: 0)
  DCC_COLORIZE_OUTPUT      if not empty, colorize output even if stderr is not a terminal
  DCC_COMPILE_HELPER       program to run after a compiler warning or error
  DCC_COMPILE_LOGGER       program to run after every compilation"""


def usage():
    return USAGE.format(program=os.path.basename(sys.argv[0]))


COMPILE_LOGGER_BASENAME = "dcc-compile-logger"


# gcc detects some typical novice programmer mistakes that clang doesn't
# We run gcc has an extra checking pass with several warnings options enabled
#
# The option -Wduplicated-branches was only added with gcc-8
# it will break older versions of gcc
# this will be silent but we lose gcc checking
#
# The option -Wnull-dererefence looks be useful but when it flags potential paths
# the errors look confusing for novice programmers,
# and there appears no way to get only definite null-derefs
#
# -O is needed with gcc to get warnings for some things

GCC_ONLY_ARGS = """
	-Wunused-but-set-variable
	-Wduplicated-cond
	-Wduplicated-branches
	-Wlogical-op
	-O
	-o /dev/null
	""".split()


class Options:
    def __init__(self):
        self.debug = debug_level_from_environment()

        # macOS has clang renamed as gcc - but it doesn't take gcc options
        self.also_run_gcc = sys.platform != "darwin" and search_path("gcc")

        self.basename = os.path.basename(sys.argv[0])
        self.cpp_mode = self.basename.endswith("++")
        self.code_suffix = "cpp" if self.cpp_mode else "c"
        self.check_output = True
        self.save_stdin_buffer_size = 10240
        self.valgrind_fix_posix_spawn = None

        self.dcc_supplied_compiler_args = COMMON_COMPILER_ARGS
        self.dcc_supplied_linker_args = IMPLICIT_LINKER_ARGS
        self.c_compiler = ""

        # needed for shared-libasan
        self.clang_lib_dir = "/usr/lib/clang/{clang_version}/lib/linux"

        self.clang_version = ""
        self.clang_version_major = 0
        self.clang_version_minor = 0
        self.clang_version_float = 0.0

        # FIXME - check terminal actually supports ANSI
        self.colorize_output = sys.stderr.isatty() or os.environ.get(
            "DCC_COLORIZE_OUTPUT", False
        )

        # used by obsolete code which use executes dcc from binary
        self.dcc_path = os.path.realpath(sys.argv[0])

        # list of system includes for standard lib function which will not
        # interfere with dual sanitizer synchronization
        safe_c_includes_basenames = [
            "assert",
            "complex",
            "ctype",
            "errno",
            "fenv",
            "float",
            "inttypes",
            "iso646",
            "limits",
            "locale",
            "math",
            "setjmp",
            "stdalign",
            "stdarg",
            "stdatomic",
            "stdbool",
            "stddef",
            "stdint",
            "stdio",
            "stdlib",
            "stdnoreturn",
            "string",
            "tgmath",
            "time",
            "uchar",
            "wchar",
            "wctype",
            "sanitizer/asan_interface",
            "malloc",
            "strings",
            "sysexits",
        ]
        safe_c_includes = [i + ".h" for i in safe_c_includes_basenames]
        safe_cpp_includes = ["c" + i for i in safe_c_includes_basenames if "/" not in i]
        safe_cpp_includes += ["iostream"]
        self.dual_sanitizer_safe_system_includes = set(
            safe_c_includes + safe_cpp_includes
        )

        self.explanations = True

        # ld doesn't have wrap on macOS
        self.ifdef_instead_of_wrap = sys.platform == "darwin"
        # fopencookie is not available on macOS
        self.use_funopen = sys.platform == "darwin"

        self.incremental_compilation = False

        self.gcc_args = COMMON_COMPILER_ARGS + GCC_ONLY_ARGS

        self.leak_check = False
        self.libraries_being_linked = False
        self.max_explanations = 3
        self.maximum_source_file_embedded_bytes = 1000000
        self.object_files_being_linked = False
        self.object_pathname = "a.out"
        self.sanitizers = []
        self.shared_libasan = None
        self.source_files = set()
        self.stack_use_after_return = None
        self.suppressions_file = os.devnull
        self.system_includes_used = set()

        self.tar_buffer = io.BytesIO()
        # pylint: disable=consider-using-with
        self.tar = tarfile.open(fileobj=self.tar_buffer, mode="w|xz", dereference=True)

        self.threads_used = False
        self.treat_warnings_as_errors = False
        self.user_supplied_compiler_args = []
        self.compile_helper = os.environ.get("DCC_COMPILE_HELPER", "") or search_path(
            COMPILE_HELPER_BASENAME
        )
        self.compile_logger = os.environ.get("DCC_COMPILE_LOGGER", "") or search_path(
            COMPILE_LOGGER_BASENAME
        )
        self.embedded_environment_variables = []

        # set by get_options
        self.unsafe_system_includes = []
        # set by compile.main
        self.temporary_directory = ""

    def die(self, *args, **kwargs):
        self.warn(*args, **kwargs)
        # if the tar is not closed an execption is raised on exit by python 3.9
        if self.tar:
            self.tar.close()
        sys.exit(1)

    def warn(self, *args, **kwargs):
        print(self.basename + ": ", end="", file=sys.stderr)
        kwargs["file"] = sys.stderr
        print(*args, **kwargs)

    def debug_print(self, *args, level=1, **kwargs):
        if self.debug >= level:
            kwargs["file"] = sys.stderr
            print(*args, **kwargs)


def get_options():
    options = parse_args(sys.argv[1:])

    if not options.c_compiler:
        clang = "clang++" if options.cpp_mode else "clang"
        test_clang_version_exists(clang, options)
        # this needs to be generalized to select preferred clang version
        # when multiple versions available
        try:
            if not options.clang_version or int(options.clang_version_major) < 11:
                for major in range(11, 31, 2):
                    if test_clang_version_exists(f"{clang}-{major}", options):
                        break

        except ValueError:
            pass
        if not options.clang_version:
            options.die("can not find clang compiler")
    elif "clang" in options.c_compiler:
        test_clang_version_exists(options.c_compiler, options)
        if not options.clang_version:
            options.die(f"can not get version information for {options.c_compiler}")

    if options.colorize_output:
        if "clang" in options.c_compiler:
            options.dcc_supplied_compiler_args += ["-fcolor-diagnostics"]
            options.dcc_supplied_compiler_args += ["-fdiagnostics-color"]
        options.gcc_args += ["-fdiagnostics-color=always"]

    options.unsafe_system_includes = list(
        options.system_includes_used - options.dual_sanitizer_safe_system_includes
    )

    if not options.sanitizers or len(options.sanitizers) > 1:
        reason = ""
        if options.incremental_compilation:
            reason = "incremental compilation"
        elif options.object_files_being_linked:
            reason = "object files being linked"
        elif options.libraries_being_linked:
            reason = "library other than C standard library used"
        elif options.threads_used:
            reason = "threads used"
        elif options.unsafe_system_includes:
            reason = options.unsafe_system_includes[0] + " used"
        elif sys.platform == "darwin":
            reason = "not supported on OSX"

        if reason:
            # if 2 sanitizer have been explicitly specified, give a warning
            if len(options.sanitizers) > 1:
                options.warn(
                    "warning: running 2 sanitizers will probably fail:", reason
                )
            else:
                options.sanitizers = ["address"]
        elif search_path("valgrind"):
            options.sanitizers = ["address", "valgrind"]
        else:
            options.sanitizers = ["address", "memory"]
            options.debug_print(
                "warning: valgrind does not seem be installed, using MemorySanitizer instead"
            )

    if "valgrind" in options.sanitizers and options.suppressions_file != os.devnull:
        if os.path.isdir(options.suppressions_file) or not os.access(
            options.suppressions_file, os.R_OK
        ):
            # valgrind would fail to start and its checking would be silently lost
            options.die(f"can not read suppressions file {options.suppressions_file}")

    if options.valgrind_fix_posix_spawn is None and "valgrind" in options.sanitizers:
        options.valgrind_fix_posix_spawn = sys.platform == "linux"

    if "memory" in options.sanitizers and platform.architecture()[0][0:2] == "32":
        options.die("MemorySanitizer not available on 32-bit architectures")

    if "clang" in options.c_compiler:
        options.dcc_supplied_compiler_args += CLANG_ONLY_ARGS
    elif "gcc" in options.c_compiler:
        options.dcc_supplied_compiler_args += GCC_ONLY_ARGS
    if "address" in options.sanitizers and platform.architecture()[0][0:2] == "32":
        libc_version = get_libc_version(options)

        if libc_version and options.clang_version_float < 6 and libc_version >= 2.27:
            options.warn(
                "incompatible clang libc versions, disabling error detection by sanitizers"
            )
            options.sanitizers = [a for a in options.sanitizers if a != "address"]

    # shared_libasan breaks easily ,e.g if there are libraries in  /etc/ld.so.preload
    # and we can't override with verify_asan_link_order=0 for clang version < 5
    # and with clang-6 on debian __asan_default_options not called with shared_libasan
    if (
        options.shared_libasan is None
        and options.clang_version_float >= 7.0
        and "clang" in options.c_compiler
    ):
        options.shared_libasan = True

    if options.use_funopen and sys.platform == "linux":
        options.dcc_supplied_linker_args += ["-lbsd"]

    if options.ifdef_instead_of_wrap:
        options.dcc_supplied_compiler_args += ["-Wno-return-type"]

    if options.incremental_compilation and len(options.sanitizers) > 1:
        options.die("only a single sanitizer supported with incremental compilation")

    if options.object_files_being_linked and len(options.sanitizers) > 1:
        options.die("only a single sanitizer supported with linking of .o files")
    return options


def parse_args(commandline_args):
    options = Options()
    if not commandline_args:
        print(usage(), file=sys.stderr)
        sys.exit(1)

    while commandline_args:
        arg = commandline_args.pop(0)
        if arg.startswith("@"):
            # a response file - its contents replace the argument
            # it must not be passed on to clang which would expand it again
            try:
                with open(arg[1:], encoding="utf-8") as argfile:
                    commandline_args = shlex.split(argfile.read()) + commandline_args
            except (OSError, ValueError) as e:
                options.die(f"can not read response file {arg[1:]}: {e}")
            continue
        parse_arg(arg, commandline_args, options)

    return options


# check for options which are for dcc and should not be passed to clang


def parse_arg(arg, remaining_args, options):
    if arg.startswith("-fsanitize="):
        options.sanitizers = []
        sanitizer_list = arg[len("-fsanitize=") :].split(",")
        for sanitizer in sanitizer_list:
            if sanitizer in ["memory", "address", "valgrind"]:
                if sanitizer == "valgrind" and not search_path("valgrind"):
                    options.warn("warning: valgrind does not seem be installed")
                options.sanitizers.append(sanitizer)
            elif sanitizer not in ["undefined"]:
                options.die("unknown sanitizer", sanitizer)
        if len(options.sanitizers) not in [1, 2]:
            options.die("only 1 or 2 sanitizers supported")
    elif arg in ["--memory"]:  # for backwards compatibility
        options.sanitizers = ["memory"]
    elif arg == "--valgrind":  # for backwards compatibility
        options.sanitizers = ["valgrind"]
    elif arg == "--leak-check" or arg == "--leakcheck":
        options.leak_check = True
    elif arg.startswith("--suppressions="):
        # the program may be run from a different directory
        options.suppressions_file = os.path.abspath(arg[len("--suppressions=") :])
    elif (
        arg == "--explanations" or arg == "--no_explanation"
    ):  # backwards compatibility
        options.explanations = True
    elif arg == "--no-explanations":
        options.explanations = False
    elif arg == "--shared-libasan" or arg == "-shared-libasan":
        options.shared_libasan = True
    # support both spelling for backwards compatibility
    elif arg == "--use-after-return" or arg == "--use_after_return":
        options.stack_use_after_return = True
    elif arg == "--use-funopen":
        options.use_funopen = True
    elif arg == "--no-shared-libasan":
        options.shared_libasan = False
    elif arg == "--valgrind-fix-posix-spawn":
        options.valgrind_fix_posix_spawn = True
    elif arg == "--no-valgrind-fix-posix-spawn":
        options.valgrind_fix_posix_spawn = False
    elif arg == "--ifdef" or arg == "--ifdef-main":
        options.ifdef_instead_of_wrap = True
    elif arg.startswith("--c-compiler="):
        options.c_compiler = arg[arg.index("=") + 1 :]
        if not search_path(options.c_compiler):
            options.die(f"{options.c_compiler} not found")
    elif arg.startswith("--compile_helper="):
        options.compile_helper = arg[len("--compile_helper=") :]
    elif arg.startswith("--compile_logger="):
        options.compile_logger = arg[len("--compile_logger=") :]
    elif arg.startswith("--embedded_environment_variable="):
        name_value = arg[len("--embedded_environment_variable=") :]
        name, _, value = name_value.partition("=")
        options.embedded_environment_variables.append((name, value))
    elif arg == "-fcolor-diagnostics":
        options.colorize_output = True
    elif arg == "-fno-color-diagnostics":
        options.colorize_output = False
    elif arg == "-v" or arg == "--version":
        print("dcc version", VERSION)
        options.tar.close()
        sys.exit(0)
    elif arg == "--help":
        print(usage())
        options.tar.close()
        sys.exit(0)
    elif arg.startswith("-o"):
        if arg == "-o":
            if remaining_args:
                options.object_pathname = remaining_args.pop(0)
        else:
            options.object_pathname = arg[2:]
        op = options.object_pathname
        if (op.endswith(".c") or op.endswith(".h")) and os.path.exists(op):
            options.die(f"will not overwrite {op} with machine code")
    elif arg == "-l":
        # separated form of -l<library>
        if not remaining_args:
            options.die("argument to '-l' is missing")
        library = remaining_args.pop(0)
        options.user_supplied_compiler_args += [arg, library]
        if library not in ["m", "c"]:
            options.libraries_being_linked = True
    elif arg == "-" or names_stdin(arg):
        options.die("compilation of stdin not supported")
    else:
        parse_clang_arg(arg, options)


# check for options which are passed intact to clang
# but modify dcc behaviour


def parse_clang_arg(arg, options):
    if (
        arg == "-Weverything"
    ):  # -Weverything generate a pile of spurious warning from dcc wrapper code
        options.warn(
            "warning: -Weverything not compatible with dcc, replaced with Wextra"
        )
        arg = "-Wextra"
    if arg == "-pthreads":
        # gcc, which is run for extra checking, only accepts -pthread
        arg = "-pthread"
    options.user_supplied_compiler_args.append(arg)
    if arg == "-c":
        options.warn(
            "warning: "
            "using incremental compilation (-c) is not recommended with dcc\n"
            "Signficant parts of dcc error detection do not work with incremental compilation."
        )
        options.incremental_compilation = True
    elif arg.startswith("-l") and arg[2:] not in ["m", "c"]:
        # libm & libc are part of the C library so don't affect dual sanitizers
        options.libraries_being_linked = True
    elif arg == "-Werror":
        options.treat_warnings_as_errors = True
    elif arg == "-pthread":
        options.threads_used = True
    else:
        process_possible_source_file(arg, options, set())


# FIXME this is crude and brittle
def process_possible_source_file(pathname, options, processed_files):
    if pathname in processed_files:
        if options.debug:
            print("recursive include", pathname)
        # could print an error here about a recursive include
        return
    processed_files.add(pathname)
    extension = os.path.splitext(pathname)[1]
    if extension.lower() in [".a", ".o", ".so"]:
        options.object_files_being_linked = True
        return
    if extension.lower() in [".cpp", ".c++"]:
        options.cpp_mode = True
    try:
        with open(pathname, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r'^\s*#\s*include\s*"(.*?)"', line)
                if m:
                    process_possible_source_file(m.group(1), options, processed_files)
                m = re.match(r"^\s*#\s*include\s*<(.*?)>", line)
                if m:
                    options.system_includes_used.add(m.group(1))
    except OSError:
        return
    # don't try to handle paths with .. or with leading /
    # should we convert argument to normalized relative path if possible
    # before passing to to compiler?
    normalized_path = os.path.normpath(pathname)
    if pathname != normalized_path and os.path.join(".", normalized_path) != pathname:
        options.debug_print(
            "not embedding source of",
            pathname,
            "because normalized path differs:",
            normalized_path,
        )
        return
    if normalized_path.startswith(".."):
        options.debug_print(
            "not embedding source of", pathname, "because it contains .."
        )
        return
    if os.path.isabs(pathname):
        options.debug_print(
            "not embedding source of", pathname, "because it has absolute path"
        )
        return
    if pathname in options.source_files:
        return
    try:
        if not os.path.isfile(pathname):
            options.debug_print("skipping", pathname, "not a regular file", level=2)
            return
        if os.path.getsize(pathname) > options.maximum_source_file_embedded_bytes:
            options.debug_print("skipping", pathname, "too large", level=2)
            return
        options.tar.add(pathname)
        options.source_files.add(pathname)
        options.debug_print("adding", pathname, "to tar file", level=2)
    except OSError as e:
        if options.debug:
            print("process_possible_source_file", pathname, e)
        return


def names_stdin(pathname):
    # /dev/stdin is a symlink to /proc/self/fd/0 on Linux, so a student can
    # name the same file several ways, and only what it is identifies it.
    # The literals are kept for when stdin is closed and can not be compared.
    if pathname in ["/dev/stdin", "/dev/fd/0", "/proc/self/fd/0"]:
        return True
    if not pathname.startswith(("/dev/", "/proc/")):
        return False
    try:
        return os.path.samestat(os.stat(pathname), os.stat(0))
    except OSError:
        return False


def is_compiled_program(pathname):
    # the execute bit is unreliable, e.g. on a file just copied from Windows,
    # so look at what is in the file
    try:
        with open(pathname, "rb") as f:
            return f.read(4) in EXECUTABLE_MAGIC_NUMBERS
    except OSError:
        return False


def test_clang_version_exists(compiler, options):
    # apple replaces clang version with xcode release
    # which might break the workarounds below for old clang version
    try:
        clang_version_string = subprocess.check_output(
            [compiler, "--version"], universal_newlines=True
        )
        options.debug_print("clang version:", clang_version_string)
        # assume little about how version is printed, e.g. because macOS mangles it
        m = re.search(r"((\d+)\.(\d+)\.\d+)", clang_version_string, flags=re.I)
        if m:
            options.clang_version = m.group(1)
            options.clang_version_major = m.group(2)
            options.clang_version_minor = m.group(3)
            options.clang_version_float = float(m.group(2) + "." + m.group(3))
            options.c_compiler = compiler
            return True
        else:
            if options.debug:
                print(f"can not parse clang version '{clang_version_string}'")

    except OSError as e:
        if options.debug:
            print(e)

    if not options.clang_version:
        if options.debug:
            print(f"can not get version information for '{options.c_compiler}'")
    return False


def get_libc_version(options):
    try:
        libc_version = subprocess.check_output(["ldd", "--version"]).decode("ascii")
        if options.debug:
            print("libc version:", libc_version)
        m = re.search(r"([0-9]\.[0-9]+)", libc_version)
        if m:
            return float(m.group(1))
    except Exception as e:
        if options.debug:
            print(e)
    return None
