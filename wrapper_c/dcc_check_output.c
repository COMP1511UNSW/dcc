static unsigned char *expected_stdout;

#if !DCC_CHECK_OUTPUT || !DCC_I_AM_SANITIZER1

static int init_check_output(void) {
	return 0;
}

static void __dcc_check_output(int fd, const char *buf, size_t size) MAYBE_UNUSED;
static void __dcc_check_output(int fd, const char *buf, size_t size) {
	(void)fd; // avoid unused parameter warning
	(void)buf; // avoid unused parameter warning
	(void)size; // avoid unused parameter warning
	expected_stdout = (unsigned char *)getenv("DCC_EXPECTED_STDOUT");
}

static void __dcc_check_close(int fd) MAYBE_UNUSED;
static void __dcc_check_close(int fd) {
	(void)fd; // avoid unused parameter warning
}

static void __dcc_check_output_exit(void) {
	debug_printf(3, "__dcc_check_output_exit\n");
	if (expected_stdout) {
		fflush(stdout);
	}
}

static void disable_check_output(void) {
	expected_stdout = NULL;
}

#else

#include <ctype.h>
#include <sys/mman.h>

#define N_ASCII 128

//lins longer than this will produce an error if output checking enabled
#define ACTUAL_LINE_MAX 65536

static int ignore_case;
static int ignore_empty_lines;
static int ignore_trailing_white_space;
static int ignore_characters[N_ASCII];
static unsigned int max_stdout_bytes;

// the position reached in the output is shared with every process the program
// fork()s, so output written by a child advances the same cursor as the parent.
// it is unsynchronised: a parent which exits while a child is still printing
// will read a partially advanced cursor, as it would without output checking
struct check_output_cursor {
	size_t n_expected_bytes_seen;
	// we accumulate output line in this array
	unsigned char actual_line[ACTUAL_LINE_MAX + 1];
	// position to put next character in above array
	int n_actual_line;
	// n bytes seen prior to those in above array
	size_t n_actual_bytes_seen;
	size_t n_actual_lines_seen;
};

static struct check_output_cursor *cursor;
// the process which initialized checking, the only one which checks at exit
static pid_t check_output_pid;

static int getenv_boolean(const char *name, int default_value) NO_SANITIZE;

