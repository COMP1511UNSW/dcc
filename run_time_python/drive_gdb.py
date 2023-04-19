import collections, json, os, platform, re, sys, signal, subprocess, traceback
import colors
from explain_output_difference import explain_output_difference
import util

RUNTIME_HELPER_BASENAME = "dcc-runtime-helper"

#
# Code below is executed from gdb.
# It prints details of the program state likely to be of interest to
# a beginner programmer
#


hash_define = collections.defaultdict(dict)
source = {}
debug_level = 0
debug_stream = sys.stderr

# workaround - avoid warning message from analysers
if 0:
    gdb = None


def drive_gdb():
    output_stream = os.fdopen(3, "w", encoding="utf-8", errors="replace")
    global debug_level
    global debug_stream
    debug_level = int(os.environ.get("DCC_DEBUG", "0"))
    if debug_level:
        debug_stream = output_stream
        dprint(2, "drive_gdb()")
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
        gdb_attach()
        pid = os.environ.get("DCC_PID", "")
        sanitizer2_pid = os.environ.get("DCC_SANITIZER2_PID", "")
        sanitizer1_pid = os.environ.get("DCC_SANITIZER1_PID", "")
        if pid and sanitizer2_pid and sanitizer1_pid:
            if pid == sanitizer2_pid:
                os.kill(int(sanitizer1_pid), signal.SIGUSR1)
        explain_error(output_stream, color)
    except gdb.error as e:
        if "ptrace" in str(e).lower() and os.path.exists("/.dockerenv"):
            print(
                "\ndcc : can not provide information about variables because docker not run with --cap-add=SYS_PTRACE\n",
                file=output_stream,
            )
        elif debug_level:
            traceback.print_exc(file=output_stream)
        sys.exit(1)
    except Exception:
        if debug_level:
            traceback.print_exc(file=output_stream)
        sys.exit(1)

    output_stream.flush()
    # __dcc_error_exit hangs for unknown reason on WSL
    if not windows_subsystem_for_linux:
        gdb_execute("call (void)__dcc_error_exit()")
    # 	kill_all()
    gdb_execute("quit")


def gdb_attach():
    pid = int(os.environ.get("DCC_PID"))
    if "DCC_VALGRIND_ERROR" in os.environ:
        dprint(2, "attaching gdb to valgrind", pid)
        gdb.execute(f"target remote | vgdb --pid={pid}")
    else:
        dprint(2, "attaching gdb to ", pid)
        gdb.execute(f"attach {pid}")
    dprint(3, "gdb_attach() returning")


def explain_error(output_stream, color):
    dprint(2, "explain_error() in drive_gdb.py starting")
    # file descriptor 3 is a dup of stderr (see below)
    # stdout & stderr have been diverted to /dev/null
    print(file=output_stream)
    stack = gdb_set_frame()
    loc = stack[0] if stack else None
    signal_number = int(os.environ.get("DCC_SIGNAL", signal.SIGABRT))
    explanation = ""
    if signal_number != signal.SIGABRT:
        explanation = explain_signal(signal_number)
    elif "DCC_ASAN_ERROR" in os.environ:
        explanation = explain_asan_error(loc, color)
    elif "DCC_UBSAN_ERROR_KIND" in os.environ:
        explanation, loc = explain_ubsan_error(loc, color)
    elif "DCC_OUTPUT_ERROR" in os.environ:
        explanation = explain_output_difference(color)
    elif os.environ.get("DCC_SANITIZER", "") == "MEMORY":
        explanation = "runtime error " + color("uninitialized variable used", "red")

    if explanation:
        # loc may be improved above so we wait to here to use it
        if loc and loc.column:
            explanation = (
                f"{loc.filename}:{loc.line_number}:{loc.column} " + explanation
            )
        elif loc:
            explanation = f"{loc.filename}:{loc.line_number} " + explanation
        print(explanation, file=output_stream)

    if loc:
        print(explain_location(loc, color), end="", file=output_stream)
        print(
            relevant_variables(loc.surrounding_source(color, clean=True), color),
            end="",
            file=output_stream,
        )

    if len(stack) > 1:
        print(color("\nFunction Call Traceback", "cyan"), file=output_stream)
        for frame, caller in zip(stack, stack[1:]):
            print(
                frame.function_call(color),
                "called at line",
                color(caller.line_number, "red"),
                "of",
                color(caller.filename, "red"),
                file=output_stream,
            )
        print(stack[-1].function_call(color), file=output_stream)

    if not explanation:
        explanation = os.environ.get("DCC_VALGRIND_ERROR", "")

    run_runtime_helper(loc, explanation, stack, output_stream)

    output_stream.flush()
    gdb.flush(gdb.STDOUT)
    gdb.flush(gdb.STDERR)


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
        loc = Location(filename, line_number)
    if column:
        loc.column = column

    source = ""
    if loc:
        source = clean_c_source(loc.source_line())

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

    # FIXME make this more specific
    if not explanation and ("overflow" in message or "underflow" in message):
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
  Valid indices for an array of size {size} are {index_range}
