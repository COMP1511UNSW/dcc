#include <errno.h>

struct cookie {
	FILE *stream;
	FILE *cookie_stream;
	int fd;
	struct cookie *next;
};
#if DCC_N_SANITIZERS > 1
static void synchronization_failed(void);
#endif
static FILE *open_cookie(void *cookie, const char *mode);


// three of these are taken permanently by stdin, stdout and stderr
static struct cookie file_cookies[FOPEN_MAX];
// a program may have more streams open than that, and giving up on a cookie
// would turn off the checking sanitizer2 does, so extra cookies are allocated
// a cookie is handed to fopencookie, so it can not be moved and the
// allocated ones are kept and reused rather than freed
static struct cookie *extra_file_cookies;

static struct cookie *get_unused_cookie(void) {
	for (int i = 0; i < FOPEN_MAX; i++) {
		if (!file_cookies[i].stream) {
			return &file_cookies[i];
		}
	}
	for (struct cookie *c = extra_file_cookies; c; c = c->next) {
		if (!c->stream) {
			return c;
		}
	}
	struct cookie *c = calloc(1, sizeof *c);
	if (c) {
		c->next = extra_file_cookies;
		extra_file_cookies = c;
	}
	return c;
}

static struct cookie *find_cookie(FILE *stream) {
	if (!stream) {
		return NULL;
	}
	for (int i = 0; i < FOPEN_MAX; i++) {
		if (file_cookies[i].cookie_stream == stream) {
			return &file_cookies[i];
		}
	}
	for (struct cookie *c = extra_file_cookies; c; c = c->next) {
		if (c->cookie_stream == stream) {
			return c;
		}
	}
	return NULL;
}

static FILE *get_cookie(FILE *f, const char *mode) {
	if (!f) {
		return f;
	}
	struct cookie *c = get_unused_cookie();
	if (!c) {
		debug_printf(1, "out of fopen cookies\n");
#if DCC_N_SANITIZERS > 1
		synchronization_failed();
#endif
		return f;
	}
	extern int __real_fileno(FILE *stream);
	c->fd = __real_fileno(f);
	c->stream = f;
	c->cookie_stream = open_cookie(c, mode);
	return c->cookie_stream;
}


static int init_check_output(void);
static void init_cookies(void) {
	setbuf(stderr, NULL);
	debug_stream = stderr;

	init_check_output();
	stdin = get_cookie(stdin, "r");
	stdout = get_cookie(stdout, "w");
	stderr = get_cookie(stderr, "w");
	// in absence of portable way to determine appropriate buffering
	// this should be workable
	setlinebuf(stdin);
	setlinebuf(stdout);
	// the replacement stderr stream must not be fully buffered, or output is
	// delayed until the program exits; it is flushed before an error is reported
	setlinebuf(stderr);
#if DCC_CPP_MODE
	extern void __dcc_replace_cin(FILE *stream);
	extern void __dcc_replace_cout(FILE *stream);
	extern void __dcc_replace_cerr(FILE *stream);
	__dcc_replace_cin(stdin);
	__dcc_replace_cout(stdout);
	__dcc_replace_cerr(stderr);
#endif
}

#if DCC_USE_FUNOPEN

#ifndef __APPLE__
#include <bsd/stdio.h>
#endif

static int __dcc_cookie_read(void *v, char *buf, int size);
static int __dcc_cookie_write(void *v, const char *buf, int size);
static off_t __dcc_cookie_seek(void *v, off_t offset, int whence);
static int __dcc_cookie_close(void *v);

FILE *open_cookie(void *cookie, const char *mode) {	
	return funopen(cookie, __dcc_cookie_read, __dcc_cookie_write, __dcc_cookie_seek, __dcc_cookie_close);
}

#else

static ssize_t __dcc_cookie_read(void *v, char *buf, size_t size);
static ssize_t __dcc_cookie_write(void *v, const char *buf, size_t size);
static int __dcc_cookie_seek(void *v, off64_t *offset, int whence);
static int __dcc_cookie_close(void *v);

