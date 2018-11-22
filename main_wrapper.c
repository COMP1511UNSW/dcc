//
// C code to intercept runtime errors and run this program
//

#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <signal.h>
#include <limits.h>
#include <errno.h>
#include <sys/prctl.h>

static int debug = 0;

static void _dcc_exit(void) {
	if (debug) fprintf(stderr, "_dcc_exit()\n");

	// use kill instead of exit or _exit because
	// exit or _exit keeps executing sanitizer code - including perhaps superfluous output

	pid_t pid = getpid();

	// SIGPIPE avoids killed message from bash
	signal(SIGPIPE, SIG_DFL); 
	kill(pid, SIGPIPE);   

	// if SIGPIPE fails
	signal(SIGINT, SIG_DFL);
	kill(pid, SIGINT);

	// if SIGINT fails
	kill(pid, SIGKILL);

	// SIGKILL fails
	_exit(1);
}

static void setenvd(char *n, char *v) {
	setenv(n, v, 1);
	if (debug) fprintf(stderr, "setenv %s=%s\n", n, v);
}

static void putenvd(char *s) {
	putenv(s);
	if (debug) fprintf(stderr, "putenv %s\n", s);
}

static char *run_tar_file = "python3 -E -c \"import os,sys,tarfile,tempfile\n\
with tempfile.TemporaryDirectory() as temp_dir:\n\
    tarfile.open(fileobj=sys.stdin.buffer, mode='r|xz').extractall(temp_dir)\n\
    os.chdir(temp_dir)\n\
    exec(open('start_gdb.py').read())\n\
\"";

static void _explain_error(void) {
	// if a program has exhausted file descriptors then we need to close some to run gdb etc,
	// so as a precaution we close a pile of file descriptors which may or may not be open
	for (int i = 4; i < 32; i++)
		close(i);

    // ensure gdb can ptrace binary
	// https://www.kernel.org/doc/Documentation/security/Yama.txt
	prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY);		

#if !__DCC_EMBED_SOURCE__
	if (debug) fprintf(stderr, "running %s\n", "__DCC_PATH__");
	system("__DCC_PATH__");
#else
	if (debug) fprintf(stderr, "running %s\n", run_tar_file);
	FILE *python_pipe = popen(run_tar_file, "w");
	fwrite(tar_data, sizeof tar_data[0],  sizeof tar_data/sizeof tar_data[0], python_pipe);
	fclose(python_pipe);
#endif
	_dcc_exit();
}


static void _signal_handler(int signum) {
	signal(SIGABRT, SIG_IGN);
	signal(SIGSEGV, SIG_IGN);
	signal(SIGINT, SIG_IGN);
	signal(SIGXCPU, SIG_IGN);
	signal(SIGXFSZ, SIG_IGN);
	signal(SIGFPE, SIG_IGN);
	signal(SIGILL, SIG_IGN);
	
	char signum_buffer[1024];
	sprintf(signum_buffer, "DCC_SIGNAL=%d", (int)signum);
	putenvd(signum_buffer); // less likely? to trigger another error than direct setenv
	
	_explain_error();
	// not reached
}


void __dcc_start(void) __attribute__((constructor))
#if __has_attribute(optnone)
 __attribute__((optnone))
#endif
;

#define STACK_BYTES_TO_CLEAR 4096000
void __dcc_start(void) {

#if !__DCC_SANITIZER_IS_VALGRIND
	// leave 0xbe for uninitialized variables which get fresh stack pages
	char a[STACK_BYTES_TO_CLEAR];
	memset(a, 0xbe, sizeof a);
#endif

	debug = getenv("DCC_DEBUG") != NULL;
	
	if (debug) fprintf(stderr, "__dcc_start\n");
	
	setenvd("DCC_SANITIZER", "__DCC_SANITIZER__");
	setenvd("DCC_PATH", "__DCC_PATH__");

	char pid_buffer[32];
	snprintf(pid_buffer, sizeof pid_buffer, "%d", (int)getpid());
	setenvd("DCC_PID", pid_buffer);
	memset(pid_buffer, 0xbe, sizeof pid_buffer);
	
	signal(SIGABRT, _signal_handler);
	signal(SIGSEGV, _signal_handler);
	signal(SIGINT, _signal_handler);
	signal(SIGXCPU, _signal_handler);
	signal(SIGXFSZ, _signal_handler);
	signal(SIGFPE, _signal_handler);
	signal(SIGILL, _signal_handler);
}