"""

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
        report += color("dcc explanation:", "cyan")
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
    else:
        return f"Execution terminated by signal {signal_number}"


def run_runtime_helper(loc, explanation, stack, output_stream):
    color = lambda text, color_name: text
    helper = os.environ.get("DCC_RUNTIME_HELPER", "")
    if not helper:
        helper = util.search_path(
            RUNTIME_HELPER_BASENAME, cwd=os.environ.get("DCC_PWD", ".")
        )
    if not helper:
        return

    explanation = colors.strip_color(explanation)

    source = "".join(loc.surrounding_source(color))

    call_stack = ""
    if len(stack) > 1:
        for frame, caller in zip(stack, stack[1:]):
            call_stack += f"{frame.function_call(color)} called at line {caller.line_number} of{caller.filename}\n"
        call_stack += stack[-1].function_call(color) + "\n"

    variables = relevant_variables(
        loc.surrounding_source(color, clean=True), color, include_title=False
    )

    helper_info = {
        "filename": loc.filename if loc else "",
        "line_number": str(loc.line_number) if loc else "",
        "column": str(loc.column) if loc else "",
        "explanation": explanation,
        "source": source,
        "call_stack": call_stack,
        "variables": variables,
    }

    dprint(2, f"run_helper helper='{helper}' info='{helper_info}'")
    for k, v in helper_info.items():
        os.environ["DCC_HELPER_" + k.upper()] = v
    os.environ["DCC_HELPER_JSON"] = json.dumps(helper_info, separators=(",", ":"))

    dprint(2, f"running {helper}")
    try:
        subprocess.run([helper], stdout=output_stream, stderr=output_stream)
    except OSError as e:
        dprint(1, e)


class Location:
    def __init__(
        self,
        filename,
        line_number,
        column="",
        function="",
        params="",
        variable="",
        frame_number="",
    ):
        self.filename = filename
        self.line_number = int(line_number)
        self.column = column
        self.function = function
        self.params = params
        self.variable = variable
        self.frame_number = frame_number

    def __str__(self):
        return f"Location({self.filename},{self.line_number},column={self.column},function={self.function},params={self.params},variable={self.variable})"

    def function_call(self, color):
        params = clarify_values(self.params, color)
        if self.function == "main" and params.startswith("argc=1,"):
            params = ""
        return self.function + "(" + params + ")"

    def location(self, color):
        return (
            color(self.filename, "red")
            + " at "
            + color("line " + str(self.line_number), "red")
        )

    def short_description(self, color):
        return self.function_call(color) + " in " + self.location(color)

    def long_description(self, color):
        where = "in " + self.short_description(color)
        source_lines = self.surrounding_source(color, markMiddle=True)
        source = "".join(source_lines).rstrip("\n") + "\n"
        if source:
            where += ":\n\n" + source
        return where

    def source_line(self):
        return fileline(self.filename, self.line_number)

    def surrounding_source(self, color, radius=2, clean=False, markMiddle=False):
        lines = []
        marked_line = None
        for offset in range(-3 * radius, 2 * radius):
            line = fileline(self.filename, self.line_number + offset)

            if re.match(r"^\S", line) and offset < 0:
                lines = []

            if markMiddle and offset == 0 and line:
                marked_line = line
                line = color(re.sub(r"^ {0,3}", "-->", line), "red")

            lines.append(clean_c_source(line) if clean else line)

            if re.match(r"^\S", line) and offset > 0:
                break

        while lines and re.match(r"^[\s}]*$", lines[0]):
            lines.pop(0)

        while lines and re.match(r"^[\s{]*$", lines[-1]):
            lines.pop()

        if len(lines) == 1 and not marked_line:
            return ""

        return lines

    def is_user_location(self):
        if not re.match(r"^[a-zA-Z]", self.function):
            return False
        if re.match(r"^/(usr|build)/", self.filename):
            return False
        if re.match(r"^\?", self.filename):
            return False
        return True


def fileline(filename, line_number):
    line_number = int(line_number)
    try:
        if filename in source:
            return source[filename][line_number - 1]
        with open(filename, encoding="utf-8", errors="replace") as f:
            source[filename] = f.readlines()
            for line in source[filename]:
                m = re.match(r"^\s*#\s*define\s*(\w+)\s*(.*\S)", line)
                if m:
                    hash_define[filename][m.group(1)] = (line.rstrip(), m.group(2))
        return source[filename][line_number - 1].rstrip() + "\n"
    except IOError:
        dprint(2, f"fileline error can not open: {filename}")
    except IndexError:
        dprint(2, f"fileline error can not find {line_number} in {filename}")
    return ""


# remove comments and truncate strings & character constants to zero-length
def clean_c_source(c_source, leave_white_space=False):
    c_source = re.sub("\\[\"']", "", c_source)
    c_source = re.sub(r'".*?"', "", c_source)
    c_source = re.sub(r"'.*?'", "", c_source)
    c_source = re.sub(r"/[/\*].*", "", c_source)
    if leave_white_space:
        return c_source
    return c_source.strip() + "\n"


def gdb_evaluate(expression):
    dprint(
        3,
        "gdb_evaluate:",
        expression,
    )
    value = gdb_execute(f"print {expression}")
    value = re.sub(r"^[^=]*=\s*", "", value).strip()
    dprint(
        3,
        "->",
        value,
    )
    return value.strip()


def gdb_execute(command):
    dprint(3, "gdb.execute:", command)
    try:
        s = gdb.execute(command, to_string=True)
    except gdb.error as e:
        dprint(3, "gdb.execute", e)
        s = ""
    dprint(3, "gdb.execute:", "->", s)
    return s


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
        return Location(
            m.group("filename"),
            m.group("line_number"),
            function=m.group("function"),
            params=m.group("params"),
            frame_number=m.group("frame_number"),
        )
    return None


def gdb_set_frame():
    try:
        stack = gdb_execute("where")
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
            gdb_execute(f"frame {frames[0].frame_number}")
        else:
            dprint(3, "gdb_set_frame no frame number")
        return frames
    except Exception:
        if debug_level:
            traceback.print_exc(file=sys.stderr)
        return None


def relevant_variables(c_source_lines, color, include_title=True):
    expressions = []
    for line in c_source_lines:
        expressions += extract_expressions(line)

    # avoid trying to evaluate types/keywords for efficiency/clarity
    done = set(
        [
            "NULL",
            "char",
            "int",
            "double",
            "while",
            "if",
            "else",
            "for",
            "while",
            "return",
            "main",
            "stdin",
            "stdout",
            "stderr",
        ]
    )

    explanation = ""
    dprint(3, "relevant_variables expressions=", c_source_lines, expressions)
    for expression in sorted(
        expressions, key=lambda e: (len(re.findall(r"\w+", e)), e)
    ):
        try:
            expression = expression.strip()
            if expression not in done:
                done.add(expression)
                expression_value = evaluate_expression(expression, color)
                if expression_value is not None:
                    explanation += f"{expression} = {expression_value}\n"
        except RuntimeError as e:
            dprint(2, "print_variables_expressions: RuntimeError", e)
    if explanation and include_title:
        prefix = color("\nValues when execution stopped:", "cyan")
        explanation = prefix + "\n\n" + explanation
    return explanation


def evaluate_expression(expression, color):
    dprint(3, "evaluate_expression:", expression)
    if re.match(r"^-?\s*[\d\.]+$", expression):
        return None  # don't print(numbers)
    if re.search(r"[a-zA-Z0-9_]\s*\(", expression):
        return None  # don't evaluate function calls

    expression_type = gdb_execute(f"whatis {expression}")
    expression_type = re.sub(r"\s*type\s*=\s*", "", expression_type).strip()
    dprint(3, "expression_type=", expression_type)
    if re.search(r"\<|\)$", expression_type):
        return None

    expression_value = gdb_evaluate(expression)

    if (
        expression_value == ""
        or "_IO_FILE" in expression_value
        or "<_IO_" in expression_value
        or "here_cg_arc_record" in expression_value
        or expression_value == "<optimized out>"
    ):
        return None

    expression_value = clarify_expression_value(
        expression_value, expression_type, color
    )

    if len(expression_value) > 160:
        return None

    # don't print hexadeximal addresses
    if re.search(r"^\(.*\s+0x[0-9a-f]{4,}\s*$", expression_value):
        return None
    return expression_value


# transform value into something a novice programmer more likely to understand


def clarify_expression_value(expression_value, expression_type, color):
    dprint(3, "clarify_value expression_value=", expression_value)

    if expression_type == "char":
        m = re.match(r"^(-?\d+) '(.*)'$", expression_value)
        if m:
            ascii_value = int(m.group(1))
            if (0 < ascii_value < 9) or (13 < ascii_value < 32) or (ascii_value == 127):
                expression_value = f"{ascii_value} (non-printable ASCII character)"
            elif ascii_value < 0 or ascii_value > 128:
                expression_value = f"{ascii_value} (not valid ASCII)"
            elif ascii_value == 0:
                expression_value = "0 = '\\0'"
            else:
                expression_value = f"{m.group(1)} = '{m.group(2)}'"
    return clarify_values(expression_value, color)


# transform value into something a novice programmer more likely to understand
def clarify_values(values, color):
    # novices will understand 0x0 better as NULL if it is a pointer
    values = re.sub(r"\b0x0\b", "NULL", values)

    # strip type cast from strings
    values = re.sub(r'^0x[0-9a-f]+\s*(<.str>)?\s*"', '"', values)

    # strip type cast from NULL pointers
    values = re.sub(r"^\([^()]+\s+\*\)\s*NULL\b", "NULL", values)

    # strip type cast from uninitialized valuess
    values = re.sub(r"^\([^()]+\s+\*\)\s*0xbebebebe(\w+)", r"0xbebebebe\1", values)

    values = re.sub(r"'\000'", r"'\\0'", values)

    warning_text = color("<uninitialized value>", "red")

    for value in [
        "-1094795586",
        "-1.8325506472120096e-06",
        "-0.372548997",
        "-66 (not valid ASCII)",
        "0xbebebebe",
        "0xbebebebebebebebe",
    ]:
        values = re.sub(
            r"(^|\D)" + re.escape(value) + r"($|\W)",
            r"\1" + warning_text + r"\2",
            values,
        )

    values = re.sub(
        r"'\\276' <repeats (\d+) times>",
        color("<\\1 uninitialized values>", "red"),
        values,
    )

    # convert "\276\276\276" ->  <3 uninitialized values>
    values = re.sub(
        r'"((\\276)+)"',
        lambda m: color(f"<{len(m.group(1)) // 4} uninitialized values>", "red"),
        values,
    )

    # make display of arrays more concise
    if values and values[0] == "{" and len(values) > 128:
        values = re.sub(r"\{(.{100}.*?),.*\}", r"{\1, ...}", values)

    return values


def balance_bracket(s, depth=0):
    # 	 dprint(2, 'balance_bracket(%s, %s)' % (s, depth))
    if not s:
        return ""
    elif s[0] == "]" or s[0] == ")":
        depth -= 1
    elif s[0] == "[" or s[0] == "(":
        depth += 1
    if depth < 0 and (len(s) == 1 or s[1] != "["):
        return ""
    return s[0] + balance_bracket(s[1:], depth)


# FIXME - this is very crude
def extract_expressions(c_source):
    c_source = c_source.strip()
    if not c_source:
        return []
    dprint(3, "extract_expressions c_source=", c_source)

    # match declaration
    m = re.match(
        r"([a-z][a-zA-Z0-9_]*|FILE)\s+\**\s*[a-z][a-zA-Z0-9_]*\s*\[(.*)",
        c_source,
        re.DOTALL,
    )
    if m:
        return extract_expressions(m.group(1))

    m = re.match(r"([a-z][a-zA-Z0-9_]*)\s*\[(.*)", c_source, re.DOTALL)
    if m:
        expressions = []
        index = balance_bracket(m.group(2))
        if index:
            expressions = [m.group(1), index, m.group(1) + "[" + index + "]"]
        return expressions + extract_expressions(m.group(2))

    m = re.match(
        r"[a-z][a-zA-Z0-9_]*(?:\s*->\s*[a-z][a-zA-Z0-9_]*)+(.*)", c_source, re.DOTALL
    )
    if m:
        remainder = m.group(1)
        expressions = []
        for i in range(0, 8):
            m = re.match(
                rf"^[a-z][a-zA-Z0-9_]*(?:\s*->\s*[a-z][a-zA-Z0-9_]*){{{i}}}",
                c_source,
                re.DOTALL,
            )
            if m:
                expressions.append(m.group(0))
            else:
                break

        dprint(3, "extract_expressions expressions=", list(expressions))
        return expressions + extract_expressions(remainder)

    m = re.match(r"([a-zA-Z][a-zA-Z0-9_]*)(.*)", c_source, re.DOTALL)
    if m:
        return [m.group(1)] + extract_expressions(m.group(2))

    m = re.match(r"^[^a-zA-Z]+(.*)", c_source, re.DOTALL)
    if m:
        return extract_expressions(m.group(1))

    return []


def explain_location(loc, color):
    if not isinstance(loc, Location):
        return f"Execution stopped at '{loc}'"
    else:
        return "Execution stopped " + loc.long_description(color)


def dprint(level, *args, **kwargs):
    if debug_level >= level:
        kwargs["file"] = debug_stream
        print(*args, **kwargs)


if __name__ == "__main__":
    drive_gdb()
