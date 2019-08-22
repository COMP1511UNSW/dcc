//
// C code to intercept runtime errors and run this program
//

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

// to get fopencookie
#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <signal.h>
#include <unistd.h>
#include <stdint.h>

#if __N_SANITIZERS__ > 1
#include <sys/stat.h>
#include <sys/wait.h>
#endif

#ifdef __linux__
# include <sys/prctl.h>
#endif

static int debug_level = 0;
static FILE *debug_stream = NULL;

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

static void __dcc_start(void) __attribute__((constructor)) NO_SANITIZE;
void __dcc_error_exit(void) NO_SANITIZE;
static void __dcc_signal_handler(int signum) NO_SANITIZE;
static void set_signals_default(void) NO_SANITIZE;
static void launch_valgrind(int argc, char *argv[], char *envp[]) NO_SANITIZE;
static void setenvd_int(char *n, int v) NO_SANITIZE;
static void setenvd(char *n, char *v) NO_SANITIZE;
static void putenvd(char *s) NO_SANITIZE;
static int debug_printf(int level, const char *format, ...) NO_SANITIZE;
static void _explain_error(void) NO_SANITIZE;
static void clear_stack(void) NO_SANITIZE;
static void quick_clear_stack(void) NO_SANITIZE;
static int __dcc_run_sanitizer1(int argc, char *argv[], char *envp[]);


#undef main


//
// any function which might appear in a user call stack
// should be prefaced with __dcc_ so it won't
// displayed in user calls stack
//

static void init_cookies(void);

#if __N_SANITIZERS__ == 1

int __wrap_main(int argc, char *argv[], char *envp[]) {
	char *mypath = realpath(argv[0], NULL);
	if (mypath) {
		setenvd("DCC_BINARY", mypath);
		free(mypath);
	}
	return __dcc_run_sanitizer1(argc, argv, envp);
}
#else

static int to_sanitizer2_pipe[2];
static int from_sanitizer2_pipe[2];

#if __I_AM_SANITIZER2__

int __wrap_main(int argc, char *argv[], char *envp[]) {
	debug_stream = stderr;
	to_sanitizer2_pipe[0] = atoi(getenv("DCC_PIPE_TO_CHILD"));
	from_sanitizer2_pipe[1] = atoi(getenv("DCC_PIPE_FROM_CHILD"));
	argv[0] = getenv("DCC_ARGV0");
	init_cookies();
	clear_stack();
	exit(__real_main(argc, argv, envp));
	return 1; // not reached
}

#else

static pid_t sanitizer2_pid;

static void __dcc_main_sanitizer1(int argc, char *argv[], char *envp[]) NO_SANITIZE;
static void __dcc_main_sanitizer2(int argc, char *argv[], char *envp[], char *sanitizer2_executable_pathname) NO_SANITIZE;

int __wrap_main(int argc, char *argv[], char *envp[]) {
	char *mypath = realpath(argv[0], NULL);
	if (mypath) {
		setenvd("DCC_BINARY", mypath);
		free(mypath);
	}
	debug_stream = stderr;
	if (pipe(to_sanitizer2_pipe) != 0) {
		debug_printf(1, "pipe failed");
		return __real_main(argc, argv, envp);
	}
	if (pipe(from_sanitizer2_pipe) != 0) {
		debug_printf(1, "pipe failed");
		return __real_main(argc, argv, envp);
	}

	char sanitizer2_executable_pathname[] = "/tmp/dcc-XXXXXX";
	int sanitizer2_executable_fd = mkstemp(sanitizer2_executable_pathname);
	if (sanitizer2_executable_fd < 0) {
		debug_printf(1, "mkostemp failed");
		__dcc_error_exit();
	}
	chmod(sanitizer2_executable_pathname, S_IRWXU);
	setenvd("DCC_UNLINK", sanitizer2_executable_pathname);
	int n_bytes_written = write(sanitizer2_executable_fd, sanitizer2_executable, __EXECUTABLE_N_BYTES__);
	if (n_bytes_written != __EXECUTABLE_N_BYTES__) {
		debug_printf(1, "write sanitizer2_executable %d != %d\n", n_bytes_written, __EXECUTABLE_N_BYTES__);
		__dcc_error_exit();
	}
	close(sanitizer2_executable_fd);
	setenvd_int("DCC_SANITIZER1_PID", (int)getpid());
	sanitizer2_pid = fork();
	if (sanitizer2_pid < 0) {
		debug_printf(1, "fork failed");
		return __real_main(argc, argv, envp);
	} else if (sanitizer2_pid == 0) {
		pid_t pid = getpid();
		setenvd_int("DCC_PID", pid);
		setenvd_int("DCC_SANITIZER2_PID", pid);
		sanitizer2_pid = pid;
		__dcc_main_sanitizer2(argc, argv, envp, sanitizer2_executable_pathname);
	} else {
		setenvd_int("DCC_SANITIZER2_PID", sanitizer2_pid);
		__dcc_main_sanitizer1(argc, argv, envp);
	}
	return 1; // not reached
}


static void __dcc_main_sanitizer1(int argc, char *argv[], char *envp[]) {
	debug_printf(2, "main sanitizer1\n");
	close(to_sanitizer2_pipe[0]);
	close(from_sanitizer2_pipe[1]);

	exit(__dcc_run_sanitizer1(argc, argv, envp));
}


static void __dcc_main_sanitizer2(int argc, char *argv[], char *envp[], char *sanitizer2_executable_pathname) {
	debug_printf(2, "main sanitizer2\n");
	close(to_sanitizer2_pipe[1]);
	close(from_sanitizer2_pipe[0]);
	setenvd_int("DCC_PIPE_TO_CHILD", to_sanitizer2_pipe[0]);
	setenvd_int("DCC_PIPE_FROM_CHILD", from_sanitizer2_pipe[1]);
	setenvd("DCC_ARGV0", argv[0]);
	setenvd("DCC_BINARY", sanitizer2_executable_pathname);

#if __SANITIZER_2__ != VALGRIND
	execvp(sanitizer2_executable_pathname, argv);
	debug_printf(1, "execvp %s failed", sanitizer2_executable_pathname);
#else
	argv[0] = sanitizer2_executable_pathname;
	launch_valgrind(argc, argv, envp);
#endif
	exit(1);
}
#endif
#endif



static int __dcc_run_sanitizer1(int argc, char *argv[], char *envp[]) {
#if __SANITIZER__ != VALGRIND
	init_cookies();
	clear_stack();
	int r = __real_main(argc, argv, envp);

	// in some circumstances leaks are not detected without this call
#if __LEAK_CHECK_1_0__ && __SANITIZER__ == ADDRESS
	extern int __lsan_do_recoverable_leak_check();
	__lsan_do_recoverable_leak_check();
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
		int r = __real_main(argc, argv, envp);
		debug_printf(2, "__real_main returning %d\n", r);
		return r;
	}
	launch_valgrind(argc, argv, envp);
	// if exec fails run program directly
	int r = __real_main(argc, argv, envp);
	debug_printf(2, "__real_main returning %d\n", r);
	return r;
#endif
}

