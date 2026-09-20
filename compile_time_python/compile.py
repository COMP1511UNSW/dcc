import hashlib, io, json, os, pkgutil, platform, re, shutil, stat
import subprocess, sys, tarfile, tempfile
import colors

from version import VERSION
from options import get_options
from explain_compiler_output import explain_compiler_output

FILES_EMBEDDED_IN_BINARY = [
    "drive_gdb.py",
    "colors.py",
    "gdb_interface.py",
    "explain_context.py",
    "explain_error.py",
    "explain_output_difference.py",
    "start_gdb.py",
    "util.py",
    "watch_valgrind.py",
]

# its possible  -g -fno-omit-frame-pointer could be needed here
# specifying dwarf-4 avoids warnings & errors from valgrind on Debian bookworm & trixie
WRAPPER_SOURCE_COMPILER_ARGS = """
    -gdwarf-4
    -g
    -O3
""".split()

DEBUG_COMPILE_FILE = "tmp_dcc.sh"


#
# Compile the user's program adding some C code
#
def main():
    os.environ["PATH"] = (
        os.path.dirname(os.path.realpath(sys.argv[0]))
        + ":/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:"
        + os.environ.get("PATH", "")
    )
    options = get_options()
    with tempfile.TemporaryDirectory(prefix="dcc") as d:
        options.temporary_directory = d
        p = compile_user_program(options)
        explanation_labels = []
        if p.stdout:
            if options.explanations:
                explanations = explain_compiler_output(p.stdout, options)
                explanation_labels = [e.label for e in explanations if e and e.label]
            else:
                print(p.stdout, end="", file=sys.stderr)
        run_compile_time_logger(p, explanation_labels, options)
        sys.exit(p.returncode)


def compile_user_program(options):
    wrapper_source, wrapper_cpp_source = get_wrapper_code(options)
    # the Python which explains errors travels in the binary as a tar file
    embedded_objects = [
        embedded_blob_object(options, "dcc_tar_data", embedded_tarfile_bytes(options))
    ]

    if options.debug > 1:
        try:
            options.debug_print(f"Leaving dcc compile_command in {DEBUG_COMPILE_FILE}")
            with open(DEBUG_COMPILE_FILE, mode="w", encoding="utf-8") as f:
                print("#!/bin/sh", file=f)
            os.chmod(DEBUG_COMPILE_FILE, 0o755)
        except OSError:
            pass

    if len(options.sanitizers) == 2:
        sanitizer2_wrapper_source, sanitizer2_sanitizer_args = update_wrapper_source(
            options.sanitizers[1], 2, wrapper_source, options
        )
        sanitizer2_wrapper_source = (
            "#undef _GNU_SOURCE\n#define _GNU_SOURCE 1\n#include <stdint.h>\n"
            + sanitizer2_wrapper_source
        )
        # the executable is placed in dcc's temporary directory
        # so it is removed even if compilation fails
        executable = os.path.join(options.temporary_directory, "dcc_sanitizer2")
        p = execute_compiler(
            options.c_compiler,
            options.dcc_supplied_compiler_args
            + sanitizer2_sanitizer_args
            + ["-o", executable],
            options,
            wrapper_C_source=sanitizer2_wrapper_source,
            wrapper_cpp_source=wrapper_cpp_source,
            wrapper_extra_options=[
                opt for opt in sanitizer2_sanitizer_args if opt.startswith("-f")
            ],
            debug_C_wrapper_file="tmp_dcc_sanitizer2.c",
            embedded_objects=embedded_objects,
        )
        if p.returncode != 0:
            return p
        # this executable travels inside the one which is about to be built
        # nothing is produced by e.g. -fsyntax-only, which embeds an empty one
        try:
            with open(executable, "rb") as f:
                executable_bytes = f.read()
        except FileNotFoundError:
            executable_bytes = b""
        except OSError as e:
            options.die(f"internal error: can not read {executable}: {e.strerror}")
        embedded_objects.append(
            embedded_blob_object(options, "dcc_sanitizer2_data", executable_bytes)
        )

    # leave leak checking to valgrind if it is running
    # because it currently gives better errors
    wrapper_source, sanitizer_args = update_wrapper_source(
        options.sanitizers[0], 1, wrapper_source, options
    )

    if options.incremental_compilation:
        incremental_compilation_args = (
            sanitizer_args
            + options.dcc_supplied_compiler_args
            + options.user_supplied_compiler_args
        )
        command = [options.c_compiler] + incremental_compilation_args
        if options.object_pathname != "a.out":
            command += ["-o", options.object_pathname]
        options.debug_print("incremental compilation, running: ", " ".join(command))
        return subprocess.run(command, check=False)

    # _GNU_SOURCE to get fopencookie
    wrapper_source = (
        "#undef _GNU_SOURCE\n#define _GNU_SOURCE 1\n#include <stdint.h>\n"
        + wrapper_source
    )
    p = execute_compiler(
        options.c_compiler,
        options.dcc_supplied_compiler_args
        + sanitizer_args
        + ["-o", options.object_pathname],
        options,
        wrapper_C_source=wrapper_source,
        wrapper_extra_options=[opt for opt in sanitizer_args if opt.startswith("-f")],
        wrapper_cpp_source=wrapper_cpp_source,
        embedded_objects=embedded_objects,
    )
    if p.returncode != 0 or p.stdout:
        return p

    # gcc picks up some errors at compile-time that clang doesn't, e.g
    # int main(void) {int a[1]; return a[0];}
    # so run gcc as well if available

    if (
        options.also_run_gcc
        and "gcc" not in options.c_compiler
        and not options.object_files_being_linked
    ):
        options.debug_print("compiling with gcc for extra checking")
        return execute_compiler(
            "g++" if options.cpp_mode else "gcc",
            options.gcc_args,
            options,
            rename_functions=False,
        )

    return p