static int init_check_output(void) NO_SANITIZE;
static int init_check_output(void) {
	expected_stdout = (unsigned char *)getenv("DCC_EXPECTED_STDOUT");
	if (!expected_stdout) {
		return 0;
	}
	debug_printf(2, "expected_stdout='%s'\n", expected_stdout);

	cursor = mmap(NULL, sizeof *cursor, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
	if (cursor == MAP_FAILED) {
		// a private cursor would miss output written by a fork()ed child
		// and report correct output as wrong, so check nothing instead
		debug_printf(1, "mmap failed - output checking disabled\n");
		cursor = NULL;
		expected_stdout = NULL;
		return 0;
	}
	check_output_pid = getpid();

	ignore_case = getenv_boolean("DCC_IGNORE_CASE", 0);
	ignore_empty_lines = getenv_boolean("DCC_IGNORE_EMPTY_LINES", 0);
	ignore_trailing_white_space = getenv_boolean("DCC_IGNORE_TRAILING_WHITE_SPACE", 1);

	char *max_stdout_bytes_string = getenv("DCC_MAX_STDOUT_BYTES");
	if (max_stdout_bytes_string) {
		max_stdout_bytes = atoi(max_stdout_bytes_string);
	}

	unsigned char *compare_only_chrs = (unsigned char *)getenv("DCC_COMPARE_ONLY_CHARACTERS");
	if (compare_only_chrs && *compare_only_chrs) {
		for (int i = 0; i < N_ASCII; i++) {
			ignore_characters[i] = 1;
		}
		for (; *compare_only_chrs; compare_only_chrs++) {
			if (*compare_only_chrs < N_ASCII) {
				ignore_characters[*compare_only_chrs] = 0;
				if (ignore_case) {
					ignore_characters[tolower(*compare_only_chrs)] = 0;
					ignore_characters[toupper(*compare_only_chrs)] = 0;
				}
			}
		}
	}

	if (getenv_boolean("DCC_IGNORE_WHITE_SPACE", 0)) {
		for (int i = 0; i < N_ASCII; i++) {
			if (isspace(i)) {
				ignore_characters[i] = 1;
			}
		}
	}

	unsigned char *ignore_chrs = (unsigned char *)getenv("DCC_IGNORE_CHARACTERS");
	if (ignore_chrs) {
		for (; *ignore_chrs; ignore_chrs++) {
			if (*ignore_chrs < N_ASCII) {
				ignore_characters[*ignore_chrs] = 1;
				if (ignore_case) {
					ignore_characters[tolower(*ignore_chrs)] = 1;
					ignore_characters[toupper(*ignore_chrs)] = 1;
				}
			}
		}
	}

	// comparison is line based so we can't ignore newline characters
	ignore_characters[(int)'\n'] = 0;
	ignore_characters[(int)'\r'] = 0;

	return 0;
}

static void disable_check_output(void) NO_SANITIZE;
static void disable_check_output(void) {
	expected_stdout = NULL;
}

static void __dcc_compare_output(unsigned char *actual, size_t size) NO_SANITIZE;
static void __dcc_check_all_output_seen_at_exit(void) NO_SANITIZE;

static void __dcc_check_output(int fd, const char *buf, size_t size) NO_SANITIZE;
static void __dcc_check_output(int fd, const char *buf, size_t size) {
	debug_printf(2, "check_output(%d, %d)\n", fd, (int)size);
	if (fd == 1 && expected_stdout) {
		__dcc_compare_output((unsigned char *)buf, size);
	}
}

static void __dcc_check_close(int fd) NO_SANITIZE;
static void __dcc_check_close(int fd) {
	debug_printf(2, "__dcc_check_close(%d)\n", fd);
	if (fd == 1 && expected_stdout && getpid() == check_output_pid) {
		 __dcc_check_all_output_seen_at_exit();
	}
}

static void __dcc_check_output_exit(void) NO_SANITIZE;
static void __dcc_check_output_exit(void) {
	debug_printf(3, "__dcc_check_output_exit\n");
	if (expected_stdout) {
		// flush first: a fork()ed child's output counts, but only the
		// process which started checking knows the program has finished
		fflush(stdout);
		if (getpid() == check_output_pid) {
			__dcc_check_all_output_seen_at_exit();
		}
	}
}

static unsigned char expected_line[ACTUAL_LINE_MAX + 2];

static void __dcc_compare_output_error(const char *reason, int actual_column, int expected_column) NO_SANITIZE;
static void __dcc_compare_line(unsigned char *expected, unsigned char *actual) NO_SANITIZE;
static int get_next_expected_line(void) NO_SANITIZE;
static int is_empty_line(unsigned char *line) NO_SANITIZE;
static void rstrip_line(unsigned char *line, int last_byte_index) NO_SANITIZE;

static void __dcc_compare_output(unsigned char *actual, size_t size) {
	int expected_bytes_in_line = get_next_expected_line();
	debug_printf(2, " __dcc_compare_output() n_actual_lines_seen=%d\n", cursor->n_actual_lines_seen);
	for (size_t i = 0; i < size; i++) {
		if (max_stdout_bytes && (cursor->n_actual_line + cursor->n_actual_bytes_seen) >= max_stdout_bytes) {
			cursor->n_actual_lines_seen++;
			cursor->actual_line[cursor->n_actual_line] = '\0';
			__dcc_compare_output_error("too much output", cursor->n_actual_line, -1);
		}

		if (cursor->n_actual_line == ACTUAL_LINE_MAX) {
			cursor->n_actual_lines_seen++;
			cursor->actual_line[ACTUAL_LINE_MAX] = '\0';
			__dcc_compare_output_error("line too long", ACTUAL_LINE_MAX, -1);
		}

		int actual_byte = actual[i];
		cursor->actual_line[cursor->n_actual_line++] = actual_byte;

		if (!actual_byte) {
			cursor->n_actual_lines_seen++;
			__dcc_compare_output_error("zero byte", cursor->n_actual_line, -1);
		}

		if (actual_byte != '\n') {
			continue;
		}
		cursor->actual_line[cursor->n_actual_line] = '\0';
		cursor->n_actual_lines_seen++;


		rstrip_line(cursor->actual_line, cursor->n_actual_line - 1);

		if (!ignore_empty_lines || !is_empty_line(cursor->actual_line)) {

			// we have a complete line of of output to compare against expected output

			__dcc_compare_line(expected_line, cursor->actual_line);
			cursor->n_expected_bytes_seen += expected_bytes_in_line;
			expected_bytes_in_line = get_next_expected_line();
		}
		cursor->n_actual_bytes_seen += cursor->n_actual_line;
		cursor->n_actual_line = 0;
		cursor->actual_line[0] = '\0';
	}


	if (cursor->n_actual_line) {
		// partial line which could check and give earlier warning for incorrect output
	}

}

static void __dcc_check_all_output_seen_at_exit(void) {
	debug_printf(2, "__dcc_check_all_output_seen_at_exit()\n");
	get_next_expected_line();
	cursor->actual_line[cursor->n_actual_line] = '\0';
	// count the partial line before rstrip_line can empty it, so a program
	// which printed only white space is not reported as printing nothing
	cursor->n_actual_bytes_seen += cursor->n_actual_line;
	rstrip_line(cursor->actual_line, cursor->n_actual_line - 1);
	cursor->n_actual_lines_seen++;
	__dcc_compare_line(expected_line, cursor->actual_line);
}

static void __dcc_compare_line(unsigned char *expected, unsigned char *actual) {
	debug_printf(2, "__dcc_compare_line()\nexpected='%s'\nactual='%s'\n", expected, actual);
	int n_actual_bytes_correct = 0;
	int n_expected_bytes_correct = 0;

	while (1) {
		int actual_byte = actual[n_actual_bytes_correct];
		int expected_byte = expected[n_expected_bytes_correct];

		if (ignore_case) {
			actual_byte = tolower(actual_byte);
			expected_byte = tolower(expected_byte);
		}

		if (actual_byte && actual_byte < N_ASCII && ignore_characters[actual_byte]) {
			n_actual_bytes_correct++;
			continue;
		}

		if (expected_byte && expected_byte < N_ASCII && ignore_characters[expected_byte]) {
			n_expected_bytes_correct++;
			continue;
		}

		if (!expected_byte && !actual_byte) {
			return;
		}

		//debug_printf(3, "expected_byte='%c' actual_byte='%c'\n", expected_byte, actual_byte);

		if (!expected_byte || actual_byte != expected_byte) {
			__dcc_compare_output_error("incorrect output", n_actual_bytes_correct, n_expected_bytes_correct);
		}

		n_expected_bytes_correct++;
		n_actual_bytes_correct++;
	}
	_exit(0);

}

static int is_empty_line(unsigned char *line) {
	for (;line[0]; line++) {
		if (line[0] == '\n' || (line[0] == '\r'  && line[1] == '\n')) {
			return 1;
		}
		if (line[0] >= N_ASCII || !ignore_characters[line[0]]) {
			return 0;
		}
	}
	return 0;
}

static int get_next_expected_line1(void) NO_SANITIZE;
static int get_next_expected_line(void) {
	while (1) {
		int bytes_seen = get_next_expected_line1();
		if (bytes_seen) {
			rstrip_line(expected_line, bytes_seen - 1);
		}
		if (!bytes_seen || !ignore_empty_lines || !is_empty_line(expected_line)) {
			return bytes_seen;
		}
		cursor->n_expected_bytes_seen += bytes_seen;
	}
}

static int get_next_expected_line1(void) {
	for (int i = 0; i < ACTUAL_LINE_MAX; i++) {
		int expected_byte = expected_stdout[cursor->n_expected_bytes_seen + i];
		expected_line[i] = expected_byte;
		if (!expected_byte) {
			return i;
		}
		if (expected_byte == '\n') {
			expected_line[i + 1] = '\0';
			return i + 1;
		}
	}
	__dcc_compare_output_error("expected line too long", -1, ACTUAL_LINE_MAX);
	return 0; // not reached
}

//int skip_to_next_expected_byte(void) {
//	while (1) {
//		int expected_byte = expected_stdout[n_expected_bytes_seen];
//		if (!expected_byte || expected_byte >= N_ASCII || !ignore_characters[expected_byte]) {
//			return expected_byte;
//		}
//		n_expected_bytes_seen++;
//	}
//}

static void __dcc_compare_output_error(const char *reason, int actual_column, int expected_column) {
	debug_printf(2, "__dcc_compare_output_error(%s)\n", reason);
	// putenv does not copy strings, so the buffers must outlive this function
	static char buffer[6][128];
	snprintf(buffer[0], sizeof buffer[0], "DCC_OUTPUT_ERROR=%s", reason);
	snprintf(buffer[1], sizeof buffer[1], "DCC_ACTUAL_LINE_NUMBER=%zu", cursor->n_actual_lines_seen);
	snprintf(buffer[2], sizeof buffer[2], "DCC_N_EXPECTED_BYTES_SEEN=%zu", cursor->n_expected_bytes_seen);
	snprintf(buffer[3], sizeof buffer[3], "DCC_N_ACTUAL_BYTES_SEEN=%zu", cursor->n_actual_bytes_seen);
	snprintf(buffer[4], sizeof buffer[4], "DCC_ACTUAL_COLUMN=%d", actual_column);
	snprintf(buffer[5], sizeof buffer[5], "DCC_EXPECTED_COLUMN=%d", expected_column);
	for (int i = 0; i < (int)(sizeof buffer / sizeof buffer[0]); i++)
		putenvd(buffer[i]);

	static char line_buffer[2][128 + ACTUAL_LINE_MAX];
	snprintf(line_buffer[0], sizeof line_buffer[0], "DCC_ACTUAL_LINE=%s", cursor->actual_line);
	snprintf(line_buffer[1], sizeof line_buffer[1], "DCC_EXPECTED_LINE=%s", expected_line);
	for (int i = 0; i < (int)(sizeof line_buffer / sizeof line_buffer[0]); i++)
		putenvd(line_buffer[i]);
	_explain_error();
}

// trim trailing white space from line
// and convert '\r\n' to '\n'
static void rstrip_line(unsigned char *line, int last_byte_index) {
	if (last_byte_index < 0) {
		return;
	}

	// the last line of the expected output, and the partial line a program
	// leaves at exit, have no newline terminator
	int has_newline = line[last_byte_index] == '\n';

	// convert Windows newline to Unix
	if (has_newline && last_byte_index > 0 && line[last_byte_index - 1] == '\r') {
		line[last_byte_index - 1] = '\n';
		line[last_byte_index] = '\0';
		last_byte_index--;
	}

	if (!ignore_trailing_white_space) {
		return;
	}

	// index of the first byte to drop, ignoring any newline terminator
	int index = has_newline ? last_byte_index : last_byte_index + 1;

	while (index > 0 && isspace(line[index - 1])) {
		index--;
	}

	if (has_newline) {
		line[index] = '\n';
		line[index + 1] = '\0';
	} else {
		line[index] = '\0';
	}
}

// treat a variable has True if its non-zero length and doesn't
// start with 0 f or n
static int getenv_boolean(const char *name, int default_value) {
	char *value = getenv(name);
	return value ? !strchr("0fFnN", *value) : default_value;
}
#endif

