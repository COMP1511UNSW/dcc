import os, re
from util import explanation_url

# Expected output has been supplied as an environment variable
# and the program has been stoped because the output was incorrect


def explain_output_difference(loc, output_stream, color):
    # autotest may try to print all errors in red, so disable this
    print(color("", "black"), end="", file=output_stream)
    explain_output_difference1(loc, output_stream, color)
    print(file=output_stream)


def explain_output_difference1(loc, output_stream, color):

    # values supplied for expected output for this execution
    expected_stdout = os.environb.get(b"DCC_EXPECTED_STDOUT", "")
    # 	ignore_case = getenv_boolean('DCC_IGNORE_CASE')
    # 	ignore_empty_lines = getenv_boolean('DCC_IGNORE_EMPTY_LINES')
    ignore_trailing_white_space = getenv_boolean(
        "DCC_IGNORE_TRAILING_WHITE_SPACE", default=True
    )
    # 	compare_only_characters = os.environ.get('DCC_COMPARE_ONLY_CHARACTERS')

    # value describing discrepency between actual and expected output
    reason = os.environ.get("DCC_OUTPUT_ERROR", "")
    line_number = getenv_int("DCC_ACTUAL_LINE_NUMBER")

    # these values do not include current line
    n_expected_bytes_seen = getenv_int("DCC_N_EXPECTED_BYTES_SEEN")
    n_actual_bytes_seen = getenv_int("DCC_N_ACTUAL_BYTES_SEEN")

    expected_line = os.environb.get(b"DCC_EXPECTED_LINE", "")
    actual_line = os.environb.get(b"DCC_ACTUAL_LINE", "")
    expected_column = getenv_int("DCC_EXPECTED_COLUMN")
    actual_column = getenv_int("DCC_ACTUAL_COLUMN")

    if 0 <= actual_column < len(actual_line):
        actual_char = actual_line[actual_column]
    else:
        actual_char = None

    if ignore_trailing_white_space and expected_stdout[-1:] == b"\n":
        expected_stdout = expected_stdout.rstrip() + b"\n"

    n_expected_lines = len(expected_stdout.splitlines())
    is_last_expected_line = n_expected_bytes_seen + len(expected_line) >= len(
        expected_stdout
    )

    if 0 <= expected_column < len(expected_line):
        expected_byte = expected_line[expected_column : expected_column + 1]
    else:
        expected_byte = None

    # 	primary = lambda text, **kwargs: color(text, style='bold', **kwargs)
    danger = lambda text, **kwargs: color(text, fg="red", style="bold", **kwargs)
    success = lambda text, **kwargs: color(text, fg="green", style="bold", **kwargs)
    # 	info = lambda text, **kwargs: color(text, fg='cyan', style='bold', **kwargs)

    if not actual_line.endswith(b"\n"):
        print("Execution failed because ", end="", file=output_stream)
    else:
        print("Execution stopped because ", end="", file=output_stream)

    if reason == "expected line too long":
        print("internal error: expected line too long", file=output_stream)
        return

    if reason == "line too long":
        print(
            "program wrote",
            danger("a line containing over " + str(actual_column) + " bytes."),
            file=output_stream,
        )
        print("Do you have an infinite loop?", file=output_stream)
        print_line(actual_line, "start of the", danger, output_stream)
        return

    if reason == "too much output":
        print("program produced", danger("too much output."), file=output_stream)
        print("Your program printed", actual_column, "bytes.")
        print("Do you have an infinite loop?", file=output_stream)
        print_line(actual_line, "last", danger, output_stream)
        return

    if reason == "zero byte":
        print("a", danger("zero byte ('\\0')"), "was printed.", file=output_stream)
        print(
            "Byte",
            actual_column,
            "of line",
            line_number,
            "of program's output was a zero byte ('\\0')",
            file=output_stream,
        )
        if len(expected_line):
            print(
                "Here are the characters on the line before the zero byte:",
                file=output_stream,
            )
            print(sanitize(actual_line), file=output_stream)
        print(
            "\nFor more information go to:",
            explanation_url("zero_byte"),
            file=output_stream,
        )
        return

    if n_actual_bytes_seen == 0 and len(actual_line) == 0:
        print("program produced", danger("no output."), file=output_stream)
        print(n_expected_lines, "lines of output were expected", file=output_stream)
        print_line(expected_line, "first expected", success, output_stream)
        return

    if len(actual_line) == 0:
        print("of", danger("missing output lines."), file=output_stream)
        print(
            "Your program printed",
            line_number,
            "lines of correct output but stopped before printing all the expected output.",
            file=output_stream,
        )
        print_line(expected_line, "next expected", success, output_stream)
        return

    if n_expected_bytes_seen == 0 and len(expected_line) == 0:
        print(
            "program produced",
            danger("output when no output was expected."),
            file=output_stream,
        )
        print_line(actual_line, "unexpected", danger, output_stream)
        return

    if len(expected_line) == 0:
        print("of", danger("unexpected extra output."), file=output_stream)
        print(
            "The program produced all the expected output and then produced extra output.",
            file=output_stream,
        )
        print_line(actual_line, "extra", danger, output_stream)
        return

    if is_last_expected_line and expected_byte == b"\n" and actual_char is None:
        print("the last", danger("newline was missing."), file=output_stream)
        print(
            "Your program produced all the expected output, except the last newline ('\\n') was missing.",
            file=output_stream,
        )
        print(
            "\nFor more information go to",
            explanation_url("missing_newline"),
            file=output_stream,
        )
        return

    show_line_length = max(len(expected_line) + 8, 80)

    bad_characters_explanation = check_bad_characters(
        actual_line, line_number, danger, expected_line
    )
    if bad_characters_explanation:
        print(bad_characters_explanation, end="", file=output_stream)
        return

    print("of an", danger("incorrect output line."), file=output_stream)
    print(
        "Byte",
        actual_column + 1,
        "of line",
        line_number,
        "of program output was incorrect.",
        file=output_stream,
    )
    if not actual_line[actual_column + 1 :]:
        if actual_line.rstrip(b"\n") + expected_byte == expected_line.rstrip(b"\n"):
            print(
                "A",
                "'" + danger(sanitize(expected_byte)) + "'",
                "was missing from the end of the output line.",
                file=output_stream,
            )
        elif actual_column > 1:
            print(
                "The characters you printed were correct, but more characters were expected.",
                file=output_stream,
            )

    print("The correct output line was:", file=output_stream)
    print(
        success(sanitize(expected_line, max_line_length_shown=show_line_length)),
        file=output_stream,
    )

    print("Your program printed this line:", file=output_stream)

    correct_prefix = success(sanitize(actual_line[0:actual_column]))
    print(correct_prefix, end="", file=output_stream)

    incorrect_byte = actual_line[actual_column : actual_column + 1]
    if incorrect_byte == " ":
        print(danger(sanitize(incorrect_byte), bg="red"), end="", file=output_stream)
    else:
        print(danger(sanitize(incorrect_byte)), end="", file=output_stream)

    print(
        sanitize(
            actual_line[actual_column + 1 :],
            max_line_length_shown=show_line_length - actual_column,
        ),
        file=output_stream,
    )