# The Python source and the second executable are made available to the C code
# as a pair of symbols defined by an object file, rather than as array
# initializers in the generated C, which the compiler would have to parse on
# every compilation.
BLOB_ASSEMBLER_SOURCE = """\
#ifdef __APPLE__
# define DCC_BLOB(name) _ ## name
    .section __TEXT,__const
#else
# define DCC_BLOB(name) name
    .section .rodata
#endif
    .p2align 3
    .globl DCC_BLOB(__SYMBOL__)
DCC_BLOB(__SYMBOL__):
    .incbin "__PATHNAME__"
    .globl DCC_BLOB(__SYMBOL___end)
DCC_BLOB(__SYMBOL___end):
"""


def embedded_blob_object(options, symbol, contents):
    """return an object file defining symbol and symbol_end around contents"""
    pathname = os.path.join(options.temporary_directory, symbol)
    with open(pathname, "wb") as f:
        f.write(contents)
    source = BLOB_ASSEMBLER_SOURCE.replace("__SYMBOL__", symbol)
    source = source.replace("__PATHNAME__", pathname)
    object_pathname = pathname + ".o"
    compiler = options.c_compiler.replace("clang++", "clang").replace("++", "cc")
    command = [compiler, "-c", "-x", "assembler-with-cpp", "-", "-o", object_pathname]
    process = run(command, options, input_text=source)
    if process.stdout or process.returncode != 0:
        options.die("Internal error embedding " + symbol + "\n" + process.stdout)
    if options.debug > 1:
        # so the recorded compile command can be re-run
        try:
            shutil.copyfile(object_pathname, os.path.basename(object_pathname))
        except OSError as e:
            options.debug_print(e)
    return object_pathname


