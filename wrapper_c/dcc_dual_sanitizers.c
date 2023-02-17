#if !__CHECK_OUTPUT__ && __N_SANITIZERS__ == 1

static void init_cookies(void) {
}

#else

#if __I_AM_SANITIZER1__
struct cookie {
	FILE *stream;
	FILE *cookie_stream;
	int fd;
};
#endif
static void synchronization_failed(void);
static FILE *open_cookie(void *cookie, const char *mode);


#if __I_AM_SANITIZER1__
static struct cookie file_cookies[FOPEN_MAX];

static FILE *get_cookie(FILE *f, const char *mode) {
	if (!f) {
		return f;
	}
	for (int i = 0; i < FOPEN_MAX; i++) {
		if (!file_cookies[i].stream) {
			file_cookies[i].fd = fileno(f);
			file_cookies[i].stream = f;
			file_cookies[i].cookie_stream = open_cookie(&file_cookies[i], mode);
			return file_cookies[i].cookie_stream;
		}
	}
	debug_printf(1, "out of fopen cookies\n");
#if __N_SANITIZERS__ > 1
	synchronization_failed();
#endif
	return f;
}

#else
static FILE *get_cookie(FILE *f, const char *mode) {
	(void)f; // avoid unused parameter warning
	return open_cookie(NULL, mode);
}
#endif

static int init_check_output(void);
static void init_cookies(void) {
	setbuf(stderr, NULL);
	debug_stream = stderr;

#if __N_SANITIZERS__ > 1
	init_check_output();
	stdin = get_cookie(stdin, "r");
	stdout = get_cookie(stdout, "w");
	stderr = get_cookie(stderr, "w");
	// in absence of portable way to determine appropriate buffering
	// this should be workable
	setlinebuf(stdin);
	setlinebuf(stdout);
#if __CPP_MODE__
	extern void __dcc_replace_cin(FILE *stream);
	extern void __dcc_replace_cout(FILE *stream);
	extern void __dcc_replace_cerr(FILE *stream);
	__dcc_replace_cin(stdin);
	__dcc_replace_cout(stdout);
	__dcc_replace_cerr(stderr);
#endif

#else
	if (init_check_output()) {
		stdout = get_cookie(stdout, "w");
#if __CPP_MODE__
		extern void __dcc_replace_cout(FILE *stream);
		__dcc_replace_cout(stdout);
#endif

	}
#endif
}

#if __USE_FUNOPEN__

#ifndef __APPLE__
#include <bsd/stdio.h>
#endif

static int __dcc_cookie_read(void *v, char *buf, int size);
static int __dcc_cookie_write(void *v, const char *buf, int size);
static off_t __dcc_cookie_seek(void *v, off_t offset, int whence);
static int __dcc_cookie_close(void *v);

