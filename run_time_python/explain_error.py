import json, os, re, signal, sys, subprocess, traceback
import colors, explain_context, gdb_interface, util
from util import dprint
from explain_output_difference import explain_output_difference

RUNTIME_HELPER_BASENAME = "dcc-runtime-helper"


def explain_error(output_stream, color):
    dprint(2, "explain_error() in drive_gdb.py starting")
    # file descriptor 3 is a dup of stderr (see below)
    # stdout & stderr have been diverted to /dev/null
    print(file=output_stream)
    stack = gdb_set_frame()
    location = stack[0] if stack else None
    signal_number = int(os.environ.get("DCC_SIGNAL", signal.SIGABRT))
    explanation = ""
    if signal_number != signal.SIGABRT:
        explanation = explain_signal(signal_number)
    elif "DCC_ASAN_ERROR" in os.environ:
        explanation = explain_asan_error(location, color)
    elif "DCC_UBSAN_ERROR_KIND" in os.environ:
        explanation, location = explain_ubsan_error(location, color)
    elif "DCC_OUTPUT_ERROR" in os.environ:
        explanation = explain_output_difference(color)
    elif os.environ.get("DCC_SANITIZER", "") == "MEMORY":
        explanation = "runtime error " + color("uninitialized variable used", "red")

    if explanation:
        # location may be improved above so we wait to here to use it
        if location and location.column:
            explanation = (
                f"{location.filename}:{location.line_number}:{location.column} "
                + explanation
            )
        elif location:
            explanation = f"{location.filename}:{location.line_number} " + explanation
        print(explanation, file=output_stream)

    variable_addresses = explain_context.get_variable_addresses(stack)
    variables = ""
    if location:
        where = explain_context.explain_location(location, variable_addresses, color)
        where = "Execution stopped in " + where
        explanation += where
        print(where, end="", file=output_stream)
        variables = explain_context.explain_relevant_variables(
            location, color, variable_addresses
        )
        if variables:
            print(color("\nValues when execution stopped:", "cyan"), file=output_stream)
            print("\n" + variables, end="", file=output_stream)

    call_stack = ""
    if len(stack) > 1:
        call_stack = explain_context.explain_stack(stack, variable_addresses, color)
        print(color("\nFunction call traceback:\n", "cyan"), file=output_stream)
        print(call_stack, file=output_stream)
    else:
        print(file=output_stream)

    if not explanation:
        explanation = os.environ.get("DCC_VALGRIND_ERROR", "")

    run_runtime_helper(location, explanation, variables, call_stack, output_stream)

    output_stream.flush()
    gdb_interface.gdb_flush()


# explain UndefinedBehaviorSanitizer error
# documentation: https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html
# source: https://code.woboq.org/gcc/libsanitizer/ubsan/ubsan_handlers.cc.html
#
# There is plenty of room here to provide more specific explanation
# which would be more helpful to novice programmers


