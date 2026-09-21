//
// C code to intercept runtime errors and run this program
//

#if !DCC_DEBUG_BUILD
#define debug_printf(...)
#endif

#undef _exit
#undef close
#undef execvp
#undef getpid
#undef lseek
#undef pipe
#undef read
#undef sleep
#undef unlink
#undef write

#define ADDRESS 			1
#define MEMORY				2
#define VALGRIND			3

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <unistd.h>
#include <stdint.h>
#include <stdarg.h>

#if DCC_N_SANITIZERS > 1
#include <pthread.h>
#include <sys/stat.h>
#include <sys/wait.h>
#endif

#include <sys/resource.h>

#ifdef __linux__
# include <sys/prctl.h>
# include <sys/syscall.h>
# include <ucontext.h>
#endif

static int debug_level = 0;
static FILE *debug_stream = NULL;


// The Python which explains errors, and in dual-sanitizer mode the second
// executable, are linked in as their own object file rather than written into
// this source as array initializers, which the compiler would have to parse
// on every compilation.  dcc defines these symbols around their contents.
extern const char dcc_tar_data[];
extern const char dcc_tar_data_end[];
#define DCC_TAR_N_BYTES ((size_t)(dcc_tar_data_end - dcc_tar_data))

extern const char dcc_sanitizer2_data[];
extern const char dcc_sanitizer2_data_end[];
#define DCC_SANITIZER2_N_BYTES ((size_t)(dcc_sanitizer2_data_end - dcc_sanitizer2_data))

// the exit status of a program stopped by an error dcc detected
//
// it is the same for every error and every combination of sanitizers, so that
// a marking script can tell a detected error from the program's own failure
// 141 is what a program killed by SIGPIPE reports, which is how dcc has
// always stopped a program in its most common configuration
#define DCC_ERROR_EXIT_STATUS 141

#if defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L
#define DCC_THREAD_LOCAL _Thread_local
#elif defined(__GNUC__)
#define DCC_THREAD_LOCAL __thread
#else
#define DCC_THREAD_LOCAL
#endif

// non-zero while a library function dcc overrides is running
//
// those functions clear the stack when they return, and they reach the stdio
// callbacks which would otherwise clear it again for the same call
static DCC_THREAD_LOCAL int __dcc_clearing_stack_suppressed;

// for functions & parameters only used in some builds of this code
#if __has_attribute(unused)
#define MAYBE_UNUSED __attribute__((unused))
#else
#define MAYBE_UNUSED
#endif

#if __has_attribute(no_sanitize)
#ifdef __clang__
#define NO_SANITIZE __attribute__((no_sanitize("address", "memory", "undefined")))
#else
#define NO_SANITIZE __attribute__((no_sanitize("address", "undefined")))
#endif
#else
#define NO_SANITIZE
#endif

int __wrap_main(int argc, char *argv[], char *envp[]) NO_SANITIZE;
int __real_main(int argc, char *argv[], char *envp[]);

//static void __dcc_start(void) __attribute__((constructor)) NO_SANITIZE;
static void __dcc_start(void) NO_SANITIZE;
void __dcc_error_exit(void) NO_SANITIZE __attribute__((noreturn));
static void __dcc_signal_handler(int signum) NO_SANITIZE;
static void __dcc_segv_handler(int signum, siginfo_t *info, void *context) NO_SANITIZE;
static char *fault_stack_pointer(void *context) NO_SANITIZE;
static long __dcc_gettid(void) NO_SANITIZE;
static void set_signals_default(void) NO_SANITIZE;
static void launch_valgrind(int argc, char *argv[]) NO_SANITIZE;
static void setenvd_int(const char *n, int v) NO_SANITIZE;
static void setenvd(const char *n, const char *v) NO_SANITIZE;
static void putenvd(const char *s) NO_SANITIZE;
#ifndef debug_printf
static int debug_printf(int level, const char *format, ...) NO_SANITIZE;
#endif
static void _explain_error(void) NO_SANITIZE __attribute__((noreturn));
static void clear_stack(void) NO_SANITIZE;
static void quick_clear_stack(void) NO_SANITIZE;
static int __dcc_run_sanitizer1(int argc, char *argv[]) MAYBE_UNUSED;
#if DCC_SANITIZER == ADDRESS
static void restore_sanitizer_report_fd(void) NO_SANITIZE;
#endif
#if DCC_N_SANITIZERS > 1 && DCC_I_AM_SANITIZER1
static void stop_sanitizer2_if_any(void) NO_SANITIZE;
#endif


#undef main


//
// any function which might appear in a user call stack
// should be prefaced with __dcc_ so it won't displayed in explanations
//