FILE *open_cookie(void *cookie, const char *mode) {	
#if __N_SANITIZERS__ > 1
	return funopen(cookie, __dcc_cookie_read, __dcc_cookie_write, __dcc_cookie_seek, __dcc_cookie_close);
#else
	return funopen(cookie, NULL, __dcc_cookie_write, NULL, __dcc_cookie_close);
#endif
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
#if __N_SANITIZERS__ > 1
				.read = __dcc_cookie_read,
				.seek = __dcc_cookie_seek,
#endif
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

#if __N_SANITIZERS__ == 1

#define synchronize_system_call(which, n)
#define synchronize_system_call_result(which, value) 0

#else

enum which_system_call {
	sc_abort,
	sc_clock,
	sc_close,
	sc_fdopen,
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
	int64_t n;
};

// only disconnect_sanitizers sets this variable
static int synchronization_terminated;

static void disconnect_sanitizers(void) {
	debug_printf(2, "disconnect_sanitizers()\n");
	if (synchronization_terminated) {
		return;
	}
#if __I_AM_SANITIZER1__
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
#if __I_AM_SANITIZER1__
static int sanitizer2_killed;

static void wait_for_sanitizer2_to_terminate(void) {
	set_signals_default();
	debug_printf(3, "waiting\n");
	if (!sanitizer2_killed) {
		// sanitizer2 sends SIGUSR1 if its printing an error
		signal(SIGUSR1, SIG_IGN);
		signal(SIGPIPE, SIG_IGN);
		pid_t pid = wait(NULL);
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
	__dcc_check_output_exit();
#if __CPP_MODE__
	extern void __dcc_restore_cin(void);
	extern void __dcc_restore_cout(void);
	extern void __dcc_restore_cerr(void);
	__dcc_restore_cin();
	__dcc_restore_cout();
	__dcc_restore_cerr();
#endif

	disconnect_sanitizers();
#if __I_AM_SANITIZER1__
	wait_for_sanitizer2_to_terminate();
#endif
	unlink_sanitizer2_executable();
}


static void stop_sanitizer2(void) {
	disconnect_sanitizers();
#if __I_AM_SANITIZER1__
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
// to have reached the same system call and writen a message down from_sanitizer2_pipe

static void synchronize_system_call(enum which_system_call which, int64_t n) {
	debug_printf(3, "synchronize_system_call(%s, %d)\n", system_call_names[which], (int)n);
	if (synchronization_terminated) {
		debug_printf(2, "synchronize_system_calls - synchronization_terminated\n");
#if __I_AM_SANITIZER2__
		__dcc_error_exit();
#endif
		return;
	}
	struct system_call s = {0};
#if __I_AM_SANITIZER1__
	int n_bytes_read = read(from_sanitizer2_pipe[0], &s, sizeof s);
	if (n_bytes_read != sizeof s) {
		debug_printf(1, "synchronize_system_call error(%s, %d): read returned %d != %d\n", system_call_names[which], (int)n, n_bytes_read, (int)sizeof s);
	} else if (which != s.which) {
		debug_printf(1, "synchronize_system_call error(%s, %d): which == %d\n", system_call_names[which], (int)n, s.which);
	} else if (n != s.n) {
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
		debug_printf(1, "system_called_reached error: write returned %d != %d\n", n_bytes_written, (int)sizeof sizeof (struct system_call));
		synchronization_failed();
	}
	debug_printf(3, "synchronize_system_call(%s, %d) returning\n", system_call_names[which], (int)n);
#endif
}

// sanitizer 2 waits for sanitizer 1 to write a message down to_sanitizer2_pipe
// passing result of a system call from sanitizer1 -> sanitizer2

static int64_t synchronize_system_call_result(enum which_system_call which
#if __I_AM_SANITIZER1__
	, int64_t return_value) {
	debug_printf(3, "synchronize_system_call_result(%s, %d)\n", system_call_names[which], (int)return_value);
	if (synchronization_terminated) {
		debug_printf(2, "synchronize_system_call_result - synchronization_terminated\n");
#if __I_AM_SANITIZER2__
		__dcc_error_exit();
#endif
		return return_value;
	}
	struct system_call s = {0};
	memset(&s, 0, sizeof s); // clear padding bytes
	s.which = which;
	s.n = return_value;
	ssize_t n_bytes_written = write(to_sanitizer2_pipe[1], &s, sizeof s);
	if (n_bytes_written != sizeof (struct system_call)) {
		debug_printf(1, "synchronize_system_call_result(%s) error: write returned %d != %d\n", system_call_names[which], n_bytes_written, (int)sizeof sizeof (struct system_call));
		synchronization_failed();
	}
	debug_printf(3, "synchronize_system_call_result(%s) returning %d\n", system_call_names[which], (int)return_value);
	return return_value;
#else
	) {
	debug_printf(3, "synchronize_system_call_result(%s)\n", system_call_names[which]);
	struct system_call s = {0};
	ssize_t n_bytes_read = read(to_sanitizer2_pipe[0], &s, sizeof s);
	if (n_bytes_read != sizeof s) {
		debug_printf(1, "synchronize_system_call_result error: read returned %d != %d\n", n_bytes_read, (int)sizeof s);
		synchronization_failed();
	} else if (which != s.which) {
		debug_printf(1, "synchronize_system_call_result error: which %d != %d\n", which, s.which);
		synchronization_failed();
	}
	debug_printf(3, "synchronize_system_call_result(%s) returning %d\n", system_call_names[which], (int)s.n);
	return s.n;
#endif
}

#endif


#if __USE_FUNOPEN__
static int __dcc_cookie_read(void *v, char *buf, int size) {
#else
static ssize_t __dcc_cookie_read(void *v, char *buf, size_t size) {
#endif
	// libc 2.28-5 doesn't flush stdout if it is a (linebuffered) fopencookie streams
	// when there is a read on stdin which is a (linebuffered) fopencookie streams
	// workaround by flushing stdout here on read of any stream

	fflush(stdout);

	synchronize_system_call(sc_read, size);
#if __I_AM_SANITIZER1__
	struct cookie *cookie = (struct cookie *)v;
	ssize_t n_bytes_read = read(cookie->fd, buf, size);
#if __N_SANITIZERS__ > 1
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
		ssize_t n_bytes_actually_read = read(to_sanitizer2_pipe[0], buf, n_bytes_read);
		if (n_bytes_read != n_bytes_actually_read) {
			debug_printf(1, "__dcc_cookie_read error: read returned %d != %d\n", (int)n_bytes_read, (int)n_bytes_actually_read);
			synchronization_failed();
		}
	}
#endif
	quick_clear_stack();
	return n_bytes_read;
}

static void __dcc_check_output(int fd, const char *buf, size_t size);
static void __dcc_check_close(int fd);

#if __USE_FUNOPEN__
static int __dcc_cookie_write(void *v, const char *buf, int size) {
#else
static ssize_t __dcc_cookie_write(void *v, const char *buf, size_t size) {
#endif
	synchronize_system_call(sc_write, size);
#if __I_AM_SANITIZER1__
	struct cookie *cookie = (struct cookie *)v;
	size_t n_bytes_written = write(cookie->fd, buf, size);

	__dcc_check_output(cookie->fd, buf, size);

	(void)synchronize_system_call_result(sc_write, n_bytes_written);
#else
	(void)v; // avoid unused parameter warning
	(void)buf; // avoid unused parameter warning
	(void)size; // avoid unused parameter warning
	size_t n_bytes_written = synchronize_system_call_result(sc_write);
#endif
	quick_clear_stack();
	return n_bytes_written;
}


#if __USE_FUNOPEN__
static off_t __dcc_cookie_seek(void *v, off_t offset, int whence) {
	synchronize_system_call(sc_seek, offset);

#if __I_AM_SANITIZER1__
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

#if __I_AM_SANITIZER1__
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
#if __I_AM_SANITIZER1__
	struct cookie *cookie = (struct cookie *)v;
	int result = fclose(cookie->stream);
	__dcc_check_close(cookie->fd);
	cookie->stream = NULL;
	cookie->cookie_stream = NULL;
	cookie->fd = 0;
	(void)synchronize_system_call_result(sc_close, result);
#else
	(void)v; // avoid unused parameter warning
	int result = (int)synchronize_system_call_result(sc_close);
#endif
	quick_clear_stack();
	return result;
}


#if __N_SANITIZERS__ > 1
void abort(void) {
#if __I_AM_SANITIZER2__
	unlink_sanitizer2_executable();
#endif
	synchronize_system_call(sc_abort, 0);
#if __I_AM_SANITIZER1__
	__dcc_signal_handler(SIGABRT);
#endif
	__dcc_error_exit();
	_exit(1); //not reached
}

// pass results of a time call sanitizer 1 -> sanitizer 2

#undef time
time_t __wrap_time(time_t *tloc) {
	synchronize_system_call(sc_time, 0);
#if __I_AM_SANITIZER1__
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
#if __I_AM_SANITIZER1__
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
#if __I_AM_SANITIZER1__
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
#if __I_AM_SANITIZER1__
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
	synchronize_system_call(sc_system, 0);
#if __I_AM_SANITIZER1__
	int __real_system(const char *command);
	return synchronize_system_call_result(sc_system, __real_system(command));
#else
	(void)command; // avoid unused parameter warning
	return synchronize_system_call_result(sc_system);
#endif
}



static FILE *fopen_helper(FILE *f, const char *mode, enum which_system_call system_call) {
#if __I_AM_SANITIZER1__
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
#if __I_AM_SANITIZER1__
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
#if __I_AM_SANITIZER1__
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
#if __I_AM_SANITIZER1__
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
#if __I_AM_SANITIZER1__
	if (!pathname || !mode || !stream) {
		(void)synchronize_system_call_result(sc_freopen, 0);
		return NULL;
	}
	int i;
	for (i = 0; i < FOPEN_MAX; i++) {
		if (file_cookies[i].cookie_stream == stream) {
			break;
		}
	}
	if (i == FOPEN_MAX) {
		debug_printf(0, "freopen can not find stream");
		__dcc_error_exit();
	}
	extern FILE *__real_freopen(const char *pathname, const char *mode, FILE *stream);
	FILE *f1 = __real_freopen(pathname, mode, file_cookies[i].stream);
	if (f1) {
		file_cookies[i].stream = f1;
		file_cookies[i].fd = fileno(f1);
		(void)synchronize_system_call_result(sc_freopen, 1);
		return file_cookies[i].cookie_stream;
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
#endif
