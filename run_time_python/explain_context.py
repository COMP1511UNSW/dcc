import re
import gdb_interface
from util import dprint


def explain_location(location, variable_addresses, color):
    where = explain_function_call(
        location.function, location.params, variable_addresses, color
    )
    where += " in "
    where += color(location.filename, style="bold")
    where += " at "
    where += color(f"line {location.line_number}", style="bold")
    source_lines = location.surrounding_source(color, markMiddle=True)
    source = "".join(source_lines).rstrip("\n") + "\n"
    if source:
        where += ":\n\n" + source
    return where


def explain_stack(stack, variable_addresses, color):
    call_stack = ""
    for frame, caller in zip(stack, stack[1:] + [None]):
        call = explain_function_call(
            frame.function, frame.params, variable_addresses, color
        )
        if caller:
            call += " called at "
            call += color("line " + str(caller.line_number), style="bold")
            call += " of "
            call += color(caller.filename, style="bold")
        call_stack += call + "\n"
    return call_stack


def explain_function_call(function, params, variable_addresses, color):
    if function == "main" and params.startswith("argc=1,"):
        params = ""
    param_list = []
    for p in params.split(", "):
        if m := re.search(r"^(\w+)=(.*)", p):
            variable, value = m.groups()
            # should we check variable type here?
            value = convert_variable_address(value, variable_addresses, color)
            value = clarify_values(value, color, variable_addresses)
            p = f"{variable}={value}"
        param_list.append(p)
    params = ", ".join(param_list)
    return f"{color(function, style='italic')}({params})"


def explain_relevant_variables(location, color, variable_addresses):
    source = location.surrounding_source(color=lambda text, _: text, clean=True)
    return relevant_variables(source, color, variable_addresses)


KEYWORDS = set(
    "NULL char double else enum for if int main return stderr stdin stdout struct void while".split()
)


def relevant_variables(c_source_lines, color, variable_addresses):
    expressions = []
    for line in c_source_lines:
        expressions += extract_expressions(line)

    # avoid trying to evaluate types/keywords for efficiency/clarity
    done = KEYWORDS
    explanation = ""
    dprint(3, "relevant_variables expressions=", c_source_lines, expressions)
    for expression in sorted(
        expressions, key=lambda e: (len(re.findall(r"\w+", e)), e)
    ):
        try:
            expression = expression.strip()
            if expression not in done:
                done.add(expression)
                expression_value = evaluate_expression(
                    expression, color, variable_addresses
                )
                if expression_value is not None:
                    explanation += f"{expression} = {expression_value}\n"
        except RuntimeError as e:
            dprint(2, "print_variables_expressions: RuntimeError", e)
    return explanation


