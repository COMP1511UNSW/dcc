# miscellaneous code used at both compile & run-time

import os, re

EXPLANATION_BASE_URL = "https://comp1511unsw.github.io/dcc/"
MAX_FILE_SIZE_PASSED_TO_HELPER = 8192


def explanation_url(page):
    return EXPLANATION_BASE_URL + page + ".html"


def search_path(program, cwd=None):
    """
    return absolute pathname for first instance of program in $PATH, None otherwise
    if cwd supplied use it as current working firectory
    """
    path = os.environ.get("PATH", "/bin:/usr/bin:/usr/local/bin:.")
    for directory in path.split(os.pathsep):
        if cwd and not os.path.isabs(directory):
            directory = os.path.join(cwd, directory)
        pathname = os.path.join(directory, program)
        if os.path.isfile(pathname) and os.access(pathname, os.X_OK):
            return pathname
    return None


# hash_define = collections.defaultdict(dict)


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


def fileline(filename, line_number, cached_source_files={}):
    line_number = int(line_number)
    try:
        if filename in cached_source_files:
            return cached_source_files[filename][line_number - 1]
        with open(filename, encoding="utf-8", errors="replace") as f:
            cached_source_files[filename] = f.readlines()
        #            for line in source[filename]:
        #                m = re.match(r"^\s*#\s*define\s*(\w+)\s*(.*\S)", line)
        #                if m:
        #                    hash_define[filename][m.group(1)] = (line.rstrip(), m.group(2))
        return cached_source_files[filename][line_number - 1].rstrip() + "\n"
    except IOError:
        # dprint(2, f"fileline error can not open: {filename}")
        pass
    except IndexError:
        # dprint(2, f"fileline error can not find {line_number} in {filename}")
        pass
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
        r"((\\276)+)",
        lambda m: color(f"<{len(m.group(1)) // 4} uninitialized values>", "red"),
        values,
    )
    values = re.sub('<1 uninitialized values>', '<uninitialized value>', values)
    # make display of arrays more concise
    if values and values[0] == "{" and len(values) > 128:
        values = re.sub(r"\{(.{100}.*?),.*\}", r"{\1, ...}", values)

    return values
