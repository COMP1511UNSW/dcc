
static void launch_valgrind(int argc, char *argv[], char *envp[]) {
	debug_printf(2, "command=%s\n", "__MONITOR_VALGRIND__");
#if __N_SANITIZERS__ > 1
	extern FILE *__real_popen(const char *command, const char *type);
	FILE *valgrind_error_pipe = __real_popen("__MONITOR_VALGRIND__", "w");
#else
	FILE *valgrind_error_pipe = popen("__MONITOR_VALGRIND__", "w");
#endif
	int valgrind_error_fd = 2;
	if (valgrind_error_pipe) {
		fwrite(tar_data, sizeof tar_data[0],  sizeof tar_data/sizeof tar_data[0], valgrind_error_pipe);
		fflush(valgrind_error_pipe);
		setbuf(valgrind_error_pipe, NULL);
		valgrind_error_fd = (int)fileno(valgrind_error_pipe);
	} else {
		debug_printf(2, "popen __MONITOR_VALGRIND__ failed");
		return;
	}
	setenvd("DCC_VALGRIND_RUNNING", "1");

	char fd_buffer[64];
	snprintf(fd_buffer, sizeof fd_buffer, "--log-fd=%d", valgrind_error_fd);
	char *valgrind_command[] = {
		"/usr/bin/valgrind",
		fd_buffer,
		"-q",
		"--vgdb=yes",
		"--leak-check=__LEAK_CHECK_YES_NO__",
		"--suppressions=__SUPRESSIONS_FILE__",
		"--max-stackframe=16000000",
		"--partial-loads-ok=no",
		"--malloc-fill=0xbe",
		"--free-fill=0xbe",
		 "--vgdb-error=1"
	};

	int valgrind_command_len = sizeof valgrind_command / sizeof valgrind_command[0];
	char *valgrind_argv[valgrind_command_len + argc + 1];
	for (int i = 0; i < valgrind_command_len; i++)
		valgrind_argv[i] = valgrind_command[i];
	for (int i = 0; i < argc; i++)
		valgrind_argv[valgrind_command_len + i] = argv[i];

	valgrind_argv[valgrind_command_len + argc] = NULL;
	for (int i = 0; i < valgrind_command_len + argc; i++)
		debug_printf(3, "valgrind_argv[%d] = %s\n", i, valgrind_argv[i]);

	// assume valgrind is in /usr/bin so bad PATH or no PATH is (mostly) handled
	execvp("/usr/bin/valgrind", valgrind_argv);
	// but if exec fails look for it in PATH
	valgrind_command[0] = "valgrind";
	execvp("valgrind", valgrind_argv);
	debug_printf(1, "execvp of /usr/bin/valgrind failed");
}


static void __dcc_start(void) {
	char *debug_level_string = getenv("DCC_DEBUG");
	if (debug_level_string) {
		debug_level = atoi(debug_level_string);
	}
	debug_printf(2, "__dcc_start debug_level=%d\n", debug_level);

	setenvd("DCC_SANITIZER", "__SANITIZER__");
	setenvd("DCC_PATH", "__PATH__");

	setenvd_int("DCC_PID", getpid());

	signal(SIGABRT, __dcc_signal_handler);
	signal(SIGSEGV, __dcc_signal_handler);
	signal(SIGINT, __dcc_signal_handler);
	signal(SIGXCPU, __dcc_signal_handler);
	signal(SIGXFSZ, __dcc_signal_handler);
	signal(SIGFPE, __dcc_signal_handler);
	signal(SIGILL, __dcc_signal_handler);
#if __N_SANITIZERS__ > 1
	signal(SIGPIPE, __dcc_signal_handler);
	signal(SIGUSR1, __dcc_signal_handler);
#endif
	clear_stack();
}

static void disable_check_output();
void __dcc_error_exit(void) {
	disable_check_output();
	debug_printf(2, "__dcc_error_exit()\n");

#if __N_SANITIZERS__ > 1
	__dcc_cleanup_before_exit();
#endif

#if __SANITIZER__ != VALGRIND
	// use kill instead of exit or _exit because
	// exit or _exit keeps executing sanitizer code - including perhaps superfluous output
	// but not with valgrind which will catch signal and start gdb
	// SIGPIPE avoids killed message from bash
	signal(SIGPIPE, SIG_DFL);
	kill(getpid(), SIGPIPE);
#endif

	_exit(1);
}

