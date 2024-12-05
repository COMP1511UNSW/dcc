#define MEMORY_FILL_HEX 0xaa
#define MEMORY_FILL_STR "aa"
#define MEMORY_FILL_INT_STR "170"

static void launch_valgrind(int argc, char *argv[]) {
    debug_printf(2, "command=%s\n", "__MONITOR_VALGRIND__");
#if __N_SANITIZERS__ > 1
    extern FILE *__real_popen(const char *command, const char *type);
    FILE *valgrind_error_pipe = __real_popen("__MONITOR_VALGRIND__", "w");
#else
    FILE *valgrind_error_pipe = popen("__MONITOR_VALGRIND__", "w");
#endif
    int valgrind_error_fd = 2;
    if (valgrind_error_pipe) {
        fwrite(tar_data, sizeof tar_data[0],
               sizeof tar_data / sizeof tar_data[0], valgrind_error_pipe);
        fflush(valgrind_error_pipe);
        setbuf(valgrind_error_pipe, NULL);
        extern int __real_fileno(FILE *stream);
        valgrind_error_fd = (int)__real_fileno(valgrind_error_pipe);
    } else {
        debug_printf(2, "popen __MONITOR_VALGRIND__ failed");
        return;
    }
    setenvd("DCC_VALGRIND_RUNNING", "1");

    char fd_buffer[64];
    snprintf(fd_buffer, sizeof fd_buffer, "--log-fd=%d", valgrind_error_fd);
    const char *valgrind_command[] = { "/usr/bin/valgrind",
                                       fd_buffer,
                                       "-q",
                                       "--vgdb=yes",
                                       "--leak-check=__LEAK_CHECK_YES_NO__",
                                       "--show-leak-kinds=all",
                                       "--suppressions=__SUPRESSIONS_FILE__",
                                       "--max-stackframe=16000000",
                                       "--partial-loads-ok=no",
                                       "--malloc-fill=0x" MEMORY_FILL_STR,
                                       "--free-fill=0x" MEMORY_FILL_STR,
                                       "--vgdb-error=1",
                                       "--" };

    int valgrind_command_len =
        sizeof valgrind_command / sizeof valgrind_command[0];
    const char *valgrind_argv[valgrind_command_len + argc + 1];
    for (int i = 0; i < valgrind_command_len; i++) {
        valgrind_argv[i] = valgrind_command[i];
    }
    for (int i = 0; i < argc; i++) {
        valgrind_argv[valgrind_command_len + i] = argv[i];
    }

    valgrind_argv[valgrind_command_len + argc] = NULL;
    for (int i = 0; i < valgrind_command_len + argc; i++) {
        debug_printf(3, "valgrind_argv[%d] = %s\n", i, valgrind_argv[i]);
    }

    // assume valgrind is in /usr/bin so bad PATH or no PATH is (mostly) handled
    execvp("/usr/bin/valgrind", (char *const *)valgrind_argv);
    // but if exec fails look for it in PATH
    valgrind_command[0] = "valgrind";
    execvp("valgrind", (char *const *)valgrind_argv);
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
void __asan_on_error(void) NO_SANITIZE;

void __asan_on_error(void) {
    debug_printf(2, "__asan_on_error\n");

    const char *report = "";
#if __SANITIZER__ == ADDRESS && __CLANG_VERSION_MAJOR__ >= 6
    extern char *__asan_get_report_description();
    extern int __asan_report_present();
    extern void *__asan_get_report_address();
    extern size_t __asan_get_alloc_stack(void *, void **, size_t, int *);
    // putenv does not copy strings, we need to alloc it outside the if block scope
    char thread_env[64];
    if (__asan_report_present()) {
        report = __asan_get_report_description();

        int thread_id;
        __asan_get_alloc_stack(__asan_get_report_address(), NULL, 0, &thread_id);
        snprintf(thread_env, sizeof thread_env, "DCC_ASAN_THREAD=%d", thread_id);
        putenvd(thread_env);
    }
#endif
    char report_description[8192];
    snprintf(report_description, sizeof report_description, "DCC_ASAN_ERROR=%s",
             report);
    putenvd(report_description);

    _explain_error();
    // not reached
}

// intercept ASAN explanation
void _Unwind_Backtrace(void *a, ...) {
    (void)a; // avoid unused parameter warning
    debug_printf(2, "_Unwind_Backtrace\n");
    _explain_error();
}

#if __SANITIZER__ == ADDRESS
const char *__asan_default_options(void) {
    // NOTE setting detect_stack_use_after_return here stops
    // clear_stack pre-initializing stack frames to MEMORY_FILL_HEX

    return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=__LEAK_CHECK_1_0__:max_malloc_fill_size=4096000:quarantine_size_mb=16:verify_asan_link_order=0:detect_stack_use_after_return=__STACK_USE_AFTER_RETURN__:malloc_fill_byte=" MEMORY_FILL_INT_STR;
}
#endif

#if __SANITIZER__ == MEMORY
const char *__msan_default_options(void) {
    return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=__LEAK_CHECK_1_0__";
}
#endif

// intercept undefined sanitizer reports
// ubsan builds on Ubuntu don't seem to expose this function

void __ubsan_on_report(void) {
    debug_printf(2, "__ubsan_on_report\n");

#if __UNDEFINED_BEHAVIOUR_SANITIZER_IN_USE__ && __CLANG_VERSION_MAJOR__ >= 7
    char *OutIssueKind;
    char *OutMessage;
    char *OutFilename;
    unsigned int OutLine;
    unsigned int OutCol;
    char *OutMemoryAddr;
    extern void __ubsan_get_current_report_data(
        char **OutIssueKind, char **OutMessage, char **OutFilename,
        unsigned int *OutLine, unsigned int *OutCol, char **OutMemoryAddr);

    __ubsan_get_current_report_data(&OutIssueKind, &OutMessage, &OutFilename,
                                    &OutLine, &OutCol, &OutMemoryAddr);

    // buffer + putenv is ugly - but safer?
    char buffer[6][128];
    snprintf(buffer[0], sizeof buffer[0], "DCC_UBSAN_ERROR_KIND=%s",
             OutIssueKind);
    snprintf(buffer[1], sizeof buffer[1], "DCC_UBSAN_ERROR_MESSAGE=%s",
             OutMessage);
    snprintf(buffer[2], sizeof buffer[2], "DCC_UBSAN_ERROR_FILENAME=%s",
             OutFilename);
    snprintf(buffer[3], sizeof buffer[3], "DCC_UBSAN_ERROR_LINE=%u", OutLine);
    snprintf(buffer[4], sizeof buffer[4], "DCC_UBSAN_ERROR_COL=%u", OutCol);
    snprintf(buffer[5], sizeof buffer[5], "DCC_UBSAN_ERROR_MEMORYADDR=%s",
             OutMemoryAddr);
    for (int i = 0; i < (int)(sizeof buffer / sizeof buffer[0]); i++)
        putenv(buffer[i]);
#endif
    _explain_error();
    // not reached
}

#if __UNDEFINED_BEHAVIOUR_SANITIZER_IN_USE__
const char *__ubsan_default_options(void) {
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
    putenvd(
        signum_buffer); // less likely? to trigger another error than direct setenv

    char threadid_buffer[64];
    snprintf(threadid_buffer, sizeof threadid_buffer, "DCC_SIGNAL_THREAD=%ld", (long)gettid());
    putenvd(threadid_buffer);

    _explain_error(); // not reached
}

static const char *run_tar_file =
    "PATH=$PATH:/bin:/usr/bin:/usr/local/bin exec python3 -B -E -c \"import io,os,sys,tarfile,tempfile\n\
with tempfile.TemporaryDirectory() as temp_dir:\n\
  buffer = io.BytesIO(sys.stdin.buffer.raw.read())\n\
  buffer_length = len(buffer.getbuffer())\n\
  if not buffer_length:\n\
    sys.exit(1)\n\
  k = {'filter':'data'} if hasattr(tarfile, 'data_filter') else {}\n\
  tarfile.open(fileobj=buffer, bufsize=buffer_length, mode='r|xz').extractall(temp_dir, **k)\n\
  os.environ['DCC_PWD'] = os.getcwd()\n\
  os.chdir(temp_dir)\n\
  exec(open('start_gdb.py').read())\n\
\"";

static void _explain_error(void) {
#if __N_SANITIZERS__ > 1 && __I_AM_SANITIZER1__
    stop_sanitizer2();
#endif
    // if a program has exhausted file descriptors then we need to close some to run gdb etc,
    // so as a precaution we close a pile of file descriptors which may or may not be open
    for (int i = 4; i < 32; i++) {
        close(i);
    }

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
    size_t n_items = sizeof tar_data / sizeof tar_data[0];
    size_t items_written =
        fwrite(tar_data, sizeof tar_data[0], n_items, python_pipe);
    if (items_written != n_items) {
        debug_printf(1, "fwrite bad return %d returned %d expected\n",
                     (int)items_written, (int)n_items);
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
    
static void clear_stack(void)
#if __has_attribute(noinline)
    __attribute__((noinline))
#endif
#if __has_attribute(optnone)
    __attribute__((optnone))
#endif
    ;

    
static void quick_clear_stack(void)
#if __has_attribute(noinline)
    __attribute__((noinline))
#endif
#if __has_attribute(optnone)
    __attribute__((optnone))
#endif
    ;

// hack to initialize (most of) stack to MEMORY_FILL_HEX
// so uninitialized values are more obvious in output
//
// clang's -ftrivial-auto-var-init=pattern can't be used with valgrind
// this often, but not always, results in clear output of uninitialized values
//
// clangs's -ftrivial-auto-var-init=pattern only sets local variables
// but not other stack space so this is still is helpful when
// values from invalid accesses are printed


static void clear_stack(void) {
    char a[4096000];
    debug_printf(3, "initialized %p to %p\n", a, a + sizeof a);
    _memset_shim(a, MEMORY_FILL_HEX, sizeof a);
}

static void quick_clear_stack(void) {
    char a[256000];
    debug_printf(3, "initialized %p to %p\n", a, a + sizeof a);
    _memset_shim(a, MEMORY_FILL_HEX, sizeof a);
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
static void _memset_shim(void *p, int byte, size_t size) {
}
#endif

static void setenvd(const char *n, const char *v) {
    setenv(n, v, 1);
    debug_printf(2, "setenv %s=%s\n", n, v);
}

static void setenvd_int(const char *n, int v) {
    char buffer[64] = { 0 };
    snprintf(buffer, sizeof buffer, "%d", v);
    setenvd(n, buffer);
}

static void putenvd(const char *s) {
    putenv((char *)s);
    debug_printf(2, "putenv '%s'\n", s);
}

#ifndef debug_printf
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
#endif

#if __WRAP_POSIX_SPAWN__

#include <spawn.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

int __real_posix_spawn(pid_t *pid, const char *path,
                       const posix_spawn_file_actions_t *file_actions,
                       const posix_spawnattr_t *attrp, char *const argv[],
                       char *const envp[]) NO_SANITIZE;

int __real_posix_spawnp(pid_t *pid, const char *path,
                        const posix_spawn_file_actions_t *file_actions,
                        const posix_spawnattr_t *attrp, char *const argv[],
                        char *const envp[]) NO_SANITIZE;

static int
_dcc_posix_spawn_helper(int is_posix_spawn, pid_t *pid, const char *path,
                        const posix_spawn_file_actions_t *file_actions,
                        const posix_spawnattr_t *attrp, char *const argv[],
                        char *const envp[]) {
// if using ifdef instead of ld wrapping this if will process a compile-time warning
#ifndef __real_posix_spawn
    if (path == NULL) {
        putenvd(
            "DCC_ASAN_ERROR=Null pointer passed to posix_spawn as argument 2");
        _explain_error();
    }

    // fake branch on parameter values to trigger unitialized variable error
    // before clone, while  a stack backtrace via gdb will still work
    if (file_actions && *(const unsigned char *)file_actions && attrp &&
        *(const unsigned char *)attrp && argv && argv[0] && envp && envp[0]) {
    }
#endif
    if (is_posix_spawn) {
        // posix_spawn with valgrind-3.14.0 returns 0 if path can not be executed
        // crude work-around so it returns 2 as it does when executed directly

        struct stat s;
        if (stat(path, &s) == 0 && S_ISREG(s.st_mode) &&
            faccessat(AT_FDCWD, path, X_OK, AT_EACCESS) == 0) {
            return __real_posix_spawn(pid, path, file_actions, attrp, argv,
                                      envp);
        } else {
            return 2;
        }

    } else {
        return __real_posix_spawnp(pid, path, file_actions, attrp, argv, envp);
    }
}

int __wrap_posix_spawn(pid_t *pid, const char *path,
                       const posix_spawn_file_actions_t *file_actions,
                       const posix_spawnattr_t *attrp, char *const argv[],
                       char *const envp[]) {
    return _dcc_posix_spawn_helper(1, pid, path, file_actions, attrp, argv,
                                   envp);
}

int __wrap_posix_spawnp(pid_t *pid, const char *path,
                        const posix_spawn_file_actions_t *file_actions,
                        const posix_spawnattr_t *attrp, char *const argv[],
                        char *const envp[]) {
    return _dcc_posix_spawn_helper(0, pid, path, file_actions, attrp, argv,
                                   envp);
}

#endif

// over-ride some C library functions commonly used by novices in small programs
// because the glibc implementation dirty much of the stack
// and can prevent student geeting clear information about uninitialized variables
// scanf, fscanf can't be overridden

int fprintf(FILE *restrict stream, const char *restrict format, ...) {
	va_list args;
	va_start(args, format);
	int done = vfprintf(stream, format, args);
	va_end(args);
	quick_clear_stack();
	return done;
}

int printf(const char *restrict format, ...) {
	va_list args;
	va_start(args, format);
	int done = vfprintf(stdout, format, args);
	va_end(args);
	quick_clear_stack();
	return done;
}

size_t strlen(const char *s) {
	size_t length = 0;
	while (s[length] != '\0') {
		length++;
	}
	return length;
}

char *stpcpy(char *restrict dst, const char *restrict src) {
	char *d = dst;
	while (*src) {
		*d++ = *src++;
	}
	*d = '\0';
	return d;
}

char *strcpy(char *restrict dst, const char *restrict src) {
	char *d = dst;
	while (*src) {
		*d++ = *src++;
	}
	*d = '\0';
	return dst;
}

char *strcat(char *restrict dst, const char *restrict src) {
	char *d = dst;
	while (*d) {
		d++;
	}
	while (*src) {
		*d++ = *src++;
	}
	*d = '\0';
	return dst;
}

char *stpncpy(char *restrict dst, const char *restrict src, size_t sz) {
	char *d = dst;
	while (sz > 0 && *src) {
		*d++ = *src++;
		sz--;
	}
	if (sz > 0) {
		*d = '\0';
	}
	return d;
}

char *strncpy(char *restrict dst, const char *restrict src, size_t sz) {
	char *d = dst;
	while (sz > 0 && *src) {
		*d++ = *src++;
		sz--;
	}
	if (sz > 0) {
		*d = '\0';
	}
	return dst;
}

int strcmp(const char *s1, const char *s2) {
	while (*s1 && *s1 == *s2) {
		s1++;
		s2++;
	}
	return *(unsigned char *)s1 - *(unsigned char *)s2;
}

int strncmp(const char *s1, const char *s2, size_t n) {
	while (n > 0 && *s1 && *s1 == *s2) {
		s1++;
		s2++;
		n--;
	}
	if (n > 0) {
		return *(unsigned char *)s1 - *(unsigned char *)s2;
	} else {
		return 0;
	}
}

#include <limits.h>

size_t strcspn(const char *s, const char *reject) {
	const char *r = reject;
	unsigned char reject_set[UCHAR_MAX + 1] = {0};
	while (*r) {
		reject_set[(unsigned char)*r] = 1;
		r++;
	}
	const char *t = s;
	while (*t && !reject_set[(unsigned char)*t]) {
		t++;
	}
	_memset_shim(reject_set, MEMORY_FILL_HEX, sizeof reject_set);
	return t - s;
}

size_t strspn(const char *s, const char *accept) {
	const char *a = accept;
	unsigned char accept_set[UCHAR_MAX + 1] = {0};
	while (*a) {
		accept_set[(unsigned char)*a] = 1;
		a++;
	}
	const char *t = s;
	while (*t && accept_set[(unsigned char)*t]) {
		t++;
	}
	_memset_shim(accept_set, MEMORY_FILL_HEX, sizeof accept_set);
	return t - s;
}
