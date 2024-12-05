# miscellaneous code used at both compile & run-time

import os, re, sys

EXPLANATION_BASE_URL = "https://comp1511unsw.github.io/dcc/"
MAX_FILE_SIZE_PASSED_TO_HELPER = 8192

# order matters long values should be first
MEMORY_FILL = {
	"gdb_unknown": "(unknown: 0xbebebebe)",
	"gdb_ascii" : "-66 (not valid ASCII)",
	"int64_hex" : "0xbebebebebebebebe",
	"int64" : "-4702111234474983746",
	"uint64" : "13744632839234567870",
	"float" : "-0.372548997",
	"double" : "-1.8325506472120096e-06",
	"int32_hex" : "0xbebebebe",
	"int32" : "-1094795586",
	"uint32" : "3200171710",
	"int8_hex" : "0xbe",
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

    def location(self, color):
        return (
            color(self.filename, "red")
            + " at "
            + color("line " + str(self.line_number), "red")
        )

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


debug_level = 0
debug_stream = sys.stderr


def set_debug_level(level=int(os.environ.get("DCC_DEBUG", "0"))):
    global debug_level
    debug_level = level


def get_debug_level():
    global debug_level
    return debug_level


def set_debug_stream(stream=sys.stderr):
    global debug_stream
    debug_stream = sys.stderr


def dprint(level, *args, **kwargs):
    if debug_level >= level:
        kwargs["file"] = debug_stream
        print(*args, **kwargs)