def evaluate_expression(expression, color, variable_addresses):
    dprint(3, "evaluate_expression:", expression)
    if re.match(r"^-?\s*[\d\.]+$", expression):
        return None  # don't print(numbers)
    if re.search(r"[a-zA-Z0-9_]\s*\(", expression):
        return None  # don't evaluate function calls

    expression_type = gdb_interface.gdb_execute(f"whatis {expression}")
    expression_type = re.sub(r"\s*type\s*=\s*", "", expression_type).strip()
    dprint(3, "expression_type=", expression_type)
    if re.search(r"\<|\)$", expression_type):
        return None

    # stop printing of values for identifiers incorrectly extracted as variabled
    # which match random global constants and hence get evaluated by gdb
    if expression_type.startswith("const ") and not any(
        v for v in variable_addresses if v["variable"] == expression
    ):
        return None

    expression_value = gdb_interface.gdb_evaluate(expression)
    # dprint(3, 'info', expression_value, gdb_interface.gdb_execute(f"info symbol {expression_value.split(' ')[-1]}"))

    if (
        expression_value == ""
        or expression_value == expression
        or "_IO_FILE" in expression_value
        or "<_IO_" in expression_value
        or "here_cg_arc_record" in expression_value
        or expression_value == "<optimized out>"
    ):
        return None

    expression_value = clarify_expression_value(
        expression_value, expression_type, color, variable_addresses
    )

    # don't print raw pointers e.g from malloc
    if expression_type[-1] == "*" and re.search(r"^0x[0-9a-f]{8,}$", expression_value):
        return None

    if re.search(r"^\w+$", expression) and re.search(
        rf"^&{expression}\b", expression_value
    ):
        return None

    if len(expression_value) > 512:
        return None

    return expression_value


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

    # match declaration of array (with false positives)
    # if declaration is e.g int f[2]; do not want to add f[2] as expression
    # printing its value would confuse novice
    m = re.match(
        r"([a-z][a-zA-Z0-9_]*|FILE)\s+\**\s*([a-z][a-zA-Z0-9_]*)\s*\[(.*)",
        c_source,
        re.DOTALL,
    )
    if m:
        return extract_expressions(m.group(1)) + extract_expressions(m.group(2))

    # avoid enum or struct name matching random global value that gdb knows about
    c_source = re.sub(r"(enum|struct|union)\s+[a-zA-Z][a-zA-Z0-9_]*\s*", "", c_source)

    m = re.match(r"([a-z][a-zA-Z0-9_]*)\s*\[(.*)", c_source, re.DOTALL)
    if m:
        expressions = []
        index = balance_bracket(m.group(2))
        if index:
            expressions = [m.group(1), index, m.group(1) + "[" + index + "]"]
        return expressions + extract_expressions(m.group(2))

    m = re.match(
        r"[a-z][a-zA-Z0-9_]*(?:\s*(?:->|\.)\s*[a-z][a-zA-Z0-9_]*)+(.*)",
        c_source,
        re.DOTALL,
    )
    if m:
        remainder = m.group(1)
        expressions = []
        for i in range(0, 8):
            m = re.match(
                rf"^[a-z][a-zA-Z0-9_]*(?:\s*(?:->|\.)\s*[a-z][a-zA-Z0-9_]*){{{i}}}",
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


def get_variable_addresses(stack):
    if not stack:
        return []
    addresses = []
    get_variables("", addresses)
    #    only in recent gdb
    #    current_level = gdb_interface.gdb_get_frame()
    current_level = stack[0].frame_number
    for frame in stack[1:]:
        gdb_interface.gdb_set_frame(frame.frame_number)
        get_variables(frame.function, addresses)
    gdb_interface.gdb_set_frame(current_level)
    return addresses


def get_variables(function, addresses):
    for line in gdb_interface.gdb_execute("info locals").splitlines():
        if a := get_variable_address(line, function):
            addresses.append(a)
    for line in gdb_interface.gdb_execute("info args").splitlines():
        if a := get_variable_address(line, function):
            dprint(2, line.strip(), a)
            addresses.append(a)


def get_variable_address(line, function):
    if "=" not in line:
        return None
    variable, value = line.strip().split("=", maxsplit=1)
    variable = variable.strip()
    value = value.strip()
    variable_type = gdb_interface.gdb_execute(f"whatis {variable}")
    variable_type = variable_type.split("=", maxsplit=1)[1].strip()
    address = gdb_interface.gdb_evaluate("&" + variable)
    address = re.sub(r"^\(.*\)\s*", "", address)
    if not address.startswith("0x"):
        return None
    address = int(address, 16)
    va = {
        "function": function,
        "variable": variable,
        "type": variable_type,
        "address_start": address,
    }
    m = re.search(r"\[(\d+)\]$", variable_type)
    if m and "(*)" not in variable_type:
        va["n_elements"] = int(m.group(1))
        va["sizeof_element"] = int(gdb_interface.gdb_evaluate(f"sizeof {variable}[0]"))
        va["address_finish"] = address + va["n_elements"] * va["sizeof_element"]
    else:
        va["address_finish"] = address
    return va


def convert_variable_address(expression_value, variable_addresses, color):
    dprint(4, "convert_variable_address", expression_value)
    m = re.match(r"(\(.*\))?\s*(0x[0-9a-f]+)", expression_value)
    if not m:
        return expression_value
    address = int(m.group(2), 16)

    for va in variable_addresses:
        if va["address_start"] <= address <= va["address_finish"]:
            suffix = ""
            #            if va["function"]:
            #                suffix = f" // in {va['function']}()"
            prefix = ""
            if va["function"]:
                prefix = color(f"{va['function']}:", style="italic")
            if "n_elements" in va:
                index = (address - va["address_start"]) // va["sizeof_element"]
                return f"{prefix}&{va['variable']}[{index}]{suffix}"
            else:
                return f"{prefix}&{va['variable']}{suffix}"

    return expression_value


def clarify_expression_value(
    expression_value, expression_type, color, variable_addresses
):
    """transform value into something a novice programmer more likely to understand"""
    dprint(
        3,
        f"clarify_value({expression_value}, {expression_type})",
    )

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
    return clarify_values(expression_value, color, variable_addresses)


def clarify_values(values, color, variable_addresses):
    # novices will understand 0x0 better as NULL if it is a pointer
    values = re.sub(r"\b0x0\b", "NULL", values)

    # strip type cast from strings
    values = re.sub(r'^0x[0-9a-f]+\s*(<.str>)?\s*"', '"', values)

    # strip type cast
    values = re.sub(r"^\(.*\) ", "", values)

    values = re.sub(r"'\000'", r"'\\0'", values)

    for value in [
        "-1094795586",
        "-1.8325506472120096e-06",
        "-0.372548997",
        "-66 (not valid ASCII)",
        "(unknown: 0xbebebebe)",
        "0xbebebebe",
        "3200171710",
        "0xbebebebebebebebe",
        "13744632839234567870",
    ]:
        values = re.sub(
            r"(^|\D)" + re.escape(value) + r"($|\W)",
            r"\1" + "<uninitialized value>" + r"\2",
            values,
        )

    values = re.sub(
        r"'\\276' <repeats (\d+) times>", r"<\1 uninitialized values>", values
    )

    values = values.replace(
        "<uninitialized value> <error: Cannot access memory at address <uninitialized value>>",
        "<uninitialized value>",
    )

    values = re.sub(
        r"\{\w+ = <uninitialized value>(, \w+ = <uninitialized value>)*\}",
        "{<uninitialized values>}",
        values,
    )
    # convert "\276\276\276" ->  <3 uninitialized values>
    values = re.sub(
        r"((\\276)+)",
        lambda m: f"<{len(m.group(1)) // 4} uninitialized values>",
        values,
    )
    values = values.replace("<1 uninitialized values>", "<uninitialized value>")

    values = re.sub(
        r"(<\d*\s*uninitialized values?>)", lambda m: color(m.group(1), "red"), values
    )

    # make display of arrays more concise
    if values and values[0] == "{" and len(values) > 128:
        values = re.sub(r"\{([^=]{100}.*?),.*\}", r"{\1, ...}", values)

    values = re.sub(
        r"\b0x[0-9a-f]{8,}\b",
        lambda m: convert_variable_address(m.group(0), variable_addresses, color),
        values,
    )

    return values