# customize wrapper source for a particular sanitizer
def update_wrapper_source(sanitizer, sanitizer_n, src, options):
    src = src.replace("__SANITIZER__", sanitizer.upper())
    if sanitizer == "valgrind":
        sanitizer_args = []
    elif sanitizer == "memory":
        sanitizer_args = ["-fsanitize=memory"]
    else:
        sanitizer_args = ["-fsanitize=address"]

    # 	if sanitizer != "memory" and not (sanitizer_n == 2 and sanitizer == "valgrind"):
    if sanitizer != "memory" and not (sanitizer_n == 2 and sanitizer == "valgrind"):
        # FIXME if we enable '-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer' for memory
        # which would be preferable here we get uninitialized variable error message for undefined errors
        src = src.replace("__UNDEFINED_BEHAVIOUR_SANITIZER_IN_USE__", "1")
        sanitizer_args += ["-fsanitize=undefined"]
    if sanitizer == "address":
        sanitizer_args += ["-ftrivial-auto-var-init=pattern"]

    # These options stop error explanations if	__ubsan_on_report can not be intercepted (on Ubuntu)
    # They appear to have  no significant benefit on other platforms
    # 		if options.clang_version_float >= 3.6:
    # 			sanitizer_args += ['-fno-sanitize-recover=undefined,integer']

    if options.shared_libasan and sanitizer == "address" and options.clang_version:
        lib_dir = options.clang_lib_dir.replace(
            "{clang_version}", options.clang_version
        )
        if os.path.exists(lib_dir):
            sanitizer_args += ["-shared-libasan", "-Wl,-rpath," + lib_dir]

    src = src.replace("__LEAK_CHECK_YES_NO__", "yes" if options.leak_check else "no")
    leak_check = options.leak_check
    if leak_check and options.sanitizers[1:] == ["valgrind"]:
        # do leak checking in valgrind (only) for (currently) better messages
        leak_check = False
    src = src.replace("__LEAK_CHECK_1_0__", "1" if leak_check else "0")
    src = src.replace("__USE_FUNOPEN__", "1" if options.use_funopen else "0")

    src = src.replace("__I_AM_SANITIZER1__", "1" if sanitizer_n == 1 else "0")
    src = src.replace("__I_AM_SANITIZER2__", "1" if sanitizer_n == 2 else "0")
    src = src.replace(
        "__WHICH_SANITIZER__", "sanitizer2" if sanitizer_n == 2 else "sanitizer1"
    )

    return src, sanitizer_args


def execute_compiler(
    compiler,
    dcc_supplied_arguments,
    options,
    wrapper_C_source="",
    debug_C_wrapper_file="tmp_dcc_sanitizer1.c",
    rename_functions=True,
    wrapper_cpp_source="",
    wrapper_extra_options=None,
    debug_cpp_wrapper_file="tmp_dcc_sanitizer1.cpp",
    embedded_objects=(),
):
    wrapper_extra_options = wrapper_extra_options or []
    extra_c_arguments, extra_c_arguments_debug = compile_wrapper_source(
        wrapper_C_source,
        options,
        debug_C_wrapper_file,
        cpp=False,
        rename_functions=rename_functions,
        wrapper_extra_options=wrapper_extra_options,
    )
    extra_cpp_arguments, extra_cpp_arguments_debug = compile_wrapper_source(
        wrapper_cpp_source,
        options,
        debug_cpp_wrapper_file,
        cpp=True,
        rename_functions=rename_functions,
        wrapper_extra_options=wrapper_extra_options,
    )

    command = (
        [compiler]
        + dcc_supplied_arguments
        + extra_c_arguments
        + extra_cpp_arguments
        + list(embedded_objects)
        + options.user_supplied_compiler_args
        + options.dcc_supplied_linker_args
    )
    if options.debug > 1:
        debug_command = (
            [compiler]
            + dcc_supplied_arguments
            + extra_c_arguments_debug
            + extra_cpp_arguments_debug
            + list(embedded_objects)
            + options.user_supplied_compiler_args
            + options.dcc_supplied_linker_args
        )
        # files in the temporary directory are recorded by basename
        # so the debug script can be re-run after the directory is removed
        debug_command = [
            os.path.basename(a) if a.startswith(options.temporary_directory) else a
            for a in debug_command
        ]
        append_debug_compile(debug_command)
    p = run(command, options)

    # avoid a confusing mess of linker errors
    if linker_reports_missing_main(p.stdout):
        p.stdout = "error: your program does not contain a main function - a C program must contain a main function"
        p.returncode = 1
        return p

    # workaround for  https://github.com/android-ndk/ndk/issues/184
    # when not triggered earlier
    if "undefined reference to `__mul" in p.stdout:
        command = [
            c
            for c in command
            if c
            not in ["-fsanitize=undefined", "-fno-sanitize-recover=undefined,integer"]
        ]
        options.debug_print("undefined reference to `__mulodi4'")
        options.debug_print("recompiling", " ".join(command))
        p = run(command, options)

    # a user call to a renamed unistd.h function appears to be undefined
    # so recompile without renames

    if rename_functions and "undefined reference to `__renamed_" in p.stdout:
        options.debug_print(
            "undefined reference to `__renamed_' recompiling without -D renames"
        )
        return execute_compiler(
            compiler,
            dcc_supplied_arguments,
            options,
            rename_functions=False,
            wrapper_C_source=wrapper_C_source,
            debug_C_wrapper_file=debug_C_wrapper_file,
            wrapper_cpp_source=wrapper_cpp_source,
            wrapper_extra_options=wrapper_extra_options,
            debug_cpp_wrapper_file=debug_cpp_wrapper_file,
            embedded_objects=embedded_objects,
        )
    return p