FILE *open_cookie(void *cookie, const char *mode) {
	return fopencookie(cookie, mode, (cookie_io_functions_t) {
				.write = __dcc_cookie_write,
				.close = __dcc_cookie_close,
				.read = __dcc_cookie_read,
				.seek = __dcc_cookie_seek,
				});
}

#endif

#ifndef getchar
// if we don't override getchar the fopencookie hooks are sometimes not called - reasons unclear
// but don't if getchar is a macro
int getchar(void) {
	int c = fgetc(stdin);
	return c;
}
#endif

#ifndef putchar
// if we don't override putchar the fopencookie hooks are sometimes not called - reasons unclear
// but don't if putchar is a macro
int putchar(int c) {
	return fputc(c, stdout);
}
#endif

#ifndef __APPLE__

// On macOS overriding puts gives this error:
// Interceptors are not working. This may be because AddressSanitizer is loaded too late
// Benefit unclear from overriding puts on any platform

#ifndef puts
// overriding puts in case this is also needed to ensure fopencookie hooks called
int puts(const char *s) {
	int ret1 = fputs(s, stdout);
	if (ret1 == EOF) {
		return EOF;
	}
	int ret2 = fputc('\n', stdout);
	if (ret2 == EOF) {
		return EOF;
	}
	return ret1 + 1;
}
#endif
#endif

#if DCC_N_SANITIZERS == 1

#define synchronize_system_call(which, n)
#define synchronize_system_call_result(which, value) 0

static void __dcc_check_output_exit(void);

// check all the expected output has been produced when the program exits
// a destructor is needed because stdio does not close streams at exit,
// so __dcc_cookie_close is not called for stdout
static void __dcc_cleanup_before_exit(void) __attribute__((destructor));
static void __dcc_cleanup_before_exit(void) {
	debug_printf(3, "__dcc_cleanup_before_exit\n");
	// a destructor is only run once, but guard against a second call anyway
	static int cleanup_started;
	if (cleanup_started) {
		return;
	}
	cleanup_started = 1;
	__dcc_check_output_exit();
#if DCC_CPP_MODE
	extern void __dcc_restore_cin(void);
	extern void __dcc_restore_cout(void);
	extern void __dcc_restore_cerr(void);
	__dcc_restore_cin();
	__dcc_restore_cout();
	__dcc_restore_cerr();
#endif
}

#else

enum which_system_call {
	sc_abort,
	sc_clock,
	sc_close,
	sc_fdopen,
	sc_fileno,
	sc_fopen,
	sc_freopen,
	sc_popen,
	sc_read,
	sc_remove,
	sc_rename,
	sc_seek,
	sc_system,
	sc_time,
	sc_write,
};

#ifndef debug_printf
static char *system_call_names[] = {
	[sc_abort] = "abort",
	[sc_clock] = "clock",
	[sc_close] = "close",
	[sc_fopen] = "fopen",
	[sc_fdopen] = "fdopen",
	[sc_fileno] = "fileno",
	[sc_freopen] = "freopen",
	[sc_popen] = "popen",
	[sc_read] = "read",
	[sc_remove] = "remove",
	[sc_rename] = "rename",
	[sc_seek] = "seek",
	[sc_system] = "system",
	[sc_time] = "time",
	[sc_write] = "write",
};
#endif


static void unlink_sanitizer2_executable(void) NO_SANITIZE;

struct system_call {
	enum which_system_call which;
	int32_t e;
	int64_t n;
};

// only disconnect_sanitizers sets this variable
static int synchronization_terminated;

static void disconnect_sanitizers(void) {
	debug_printf(2, "disconnect_sanitizers()\n");
	if (synchronization_terminated) {
		return;
	}
#if DCC_I_AM_SANITIZER1
	close(to_sanitizer2_pipe[1]);
	close(from_sanitizer2_pipe[0]);
#else
	close(to_sanitizer2_pipe[0]);
	close(from_sanitizer2_pipe[1]);
#endif
	synchronization_terminated = 1;
}

static void stop_sanitizer2(void);