// intercept ASAN explanation
void _Unwind_Backtrace(void *a, ...) {
	if (debug) fprintf(stderr, "_Unwind_Backtrace\n");
	_explain_error();
}

#if !__DCC_SANITIZER_IS_VALGRIND__
extern char *__asan_get_report_description();
extern  int __asan_report_present();

// intercept ASAN explanation
void __asan_on_error() {
	if (debug) fprintf(stderr, "__asan_on_error\n");

	char *report = "";
	if (__asan_report_present()) {
		report = __asan_get_report_description();
	}
	char report_description[8192];
	snprintf(report_description, sizeof report_description, "DCC_ASAN_ERROR=%s", report);
	putenvd(report_description);
	
	_explain_error();
	// not reached
}
#endif

char *__ubsan_default_options() {
	return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=0";
}

char *__asan_default_options() {
	return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=0:max_malloc_fill_size=4096000:quarantine_size_mb=16:detect_stack_use_after_return=1";
}

char *__msan_default_options() {
	return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=0";
}


#if !__DCC_SANITIZER_IS_VALGRIND__

// wrapping ASAN

int __wrap_main(int argc, char *argv[], char *envp[]) {
	extern int __real_main(int argc, char *argv[], char *envp[]);
	char mypath[PATH_MAX];
	realpath(argv[0], mypath);
	setenvd("DCC_BINARY", mypath);
	return __real_main(argc, argv, envp);
}

#else

// wrapping valgrind

int __wrap_main(int argc, char *argv[], char *envp[]) {
	extern int __real_main(int argc, char *argv[], char *envp[]);
	char mypath[PATH_MAX];
	realpath(argv[0], mypath);
	setenvd("DCC_BINARY", mypath);
	
	int valgrind_running = getenv("DCC_VALGRIND_RUNNING") != NULL;
	if (debug) printf("__wrap_main(valgrind_running=%d)\n", valgrind_running);
	if (valgrind_running) {
		// valgrind errors get reported earlier if we unbuffer stdout
		// otherwise uninitialized variables may not be detected until fflush when program exits
		// which produces poor error message
		setbuf(stdout, NULL);		   
		signal(SIGPIPE, SIG_DFL);
		if (debug) printf("running __real_main\n");
		return __real_main(argc, argv, envp);
	}
	
	if (debug) fprintf(stderr, "command=%s\n", "__DCC_MONITOR_VALGRIND__");
	FILE *valgrind_error_pipe = popen("__DCC_MONITOR_VALGRIND__", "w");
	fwrite(tar_data, sizeof tar_data[0],  sizeof tar_data/sizeof tar_data[0], valgrind_error_pipe);
    fflush(valgrind_error_pipe);
	setbuf(valgrind_error_pipe, NULL);			
	setenvd("DCC_VALGRIND_RUNNING", "1");

	char fd_buffer[1024];
	sprintf(fd_buffer, "--log-fd=%d", (int)fileno(valgrind_error_pipe));
	char *valgrind_command[] = {"/usr/bin/valgrind", "-q", "--vgdb=yes", "--leak-check=__DCC_LEAK_CHECK__", "--suppressions=__DCC_SUPRESSIONS_FILE__", "--max-stackframe=16000000", "--partial-loads-ok=no", fd_buffer, "--vgdb-error=1"};

	int valgrind_command_len = sizeof valgrind_command / sizeof valgrind_command[0];
	char *valgrind_argv[argc + 1 + valgrind_command_len];
	for (int i = 0; i < valgrind_command_len; i++)
		valgrind_argv[i] = valgrind_command[i];
	valgrind_argv[valgrind_command_len] = argv[0];
	for (int i = 1; i < argc; i++)
		valgrind_argv[i+valgrind_command_len] = argv[i];
	valgrind_argv[argc+valgrind_command_len] = NULL;
	execvp("/usr/bin/valgrind", valgrind_argv);

	return 0;
}

#endif