// is __asan_on_error  address sanitizer only??
//
// intercept ASAN explanation
void __asan_on_error() NO_SANITIZE;

void __asan_on_error() {
	debug_printf(2, "__asan_on_error\n");

	char *report = "";
#if __SANITIZER__ == ADDRESS && __CLANG_VERSION_MAJOR__ >= 6
	extern char *__asan_get_report_description();
	extern int __asan_report_present();
	if (__asan_report_present()) {
		report = __asan_get_report_description();
	}
#endif
	char report_description[8192];
	snprintf(report_description, sizeof report_description, "DCC_ASAN_ERROR=%s", report);
	putenvd(report_description);

	_explain_error();
	// not reached
}

// intercept ASAN explanation
void _Unwind_Backtrace(void *a, ...) {
	debug_printf(2, "_Unwind_Backtrace\n");
	_explain_error();
}

#if __SANITIZER__ == ADDRESS
char *__asan_default_options() {

	// NOTE setting detect_stack_use_after_return here stops
	// clear_stack pre-initializing stack frames to 0xbe

	return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=__LEAK_CHECK_1_0__:max_malloc_fill_size=4096000:quarantine_size_mb=16:verify_asan_link_order=0:detect_stack_use_after_return=__STACK_USE_AFTER_RETURN__";
}
#endif

#if __SANITIZER__ == MEMORY
char *__msan_default_options() {
	return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=__LEAK_CHECK_1_0__";
}
#endif

void __ubsan_on_report(void) {
	debug_printf(2, "__ubsan_on_report\n");

#if __UNDEFINED_BEHAVIOUR_SANITIZER_IN_USE__ && __CLANG_VERSION_MAJOR__ >= 7
	char *OutIssueKind;
	char *OutMessage;
	char *OutFilename;
	unsigned int OutLine;
	unsigned int OutCol;
	char *OutMemoryAddr;
	extern void __ubsan_get_current_report_data(char **OutIssueKind, char **OutMessage, char **OutFilename, unsigned int *OutLine, unsigned int *OutCol, char **OutMemoryAddr);

	__ubsan_get_current_report_data(&OutIssueKind, &OutMessage, &OutFilename, &OutLine, &OutCol, &OutMemoryAddr);

	// buffer + putenv is ugly - but safer?
	char buffer[6][128];
	snprintf(buffer[0], sizeof buffer[0], "DCC_UBSAN_ERROR_KIND=%s", OutIssueKind);
	snprintf(buffer[1], sizeof buffer[1], "DCC_UBSAN_ERROR_MESSAGE=%s", OutMessage);
	snprintf(buffer[2], sizeof buffer[2], "DCC_UBSAN_ERROR_FILENAME=%s", OutFilename);
	snprintf(buffer[3], sizeof buffer[3], "DCC_UBSAN_ERROR_LINE=%u", OutLine);
	snprintf(buffer[4], sizeof buffer[4], "DCC_UBSAN_ERROR_COL=%u", OutCol);
	snprintf(buffer[5], sizeof buffer[5], "DCC_UBSAN_ERROR_MEMORYADDR=%s", OutMemoryAddr);
	for (int i = 0; i < sizeof buffer/sizeof buffer[0]; i++)
		putenv(buffer[i]);
#endif
	_explain_error();
	// not reached
}

#if __UNDEFINED_BEHAVIOUR_SANITIZER_IN_USE__
char *__ubsan_default_options() {
	return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=__LEAK_CHECK_1_0__";
}
#endif

static void set_signals_default(void) {
	debug_printf(2, "set_signals_default()\n");
	signal(SIGABRT, SIG_DFL);
	signal(SIGSEGV, SIG_DFL);
	signal(SIGINT, SIG_DFL);
	signal(SIGXCPU, SIG_DFL);
	signal(SIGXFSZ, SIG_DFL);
	signal(SIGFPE, SIG_DFL);
	signal(SIGILL, SIG_DFL);
#if __N_SANITIZERS__ > 1
	signal(SIGPIPE, SIG_DFL);
	signal(SIGUSR1, SIG_IGN);
#endif
}