def linker_reports_missing_main(linker_output):
    """return True if GNU ld or lld reports that main is undefined"""
    return bool(
        re.search(r"undefined (reference to `|symbol: )main(['\s]|$)", linker_output, re.M)
    )


def compile_wrapper_source(
    source,
    options,
    debug_wrapper_file,
    cpp=False,
    rename_functions=True,
    wrapper_extra_options=None,
):
    if not source:
        return [], []
    wrapper_extra_options = wrapper_extra_options or []
    rename_arguments, source = get_rename_arguments(source, options, rename_functions)
    relocatable_basename = (
        "dcc_cpp_wrapper_source.o" if cpp else "dcc_c_wrapper_source.o"
    )
    relocatable_pathname = os.path.join(
        options.temporary_directory, relocatable_basename
    )
    compiler = options.c_compiler
    if not cpp:
        compiler = options.c_compiler.replace("clang++", "clang").replace("++", "cc")
    if options.debug > 1:
        try:
            options.debug_print("Leaving dcc code in", debug_wrapper_file)
            with open(debug_wrapper_file, "w", encoding="utf-8") as f:
                f.write(source)
        except OSError as e:
            print(e)
        debug_command = [
            compiler,
            "-c",
            debug_wrapper_file,
            "-o",
            relocatable_basename,
        ] + WRAPPER_SOURCE_COMPILER_ARGS + wrapper_extra_options
        append_debug_compile(debug_command)
    command = [
        compiler,
        "-c",
        "-x",
        "c++" if cpp else "c",
        "-",
        "-o",
        relocatable_pathname,
    ] + WRAPPER_SOURCE_COMPILER_ARGS + wrapper_extra_options
    options.debug_print("wrapper options", wrapper_extra_options)
    process = run(command, options, input_text=source)
    if process.stdout or process.returncode != 0:
        options.die("Internal error\n" + process.stdout)
    return rename_arguments + [relocatable_pathname], rename_arguments + [
        relocatable_basename
    ]