static void init_cookies(void);

#if DCC_N_SANITIZERS == 1

int __wrap_main(int argc, char *argv[], char *envp[]) {
	__dcc_start();
	(void)envp; // avoid unused parameter warning
	debug_stream = stderr;
	char *mypath = realpath(argv[0], NULL);
	if (mypath) {
		setenvd("DCC_BINARY", mypath);
		free(mypath);
	}
	DCC_SET_EMBEDDED_ENVIRONMENT_VARIABLES();
	return __dcc_run_sanitizer1(argc, argv);
}
#else

// -1 so that a failure to create them leaves no descriptor which could be
// closed or read by mistake: 0 would be the program's own stdin
static int to_sanitizer2_pipe[2] = { -1, -1 };
static int from_sanitizer2_pipe[2] = { -1, -1 };

// set while dcc forks a process of its own, so __dcc_forked_child can tell
// the student's fork from dcc's and leave dcc's alone
static volatile sig_atomic_t dcc_forking;

#if DCC_I_AM_SANITIZER2

int __wrap_main(int argc, char *argv[], char *envp[]) {
	__dcc_start();
	(void)envp; // avoid unused parameter warning
	debug_stream = stderr;
	// this executable is only meant to be run by the sanitizer1 executable
	char *pipe_to_child = getenv("DCC_PIPE_TO_CHILD");
	char *pipe_from_child = getenv("DCC_PIPE_FROM_CHILD");
	char *argv0 = getenv("DCC_ARGV0");
	if (!pipe_to_child || !pipe_from_child || !argv0) {
		fprintf(stderr, "%s: this program can not be run directly\n", argv[0]);
		exit(1);
	}
	to_sanitizer2_pipe[0] = atoi(pipe_to_child);
	from_sanitizer2_pipe[1] = atoi(pipe_from_child);
	argv[0] = argv0;
	init_cookies();
	clear_stack();
	extern char **environ;
	int r = __real_main(argc, argv, environ);
	debug_printf(2, "__real_main exiting %d\n", r);
	exit(r);
	return 1; // not reached
}

#else

static pid_t sanitizer2_pid;

// set in the process forked to become sanitizer2, before any signal can reach it
//
// that process is still executing sanitizer1's code, in which the compile-time
// DCC_I_AM_SANITIZER1 is true and sanitizer2_pid is still 0, so a signal
// arriving there would have it kill(0, ...) the whole process group
static volatile sig_atomic_t i_am_sanitizer2;

static void __dcc_main_sanitizer1(int argc, char *argv[]) NO_SANITIZE;
static void __dcc_main_sanitizer2(int argc, char *argv[], const char *sanitizer2_executable_pathname) NO_SANITIZE;

int __wrap_main(int argc, char *argv[], char *envp[]) {
	__dcc_start();
	(void)envp; // avoid unused parameter warning
	extern char **environ;
	char *mypath = realpath(argv[0], NULL);
	if (mypath) {
		setenvd("DCC_BINARY", mypath);
		free(mypath);
	}
	DCC_SET_EMBEDDED_ENVIRONMENT_VARIABLES();
	debug_stream = stderr;
	if (pipe(to_sanitizer2_pipe) != 0) {
		debug_printf(1, "pipe failed");
		stop_sanitizer2_if_any();
		return __real_main(argc, argv, environ);
	}
	if (pipe(from_sanitizer2_pipe) != 0) {
		debug_printf(1, "pipe failed");
		stop_sanitizer2_if_any();
		return __real_main(argc, argv, environ);
	}

	char sanitizer2_executable_pathname[] = "/tmp/dcc-XXXXXX";
	int sanitizer2_executable_fd = mkstemp(sanitizer2_executable_pathname);
	if (sanitizer2_executable_fd < 0) {
		debug_printf(1, "mkostemp failed");
		stop_sanitizer2_if_any();
		__dcc_error_exit();
	}
	chmod(sanitizer2_executable_pathname, S_IRWXU);
	setenvd("DCC_UNLINK", sanitizer2_executable_pathname);
	ssize_t n_bytes_written = write(sanitizer2_executable_fd, dcc_sanitizer2_data, DCC_SANITIZER2_N_BYTES);
	if (n_bytes_written != (ssize_t)DCC_SANITIZER2_N_BYTES) {
		debug_printf(1, "write sanitizer2_executable %d != %d\n", (int)n_bytes_written, (int)DCC_SANITIZER2_N_BYTES);
		stop_sanitizer2_if_any();
		__dcc_error_exit();
	}
	close(sanitizer2_executable_fd);
	setenvd_int("DCC_SANITIZER1_PID", (int)getpid());
	// the signals sanitizer1 uses to stop sanitizer2 are blocked across the
	// fork, because until the child has recorded that it is sanitizer2 it
	// would handle one of them as sanitizer1 and signal the process group
	//
	// the sets are static so this function's frame stays the size it was and
	// the frames below it, the student's main among them, stay where they were
	static sigset_t stop_signals, signals_before_fork;
	sigemptyset(&stop_signals);
	sigaddset(&stop_signals, SIGPIPE);
	sigaddset(&stop_signals, SIGUSR1);
	sigprocmask(SIG_BLOCK, &stop_signals, &signals_before_fork);
	dcc_forking = 1;
	sanitizer2_pid = fork();
	dcc_forking = 0;
	if (sanitizer2_pid < 0) {
		sigprocmask(SIG_SETMASK, &signals_before_fork, NULL);
		debug_printf(1, "fork failed");
		stop_sanitizer2_if_any();
		return __real_main(argc, argv, environ);
	} else if (sanitizer2_pid == 0) {
		pid_t pid = getpid();
		i_am_sanitizer2 = 1;
		setenvd_int("DCC_PID", pid);
		setenvd_int("DCC_SANITIZER2_PID", pid);
		sanitizer2_pid = pid;
		// the mask is inherited through the exec below, so it must be restored
		sigprocmask(SIG_SETMASK, &signals_before_fork, NULL);
		__dcc_main_sanitizer2(argc, argv, sanitizer2_executable_pathname);
	} else {
		sigprocmask(SIG_SETMASK, &signals_before_fork, NULL);
		setenvd_int("DCC_SANITIZER2_PID", sanitizer2_pid);
		__dcc_main_sanitizer1(argc, argv);
	}
	return 1; // not reached
}