static void __dcc_signal_handler(int signum) {
	debug_printf(2, "received signal %d\n", signum);
	set_signals_default();
#if __N_SANITIZERS__ > 1
#if __I_AM_SANITIZER1__
	if (signum == SIGPIPE) {
		if (!synchronization_terminated) {
			stop_sanitizer2();
		} else {
			__dcc_error_exit();
		}
	} else if (signum == SIGUSR1) {
		__dcc_error_exit();
	}
#else
	__dcc_error_exit();
#endif
#endif

	char signum_buffer[64];
	snprintf(signum_buffer, sizeof signum_buffer, "DCC_SIGNAL=%d", (int)signum);
	putenvd(signum_buffer); // less likely? to trigger another error than direct setenv

	_explain_error();// not reached
}

static char *run_tar_file = "PATH=$PATH:/bin:/usr/bin:/usr/local/bin python3 -B -E -c \"import io,os,sys,tarfile,tempfile\n\
with tempfile.TemporaryDirectory() as temp_dir:\n\
  buffer = io.BytesIO(sys.stdin.buffer.raw.read())\n\
  buffer_length = len(buffer.getbuffer())\n\
  if not buffer_length:\n\
    sys.exit(1)\n\
  tarfile.open(fileobj=buffer, bufsize=buffer_length, mode='r|xz').extractall(temp_dir)\n\
  os.chdir(temp_dir)\n\
  exec(open('start_gdb.py').read())\n\
\"";

static void _explain_error(void) {
#if __N_SANITIZERS__ > 1 && __I_AM_SANITIZER1__
	stop_sanitizer2();
#endif
	// if a program has exhausted file descriptors then we need to close some to run gdb etc,
	// so as a precaution we close a pile of file descriptors which may or may not be open
	for (int i = 4; i < 32; i++)
		close(i);

#ifdef __linux__
    // ensure gdb can ptrace binary
	// https://www.kernel.org/doc/Documentation/security/Yama.txt
	prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY);
#endif

	debug_printf(2, "running %s\n", run_tar_file);
#if __N_SANITIZERS__ > 1
	extern FILE *__real_popen(const char *command, const char *type);
	FILE *python_pipe = __real_popen(run_tar_file, "w");
#else
	FILE *python_pipe = popen(run_tar_file, "w");
#endif
	size_t n_items = sizeof tar_data/sizeof tar_data[0];
	size_t items_written = fwrite(tar_data, sizeof tar_data[0], n_items, python_pipe);
	if (items_written != n_items) {
		debug_printf(1, "fwrite bad return %d returned %d expected\n", (int)items_written, (int)n_items);
	}
	pclose(python_pipe);
	__dcc_error_exit();
}

#if !__STACK_USE_AFTER_RETURN__
static void _memset_shim(void *p, int byte, size_t size) NO_SANITIZE
#if __has_attribute(noinline)
__attribute__((noinline))
#endif
#if __has_attribute(optnone)
__attribute__((optnone))
#endif
;


// hack to initialize (most of) stack to 0xbe
// so uninitialized variables are more obvious

static void clear_stack(void) {
	char a[4096000];
	debug_printf(3, "initialized %p to %p\n", a, a + sizeof a);
	_memset_shim(a, 0xbe, sizeof a);
}

static void quick_clear_stack(void) {
	char a[256000];
	debug_printf(3, "initialized %p to %p\n", a, a + sizeof a);
	_memset_shim(a, 0xbe, sizeof a);
}


// hide memset in a function with optimization turned off
// to avoid calls being removed by optimizations
static void _memset_shim(void *p, int byte, size_t size) {
	memset(p, byte, size);
}
#else
static void clear_stack(void) {
}
static void quick_clear_stack(void) {
}
#endif

static void setenvd(char *n, char *v) {
	setenv(n, v, 1);
	debug_printf(2, "setenv %s=%s\n", n, v);
}

