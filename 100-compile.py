#
# Compile the user's program adding some C code
#
def compile():
	global colorize_output
	print_explanations = True  
	commandline_args = sys.argv[1:]
	if not commandline_args:
		print("Usage: %s [--valgrind|--memory|--no_explanation] <c-files>" % sys.argv[0], file=sys.stderr)
		sys.exit(1)
#	for c_compiler in ["clang-3.9", "clang-3.8", "clang"]:
#		if search_path(c_compiler):	 # shutil.which not available in Python 2
#			break
	c_compiler = "clang"
	which_sanitizer = "address"
	incremental_compilation = False
	leak_check = False
	suppressions_file = os.devnull
#	 linking_object_files = False
	user_supplied_compiler_args = []
	while commandline_args:
		arg = commandline_args.pop(0)
		if arg in ['-u', '--undefined', '--uninitialized', '--uninitialised', '-fsanitize=memory', '--memory']:
			which_sanitizer = "memory"
			continue
		elif arg == '--valgrind':
			which_sanitizer = "valgrind"
			continue
		elif arg == '--leak-check':
			which_sanitizer = "valgrind"
			leak_check = True
			continue
		elif arg.startswith('--suppressions='):
			suppressions_file = arg[len('--suppressions='):]
			continue
		elif arg == '--explanation':
			print_explanations = True
			continue
		elif arg == '--no_explanation':
			print_explanations = False
			continue
		user_supplied_compiler_args.append(arg)
		if arg	== '-c':
			incremental_compilation = True
#		 elif arg.endswith('.o'):
#			 linking_object_files = True
		elif arg == '-fcolor-diagnostics':
			colorize_output = True
		elif arg == '-fno-color-diagnostics':
			colorize_output = False
		elif arg == '-o' and commandline_args:
			object_filename = commandline_args[0]
			if object_filename.endswith('.c') and os.path.exists(object_filename):
				print("%s: will not overwrite %s with machine code" % (os.path.basename(sys.argv[0]), object_filename), file=sys.stderr)
				sys.exit(1)
	source = dcc_c_source
	source = source.replace('__DCC_PATH', '"'+dcc_path+'"')
	source = source.replace('__DCC_SANITIZER', '"'+which_sanitizer+'"')
	wrapper_source = dcc_wrapper_source
	if which_sanitizer == "memory" and platform.architecture()[0][0:2] == '32':
		if search_path('valgrind'):
			# -fsanitize=memory requires 64-bits so we fallback to embedding valgrind
			which_sanitizer = "valgrind"
		else:
			print("%s: uninitialized value checking not support on 32-bit architectures", file=sys.stderr)
			sys.exit(1)
	if which_sanitizer == "valgrind":
		sanitizer_args = []
		wrapper_source = valgrind_wrapper_source.replace('__DCC_MONITOR_VALGRIND', '"'+dcc_path+' --watch-stdin-for-valgrind-errors"')
		wrapper_source = wrapper_source.replace('__DCC_LEAK_CHECK', "yes" if leak_check else "no")
		wrapper_source = wrapper_source.replace('__DCC_SUPRESSIONS_FILE', suppressions_file)
	elif which_sanitizer == "memory":
		sanitizer_args = ['-fsanitize=memory']
	else:
		# fixme add code to check version supports these
		sanitizer_args = ['-fsanitize=address', '-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer']
		which_sanitizer = "address"