static void __dcc_main_sanitizer1(int argc, char *argv[]) {
	debug_printf(2, "main sanitizer1\n");
	close(to_sanitizer2_pipe[0]);
	close(from_sanitizer2_pipe[1]);

	exit(__dcc_run_sanitizer1(argc, argv));
}


static void __dcc_main_sanitizer2(int argc, char *argv[], const char *sanitizer2_executable_pathname) {
	debug_printf(2, "main sanitizer2\n");
	close(to_sanitizer2_pipe[1]);
	close(from_sanitizer2_pipe[0]);
	setenvd_int("DCC_PIPE_TO_CHILD", to_sanitizer2_pipe[0]);
	setenvd_int("DCC_PIPE_FROM_CHILD", from_sanitizer2_pipe[1]);
	setenvd("DCC_ARGV0", argv[0]);
	setenvd("DCC_BINARY", sanitizer2_executable_pathname);

#if DCC_SANITIZER_2 != VALGRIND
	execvp(sanitizer2_executable_pathname, argv);
	debug_printf(1, "execvp %s failed", sanitizer2_executable_pathname);
#else
	argv[0] = (char *)sanitizer2_executable_pathname;
	launch_valgrind(argc, argv);
#endif
	exit(1);
}
#endif
#endif



static int __dcc_run_sanitizer1(int argc, char *argv[]) {
	extern char **environ;
#if DCC_SANITIZER != VALGRIND
	init_cookies();
	clear_stack();
	int r = __real_main(argc, argv, environ);

	// in some circumstances leaks are not detected without this call
	// the non-recoverable check is used so that leaks are reported only once:
	// it exits if leaks are found and stops the check at exit repeating them
#if DCC_LEAK_CHECK && DCC_SANITIZER == ADDRESS
	extern void __lsan_do_leak_check(void);
	// the leak report is the sanitizer's own output and is meant for the student
	restore_sanitizer_report_fd();
	__lsan_do_leak_check();
#endif

	debug_printf(2, "__real_main returning %d\n", r);
	return r;
#else
	int valgrind_running = getenv("DCC_VALGRIND_RUNNING") != NULL;
	debug_printf(2, "__wrap_main(valgrind_running=%d)\n", valgrind_running);

	if (valgrind_running) {
		// valgrind errors get reported earlier if we unbuffer stdout
		// otherwise uninitialized variables may not be detected until fflush when program exits
		// which produces poor error message
		init_cookies();
		debug_printf(2, "running __real_main\n");
		clear_stack();
		int r = __real_main(argc, argv, environ);
		debug_printf(2, "__real_main returning %d\n", r);
		return r;
	}
	launch_valgrind(argc, argv);
	// if exec fails run program directly
	int r = __real_main(argc, argv, environ);
	debug_printf(2, "__real_main returning %d\n", r);
	return r;
#endif
}