static void setenvd_int(char *n, int v) {
	char buffer[64] = {0};
	snprintf(buffer, sizeof buffer, "%d", v);
	setenvd(n, buffer);
}

static void putenvd(char *s) {
	putenv(s);
	debug_printf(2, "putenv '%s'\n", s);
}

static int debug_printf(int level, const char *format, ...) {
	if (level > debug_level) {
		return 0;
	}
#if __N_SANITIZERS__ > 1
	fprintf(debug_stream ? debug_stream : stderr, "__WHICH_SANITIZER__: ");
#if __I_AM_SANITIZER2__
	fprintf(debug_stream ? debug_stream : stderr, "\t");
#endif
#endif
    va_list arg;
    va_start(arg, format);
    int n = vfprintf(debug_stream ? debug_stream : stderr, format, arg);
    va_end(arg);
    return n;
}

#if __WRAP_POSIX_SPAWN__

// posix_spawn with valgrind-3.14.0 returns 0 if path can not be executed
// crude work-around so it returns 2 as it does when executed directly

#include <spawn.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h> 

int __real_posix_spawn(pid_t *pid, const char *path,
                       const posix_spawn_file_actions_t *file_actions,
                       const posix_spawnattr_t *attrp,
                       char *const argv[], char *const envp[]) NO_SANITIZE;

int __wrap_posix_spawn(pid_t *pid, const char *path,
                       const posix_spawn_file_actions_t *file_actions,
                       const posix_spawnattr_t *attrp,
                       char *const argv[], char *const envp[]) {

// if using ifdef instead of ld wrapping this if will process a compile-time warning
#ifndef __real_posix_spawn
	if (path == NULL) {
		putenvd("DCC_ASAN_ERROR=Null pointer passed to posix_spawn as argument 2");
		_explain_error();
	}
	// fake branch on parameter values to trigger unitialized variable error
	// before clone, so we can get a stack backtrace
	if (
		(file_actions && *(unsigned char *)file_actions != *(unsigned char *)file_actions) ||
		(attrp && *(unsigned char *)attrp != *(unsigned char *)attrp) ||
		(argv && argv[0] != argv[0]) ||
		(envp && envp[0] != envp[0])
		)
		 {
	}
#endif
    struct stat s;
 	if (stat(path, &s) == 0 &&
        S_ISREG(s.st_mode) &&
        faccessat(AT_FDCWD, path, X_OK, AT_EACCESS) == 0) {
    		return __real_posix_spawn(pid, path, file_actions, attrp, argv, envp);
    } else {
    	return 2;
    }

}

int __real_posix_spawnp(pid_t *pid, const char *path,
                       const posix_spawn_file_actions_t *file_actions,
                       const posix_spawnattr_t *attrp,
                       char *const argv[], char *const envp[]) NO_SANITIZE;

int __wrap_posix_spawnp(pid_t *pid, const char *path,
                       const posix_spawn_file_actions_t *file_actions,
                       const posix_spawnattr_t *attrp,
                       char *const argv[], char *const envp[]) {

// if using ifdef instead of ld wrapping this if will process a compile-time warning
#ifndef __real_posix_spawnp
	if (path == NULL) {
		putenvd("DCC_ASAN_ERROR=Null pointer passed to posix_spawn as argument 2");
		_explain_error();
	}
	// fake branch on parameter values to trigger unitialized variable error
	// before clone, so we can get a stack backtrace
	if (
		(file_actions && *(unsigned char *)file_actions != *(unsigned char *)file_actions) ||
		(attrp && *(unsigned char *)attrp != *(unsigned char *)attrp) ||
		(argv && argv[0] != argv[0]) ||
		(envp && envp[0] != envp[0])
		)
		 {
	}
#endif
    struct stat s;
 	if (stat(path, &s) == 0 &&
        S_ISREG(s.st_mode) &&
        faccessat(AT_FDCWD, path, X_OK, AT_EACCESS) == 0) {
    		return __real_posix_spawnp(pid, path, file_actions, attrp, argv, envp);
    } else {
    	return 2;
    }

}


#endif