def print_line(line, description, line_color, output_stream):
    if line == b"\n":
        print(
            "The", description, "line was an empty line (a '\\n').", file=output_stream
        )
    else:
        print("The", description, "line was:", file=output_stream)
        print(line_color(sanitize(line)), file=output_stream)


def sanitize(line, max_line_length_shown=256):
    if len(line) > max_line_length_shown:
        line = line[0:max_line_length_shown] + b" ..."
    return repr(line.rstrip(b"\n"))[2:-1]


def check_bad_characters(line, line_number, danger, expected):
    if re.search(rb"[\x00-\x08\x14-\x1f\x7f-\xff]", expected):
        return None
    m = re.search(rb"^(.*?)([\x00-\x08\x14-\x1f\x7f-\xff])", line)
    if not m:
        return None
    (prefix, offending_char) = m.groups()
    offending_value = ord(offending_char)
    if offending_value == 0:
        description = "zero byte ('" + danger("\\0") + "')"
    elif offending_value > 127:
        description = "non-ascii byte " + danger("\\x%02x" % (offending_value))
    else:
        description = "non-printable character " + danger("\\x%02x" % (offending_value))
    column = len(prefix)
    explanation = "a " + danger("non-ASCII byte") + " was printed.\n"
    explanation += "Byte %d of line %d of program output was a %s\n" % (
        column + 1,
        line_number,
        description,
    )

    explanation += (
        "Here is line %d with non-printable characters replaced with backslash-escaped equivalents:\n"
        % (line_number)
    )
    line = repr(line)[2:-1] + "\n"
    line = re.sub(r"(\\x[0-9a-f][0-9a-f])", danger(r"\1"), line)
    explanation += line
    if offending_value == 255:
        explanation += (
            "\nHave you accidentally printed the special EOF value getchar returns?\n"
        )
        explanation += (
            "For more information go to: " + explanation_url("eof_byte") + "\n"
        )
    return explanation


def getenv_boolean(name, default=False):
    if name in os.environ:
        value = os.environ[name]
        return value and value[0] not in "0fFnN"
    else:
        return default


def getenv_int(name):
    try:
        return int(os.environ.get(name, 0))
    except ValueError:
        return 0