def get_rename_arguments(source, options, rename_functions=True):
    rename_arguments = []

    # stop programs with a function clashing with a function from unistd.h e.g read
    # breaking dcc wrapper code by renaming them
    if rename_functions and not options.unsafe_system_includes:
        # unistd functions used by single-sanitizer dcc
        rename_function_names = ["_exit", "close", "execvp", "getpid"]
        # unistd functions used by dual-sanitizer dcc
        if len(options.sanitizers) > 1:
            rename_function_names += [
                "lseek",
                "pipe",
                "read",
                "sleep",
                "unlink",
                "write",
            ]
        rename_arguments += [f"-D{f}=__renamed_{f}" for f in rename_function_names]

    override_functions = []
    if len(options.sanitizers) > 1:
        override_functions = [
            "clock",
            "fdopen",
            "fopen",
            "freopen",
            "popen",
            "remove",
            "rename",
            "system",
            "time",
        ]
    if options.valgrind_fix_posix_spawn:
        override_functions += ["posix_spawn", "posix_spawnp"]

    if options.ifdef_instead_of_wrap:
        if options.cpp_mode:
            rename_arguments += ['-Dmain=__fake_variable;extern "C" int __real_main']
        else:
            rename_arguments += ["-Dmain=__real_main"]
        rename_arguments += [
            f"-D{f}=__wrap_{f}" for f in ["fileno"] + override_functions
        ]
        source = source.replace("__wrap_main", "main")
        source = source.replace("__real_fileno", "fileno")
        for f in override_functions:
            source = source.replace("__real_" + f, f)
    else:
        rename_arguments += [
            "-Wl"
            + "".join(",-wrap," + f for f in ["main", "fileno"] + override_functions)
        ]
    return rename_arguments, source


def append_debug_compile(command):
    try:
        with open(DEBUG_COMPILE_FILE, "a", encoding="utf-8") as f:
            print(" ".join(command), file=f)
    except OSError as e:
        print(e, file=sys.stderr)


def get_wrapper_code(options):
    wrapper_source = "".join(
        pkgutil.get_data("embedded_src", f).decode("utf8")
        for f in [
            "dcc_main.c",
            "dcc_dual_sanitizers.c",
            "dcc_util.c",
            "dcc_check_output.c",
            "dcc_save_stdin.c",
        ]
    )
    wrapper_source = add_constants_to_source_code(wrapper_source, options)
    wrapper_source = add_embedded_tarfile_handling_to_source_code(wrapper_source)
    wrapper_cpp_source = ""
    if options.cpp_mode:
        wrapper_cpp_source = "".join(
            pkgutil.get_data("embedded_src", f).decode("utf8")
            for f in [
                "dcc_io.cpp",
            ]
        )
    return wrapper_source, wrapper_cpp_source


def add_constants_to_source_code(src, options):
    # these values become C string literals so they must be escaped
    src = src.replace("__PATH__", c_repr(options.dcc_path))
    src = src.replace("__SUPRESSIONS_FILE__", c_repr(options.suppressions_file))
    src = src.replace(
        "__STACK_USE_AFTER_RETURN__", "1" if options.stack_use_after_return else "0"
    )
    src = src.replace("__CHECK_OUTPUT__", "1" if options.check_output else "0")
    src = src.replace("__SAVE_STDIN_BUFFER_SIZE__", str(options.save_stdin_buffer_size))
    src = src.replace("__CPP_MODE__", "1" if options.cpp_mode else "0")
    src = src.replace(
        "__WRAP_POSIX_SPAWN__", "1" if options.valgrind_fix_posix_spawn else "0"
    )
    src = src.replace("__CLANG_VERSION_MAJOR__", str(options.clang_version_major))
    src = src.replace("__CLANG_VERSION_MINOR__", str(options.clang_version_minor))
    src = src.replace("__N_SANITIZERS__", str(len(options.sanitizers)))
    src = src.replace("__DEBUG__", "1" if options.debug else "0")
    src = src.replace(
        "__SET_EMBEDDED_ENVIRONMENT_VARIABLES__", embeded_environment_variables(options)
    )
    if len(options.sanitizers) > 1:
        src = src.replace("__SANITIZER_2__", options.sanitizers[1].upper())
    return src


def add_embedded_tarfile_handling_to_source_code(src):
    # the size of the tar file is passed in the environment, because the
    # bytes are linked in rather than being part of this source
    watcher = r"""PATH=$PATH:/bin:/usr/bin:/usr/local/bin exec python3 -E -c \"import io,os,sys,tarfile,tempfile\n\
with tempfile.TemporaryDirectory() as temp_dir:\n\
 n = int(os.environ['DCC_TAR_N_BYTES'])\n\
 buffer = io.BytesIO(sys.stdin.buffer.raw.read(n))\n\
 if len(buffer.getbuffer()) == n:\n\
  k = {'filter':'data'} if hasattr(tarfile, 'data_filter') else {}\n\
  tarfile.open(fileobj=buffer, bufsize=n, mode='r|xz').extractall(temp_dir, **k)\n\
  os.environ['DCC_PWD'] = os.getcwd()\n\
  os.chdir(temp_dir)\n\
  exec(open('watch_valgrind.py').read())\n\
\""""
    return src.replace("__MONITOR_VALGRIND__", watcher)