// FIXME - race condition
#if DCC_I_AM_SANITIZER1
static int sanitizer2_killed;

// set by note_sanitizer2_error when sanitizer2 signals that it found an error
// sanitizer2 has already explained the error, so only the exit status is needed
static volatile sig_atomic_t sanitizer2_reported_error;

static void note_sanitizer2_error(int signum) NO_SANITIZE;
static void note_sanitizer2_error(int signum) {
	(void)signum;
	sanitizer2_reported_error = 1;
}

static void wait_for_sanitizer2_to_terminate(void) {
	// set_signals_default leaves SIGUSR1 handled by note_sanitizer2_error
	set_signals_default();
	debug_printf(3, "waiting\n");
	if (!sanitizer2_killed) {
		signal(SIGPIPE, SIG_IGN);
		pid_t pid;
		do {
			pid = wait(NULL);
		} while (pid < 0 && errno == EINTR);
		debug_printf(3, "wait returned %d\n", pid);
		if (pid != sanitizer2_pid) {
			stop_sanitizer2();
		} else {
			sanitizer2_killed = 1;
		}
	}
}
#endif

static void __dcc_check_output_exit(void);

static void __dcc_cleanup_before_exit(void) __attribute__((destructor));
static void __dcc_cleanup_before_exit(void) {
	debug_printf(3, "__dcc_cleanup_before_exit\n");
	// __dcc_error_exit also calls this, so it can be re-entered
	static int cleanup_started;
	if (cleanup_started) {
		return;
	}
	cleanup_started = 1;
	__dcc_check_output_exit();
#if DCC_CPP_MODE
	extern void __dcc_restore_cin(void);
	extern void __dcc_restore_cout(void);
	extern void __dcc_restore_cerr(void);
	__dcc_restore_cin();
	__dcc_restore_cout();
	__dcc_restore_cerr();
#endif

	disconnect_sanitizers();
#if DCC_I_AM_SANITIZER1
	wait_for_sanitizer2_to_terminate();
#endif
	unlink_sanitizer2_executable();
#if DCC_I_AM_SANITIZER1
	if (sanitizer2_reported_error) {
		// the program has an error even though main finished normally
		// the output the program has produced is flushed first,
		// because _exit does not flush and the error is not the program's fault
		debug_printf(2, "sanitizer2 reported an error, exiting\n");
		fflush(NULL);
		_exit(DCC_ERROR_EXIT_STATUS);
	}
#endif
}


static void stop_sanitizer2(void) {
	disconnect_sanitizers();
#if DCC_I_AM_SANITIZER1
	if (!sanitizer2_killed) {
		debug_printf(2, "killing sanitizer2 pid=%d and unlinking executable\n", sanitizer2_pid);
		kill(sanitizer2_pid, SIGPIPE);
		unlink_sanitizer2_executable();
		kill(sanitizer2_pid, SIGKILL);
		sanitizer2_killed = 1;
	}
#else
	__dcc_error_exit();
#endif
}

static void synchronization_failed(void) {
	debug_printf(1, "warning: sanitizer synchronization lost\n");
	if (debug_level > 3) {
		debug_printf(3, "sleeping for 3600 seconds because in debug mode\n");
		sleep(3600);
	}
	stop_sanitizer2();
}

// when it reaches a system call sanitizer 1 waits for sanitizer 2
// to have reached the same system call and writes a message down from_sanitizer2_pipe

