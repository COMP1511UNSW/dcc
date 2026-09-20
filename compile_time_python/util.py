# miscellaneous code used at both compile & run-time

import os, re, sys

EXPLANATION_BASE_URL = "https://comp1511unsw.github.io/dcc/"
MAX_FILE_SIZE_PASSED_TO_HELPER = 8192

# order matters long values should be first
# tests/run_time_errors/uninitialized-types.c test most of these values
MEMORY_FILL = {
    "gdb_unknown": "(unknown: 0xaaaaaaaa)",
    "gdb_ascii": "-86 (not valid ASCII)",
    "gdb_int8": "-86 '\\252'",
    "gdb_uint8": "170 '\\252'",
    "clang_float": "-nan(0x7fffff)",
    "clang_double": "-nan(0xfffffffffffff)",
    "int64_hex": "0xaaaaaaaaaaaaaaaa",
    "int64": "-6148914691236517206",
    "uint64": "12297829382473034410",
    "float": "-3.03164883e-13",
    "double": "-3.7206620809969885e-103",
    "int32_hex": "0xaaaaaaaa",
    "int32": "-1431655766",
    "uint32": "2863311530",
    "int8_hex": "0xaa",
    "int8_char": '\\252',
}


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

    def source_line(self):
        return fileline(self.filename, self.line_number)

    def surrounding_source(self, color, radius=2, clean=False, markMiddle=False):
        lines = []
        for offset in range(-3 * radius, 2 * radius):
            line = fileline(self.filename, self.line_number + offset)

            if re.match(r"^\S", line) and offset < 0:
                lines = []

            if markMiddle and offset == 0 and line:
                line = color(re.sub(r"^ {0,3}", "-->", line), "red")

            lines.append(clean_c_source(line) if clean else line)

            if re.match(r"^\S", line) and offset > 0:
                break

        while lines and re.match(r"^[\s}]*$", lines[0]):
            lines.pop(0)

        while lines and re.match(r"^[\s{]*$", lines[-1]):
            lines.pop()

        return lines

    def is_user_location(self):
        if not re.match(r"^[a-zA-Z]", self.function):
            return False
        if re.match(r"^/(usr|build)/", self.filename):
            return False
        if re.match(r"^\?", self.filename):
            return False
        return True


# the lines of source files already read, keyed by filename
cached_source_files: dict[str, list[str]] = {}


def fileline(filename, line_number):
    line_number = int(line_number)
    if line_number < 1:
        # a negative index would wrap around to lines at the end of the file
        return ""
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
    # remove string & character literals, allowing for escaped characters inside them
    c_source = re.sub(r'"(?:\\.|[^"\\\n])*"', "", c_source)
    c_source = re.sub(r"'(?:\\.|[^'\\\n])*'", "", c_source)
    c_source = re.sub(r"/[/\*].*", "", c_source)
    if leave_white_space:
        return c_source
    return c_source.strip() + "\n"


debug_level = 0
debug_stream = sys.stderr


def debug_level_from_environment():
    """the value of DCC_DEBUG, or 0 if it is not an integer"""
    try:
        return int(os.environ.get("DCC_DEBUG", "0"))
    except ValueError:
        return 0


def set_debug_level(level=None):
    global debug_level
    debug_level = debug_level_from_environment() if level is None else level


def get_debug_level():
    return debug_level


def set_debug_stream(stream=sys.stderr):
    global debug_stream
    debug_stream = stream


def dprint(level, *args, **kwargs):
    if debug_level >= level:
        kwargs["file"] = debug_stream
        print(*args, **kwargs)
