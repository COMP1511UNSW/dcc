import io, os, pkgutil, platform, re, subprocess, sys, tarfile, tempfile

from version import VERSION
from options import get_options
from explain_compiler_output import explain_compiler_output

FILES_EMBEDDED_IN_BINARY = [
    "start_gdb.py",
    "drive_gdb.py",
    "watch_valgrind.py",
    "colors.py",
    "explain_output_difference.py",
    "util.py",
]

# its possible  -g -fno-omit-frame-pointer could be needed here
WRAPPER_SOURCE_COMPILER_ARGS = """
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
        compile_user_program(options)


def compile_user_program(options):
    wrapper_source, tar_source = get_wrapper_tar_source(options)
    compiler_stdout = ""
    executable_source = ""

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
            options.sanitizers[1], 2, wrapper_source, tar_source, options
        )
        sanitizer2_wrapper_source = (
            "#undef _GNU_SOURCE\n#define _GNU_SOURCE 1\n#include <stdint.h>\n"
            + sanitizer2_wrapper_source
        )
        try:
            # can't use tempfile.NamedTemporaryFile because may be multiple opens of file
            executable = tempfile.mkstemp(prefix="dcc_sanitizer2")[1]
            compiler_stdout = execute_compiler(
                options.c_compiler,
                options.dcc_supplied_compiler_args
                + sanitizer2_sanitizer_args
                + ["-o", executable],
                options,
                wrapper_source=sanitizer2_wrapper_source,
                debug_wrapper_file="tmp_dcc_sanitizer2.c",
            )
            with open(executable, "rb") as f:
                (
                    executable_n_bytes,
                    executable_source,
                ) = source_for_sanitizer2_executable(f.read())
            os.unlink(executable)
        except OSError:
            # compiler may unlink temporary file resulting in this exception
            sys.exit(1)

    # leave leak checking to valgrind if it is running
    # because it currently gives better errors
    wrapper_source, sanitizer_args = update_wrapper_source(
        options.sanitizers[0], 1, wrapper_source, tar_source, options
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
        sys.exit(subprocess.call(command))

    if executable_source:
        wrapper_source = wrapper_source.replace(
            "__EXECUTABLE_N_BYTES__", str(executable_n_bytes)
        )
        wrapper_source = executable_source + wrapper_source

    # _GNU_SOURCE to get fopencookie
    wrapper_source = (
        "#undef _GNU_SOURCE\n#define _GNU_SOURCE 1\n#include <stdint.h>\n"
        + wrapper_source
    )
    compiler_stdout = execute_compiler(
        options.c_compiler,
        options.dcc_supplied_compiler_args
        + sanitizer_args
        + ["-o", options.object_pathname],
        options,
        wrapper_source=wrapper_source,
        print_stdout=not compiler_stdout,
    )

    # gcc picks up some errors at compile-time that clang doesn't, e.g
    # int main(void) {int a[1]; return a[0];}
    # so run gcc as well if available

    if (
        not compiler_stdout
        and options.also_run_gcc
        and "gcc" not in options.c_compiler
        and not options.object_files_being_linked
    ):
        options.debug_print("compiling with gcc for extra checking")
        execute_compiler(
            "g++" if options.cpp_mode else "gcc",
            options.gcc_args,
            options,
            rename_functions=False,
            checking_only=True,
        )

    sys.exit(0)


# customize wrapper source for a particular sanitizer
def update_wrapper_source(sanitizer, sanitizer_n, wrapper_source, tar_source, options):
    wrapper_source = wrapper_source.replace("__SANITIZER__", sanitizer.upper())
    if sanitizer == "valgrind":
        sanitizer_args = []
    elif sanitizer == "memory":
        sanitizer_args = ["-fsanitize=memory"]
    else:
        sanitizer_args = ["-fsanitize=address"]

    # 	if sanitizer != "memory" and not (sanitizer_n == 2 and sanitizer == "valgrind"):
    if sanitizer != "memory" and not (sanitizer_n == 2 and sanitizer == "valgrind"):
        # FIXME if we enable  '-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer' for memory
        # which would be preferable here we get uninitialized variable error message for undefined errors
        wrapper_source = wrapper_source.replace(
            "__UNDEFINED_BEHAVIOUR_SANITIZER_IN_USE__", "1"
        )
        sanitizer_args += ["-fsanitize=undefined"]

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

    wrapper_source = wrapper_source.replace(
        "__LEAK_CHECK_YES_NO__", "yes" if options.leak_check else "no"
    )
    leak_check = options.leak_check
    if leak_check and options.sanitizers[1:] == ["valgrind"]:
        # do leak checking in valgrind (only) for (currently) better messages
        leak_check = False
    wrapper_source = wrapper_source.replace(
        "__LEAK_CHECK_1_0__", "1" if leak_check else "0"
    )
    wrapper_source = wrapper_source.replace(
        "__USE_FUNOPEN__", "1" if options.use_funopen else "0"
    )

    wrapper_source = wrapper_source.replace(
        "__I_AM_SANITIZER1__", "1" if sanitizer_n == 1 else "0"
    )
    wrapper_source = wrapper_source.replace(
        "__I_AM_SANITIZER2__", "1" if sanitizer_n == 2 else "0"
    )
    wrapper_source = wrapper_source.replace(
        "__WHICH_SANITIZER__", "sanitizer2" if sanitizer_n == 2 else "sanitizer1"
    )

    wrapper_source = tar_source + wrapper_source
    return wrapper_source, sanitizer_args


def execute_compiler(
    compiler,
    dcc_supplied_arguments,
    options,
    wrapper_source="",
    debug_wrapper_file="tmp_dcc_sanitizer1.c",
    rename_functions=True,
    print_stdout=True,
    checking_only=False,
):
    extra_arguments, extra_arguments_debug = compile_wrapper_source(
        wrapper_source, options, rename_functions, debug_wrapper_file
    )

    command = (
        [compiler]
        + dcc_supplied_arguments
        + extra_arguments
        + options.user_supplied_compiler_args
    )
    if options.debug > 1:
        debug_command = (
            [compiler]
            + dcc_supplied_arguments
            + extra_arguments_debug
            + options.user_supplied_compiler_args
        )
        append_debug_compile(debug_command)
    process = run(command, options)
    stdout = process.stdout
    if checking_only:
        # we are running gcc as an extra checking phase
        # and options don't match the gcc version so give up silently
        if "command line" in stdout or "option" in stdout or "/dev/null" in stdout:
            options.debug_print(stdout)
            return ""

        # checking is run after we have already successfully generated an executable with clang
        # so if we can get an error, unlink the executable
        if process.returncode:
            try:
                os.unlink(options.object_pathname)
            except OSError as e:
                if options.debug:
                    print(e)

    # avoid a confusing mess of linker errors
    if "undefined reference to `main" in stdout:
        options.die(
            "error: your program does not contain a main function - a C program must contain a main function"
        )

    # workaround for  https://github.com/android-ndk/ndk/issues/184
    # when not triggered earlier
    if "undefined reference to `__mul" in stdout and not checking_only:
        command = [
            c
            for c in command
            if c
            not in ["-fsanitize=undefined", "-fno-sanitize-recover=undefined,integer"]
        ]
        options.debug_print("undefined reference to `__mulodi4'")
        options.debug_print("recompiling", " ".join(command))
        process = run(command, options)
        stdout = process.stdout

    # a user call to a renamed unistd.h function appears to be undefined
    # so recompile without renames

    if (
        rename_functions
        and "undefined reference to `__renamed_" in stdout
        and not checking_only
    ):
        options.debug_print(
            "undefined reference to `__renamed_' recompiling without -D renames"
        )
        return execute_compiler(
            compiler,
            dcc_supplied_arguments,
            options,
            rename_functions=False,
            wrapper_source=wrapper_source,
            print_stdout=print_stdout,
            debug_wrapper_file=debug_wrapper_file,
        )

    if stdout and print_stdout:
        if options.explanations:
            explain_compiler_output(stdout, options)
        else:
            print(stdout, end="", file=sys.stderr)

    if process.returncode:
        sys.exit(process.returncode)

    return stdout


def compile_wrapper_source(
    source, options, rename_functions=True, debug_wrapper_file="tmp_dcc_sanitizer1.c"
):
    if not source:
        return [], []
    rename_arguments, source = get_rename_arguments(source, options, rename_functions)
    relocatable_filename = os.path.join(
        options.temporary_directory, "dcc_wrapper_source.o"
    )
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
            "dcc_wrapper_source.o",
        ] + WRAPPER_SOURCE_COMPILER_ARGS
        append_debug_compile(debug_command)
    command = [
        compiler,
        "-c",
        "-x",
        "c",
        "-",
        "-o",
        relocatable_filename,
    ] + WRAPPER_SOURCE_COMPILER_ARGS
    process = run(command, options, input=source)
    if process.stdout or process.returncode != 0:
        options.die("Internal error\n" + process.stdout)
    return rename_arguments + [relocatable_filename], rename_arguments + [
        "dcc_wrapper_source.o",
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
        rename_arguments += [f"-D{f}=__wrap_{f}" for f in override_functions]
        source = source.replace("__wrap_main", "main")
        for f in override_functions:
            source = source.replace("__real_" + f, f)
    else:
        rename_arguments += [
            "-Wl" + "".join(",-wrap," + f for f in ["main"] + override_functions)
        ]
    return rename_arguments, source


def append_debug_compile(command):
    try:
        with open(DEBUG_COMPILE_FILE, "a", encoding="utf-8") as f:
            print(" ".join(command), file=f)
    except OSError as e:
        print(e, file=sys.stderr)


def get_wrapper_tar_source(options):
    wrapper_source = "".join(
        pkgutil.get_data("embedded_src", f).decode("utf8")
        for f in [
            "dcc_main.c",
            "dcc_dual_sanitizers.c",
            "dcc_util.c",
            "dcc_check_output.c",
        ]
    )

    wrapper_source = wrapper_source.replace("__PATH__", options.dcc_path)
    wrapper_source = wrapper_source.replace("__DCC_VERSION__", '"' + VERSION + '"')
    wrapper_source = wrapper_source.replace("__HOSTNAME__", '"' + platform.node() + '"')
    wrapper_source = wrapper_source.replace(
        "__CLANG_VERSION__", f'"{options.clang_version}"'
    )
    wrapper_source = wrapper_source.replace(
        "__SUPRESSIONS_FILE__", options.suppressions_file
    )
    wrapper_source = wrapper_source.replace(
        "__STACK_USE_AFTER_RETURN__", "1" if options.stack_use_after_return else "0"
    )
    wrapper_source = wrapper_source.replace(
        "__CHECK_OUTPUT__", "1" if options.check_output else "0"
    )
    wrapper_source = wrapper_source.replace(
        "__WRAP_POSIX_SPAWN__", "1" if options.valgrind_fix_posix_spawn else "0"
    )
    wrapper_source = wrapper_source.replace(
        "__CLANG_VERSION_MAJOR__", str(options.clang_version_major)
    )
    wrapper_source = wrapper_source.replace(
        "__CLANG_VERSION_MINOR__", str(options.clang_version_minor)
    )
    wrapper_source = wrapper_source.replace(
        "__N_SANITIZERS__", str(len(options.sanitizers))
    )
    wrapper_source = wrapper_source.replace("__DEBUG__", "1" if options.debug else "0")

    if len(options.sanitizers) > 1:
        wrapper_source = wrapper_source.replace(
            "__SANITIZER_2__", options.sanitizers[1].upper()
        )

    tar_n_bytes, tar_source = source_for_embedded_tarfile(options)
    watcher = rf"python3 -E -c \"import io,os,sys,tarfile,tempfile\n\
with tempfile.TemporaryDirectory() as temp_dir:\n\
 buffer = io.BytesIO(sys.stdin.buffer.raw.read({tar_n_bytes}))\n\
 if len(buffer.getbuffer()) == {tar_n_bytes}:\n\
  tarfile.open(fileobj=buffer, bufsize={tar_n_bytes}, mode='r|xz').extractall(temp_dir)\n\
  os.chdir(temp_dir)\n\
  exec(open('watch_valgrind.py').read())\n\
\""

    wrapper_source = wrapper_source.replace("__MONITOR_VALGRIND__", watcher)

    return wrapper_source, tar_source


def run(
    command,
    options,
    input="",
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    errors="replace",
    check=False,
):
    options.debug_print(" ".join(command))
    return subprocess.run(
        command,
        input=input,
        stdout=stdout,
        stderr=stderr,
        text=text,
        errors=errors,
        check=check,
    )


def source_for_sanitizer2_executable(executable):
    source = "\nstatic uint64_t sanitizer2_executable[] = {"
    source += bytes2hex64_initializers(executable)
    source += "};\n"
    n_bytes = len(executable)
    return n_bytes, source


def source_for_embedded_tarfile(options):
    for file in FILES_EMBEDDED_IN_BINARY:
        contents = pkgutil.get_data("embedded_src", file)
        if file.endswith(".py"):
            contents = minify(contents, options)
        add_tar_file(options.tar, file, contents)
    options.tar.close()
    n_bytes = options.tar_buffer.tell()
    options.tar_buffer.seek(0)

    source = "\nstatic uint64_t tar_data[] = {"
    while True:
        bytes_read = options.tar_buffer.read(1024)
        if not bytes_read:
            break
        source += bytes2hex64_initializers(bytes_read) + ",\n"
    source += "};\n"
    return n_bytes, source


def bytes2hex64_initializers(b):
    chunk = 8
    n_bytes = len(b)
    if n_bytes % chunk:
        b += bytes([0] * (chunk - n_bytes % chunk))
    hex_int64 = [
        hex(int.from_bytes(b[i : i + chunk], sys.byteorder))
        for i in range(0, len(b), chunk)
    ]
    return ",".join(hex_int64)


# Do some brittle shrinking of Python source  before embedding in binary.
# Very limited benefits as source is xz compressed before embedded in binary
def minify(python_source_bytes, options):
    python_source = python_source_bytes.decode("utf-8")
    lines = python_source.splitlines()
    lines1 = []
    while lines:
        line = lines.pop(0)
        if is_doc_string_delimiter(line):
            line = lines.pop(0)
            while not is_doc_string_delimiter(line):
                line = lines.pop(0)
            line = lines.pop(0)
        if is_comment(line):
            continue
        if not options.debug:
            line = re.sub(r"^(\s*)debug_print.*", r"\1pass", line)
        # removing white-space is probably safe but with xz it get us nothing
        # if line.startswith('\t') and '"' not in line and "'" not in line:
        # 	line = re.sub(r' *([=,+\-*/%:]) *', r'\1', line)
        lines1.append(line)
    python_source = "\n".join(lines1) + "\n"
    return python_source.encode("utf-8")


def is_doc_string_delimiter(line):
    return re.match(r'^(\t|	   )"""\s*$', line)


def is_comment(line):
    return re.match(r"^\s*#", line)


def add_tar_file(tar, pathname, contents):
    file_buffer = io.BytesIO(contents)
    file_info = tarfile.TarInfo(pathname)
    file_info.size = len(contents)
    tar.addfile(file_info, file_buffer)