static void synchronize_system_call(enum which_system_call which, int64_t n) {
	debug_printf(3, "synchronize_system_call(%s, %d)\n", system_call_names[which], (int)n);
	if (synchronization_terminated) {
		debug_printf(2, "synchronize_system_calls - synchronization_terminated\n");
#if DCC_I_AM_SANITIZER2
		__dcc_error_exit();
#endif
		return;
	}
	struct system_call s = {0};
#if DCC_I_AM_SANITIZER1
	int n_bytes_read = read(from_sanitizer2_pipe[0], &s, sizeof s);
	// the two sanitizers can legitimately write different numbers of bytes,
	// e.g. %p prints a shorter pointer under valgrind, and sanitizer2's bytes are discarded anyway
	if (n_bytes_read != sizeof s) {
		debug_printf(1, "synchronize_system_call error(%s, %d): read returned %d != %d\n", system_call_names[which], (int)n, n_bytes_read, (int)sizeof s);
	} else if (which != s.which) {
		debug_printf(1, "synchronize_system_call error(%s, %d): which == %d\n", system_call_names[which], (int)n, s.which);
	} else if (which != sc_write && n != s.n) {
		debug_printf(1, "synchronize_system_call error(%s, %d) n == %d\n", system_call_names[which], (int)n, (int)s.n);
	} else {
		debug_printf(2, "synchronize_system_call(%s, %d) returning\n", system_call_names[which], (int)n);
		return;
	}

	synchronization_failed();
#else
	memset(&s, 0, sizeof s); // clear padding bytes
	s.which = which;
	s.n = n;
	ssize_t n_bytes_written = write(from_sanitizer2_pipe[1], &s, sizeof s);
	if (n_bytes_written != sizeof (struct system_call)) {
		debug_printf(1, "system_called_reached error: write returned %d != %d\n", (int)n_bytes_written, (int)sizeof (struct system_call));
		synchronization_failed();
	}
	debug_printf(3, "synchronize_system_call(%s, %d) returning\n", system_call_names[which], (int)n);
#endif
}

// sanitizer 2 waits for sanitizer 1 to write a message down to_sanitizer2_pipe
// passing result of a system call from sanitizer1 -> sanitizer2

#if DCC_I_AM_SANITIZER1
static int64_t synchronize_system_call_result(enum which_system_call which, int64_t return_value) {
	debug_printf(3, "synchronize_system_call_result(%s, %d)\n", system_call_names[which], (int)return_value);
	if (synchronization_terminated) {
		debug_printf(2, "synchronize_system_call_result - synchronization_terminated\n");
		return return_value;
	}
	struct system_call s = {0};
	memset(&s, 0, sizeof s); // clear padding bytes
	s.which = which;
	s.e = errno;
	s.n = return_value;
	ssize_t n_bytes_written = write(to_sanitizer2_pipe[1], &s, sizeof s);
	if (n_bytes_written != sizeof (struct system_call)) {
		debug_printf(1, "synchronize_system_call_result(%s) error: write returned %d != %d\n", system_call_names[which], (int)n_bytes_written, (int)sizeof (struct system_call));
		synchronization_failed();
	}
	debug_printf(3, "synchronize_system_call_result(%s) returning %d\n", system_call_names[which], (int)return_value);
	return return_value;
}
#else
static int64_t synchronize_system_call_result(enum which_system_call which) {
	debug_printf(3, "synchronize_system_call_result(%s)\n", system_call_names[which]);
	struct system_call s = {0};
	ssize_t n_bytes_read = read(to_sanitizer2_pipe[0], &s, sizeof s);
	if (n_bytes_read != sizeof s) {
		debug_printf(1, "synchronize_system_call_result error: read returned %d != %d\n", (int)n_bytes_read, (int)sizeof s);
		synchronization_failed();
	} else if (which != s.which) {
		debug_printf(1, "synchronize_system_call_result error: which %d != %d\n", which, s.which);
		synchronization_failed();
	}
	debug_printf(3, "synchronize_system_call_result(%s) returning %d\n", system_call_names[which], (int)s.n);
	errno = s.e;
	return s.n;
}
#endif

#endif

static void __dcc_save_stdin(const char *buf, size_t size);