def explain_ubsan_error(loc, color):
    # kind = os.environ.get('DCC_UBSAN_ERROR_KIND', '')
    message = os.environ.get("DCC_UBSAN_ERROR_MESSAGE", "")
    filename = os.environ.get("DCC_UBSAN_ERROR_FILENAME", "")
    try:
        line_number = int(os.environ.get("DCC_UBSAN_ERROR_LINE", 0))
    except ValueError:
        line_number = 0
    try:
        column = int(os.environ.get("DCC_UBSAN_ERROR_COL", 0))
    except ValueError:
        column = 0
    # memoryaddr = os.environ.get('DCC_UBSAN_ERROR_MEMORYADDR', '')

    if loc:
        if filename and line_number:
            loc.filename = filename
            loc.line_number = line_number
    else:
        loc = util.Location(filename, line_number)
    if column:
        loc.column = column

    source = ""
    if loc:
        source = util.clean_c_source(loc.source_line())

    dprint(3, "source", source)
    explanation = None

    if message:
        message = message[0].lower() + message[1:]

    m = re.search("(load|store|applying).*(0xbebebebe|null pointer)", message.lower())
    if m:
        access = "accessing" if m.group(1) in ["load", "applying"] else "assigning to"
        problem = "uninitialized" if m.group(2).startswith("0xbe") else "NULL"

        if "*" in source and "[" not in source:
            what = "*p"
        elif "*" not in source and "[" in source:
            what = "p[index]"
        else:
            what = "*p or p[index]"

        message = f"{access} a value via a {problem} pointer"
        explanation = "You are using a pointer which "

        if problem == "uninitialized":
            explanation += "has not been initialized\n"
            explanation += f"  A common error is {access} {what} without first assigning a value to p.\n"
        else:
            explanation += "is NULL\n"
            explanation += f"  A common error is {access} {what} when p == NULL.\n"

    if not explanation:
        m = re.search("member access.*(0xbebebebe|null pointer)", message.lower())
        if m:
            if m.group(1).startswith("0xbe"):
                message = "accessing a field via an uninitialized pointer"
                explanation = """You are using a pointer which has not been initialized
  A common error is using p->field without first assigning a value to p.\n"""
            else:
                message = "accessing a field via a NULL pointer"
                explanation = """You are using a pointer which is NULL
  A common error is  using p->field when p == NULL.\n"""

    if not explanation and "division by zero" in message:
        if "/" in source and "%" not in source:
            what = "x / y"
        elif "/" not in source and "%" in source:
            what = "x % y"
        else:
            what = "x / y or x % y"
        explanation = (
            f"A common error is to evaluate {what} when y == 0 which is undefined.\n"
        )

    if not explanation:
        for value in [
            "-1094795586",
            "-1.8325506472120096e-06",
            "-0.372548997",
            "0xbe",
        ]:
            if value in message:
                explanation = f"""Your program looks to be using an uninitialized value.
  {color(value, "red")} is probably actually an uninitialized value.\n"""
            break

    # FIXME make this more specific
    if not explanation and ("overflow" in message or "underflow" in message):
        if "-10947955" in message:
            explanation = """Arithmetic on an an uninitialized value has produced a value that can not be represented.\n"""
        else:
            explanation = """There are limits in the range of values that can be represented in all types.
  Your program has produced a value outside that range.\n"""

    if not explanation and re.search(r"index .* out of bounds .*\[0\]", message):
        explanation = "You have created a array of size 0 which is illegal.\n"

    if not explanation:
        m = re.search(r"index (-?\d+) out of bounds .*\[(\d+)\]", message)
        if m:
            index = color(m.group(1), "red")
            size = color(m.group(2), "red")
            index_range = (
                f'{color("0", "red")}..{color(str(int(m.group(2)) - 1), "red")}'
            )
            explanation = f"""You are using an illegal array index: {index}
  Valid indices for an array of size {size} are {index_range}\n"""

    if not explanation:
        m = re.search(r"index (-?\d+) out of bounds", message)
        if m:
            index = color(m.group(1), "red")
            explanation = f"You are using an illegal array index: {index}\n"

    if not explanation and "out of bounds" in message:
        explanation = "You are using an illegal array index."

    if explanation and "out of bounds" in message:
        explanation += """  Make sure the size of your array is correct.
  Make sure your array indices are correct.\n"""

    if not message:
        message = "undefined operation"

    report = "runtime error - " + color(message, "red")
    if explanation:
        report += "\n"
        report += color("dcc explanation: ", "cyan")
        report += explanation
    return report, loc


def explain_asan_error(loc, color):
    asan_error = os.environ.get("DCC_ASAN_ERROR")
    if asan_error:
        asan_error = asan_error.replace("-", " ")
        asan_error = asan_error.replace("heap", "malloc")
        asan_error = asan_error.replace("null deref", "NULL pointer dereferenced")
    else:
        asan_error = "illegal array, pointer or other operation"
    report = "runtime error - " + color(asan_error, "red")
    for substring, explanation in ASAN_EXPLANATIONS:
        if substring in report.lower():
            report += "\n"
            report += color("dcc explanation: ", "cyan")
            report += explanation
            break
    return report


ASAN_EXPLANATIONS = [
    (
        "malloc buffer overflow",
        f"""access past the end of malloc'ed memory.
  Make sure you have allocated enough memory for the size of your struct/array.
  A common error is to use the size of a pointer instead of the size of the struct or array.

  For more information see: {util.explanation_url("malloc_sizeof")}
""",
    ),
    (
        "stack buffer overflow",
        """access past the end of a local variable.
  Make sure the size of your array is correct.
  Make sure your array indices are correct.""",
    ),
    (
        "use after return",
        f"""You have used a pointer to a local variable that no longer exists.
  When a function returns its local variables are destroyed.

  For more information see: {util.explanation_url("stack_use_after_return")}""",
    ),
    ("use after", """access to memory that has already been freed."""),
    ("double free", """attempt to free memory that has already been freed."""),
    ("null", """attempt to access value using a pointer which is NULL."""),
]