def embeded_environment_variables(options):
    ev = options.embedded_environment_variables
    assignments = [f"setenvd({c_repr(k)}, {c_repr(v)});" for (k, v) in ev]
    return "\n".join(assignments)


def c_repr(s):
    """return s as a C string literal"""
    literal = '"'
    for c in s:
        if c in '"\\?':
            # ? is escaped so that ?? can not form a trigraph
            literal += "\\" + c
        elif " " <= c <= "~":
            literal += c
        else:
            # octal escapes are at most 3 digits so a following digit is safe
            literal += "".join(f"\\{b:03o}" for b in c.encode("utf-8", "surrogateescape"))
    return literal + '"'


def run(
    command,
    options,
    input_text="",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    errors="replace",
    check=False,
):
    options.debug_print(" ".join(command))
    return subprocess.run(
        command,
        input=input_text,
        stdout=stdout,
        stderr=stderr,
        text=text,
        errors=errors,
        check=check,
    )


def embedded_tarfile_bytes(options):
    """return the xz-compressed tar of the Python which explains errors"""
    for file in FILES_EMBEDDED_IN_BINARY:
        contents = pkgutil.get_data("embedded_src", file)
        if file.endswith(".py"):
            contents = minify(contents)
        add_tar_file(options.tar, file, contents)
    options.tar.close()
    return options.tar_buffer.getvalue()


# Remove comment lines from Python source before embedding it in the binary.
# Very limited benefit as the source is xz compressed before being embedded.
def minify(python_source_bytes):
    python_source = python_source_bytes.decode("utf-8")
    lines = [line for line in python_source.splitlines() if not is_comment(line)]
    return ("\n".join(lines) + "\n").encode("utf-8")


def is_comment(line):
    return re.match(r"^\s*#", line)


def add_tar_file(tar, pathname, contents):
    file_buffer = io.BytesIO(contents)
    file_info = tarfile.TarInfo(pathname)
    file_info.size = len(contents)
    tar.addfile(file_info, file_buffer)


MAX_BYTES_LOG_SOURCE_FILE = 20480


def run_compile_time_logger(process, explanation_labels, options):
    """
    run a script to log compiles
    """
    if not options.compile_logger:
        return
    stdout = process.stdout or ""
    stdout_first_line = colors.strip_color("".join(stdout.splitlines()[:1]))
    logger_info = {
        "argv": sys.argv[1:],
        "exit": process.returncode,
        "first_line": stdout_first_line,
        "labels": explanation_labels,
    }
    source_file = stdout_first_line.split(":")[0]
    try:
        if (
            source_file.endswith((".c", ".cpp", ".cc", ".cxx", ".c++"))
            and os.path.getsize(source_file) < MAX_BYTES_LOG_SOURCE_FILE
        ):
            with open(source_file, encoding="utf-8", errors="replace") as f:
                logger_info["source"] = f.read(MAX_BYTES_LOG_SOURCE_FILE)
    except OSError:
        pass

    if options.debug:
        print(f"compile_logger logger='{options.compile_logger} info='{logger_info}'")

    for k, v in logger_info.items():
        os.environ["DCC_LOGGER_" + k.upper()] = str(v).replace("\x00", "\\x00")
    os.environ["DCC_LOGGER_JSON"] = json.dumps(logger_info, separators=(",", ":"))

    if options.debug:
        print(f"running {options.compile_logger}")
    try:
        sys.stdout.flush()
        sys.stderr.flush()
        subprocess.run([options.compile_logger], check=False)
    except OSError as e:
        if options.debug:
            print(e)