#if DCC_USE_FUNOPEN
static int __dcc_cookie_read(void *v, char *buf, int size) {
#else
static ssize_t __dcc_cookie_read(void *v, char *buf, size_t size) {
#endif
	// libc 2.28-5 doesn't flush stdout if it is a (linebuffered) fopencookie streams
	// when there is a read on stdin which is a (linebuffered) fopencookie streams
	// workaround by flushing stdout here on read of any stream
	fflush(stdout);

	synchronize_system_call(sc_read, size);
#if DCC_I_AM_SANITIZER1
	struct cookie *cookie = (struct cookie *)v;
    if (cookie == NULL || cookie->fd == -1) {
        putenvd("DCC_ASAN_ERROR=attempt to use stream after closed with fclose");
        _explain_error();
    }
	ssize_t n_bytes_read = read(cookie->fd, buf, size);
#if DCC_N_SANITIZERS > 1
	(void)synchronize_system_call_result(sc_read, n_bytes_read);
	if (n_bytes_read > 0  && !synchronization_terminated) {
		ssize_t n_bytes_written = write(to_sanitizer2_pipe[1], buf, n_bytes_read);
		if (n_bytes_written != n_bytes_read) {
			debug_printf(1, "__dcc_cookie_read %d != %d\n", (int)n_bytes_written, (int)n_bytes_read);
			synchronization_failed();
		}
	}
#endif
#else
	(void)v; // avoid unused parameter warning
	ssize_t n_bytes_read = synchronize_system_call_result(sc_read);
	if (n_bytes_read > 0) {
		// the data may arrive in several pieces if it is larger than PIPE_BUF
		ssize_t n_bytes_actually_read = 0;
		while (n_bytes_actually_read < n_bytes_read) {
			ssize_t n = read(to_sanitizer2_pipe[0], buf + n_bytes_actually_read, n_bytes_read - n_bytes_actually_read);
			if (n <= 0) {
				break;
			}
			n_bytes_actually_read += n;
		}
		if (n_bytes_read != n_bytes_actually_read) {
			debug_printf(1, "__dcc_cookie_read error: read returned %d != %d\n", (int)n_bytes_read, (int)n_bytes_actually_read);
			synchronization_failed();
		}
	}
#endif
    debug_printf(5, "__dcc_save_stdin %p\n", v);
    if (v != NULL && ((struct cookie *)v)->stream != NULL && ((struct cookie *)v)->fd == 0) {
	    __dcc_save_stdin(buf, n_bytes_read);
	}
	quick_clear_stack();
	return n_bytes_read;
}

static void __dcc_check_output(int fd, const char *buf, size_t size);
static void __dcc_check_close(int fd);
// defined with the checker, which clears it when checking is turned off
static unsigned char *expected_stdout;

#ifdef __linux__
#define DCC_OVERRIDE_WRITE 1
#endif

#if DCC_OVERRIDE_WRITE
#include <dlfcn.h>

// the write below is called for the program's writes to stdout, so the
// wrapper's own writes have to go to the next write in the library search
// order, which is the sanitizer's, so it still checks the bytes written
static ssize_t raw_write(int fd, const void *buf, size_t size) {
	static ssize_t (*next_write)(int fd, const void *buf, size_t size);
	if (!next_write) {
		next_write = (ssize_t (*)(int, const void *, size_t))dlsym(RTLD_NEXT, "write");
		if (!next_write) {
			debug_printf(1, "dlsym(RTLD_NEXT, \"write\") failed\n");
		}
	}
	if (!next_write) {
		return syscall(SYS_write, fd, buf, size);
	}
	return next_write(fd, buf, size);
}
#else
#define raw_write write
#endif

#if DCC_USE_FUNOPEN
static int __dcc_cookie_write(void *v, const char *buf, int size) {
#else
static ssize_t __dcc_cookie_write(void *v, const char *buf, size_t size) {
#endif
	synchronize_system_call(sc_write, size);
#if DCC_I_AM_SANITIZER1
	struct cookie *cookie = (struct cookie *)v;
	size_t n_bytes_written = raw_write(cookie->fd, buf, size);

	__dcc_check_output(cookie->fd, buf, size);
	(void)synchronize_system_call_result(sc_write, n_bytes_written);
#else
	(void)v; // avoid unused parameter warning
	(void)buf; // avoid unused parameter warning
	// sanitizer1 may have been asked to write more bytes than we were,
	// and stdio treats a return larger than its request as a failed write
	int64_t result = synchronize_system_call_result(sc_write);
	size_t n_bytes_written = result > (int64_t)size ? (size_t)size : (size_t)result;
#endif
	quick_clear_stack();
	return n_bytes_written;
}


#if DCC_OVERRIDE_WRITE
// bytes written straight to file descriptor 1 or 2 are the program's output
// too, but they do not pass through the stdout or stderr stream, so they would
// not be compared with the expected output and both sanitizers would write them
//
// weak so a program defining its own write is still linked
__attribute__((weak)) ssize_t write(int fd, const void *buf, size_t size) {
	if (fd != 1 && fd != 2) {
		return raw_write(fd, buf, size);
	}
	// what the program has printed to the stream for this descriptor is
	// flushed first so these bytes are not moved ahead of it, and both
	// sanitizers do it so the write it may cause still pairs up
	fflush(fd == 1 ? stdout : stderr);
	synchronize_system_call(sc_write, size);
#if DCC_I_AM_SANITIZER1
	ssize_t n_bytes_written = raw_write(fd, buf, size);
	if (n_bytes_written > 0) {
		// bytes a short or failed write did not produce are not the program's output
		__dcc_check_output(fd, (const char *)buf, (size_t)n_bytes_written);
	}
	(void)synchronize_system_call_result(sc_write, n_bytes_written);
#else
	(void)buf; // avoid unused parameter warning
	int64_t result = synchronize_system_call_result(sc_write);
	ssize_t n_bytes_written = result > (int64_t)size ? (ssize_t)size : (ssize_t)result;
#endif
	quick_clear_stack();
	return n_bytes_written;
}
#endif


#if DCC_USE_FUNOPEN
static off_t __dcc_cookie_seek(void *v, off_t offset, int whence) {
	synchronize_system_call(sc_seek, offset);

#if DCC_I_AM_SANITIZER1
	struct cookie *cookie = (struct cookie *)v;
	off_t result = lseek(cookie->fd, offset, whence);
	(void)synchronize_system_call_result(sc_seek, result);
#else
	(void)v; // avoid unused parameter warning
	(void)offset; // avoid unused parameter warning
	(void)whence; // avoid unused parameter warning
	int result = synchronize_system_call_result(sc_seek);
#endif
	quick_clear_stack();
	return result;
}
#else
static int __dcc_cookie_seek(void *v, off64_t *offset, int whence) {
	synchronize_system_call(sc_seek, *offset);

#if DCC_I_AM_SANITIZER1
	struct cookie *cookie = (struct cookie *)v;
	off_t result = lseek(cookie->fd, *offset, whence);
	if (result != -1) {
		*offset = result;
		result = 0;
	}

	(void)synchronize_system_call_result(sc_seek, result);
#else
	(void)v; // avoid unused parameter warning
	(void)offset; // avoid unused parameter warning
	(void)whence; // avoid unused parameter warning
	int result = synchronize_system_call_result(sc_seek);
#endif
	quick_clear_stack();
	return result;
}
#endif

// pass results of a close sanitizer 1 -> sanitizer 2

static int __dcc_cookie_close(void *v) {
	synchronize_system_call(sc_close, 0);
#if DCC_I_AM_SANITIZER1
	struct cookie *cookie = (struct cookie *)v;
	int result = fclose(cookie->stream);
	__dcc_check_close(cookie->fd);
	cookie->stream = NULL;
	cookie->cookie_stream = NULL;
	cookie->fd = -1;
	(void)synchronize_system_call_result(sc_close, result);
#else
	(void)v; // avoid unused parameter warning
	int result = (int)synchronize_system_call_result(sc_close);
#endif
	quick_clear_stack();
	return result;
}


#if DCC_I_AM_SANITIZER1
// the output of a child process is the program's output too, but it is
// written to file descriptor 1 by another process, so while output is being
// checked the command is run with its output coming back through a pipe
static int run_system_command(const char *command) {
	extern int __real_system(const char *command);
#if DCC_CHECK_OUTPUT
	if (command && expected_stdout) {
#if DCC_N_SANITIZERS > 1
		// popen is wrapped as well when there are two sanitizers
		extern FILE *__real_popen(const char *command, const char *type);
		FILE *f = __real_popen(command, "r");
#else
		FILE *f = popen(command, "r");
#endif
		if (f) {
			char buf[4096];
			size_t n_bytes_read;
			while ((n_bytes_read = fread(buf, 1, sizeof buf, f)) > 0) {
				raw_write(1, buf, n_bytes_read);
				__dcc_check_output(1, buf, n_bytes_read);
			}
			return pclose(f);
		}
	}
#endif
	return __real_system(command);
}
#endif

#if DCC_N_SANITIZERS == 1
#undef system
// with one sanitizer there is no second process to keep in step with, but a
// child's output is still the program's output and still has to be checked
int __wrap_system(const char *command) {
	fflush(stdout);
	return run_system_command(command);
}
#endif

#if DCC_N_SANITIZERS > 1
void abort(void) {
#if DCC_I_AM_SANITIZER2
	unlink_sanitizer2_executable();
#endif
	synchronize_system_call(sc_abort, 0);
#if DCC_I_AM_SANITIZER1
	__dcc_signal_handler(SIGABRT);
#endif
	__dcc_error_exit();
	_exit(DCC_ERROR_EXIT_STATUS); //not reached
}

// pass results of a time call sanitizer 1 -> sanitizer 2

#undef time
time_t __wrap_time(time_t *tloc) {
	synchronize_system_call(sc_time, 0);
#if DCC_I_AM_SANITIZER1
	extern time_t __real_time(time_t *tloc);
	return synchronize_system_call_result(sc_time, __real_time(tloc));
#else
	time_t t = synchronize_system_call_result(sc_time);
	if (tloc) {
		*tloc = t;
	}
	return t;
#endif
}

// pass results of a clock call sanitizer 1 -> sanitizer 2

#undef clock
clock_t __wrap_clock(void) {
	synchronize_system_call(sc_clock, 0);
#if DCC_I_AM_SANITIZER1
	extern clock_t __real_clock(void);
	return synchronize_system_call_result(sc_clock, __real_clock());
#else
	return synchronize_system_call_result(sc_clock);
#endif
}


// pass results of a remove call sanitizer 1 -> sanitizer 2

#undef remove
int __wrap_remove(const char *pathname) {
	synchronize_system_call(sc_remove, 0);
#if DCC_I_AM_SANITIZER1
	extern int __real_remove(const char *pathname);
	return synchronize_system_call_result(sc_remove, __real_remove(pathname));
#else
	(void)pathname; // avoid unused parameter warning
	return synchronize_system_call_result(sc_remove);
#endif
}

// pass results of a rename call sanitizer 1 -> sanitizer 2

#undef rename
int __wrap_rename(const char *oldpath, const char *newpath) {
	synchronize_system_call(sc_rename, 0);
#if DCC_I_AM_SANITIZER1
	extern int __real_rename(const char *oldpath, const char *newpath);
	return synchronize_system_call_result(sc_rename, __real_rename(oldpath, newpath));
#else
	(void)oldpath; // avoid unused parameter warning
	(void)newpath; // avoid unused parameter warning
	return synchronize_system_call_result(sc_rename);
#endif
}


// pass results of a call to system  sanitizer 1 -> sanitizer 2


#undef system
int __wrap_system(const char *command) {
	// what the program has printed is flushed before the handshake, so the
	// command's output is not moved ahead of it, and so the write the flush
	// may cause still pairs up between the sanitizers
	fflush(stdout);
	synchronize_system_call(sc_system, 0);
#if DCC_I_AM_SANITIZER1
	return synchronize_system_call_result(sc_system, run_system_command(command));
#else
	(void)command; // avoid unused parameter warning
	return synchronize_system_call_result(sc_system);
#endif
}


static FILE *fopen_helper(FILE *f, const char *mode, enum which_system_call system_call) {
#if DCC_I_AM_SANITIZER1
	FILE *f1 = get_cookie(f, mode);
	(void)synchronize_system_call_result(system_call, !!f1);
	return f1;
#else
	(void)f; // avoid unused parameter warning
	int64_t r = synchronize_system_call_result(system_call);
	if (r) {
		return open_cookie(NULL, mode);
	} else {
		return NULL;
	}
#endif
}

#undef popen
FILE *__wrap_popen(const char *command, const char *type) {
	synchronize_system_call(sc_popen, 0);
#if DCC_I_AM_SANITIZER1
	extern FILE *__real_popen(const char *command, const char *type);
	FILE *f = __real_popen(command, type);
#else
	(void)command; // avoid unused parameter warning
	FILE *f = NULL;
#endif
	return fopen_helper(f, type, sc_popen);
}


#undef fopen
FILE *__wrap_fopen(const char *pathname, const char *mode) {
	synchronize_system_call(sc_fopen, 0);
#if DCC_I_AM_SANITIZER1
	extern FILE *__real_fopen(const char *pathname, const char *mode);
	FILE *f = __real_fopen(pathname, mode);
#else
	(void)pathname; // avoid unused parameter warning
	FILE *f = NULL;
#endif
	return fopen_helper(f, mode, sc_fopen);
}

#undef fdopen
FILE *__wrap_fdopen(int fd, const char *mode) {
	synchronize_system_call(sc_fdopen, 0);
#if DCC_I_AM_SANITIZER1
	extern FILE *__real_fdopen(int fd, const char *mode);
	FILE *f = __real_fdopen(fd, mode);
#else
	(void)fd; // avoid unused parameter warning
	FILE *f = NULL;
#endif
	return fopen_helper(f, mode, sc_fdopen);
}

#undef freopen
FILE *__wrap_freopen(const char *pathname, const char *mode, FILE *stream) {
	synchronize_system_call(sc_freopen, 0);
#if DCC_I_AM_SANITIZER1
	if (!pathname || !mode || !stream) {
		(void)synchronize_system_call_result(sc_freopen, 0);
		return NULL;
	}
	struct cookie *c = find_cookie(stream);
	if (!c) {
		debug_printf(0, "freopen can not find stream");
		__dcc_error_exit();
	}
	extern FILE *__real_freopen(const char *pathname, const char *mode, FILE *stream);
	FILE *f1 = __real_freopen(pathname, mode, c->stream);
	if (f1) {
		c->stream = f1;
		extern int __real_fileno(FILE *stream);
		c->fd = __real_fileno(f1);
		(void)synchronize_system_call_result(sc_freopen, 1);
		return c->cookie_stream;
	} else {
		(void)synchronize_system_call_result(sc_freopen, 0);
		return NULL;
	}
#else
	(void)pathname; // avoid unused parameter warning
	(void)stream; // avoid unused parameter warning
	int64_t r = synchronize_system_call_result(sc_freopen);
	if (r) {
		return open_cookie(NULL, mode);
	} else {
		return NULL;
	}
#endif
}

static void unlink_sanitizer2_executable(void) {
	static int unlink_done;
	if (!unlink_done) {
		char *pathname = getenv("DCC_UNLINK");
		if (pathname) {
			unlink(pathname);
		}
		unlink_done = 1;
	}
}
#endif

static int cookie_stream_to_fd(FILE *stream) MAYBE_UNUSED;
static int cookie_stream_to_fd(FILE *stream) {
	struct cookie *c = find_cookie(stream);
	int fd = c ? c->fd : -1;

	// in single santizer mode cookies are used for stdin, stdout & stderr not files
	if (fd == -1) {
		extern int __real_fileno(FILE *stream);
		fd = __real_fileno(stream);
	}
	return fd;
}

#if DCC_N_SANITIZERS > 1

#undef fileno

int __wrap_fileno(FILE *stream) {
	synchronize_system_call(sc_fileno, 0);
#if DCC_I_AM_SANITIZER1
	return synchronize_system_call_result(sc_fileno, cookie_stream_to_fd(stream));
#else
	(void)stream; // avoid unused parameter warning
	return synchronize_system_call_result(sc_fileno);
#endif
}

#else

int __wrap_fileno(FILE *stream) {
	return cookie_stream_to_fd(stream);
}

#endif