#	if c_compiler == 'clang-3.8' and platform.architecture()[0][0:2] == '32':
#		# backport clang-3.8 on CSE	 machines needs this
#		sanitizer_args +=  ['-target', 'i386-pc-linux-gnu']
	# First run	 with -O enabled for better compile-time warnings 
	command = [c_compiler, '-O', '-Wall']  + sanitizer_args + extra_c_compiler_args + user_supplied_compiler_args
	if colorize_output:
		command += ['-fcolor-diagnostics']
	if debug:
		print(" ".join(command), file=sys.stderr)
	process = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
	# workaround for  https://github.com/android-ndk/ndk/issues/184
	if "undefined reference to `__" in process.stdout:
			sanitizer_args = [c for c in sanitizer_args if not c in ['-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer']]
			command = [c_compiler, '-O', '-Wall']  + sanitizer_args + extra_c_compiler_args + user_supplied_compiler_args
			if debug:
				print("undefined reference to `__mulodi4'", file=sys.stderr)
				print("recompiling", " ".join(command), file=sys.stderr)
			process = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
	if process.stdout:
		output = process.stdout
		# remove any ANSI codes
		# http://stackoverflow.com/a/14693789
		colourless_output = re.sub(r'\x1b[^m]*m', '', output)
		lines = output.splitlines()
		colourless_lines = colourless_output.splitlines()
		errors_explained = 0
		try:
			i = 0
			explanation_made = {}
			last_explanation_file_line = ''
			while i < len(lines) and print_explanations:
				matching_error_messages = help_dcc(colourless_lines[i:]) or help(colourless_lines[i:])
				if not matching_error_messages: 
					break
				matched_error_messages, explanation = matching_error_messages
				# ignore some I don't know explanations
				if re.match(r'not quite sure', explanation[0], flags=re.I):
					break
				explanation = "\n ".join([e for e in explanation if 'cs50' not in e])
				explanation = explanation.replace("`clang`", 'the compiler')
				# Don't repeat explanations
				n_explained_lines = len(matched_error_messages)
				# some help messages miss the caret
				if (n_explained_lines == 1 or  n_explained_lines == 2) and len(lines) > i + 2 and has_caret(colourless_lines[i+2]):
					n_explained_lines = 3
				if len(lines) > i + n_explained_lines and re.match(r'^.*note:', colourless_lines[i + n_explained_lines]):
					#print('note line detcted')
					n_explained_lines += 1
				e = re.sub('line.*', '', explanation, flags=re.I)
				if e not in explanation_made:
					explanation_made[e] = 1
					m = re.match(r'^([^:]+:\d+):', colourless_lines[i])
					if m:
						if m.group(1) == last_explanation_file_line:
							# stop if there are two errors for one line - the second is probably wrong
							break
						last_explanation_file_line = m.group(1)
					print("\n".join(lines[i:i+n_explained_lines]),	file=sys.stderr)
					if colorize_output:
						print("\033[0m\033[34mEXPLANATION:\033[0m", explanation+'\n', file=sys.stderr)
					else:
						print("EXPLANATION:", explanation+'\n', file=sys.stderr)
					if 'warning:' not in lines[i]:
						errors_explained += 1
				i += n_explained_lines
				if errors_explained >= 3:
					break
			if not errors_explained:
				sys.stderr.write('\n'.join(lines[i:])+"\n")
		except Exception:
			etype, evalue, etraceback = sys.exc_info()
			eformatted = "\n".join(traceback.format_exception_only(etype, evalue))
			print("%s: internal error: %s" % (os.path.basename(sys.argv[0]), eformatted), file=sys.stderr)
			sys.stderr.write(output)
		if process.returncode:
			sys.exit(process.returncode)
	# run a second time without -O for better debugging code
	command = [c_compiler, '-w'] + sanitizer_args + extra_c_compiler_args + user_supplied_compiler_args
	if incremental_compilation:
		if debug:
			print(" ".join(command), file=sys.stderr)
		sys.exit(subprocess.call(command))
	command +=	['-Wl,-wrap,main', '-x', 'c', '-']
	if debug:
		print(" ".join(command), file=sys.stderr)
	if debug > 1:
		print(" ".join(command), '<<eof', file=sys.stderr)
		print(source + wrapper_source)
		print("eof")
	process = subprocess.run(command, input=source + wrapper_source, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
	# workaround for  https://github.com/android-ndk/ndk/issues/184
	# can  be triggered	 not earlier
	if "undefined reference to `__" in process.stdout:
		command = [c for c in command if not c in ['-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer']]
		if debug:
			print("undefined reference to `__mulodi4'", file=sys.stderr)
			print("recompiling", " ".join(command), file=sys.stderr)
		process = subprocess.run(command, input=source + wrapper_source, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
	print(process.stdout, end='', file=sys.stderr)
	sys.exit(process.returncode)

def search_path(program):
	for path in os.environ["PATH"].split(os.pathsep):
		full_path = os.path.join(path, program)
		if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
			return full_path

#
# C code to intercept runtime errors and run this program
#

dcc_c_source = r"""
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include <signal.h>
#include <limits.h>
#include <errno.h>

static int debug = 0;

static void _dcc_exit(void) {
	if (debug) fprintf(stderr, "_dcc_exit()\n");
	// exit or _exit keeps executing sanitizer code - including perhaps superfluous output
	// SIGPIPE avoids killed message from bash
	signal(SIGPIPE, SIG_DFL);
	kill(getpid(), SIGPIPE);
	signal(SIGINT, SIG_DFL);
	kill(getpid(), SIGINT);
	// if SIGINT fails
	kill(getpid(), SIGKILL);
	// should never reach here
	_exit(1);
}

static void setenvd(char *n, char *v) {
	setenv(n, v, 1);
	if (debug) fprintf(stderr, "setenv %s=%s\n", n, v);
}

static void _explain_error(void) {
	// if a program has exhausted file descriptor then we need to close some to run gdb etc,
	// so as a precaution we close a pile of file descriptiors which may or may not be open
	for (int i = 4; i < 32; i++)
		close(i);
	if (debug) fprintf(stderr, "running %s\n", __DCC_PATH);
	system(__DCC_PATH);
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
	sprintf(signum_buffer, "%d", (int)signum);
	setenvd("DCC_SIGNAL", signum_buffer);
	_explain_error();
}


void __dcc_start(void) __attribute__((constructor))
#if __has_attribute(optnone)
 __attribute__((optnone))
#endif
;

#define STACK_BYTES_TO_CLEAR 4096000
void __dcc_start(void) {
	// leave 0xbe for uninitialized variables which get fresh stack pages
	char a[STACK_BYTES_TO_CLEAR];
	memset(a, 0xbe, sizeof a);
	debug = getenv("DCC_DEBUG") != NULL;
	if (debug) fprintf(stderr, "__dcc_start\n");
	debug = getenv("DCC_DEBUG") != NULL;
	setenvd("DCC_SANITIZER", __DCC_SANITIZER);
	setenvd("DCC_PATH", __DCC_PATH);

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


// intercept ASAN explanation
void __asan_on_error() {
	if (debug) fprintf(stderr, "__asan_on_error\n");
	setenvd("DCC_ASAN_ERROR", "1");
	_explain_error();
}

char *__ubsan_default_options() {
	return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=0";
}

char *__asan_default_options() {
	return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=0:max_malloc_fill_size=4096000:quarantine_size_mb=16";
}

char *__msan_default_options() {
	return "verbosity=0:print_stacktrace=1:halt_on_error=1:detect_leaks=0";
}
""" 

dcc_wrapper_source = r""" 
int __wrap_main(int argc, char *argv[], char *envp[]) {
	extern int __real_main(int argc, char *argv[], char *envp[]);
	int i;
	char mypath[PATH_MAX];
	realpath(argv[0], mypath);
	setenvd("DCC_BINARY", mypath);
	return __real_main(argc, argv, envp);
}
""" 

valgrind_wrapper_source = r""" 
int __wrap_main(int argc, char *argv[], char *envp[]) {
	extern int __real_main(int argc, char *argv[], char *envp[]);
	int i;
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
	if (debug) fprintf(stderr, "command=%s\n", __DCC_MONITOR_VALGRIND);
	FILE *valgrind_error_pipe = popen(__DCC_MONITOR_VALGRIND, "w");
	setbuf(valgrind_error_pipe, NULL);			
	setenvd("DCC_VALGRIND_RUNNING", "1");
	char fd_buffer[1024];
	sprintf(fd_buffer, "--log-fd=%d", (int)fileno(valgrind_error_pipe));
//	char *valgrind_command[] = {"/usr/bin/valgrind", "-q", "--vgdb=yes", "--max-stackframe=16000000", fd_buffer, "--track-origins=yes", "--vgdb-error=1"};
	char *valgrind_command[] = {"/usr/bin/valgrind", "-q", "--vgdb=yes", "--leak-check=__DCC_LEAK_CHECK", "--suppressions=__DCC_SUPRESSIONS_FILE", "--max-stackframe=16000000", "--partial-loads-ok=no", fd_buffer, "--vgdb-error=1"};
	int valgrind_command_len = sizeof valgrind_command / sizeof valgrind_command[0];
	char *valgrind_argv[argc + 1 + valgrind_command_len];
	for (i = 0; i < valgrind_command_len; i++)
		valgrind_argv[i] = valgrind_command[i];
	valgrind_argv[valgrind_command_len] = argv[0];
	for (i = 1; i < argc; i++)
		valgrind_argv[i+valgrind_command_len] = argv[i];
	valgrind_argv[argc+valgrind_command_len] = NULL;
	execvp("/usr/bin/valgrind", valgrind_argv);
	return 0;
}
""" 