def explain_signal(signal_number):
    if signal_number == signal.SIGINT:
        return "Execution was interrupted"
    elif signal_number == signal.SIGFPE:
        return "Execution stopped by an arithmetic error.\nOften this is caused by division (or %) by zero."
    elif signal_number == signal.SIGXCPU:
        return "Execution stopped by a CPU time limit."
    elif signal_number == signal.SIGXFSZ:
        return "Execution stopped because too much data written."
    elif signal_number == signal.SIGSEGV:
        return "Execution stopped because of an invalid pointer or string."
    else:
        return f"Execution terminated by signal {signal_number}"


def run_runtime_helper(loc, explanation, variables, call_stack, output_stream):
    color = lambda text, _: text
    helper = os.environ.get("DCC_RUNTIME_HELPER", "")
    if not helper:
        helper = util.search_path(
            RUNTIME_HELPER_BASENAME, cwd=os.environ.get("DCC_PWD", ".")
        )
    if not helper:
        return

    explanation = colors.strip_color(explanation)
    call_stack = colors.strip_color(call_stack)
    variables = colors.strip_color(variables)

    source = ""
    try:
        if os.path.getsize(loc.filename) < util.MAX_FILE_SIZE_PASSED_TO_HELPER:
            with open(loc.filename) as f:
                source = f.read(util.MAX_FILE_SIZE_PASSED_TO_HELPER)
    except OSError:
        pass

    if not source:
        source = "".join(
            loc.surrounding_source(color, radius=10, clean=False, markMiddle=False)
        )

    helper_info = {
        "file": loc.filename if loc else "",
        "line": str(loc.line_number) if loc else "",
        "col": str(loc.column) if loc else "",
        "explanation": explanation,
        "source": source,
        "call_stack": call_stack,
        "variables": variables,
    }

    # needed?
    #    signal_number = int(os.environ.get("DCC_SIGNAL", signal.SIGABRT))
    #    if signal_number != signal.SIGABRT:
    #        helper_info["signal"] = signal.Signals(signal_number).name

    dprint(2, f"run_helper helper='{helper}' info='{helper_info}'")
    for k, v in helper_info.items():
        os.environ["HELPER_" + k.upper()] = v
    os.environ["HELPER_JSON"] = json.dumps(helper_info, separators=(",", ":"))

    dprint(2, f"running {helper}")
    try:
        subprocess.run([helper], stdout=output_stream, stderr=output_stream)
    except OSError as e:
        dprint(1, e)


def gdb_set_frame():
    try:
        stack = gdb_interface.gdb_execute("where")
        dprint(3, "\nStack:\n", stack, "\n")
        stack_lines = stack.splitlines()
        reversed_stack_lines = reversed(stack_lines)
        frames = []
        for line in stack_lines:
            frame = parse_gdb_stack_frame(line)
            if frame is not None and os.path.exists(frame.filename):
                frames.append(frame)
        if not frames:
            # FIXME - does this code make sense?
            frame = None
            for line in reversed_stack_lines:
                frame = parse_gdb_stack_frame(line) or frame
            if frame is not None:
                frames = [frame]
        if frames:
            gdb_interface.gdb_execute(f"frame {frames[0].frame_number}")
        else:
            dprint(3, "gdb_set_frame no frame number")
        return frames
    except Exception:
        if util.get_debug_level():
            traceback.print_exc(file=sys.stderr)
        return None


def parse_gdb_stack_frame(line):
    # note don't match function names starting with _ these are not user functions
    line = re.sub("__real_main", "main", line)
    m = re.match(
        r"^\s*#(?P<frame_number>\d+)\s+(0x[0-9a-f]+\s+in+\s+)?"
        r"(?P<function>[a-zA-Z][^\s\(]*).*\((?P<params>.*)\)\s+at\s+"
        r"(?P<filename>[^\s:]+):(?P<line_number>\d+)\s*$",
        line,
    )
    dprint(3, "parse_gdb_stack_frame", m is not None, line)
    if m:
        filename = m.group("filename")
        if (
            filename.startswith("/usr/")
            or filename.startswith("../sysdeps/")
            or filename.endswith("libioP.h")
            or filename.endswith("iofclose.c")
            or filename.startswith("<")
            or filename.startswith("m_scheduler/scheduler")
            or filename.startswith("m_syswrap/sys")
        ):
            m = None
        dprint(3, f"parse_gdb_stack_frame filename='{filename}' m={m}")
    if m:
        return util.Location(
            m.group("filename"),
            m.group("line_number"),
            function=m.group("function"),
            params=m.group("params"),
            frame_number=m.group("frame_number"),
        )
    return None
