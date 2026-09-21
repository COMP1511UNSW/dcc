#define MEMORY_FILL_HEX 0xaa
#define MEMORY_FILL_STR "aa"
#define MEMORY_FILL_INT_STR "170"

// only used when valgrind is one of the sanitizers
static void launch_valgrind(int argc, char *argv[]) MAYBE_UNUSED;
static void launch_valgrind(int argc, char *argv[]) {
    debug_printf(2, "command=%s\n", DCC_MONITOR_VALGRIND);
    // the watcher reads exactly this many bytes of tar file from its stdin
    setenvd_int("DCC_TAR_N_BYTES", (int)DCC_TAR_N_BYTES);
#if DCC_N_SANITIZERS > 1
    extern FILE *__real_popen(const char *command, const char *type);
    dcc_forking = 1;
    FILE *valgrind_error_pipe = __real_popen(DCC_MONITOR_VALGRIND, "w");
    dcc_forking = 0;
#else
    FILE *valgrind_error_pipe = popen(DCC_MONITOR_VALGRIND, "w");
#endif
    int valgrind_error_fd = 2;
    if (valgrind_error_pipe) {
        fwrite(dcc_tar_data, 1, DCC_TAR_N_BYTES, valgrind_error_pipe);
        fflush(valgrind_error_pipe);
        setbuf(valgrind_error_pipe, NULL);
        extern int __real_fileno(FILE *stream);
        valgrind_error_fd = (int)__real_fileno(valgrind_error_pipe);
    } else {
        debug_printf(2, "popen %s failed", DCC_MONITOR_VALGRIND);
        return;
    }
    setenvd("DCC_VALGRIND_RUNNING", "1");

    char fd_buffer[64];
    snprintf(fd_buffer, sizeof fd_buffer, "--log-fd=%d", valgrind_error_fd);
    const char *valgrind_command[] = { "/usr/bin/valgrind",
                                       fd_buffer,
                                       "-q",
                                       "--vgdb=yes",
                                       "--leak-check=" DCC_LEAK_CHECK_YES_NO,
                                       "--show-leak-kinds=all",
                                       "--suppressions=" DCC_SUPPRESSIONS_FILE,
                                       "--max-stackframe=16000000",
                                       "--partial-loads-ok=no",
                                       "--malloc-fill=0x" MEMORY_FILL_STR,
                                       "--free-fill=0x" MEMORY_FILL_STR,
                                       "--vgdb-error=1",
                                       "--error-exitcode=" DCC_STRINGIFY(
                                           DCC_ERROR_EXIT_STATUS),
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

// an address near the top of the stack, used to recognize a stack overflow
static char *stack_top;

// the thread stack_top belongs to
static long main_thread_id;

#if DCC_N_SANITIZERS > 1
// a program which forks leaves the child a copy of sanitizer2_pid, and the
// child running exit or returning from main would then have its cleanup wait
// for and kill its parent's sanitizer2, ending the checking the parent is
// still relying on
static void __dcc_forked_child(void) NO_SANITIZE;
static void __dcc_forked_child(void) {
    if (dcc_forking) {
        // dcc's own fork, which is about to exec, and which needs what it
        // inherited
        return;
    }
#if DCC_I_AM_SANITIZER1
    sanitizer2_killed = 1;
#endif
    // the same cleanup unlinks the pathname in DCC_UNLINK, which is the
    // executable sanitizer2 is still running and the one gdb is given to
    // explain an error in it; the value is emptied rather than unset because
    // unsetenv takes a lock which a fork from a thread can leave held
    char *sanitizer2_executable_pathname = getenv("DCC_UNLINK");
    if (sanitizer2_executable_pathname) {
        *sanitizer2_executable_pathname = '\0';
    }
}
#endif

#if DCC_SANITIZER == ADDRESS
static void restore_sanitizer_report_fd(void) {
    extern void __sanitizer_set_report_fd(void *fd);
    __sanitizer_set_report_fd((void *)(intptr_t)2);
}

// compiler-rt prints a line of 65 '=' characters before it calls
// __asan_on_error, and no option turns it off, so its report stream is sent
// to /dev/null - dcc writes the student's explanation itself
//
// leak reports are the sanitizer's own output and are wanted, so the stream
// is put back before a leak check, including the one the sanitizer runs at
// exit: this handler is registered after the sanitizer's, and atexit runs
// handlers in reverse order of registration
//
// this is a constructor rather than part of __dcc_start because an error can
// happen in a constructor of the student's, before main; the priority is
// higher than the compiler's own (1) and lower than a plain constructor's,
// so the sanitizer is initialized and no user constructor has run yet
static void suppress_sanitizer_report(void) NO_SANITIZE
    __attribute__((constructor(101)));
static void suppress_sanitizer_report(void) {
    char *debug_level_string = getenv("DCC_DEBUG");
    if (debug_level_string && atoi(debug_level_string)) {
        return;
    }
    int null_fd = open("/dev/null", O_WRONLY | O_CLOEXEC);
    if (null_fd < 0) {
        return;
    }
    // _explain_error closes 4 to 31 before it starts gdb
    int kept_fd = fcntl(null_fd, F_DUPFD_CLOEXEC, 32);
    if (kept_fd >= 0) {
        close(null_fd);
        null_fd = kept_fd;
    }
    extern void __sanitizer_set_report_fd(void *fd);
    __sanitizer_set_report_fd((void *)(intptr_t)null_fd);
    atexit(restore_sanitizer_report_fd);
}
#endif

#if DCC_SANITIZER != MEMORY

#if defined(__linux__) && !DCC_I_AM_SANITIZER2
// where the program is, for an error which happened before __wrap_main could
// record it from argv[0]
static void set_binary_from_proc(void) NO_SANITIZE;
static void set_binary_from_proc(void) {
    static char executable_pathname[PATH_MAX];
    ssize_t n_bytes = readlink("/proc/self/exe", executable_pathname, sizeof executable_pathname - 1);
    if (n_bytes > 0) {
        executable_pathname[n_bytes] = '\0';
        setenvd("DCC_BINARY", executable_pathname);
    }
}
#endif

// a run-time error can happen before main, in a constructor function or in the
// initializer of a C++ global object, where __dcc_start has not run and the
// explanation has neither a program to look at nor a process to attach to,
// so the student was shown nothing at all
//
// not done for MemorySanitizer: nothing has run there to say what went wrong,
// and explain_error.py would call any error it is handed an uninitialized
// variable, so a null pointer write would be explained as the wrong thing
//
// this runs when the error is explained rather than from a constructor of
// dcc's own, because a constructor's frame is where main's frame will be and
// what it leaves behind is what a later out of bounds read shows the student
static void __dcc_error_before_main(void) NO_SANITIZE;
static void __dcc_error_before_main(void) {
    char *debug_level_string = getenv("DCC_DEBUG");
    if (debug_level_string) {
        debug_level = atoi(debug_level_string);
    }
    setenvd("DCC_SANITIZER", DCC_SANITIZER_NAME);
    setenvd("DCC_PATH", DCC_PATH_LITERAL);
    setenvd_int("DCC_PID", getpid());
#if defined(__linux__) && !DCC_I_AM_SANITIZER2
    set_binary_from_proc();
#endif
}

#endif

static void __dcc_start(void) {
    char *debug_level_string = getenv("DCC_DEBUG");
    if (debug_level_string) {
        debug_level = atoi(debug_level_string);
    }
    debug_printf(2, "__dcc_start debug_level=%d\n", debug_level);

    setenvd("DCC_SANITIZER", DCC_SANITIZER_NAME);
    setenvd("DCC_PATH", DCC_PATH_LITERAL);

    setenvd_int("DCC_PID", getpid());

    signal(SIGABRT, __dcc_signal_handler);
    signal(SIGINT, __dcc_signal_handler);
#if DCC_N_SANITIZERS > 1
    pthread_atfork(NULL, NULL, __dcc_forked_child);
#endif

    // a stack overflow, e.g. from infinite recursion, leaves no stack for a
    // signal handler to run on, so SIGSEGV is handled on an alternate stack
    static char alternate_stack[65536];
    stack_t alternate = { .ss_sp = alternate_stack, .ss_size = sizeof alternate_stack, .ss_flags = 0 };
    sigaltstack(&alternate, NULL);
    struct sigaction segv_action;
    memset(&segv_action, 0, sizeof segv_action);
    segv_action.sa_sigaction = __dcc_segv_handler;
    segv_action.sa_flags = SA_SIGINFO | SA_ONSTACK;
    sigemptyset(&segv_action.sa_mask);
    sigaction(SIGSEGV, &segv_action, NULL);
    stack_top = (char *)&alternate;
    main_thread_id = __dcc_gettid();
    signal(SIGXCPU, __dcc_signal_handler);
    signal(SIGXFSZ, __dcc_signal_handler);
    signal(SIGFPE, __dcc_signal_handler);
    signal(SIGILL, __dcc_signal_handler);
#if DCC_N_SANITIZERS > 1
    signal(SIGPIPE, __dcc_signal_handler);
    signal(SIGUSR1, __dcc_signal_handler);
#endif
    clear_stack();
}

static void disable_check_output();
void __dcc_error_exit(void) {
    disable_check_output();
    debug_printf(2, "__dcc_error_exit()\n");

#if DCC_N_SANITIZERS > 1
    __dcc_cleanup_before_exit();
#endif

#if DCC_SANITIZER != VALGRIND
    // use kill instead of exit or _exit because
    // exit or _exit keeps executing sanitizer code - including perhaps superfluous output
    // but not with valgrind which will catch signal and start gdb
    // SIGPIPE avoids killed message from bash
    signal(SIGPIPE, SIG_DFL);
    kill(getpid(), SIGPIPE);
#endif

    _exit(DCC_ERROR_EXIT_STATUS);
}

// is __asan_on_error  address sanitizer only??
//
// intercept ASAN explanation
void __asan_on_error(void) NO_SANITIZE;

void __asan_on_error(void) {
    debug_printf(2, "__asan_on_error\n");

    const char *report = "";
#if DCC_SANITIZER == ADDRESS && DCC_CLANG_VERSION_MAJOR >= 6
    extern char *__asan_get_report_description();
    extern int __asan_report_present();
    extern void *__asan_get_report_address();
    extern size_t __asan_get_alloc_stack(void *, void **, size_t, int *);
    // putenv does not copy strings, so the buffer must outlive this function
    static char thread_env[64];
    if (__asan_report_present()) {
        report = __asan_get_report_description();

        int thread_id;
        __asan_get_alloc_stack(__asan_get_report_address(), NULL, 0, &thread_id);
        snprintf(thread_env, sizeof thread_env, "DCC_ASAN_THREAD=%d", thread_id);
        putenvd(thread_env);
    }
#endif
    static char report_description[8192];
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

#if DCC_SANITIZER == ADDRESS
const char *__asan_default_options(void) {
    // NOTE setting detect_stack_use_after_return here stops
    // clear_stack pre-initializing stack frames to MEMORY_FILL_HEX

    // exitcode is the status LeakSanitizer uses when it reports a leak
    return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=" DCC_STRINGIFY(DCC_LEAK_CHECK) ":max_malloc_fill_size=4096000:quarantine_size_mb=16:verify_asan_link_order=0:detect_stack_use_after_return=" DCC_STRINGIFY(DCC_STACK_USE_AFTER_RETURN) ":exitcode=" DCC_STRINGIFY(DCC_ERROR_EXIT_STATUS) ":malloc_fill_byte=" MEMORY_FILL_INT_STR;
}
#endif

#if DCC_SANITIZER == MEMORY
const char *__msan_default_options(void) {
    return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=" DCC_STRINGIFY(DCC_LEAK_CHECK) ":exitcode=" DCC_STRINGIFY(DCC_ERROR_EXIT_STATUS);
}
#endif

// intercept undefined sanitizer reports
// ubsan builds on Ubuntu don't seem to expose this function

void __ubsan_on_report(void) {
    debug_printf(2, "__ubsan_on_report\n");

// gcc's libubsan exports these too, and DCC_CLANG_VERSION_MAJOR is 0 there,
// so the version test only excludes clang releases older than 7.  The accessor
// is weak because some builds of the sanitizer runtime do not export it, and a
// missing symbol would otherwise stop every program linking
#if DCC_UBSAN_IN_USE && (DCC_CLANG_VERSION_MAJOR == 0 || DCC_CLANG_VERSION_MAJOR >= 7)
    char *OutIssueKind;
    char *OutMessage;
    char *OutFilename;
    unsigned int OutLine;
    unsigned int OutCol;
    char *OutMemoryAddr;
    extern void __ubsan_get_current_report_data(
        char **OutIssueKind, char **OutMessage, char **OutFilename,
        unsigned int *OutLine, unsigned int *OutCol, char **OutMemoryAddr)
        __attribute__((weak));

    if (!__ubsan_get_current_report_data) {
        debug_printf(2, "__ubsan_get_current_report_data not available\n");
        return;
    }
    __ubsan_get_current_report_data(&OutIssueKind, &OutMessage, &OutFilename,
                                    &OutLine, &OutCol, &OutMemoryAddr);

    // putenv does not copy strings, so the buffers must outlive this function
    // the message and filename can be long so the buffers are generous
    static char buffer[6][4096];
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
        putenvd(buffer[i]);

    // the thread the error happened in, as __asan_on_error and the signal
    // handler publish theirs: the frame the values are read from is the
    // faulting one only if gdb is moved to it first
    static char thread_buffer[64];
    snprintf(thread_buffer, sizeof thread_buffer, "DCC_UBSAN_THREAD=%ld",
             __dcc_gettid());
    putenvd(thread_buffer);
#endif
    _explain_error();
    // not reached
}

#if DCC_UBSAN_IN_USE
const char *__ubsan_default_options(void) {
    return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=" DCC_STRINGIFY(DCC_LEAK_CHECK);
}
#endif

// gettid was only added to glibc in 2.30 and does not exist on macOS
static long __dcc_gettid(void) {
#ifdef SYS_gettid
    return (long)syscall(SYS_gettid);
#else
    return (long)getpid();
#endif
}

static void set_signals_default(void) {
    debug_printf(2, "set_signals_default()\n");
    signal(SIGABRT, SIG_DFL);
    signal(SIGSEGV, SIG_DFL);
    signal(SIGINT, SIG_DFL);
    signal(SIGXCPU, SIG_DFL);
    signal(SIGXFSZ, SIG_DFL);
    signal(SIGFPE, SIG_DFL);
    signal(SIGILL, SIG_DFL);
#if DCC_N_SANITIZERS > 1
    signal(SIGPIPE, SIG_DFL);
#if DCC_I_AM_SANITIZER1
    // sanitizer2 sends SIGUSR1 when it reports an error, which must not be
    // lost while sanitizer1 is winding down, because it sets the exit status
    signal(SIGUSR1, note_sanitizer2_error);
#else
    signal(SIGUSR1, SIG_IGN);
#endif
#endif
}

// how far from the end of the stack a fault may be and still be an overflow
#define STACK_OVERFLOW_SLACK 1048576

// set if the faulting address looks like a stack overflow
static volatile sig_atomic_t stack_overflow_detected;

// the stack pointer of the code a signal interrupted, or NULL where it can
// not be read from the signal context
static char *fault_stack_pointer(void *context) {
#if defined(__linux__) && (defined(__x86_64__) || defined(__i386__) || defined(__aarch64__))
    ucontext_t *interrupted = (ucontext_t *)context;
    if (!interrupted) {
        return NULL;
    }
#if defined(__x86_64__)
    return (char *)interrupted->uc_mcontext.gregs[REG_RSP];
#elif defined(__i386__)
    return (char *)interrupted->uc_mcontext.gregs[REG_ESP];
#else
    return (char *)interrupted->uc_mcontext.sp;
#endif
#else
    (void)context;
    return NULL;
#endif
}

// a fault just past the end of the stack is a stack overflow,
// usually from infinite recursion or one very large local array
//
// only the main thread is recognized: stack_top and main_thread_id are its
// stack and its id, and sigaltstack is per-thread, so a thread which
// overflows its own stack gets the generic explanation for an invalid
// memory access
static void __dcc_segv_handler(int signum, siginfo_t *info, void *context) {
    struct rlimit stack_limit;
    if (info && stack_top && getrlimit(RLIMIT_STACK, &stack_limit) == 0 &&
        stack_limit.rlim_cur != RLIM_INFINITY) {
        char *fault_address = (char *)info->si_addr;
        // another thread's stack pointer is an arbitrary distance from
        // stack_top, which would make any fault there look like an overflow
        char *stack_pointer = __dcc_gettid() == main_thread_id
                                  ? fault_stack_pointer(context)
                                  : NULL;
        size_t limit = (size_t)stack_limit.rlim_cur;
        // the stack occupies [stack_top - rlim_cur, stack_top]
        if (stack_pointer && stack_pointer < stack_top) {
            // an overflow has moved the stack pointer itself past the end of
            // the stack and faults where it points, however large the frame
            // which took it there; a wild pointer faults far from it
            size_t used = (size_t)(stack_top - stack_pointer);
            if (used + STACK_OVERFLOW_SLACK > limit && fault_address < stack_top &&
                fault_address + STACK_OVERFLOW_SLACK > stack_pointer) {
                stack_overflow_detected = 1;
            }
        } else if (fault_address < stack_top) {
            // no stack pointer available, so the fault must itself be near the
            // lowest address of the stack and not merely somewhere below stack_top
            size_t depth = (size_t)(stack_top - fault_address);
            if (depth + STACK_OVERFLOW_SLACK > limit &&
                depth < limit + STACK_OVERFLOW_SLACK) {
                stack_overflow_detected = 1;
            }
        }
    }
    // the environment is set in __dcc_signal_handler, after the handlers have
    // been reset, because putenv is not safe to call from a signal handler
    __dcc_signal_handler(signum);
}

#if DCC_N_SANITIZERS > 1 && DCC_I_AM_SANITIZER1
// sanitizer2_pid is 0 until the fork in __wrap_main succeeds, and on every
// path where that fork does not happen, so stop_sanitizer2 would kill(0, ...)
// -- every process in the group, i.e. the shell or marking script which ran
// the program and its other jobs
static void stop_sanitizer2_if_any(void) {
    if (sanitizer2_pid > 0) {
        stop_sanitizer2();
    } else {
        // nothing to wait for or to signal when exiting either, and the
        // stdio wrappers must stop trying to synchronize with a sanitizer2
        // which is not there
        disconnect_sanitizers();
        sanitizer2_killed = 1;
    }
}
#endif

static void __dcc_signal_handler(int signum) {
    debug_printf(2, "received signal %d\n", signum);
    set_signals_default();
    if (stack_overflow_detected) {
        putenvd("DCC_STACK_OVERFLOW=1");
    }
#if DCC_N_SANITIZERS > 1
#if DCC_I_AM_SANITIZER1
    if (i_am_sanitizer2) {
        // forked to become sanitizer2 but still running sanitizer1's code
        __dcc_error_exit();
    } else if (signum == SIGPIPE) {
        if (!synchronization_terminated) {
            stop_sanitizer2_if_any();
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

    // putenv does not copy strings, so the buffers must outlive this function
    static char signum_buffer[64];
    snprintf(signum_buffer, sizeof signum_buffer, "DCC_SIGNAL=%d", (int)signum);
    putenvd(
        signum_buffer); // less likely? to trigger another error than direct setenv

    static char threadid_buffer[64];
    snprintf(threadid_buffer, sizeof threadid_buffer, "DCC_SIGNAL_THREAD=%ld", __dcc_gettid());
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
    __dcc_clearing_stack_suppressed = 0;
#if DCC_SANITIZER != MEMORY
    if (!getenv("DCC_BINARY")) {
        // the error happened before __wrap_main recorded where the program is
        __dcc_error_before_main();
    }
#endif
#if DCC_N_SANITIZERS > 1 && DCC_I_AM_SANITIZER1
    stop_sanitizer2_if_any();
#endif
    // output the program has buffered but not written is lost here:
    // flushing it is not safe on this path, because the stdio cookies
    // re-enter the output checker, use far more stack than a signal handler
    // has, and in sanitizer2 can block on the pipes to the other process
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
#if DCC_N_SANITIZERS > 1
    extern FILE *__real_popen(const char *command, const char *type);
    dcc_forking = 1;
    FILE *python_pipe = __real_popen(run_tar_file, "w");
    dcc_forking = 0;
#else
    FILE *python_pipe = popen(run_tar_file, "w");
#endif
    size_t n_bytes = DCC_TAR_N_BYTES;
    size_t n_bytes_written = fwrite(dcc_tar_data, 1, n_bytes, python_pipe);
    if (n_bytes_written != n_bytes) {
        debug_printf(1, "fwrite bad return %d returned %d expected\n",
                     (int)n_bytes_written, (int)n_bytes);
    }
    pclose(python_pipe);
    __dcc_error_exit();
}

#if !DCC_STACK_USE_AFTER_RETURN
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

// with -ftrivial-auto-var-init=pattern the compiler fills local arrays on function entry,
// which would double the cost of the functions below, so their arrays opt out
#if __has_attribute(uninitialized)
#define UNINITIALIZED __attribute__((uninitialized))
#else
#define UNINITIALIZED
#endif

// bytes of stack cleared when the program starts
#define CLEAR_STACK_BYTES 4096000

// most bytes quick_clear_stack will clear
#define QUICK_CLEAR_STACK_MAX_BYTES 262144

// quick_clear_stack examines and clears the stack in chunks of this size
#define QUICK_CLEAR_STACK_CHUNK_BYTES 4096

// quick_clear_stack stops when this many consecutive chunks are found clean
// a returned frame holding a large untouched array can leave a clean gap
// above deeper dirt, so this is several chunks rather than one
// dirt below a gap larger than this many chunks is not re-cleared
// (a larger value costs every stdio call: 16 chunks measured 65% slower)
#define QUICK_CLEAR_STACK_CLEAN_CHUNKS_TO_STOP 8

// bytes cleared by quick_clear_stack when running under valgrind
// if valgrind's headers were not available when the program was compiled
#define QUICK_CLEAR_STACK_VALGRIND_BYTES 256000

// memcheck reports a conditional jump depending on uninitialized values if
// the stack is examined, unless it has first been told the memory is defined
// by a client request, which needs valgrind's headers when the program is compiled
#if DCC_SANITIZER == VALGRIND && defined(__has_include)
#if __has_include(<valgrind/memcheck.h>)
#include <valgrind/memcheck.h>
#define QUICK_CLEAR_STACK_SCAN 1
#endif
#elif DCC_SANITIZER != VALGRIND
#define QUICK_CLEAR_STACK_SCAN 1
#endif
#ifndef QUICK_CLEAR_STACK_SCAN
#define QUICK_CLEAR_STACK_SCAN 0
#endif

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
    char a[CLEAR_STACK_BYTES] UNINITIALIZED;
    debug_printf(3, "initialized %p to %p\n", a, a + sizeof a);
    _memset_shim(a, MEMORY_FILL_HEX, sizeof a);
}

// quick_clear_stack re-initializes the stack below the current frame
// after a library call has dirtied it, so uninitialized variables in
// functions called later are still filled with MEMORY_FILL_HEX
//
// it is called after every stdio operation so it must be cheap

#if !QUICK_CLEAR_STACK_SCAN

// under valgrind without its headers a fixed amount is cleared

static void quick_clear_stack(void) {
    if (__dcc_clearing_stack_suppressed) {
        return;
    }
    char a[QUICK_CLEAR_STACK_VALGRIND_BYTES] UNINITIALIZED;
    debug_printf(3, "initialized %p to %p\n", a, a + sizeof a);
    _memset_shim(a, MEMORY_FILL_HEX, sizeof a);
}

#else

static int _is_filled(const void *p, size_t size) NO_SANITIZE
#if __has_attribute(noinline)
    __attribute__((noinline))
#endif
    ;

// The stack dirtied by the preceding library call is at the top of the array
// below, and glibc's stdio functions use only a few kilobytes.  Dirt left by
// the program's own earlier calls may lie deeper, separated by clean gaps.
// The array is examined and cleared a chunk at a time from the top down,
// stopping when QUICK_CLEAR_STACK_CLEAN_CHUNKS_TO_STOP consecutive chunks are
// found still filled with MEMORY_FILL_HEX, so the cost is proportional to
// the depth of the dirt rather than to the size of the array.

static void quick_clear_stack(void) {
    if (__dcc_clearing_stack_suppressed) {
        return;
    }
    char a[QUICK_CLEAR_STACK_MAX_BYTES] UNINITIALIZED;
    char *chunk = a + sizeof a;
    int n_consecutive_clean_chunks = 0;
    while (chunk > a) {
        chunk -= QUICK_CLEAR_STACK_CHUNK_BYTES;
#if DCC_SANITIZER == VALGRIND
        // the chunk is examined below so tell memcheck its contents are defined
        // this does not affect error detection because memcheck marks the stack
        // undefined again whenever a function later allocates a frame there
        VALGRIND_MAKE_MEM_DEFINED(chunk, QUICK_CLEAR_STACK_CHUNK_BYTES);
#endif
        if (_is_filled(chunk, QUICK_CLEAR_STACK_CHUNK_BYTES)) {
            n_consecutive_clean_chunks++;
            if (n_consecutive_clean_chunks == QUICK_CLEAR_STACK_CLEAN_CHUNKS_TO_STOP) {
                break;
            }
        } else {
            n_consecutive_clean_chunks = 0;
            _memset_shim(chunk, MEMORY_FILL_HEX, QUICK_CLEAR_STACK_CHUNK_BYTES);
        }
    }
    debug_printf(3, "initialized %p to %p\n", chunk, a + sizeof a);
}

// return 1 if the size bytes at p are all MEMORY_FILL_HEX
// the bytes are uninitialized as far as the compiler is concerned,
// so they are examined in a separate function which is not inlined,
// to stop the compiler making assumptions about their values
// the loop has no early exit so the compiler can vectorize it

static int _is_filled(const void *p, size_t size) {
    const unsigned char *bytes = p;
    unsigned char difference = 0;
    for (size_t i = 0; i < size; i++) {
        difference |= bytes[i] ^ MEMORY_FILL_HEX;
    }
    return difference == 0;
}

#endif

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
    (void)p;
    (void)byte;
    (void)size;
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
#if DCC_N_SANITIZERS > 1
    fprintf(debug_stream ? debug_stream : stderr, DCC_WHICH_SANITIZER ": ");
#if DCC_I_AM_SANITIZER2
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

#if DCC_WRAP_POSIX_SPAWN

#include <spawn.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <limits.h>

int __real_posix_spawn(pid_t *pid, const char *path,
                       const posix_spawn_file_actions_t *file_actions,
                       const posix_spawnattr_t *attrp, char *const argv[],
                       char *const envp[]) NO_SANITIZE;

int __real_posix_spawnp(pid_t *pid, const char *path,
                        const posix_spawn_file_actions_t *file_actions,
                        const posix_spawnattr_t *attrp, char *const argv[],
                        char *const envp[]) NO_SANITIZE;

// the errno posix_spawn reports when path can not be executed, or 0 if it can
static int _dcc_spawn_error(const char *path) {
    struct stat s;
    if (stat(path, &s) != 0) {
        return errno;
    }
    if (!S_ISREG(s.st_mode)) {
        // execve reports EACCES for a directory, as posix_spawn does natively
        return EACCES;
    }
    if (faccessat(AT_FDCWD, path, X_OK, AT_EACCESS) != 0) {
        return errno;
    }
    return 0;
}

// the same for posix_spawnp, which searches $PATH unless file contains a '/'
static int _dcc_spawnp_error(const char *file) {
    // an empty name is ENOENT natively, and the $PATH search below would
    // instead report EACCES for the directories it would build from it
    if (!file || !*file) {
        return ENOENT;
    }
    if (strchr(file, '/')) {
        return _dcc_spawn_error(file);
    }
    const char *search = getenv("PATH");
    if (!search) {
        search = "/bin:/usr/bin";
    }
    size_t file_length = strlen(file);
    int error = ENOENT;
    for (;;) {
        const char *colon = strchr(search, ':');
        size_t length = colon ? (size_t)(colon - search) : strlen(search);
        char candidate[PATH_MAX];
        // a PATH element too long to hold is simply not considered
        if (length + file_length + 2 <= sizeof candidate) {
            memcpy(candidate, search, length);
            // an empty PATH element means the current directory
            if (length > 0 && candidate[length - 1] != '/') {
                candidate[length++] = '/';
            }
            memcpy(candidate + length, file, file_length + 1);
            int candidate_error = _dcc_spawn_error(candidate);
            if (candidate_error == 0) {
                return 0;
            }
            // execvp reports EACCES if a candidate existed but was not executable
            if (candidate_error == EACCES) {
                error = EACCES;
            }
        }
        if (!colon) {
            return error;
        }
        search = colon + 1;
    }
}

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
    // posix_spawn with valgrind-3.14.0 returns 0 if path can not be executed
    // crude work-around so it returns the errno it does when executed directly
    //
    // file_actions may chdir, so only the child can resolve a relative path
    int spawn_error =
        file_actions && (!path || path[0] != '/') ? 0
        : is_posix_spawn ? _dcc_spawn_error(path) : _dcc_spawnp_error(path);
    if (spawn_error) {
        return spawn_error;
    }

    if (is_posix_spawn) {
        return __real_posix_spawn(pid, path, file_actions, attrp, argv, envp);
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
	int suppressed = __dcc_clearing_stack_suppressed;
	__dcc_clearing_stack_suppressed = 1;
	int done = vfprintf(stream, format, args);
	__dcc_clearing_stack_suppressed = suppressed;
	va_end(args);
	quick_clear_stack();
	return done;
}

int printf(const char *restrict format, ...) {
	va_list args;
	va_start(args, format);
	int suppressed = __dcc_clearing_stack_suppressed;
	__dcc_clearing_stack_suppressed = 1;
	int done = vfprintf(stdout, format, args);
	__dcc_clearing_stack_suppressed = suppressed;
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
