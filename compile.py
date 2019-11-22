import codecs,io, os, pkgutil, platform, re, subprocess, sys, tarfile, tempfile

from version import VERSION
from explain_compiler_output import explain_compiler_output

FILES_EMBEDDED_IN_BINARY = ["start_gdb.py", "drive_gdb.py", "watch_valgrind.py", "colors.py", "explain_output_difference.py"]

# on some platforms -Wno-unused-result is needed to avoid warnings about scanf's return value being ignored -
# novice programmers will often be told to ignore scanf's return value
# when writing their first programs

COMMON_WARNING_ARGS = "-Wall -Wno-unused -Wunused-variable -Wunused-value -Wno-unused-result -Wshadow".split()
COMMON_COMPILER_ARGS = COMMON_WARNING_ARGS + "-std=gnu11 -g -lm".split()

CLANG_ONLY_ARGS = "-Wunused-comparison -fno-omit-frame-pointer -fno-common -funwind-tables -fno-optimize-sibling-calls -Qunused-arguments".split()

# gcc flags some novice programmer mistakes than clang doesn't so
# we run it has an extra checking pass with several extra warnings enabled
# -Wduplicated-branches was only added with gcc-8 so it will break older versions of gcc
# this will be silent but we lose gcc checking - we could fix by  checking gcc version
#
# -Wnull-dererefence would be useful here fbut when it flags potential paths
# the errors look confusing for novice programmers ,and there appears no way to get only definite null-derefs
#
# -O is needed with gcc to get warnings for some things

GCC_ONLY_ARGS = "-Wunused-but-set-variable -Wduplicated-cond -Wduplicated-branches -Wlogical-op -O  -o /dev/null".split()

#
# Compile the user's program adding some C code
#
def compile():
	os.environ['PATH'] = os.path.dirname(os.path.realpath(sys.argv[0])) + ':/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:' + os.environ.get('PATH', '')
	options = get_options()

	wrapper_source, tar_source = get_wrapper_tar_source(options)

	#
	# -x - must come after any filenames but before ld options
	
	#
	# if we have two sanitizers we need to do first compile a binary with appropriate
	# options for sanitizers 2 and embed the binary as C data inside the binary for sanitizer 1
	#
	base_compile_command = [options.c_compiler] + options.user_supplied_compiler_args + ['-x', 'c', '-', ] +  options.clang_args
	compiler_stdout = ''
	executable_source = ''
	if len(options.sanitizers) == 2:
		sanitizer2_wrapper_source, sanitizer2_sanitizer_args = update_wrapper_source(options.sanitizers[1], 2, wrapper_source, tar_source, options)
		try:
			# can't use tempfile.NamedTemporaryFile because may be multiple opens of file
			executable = tempfile.mkstemp(prefix='dcc_sanitizer2')[1]
			command = base_compile_command + sanitizer2_sanitizer_args + ['-o', executable]
			compiler_stdout = execute_compiler(command, sanitizer2_wrapper_source, options, debug_wrapper_file="tmp_dcc_sanitizer2.c")
			with open(executable, "rb") as f:
				executable_n_bytes, executable_source = source_for_sanitizer2_executable(f.read())
			os.unlink(executable)
		except OSError:
			# compiler may unlink temporary file resulting in this exception
			sys.exit(1)

	# leave leak checking to valgrind if it is running
	# because it currently gives better errors
	wrapper_source, sanitizer_args = update_wrapper_source(options.sanitizers[0], 1, wrapper_source, tar_source, options)

	if options.incremental_compilation:
		incremental_compilation_args = sanitizer_args + options.clang_args + options.user_supplied_compiler_args
		command = [options.c_compiler] + incremental_compilation_args
		options.debug_print('incremental compilation, running: ', " ".join(command))
		sys.exit(subprocess.call(command))

	if executable_source:
		wrapper_source = wrapper_source.replace('__EXECUTABLE_N_BYTES__', str(executable_n_bytes))
		wrapper_source = executable_source + wrapper_source

	command = base_compile_command + sanitizer_args  + ['-o', options.object_pathname]
	compiler_stdout = execute_compiler(command, wrapper_source, options, print_stdout=not compiler_stdout)

	# gcc picks up some errors at compile-time that clang doesn't, e.g
	# int main(void) {int a[1]; return a[0];}
	# so run gcc as well if available

	if not compiler_stdout and options.also_run_gcc and 'gcc' not in options.c_compiler and not options.object_files_being_linked:
		command = ['gcc'] + options.user_supplied_compiler_args + options.gcc_args
		options.debug_print("compiling with gcc for extra checking")
		execute_compiler(command, '', options, rename_functions=False, checking_only=True)

	sys.exit(0)


# customize wrapper source for a particular sanitizer
def update_wrapper_source(sanitizer, sanitizer_n, wrapper_source, tar_source,  options):
	wrapper_source = wrapper_source.replace('__SANITIZER__', sanitizer.upper())
	if sanitizer == "valgrind":
		sanitizer_args = []
	elif sanitizer == "memory":
		sanitizer_args = ['-fsanitize=memory']
	else:
		sanitizer_args = ['-fsanitize=address']

	if sanitizer != "memory" and not (sanitizer_n == 2 and sanitizer == "valgrind"):
		# FIXME if we enable  '-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer' for memory
		# which would be preferable here we get uninitialized variable error message for undefined errors
		wrapper_source = wrapper_source.replace('__UNDEFINED_BEHAVIOUR_SANITIZER_IN_USE__', '1')
		sanitizer_args += ['-fsanitize=undefined']
		if options.clang_version_float >= 3.6:
			sanitizer_args += ['-fno-sanitize-recover=undefined,integer']

	if options.shared_libasan and  sanitizer == "address":
		lib_dir = options.clang_lib_dir.replace('{clang_version}', options.clang_version)
		if os.path.exists(lib_dir):
			sanitizer_args += ['-shared-libasan', '-Wl,-rpath,' + lib_dir]

	wrapper_source = wrapper_source.replace('__LEAK_CHECK_YES_NO__', "yes" if options.leak_check else "no")
	leak_check = options.leak_check
	if leak_check and options.sanitizers[1:] == ["valgrind"]:
		# do leak checking in valgrind (only) for (currently) better messages
		leak_check = False
	wrapper_source = wrapper_source.replace('__LEAK_CHECK_1_0__', "1" if leak_check else "0")

	wrapper_source = wrapper_source.replace('__I_AM_SANITIZER1__', "1" if sanitizer_n == 1 else "0")
	wrapper_source = wrapper_source.replace('__I_AM_SANITIZER2__', "1" if sanitizer_n == 2 else "0")
	wrapper_source = wrapper_source.replace('__WHICH_SANITIZER__', "sanitizer2" if sanitizer_n == 2 else "sanitizer1")

	if tar_source:
		wrapper_source = wrapper_source.replace('__EMBED_SOURCE__', '1')
		wrapper_source = tar_source + wrapper_source
	return wrapper_source, sanitizer_args


def execute_compiler(base_command, compiler_stdin, options, rename_functions=True, print_stdout=True, debug_wrapper_file="tmp_dcc_sanitizer1.c", checking_only=False):
	command = list(base_command)
	if compiler_stdin:
		if rename_functions and not options.unsafe_system_includes:
			# unistd functions used by single-sanitizer dcc
			rename_function_names = ['_exit', 'close', 'execvp', 'getpid']
			# unistd functions used by dual-sanitizer dcc
			if len(options.sanitizers) > 1:
				rename_function_names += ['lseek', 'pipe', 'read', 'sleep', 'unlink', 'write']
			command +=  ['-D{}=__renamed_{}'.format(f, f) for f in rename_function_names]

		wrapped_functions = ['main']

		override_functions = []
		if len(options.sanitizers) > 1:
			override_functions  = ['clock', 'fdopen', 'fopen', 'freopen', 'popen', 'system', 'time']

		if options.ifdef_instead_of_wrap:
			command +=  ['-D{}=__real_{}'.format(f, f) for f in wrapped_functions]
			command +=  ['-D{}=__wrap_{}'.format(f, f) for f in override_functions]
			for f in wrapped_functions:
				compiler_stdin = compiler_stdin.replace('__wrap_' + f, f)
			for f in override_functions:
				compiler_stdin = compiler_stdin.replace('__real_' + f, f)
		else:
			command += ['-Wl' + ''.join(',-wrap,' + f for f in wrapped_functions + override_functions)]

	options.debug_print(" ".join(command))

	if options.debug > 1 and compiler_stdin:
		options.debug_print("Leaving dcc code in", debug_wrapper_file, "compile with this command:")
		options.debug_print(" ".join(command).replace('-x c -', debug_wrapper_file))
		try:
			with open(debug_wrapper_file,"w") as f:
				f.write(compiler_stdin)
		except OSError as e:
			print(e)
	input = codecs.encode(compiler_stdin, 'utf8')
	process = subprocess.run(command, input=input, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout = codecs.decode(process.stdout, 'utf8', errors='replace')

	if checking_only:
		# we are running gcc as an extra checking phase
		# and options don't match the gcc version so give up silently
		if 'command line' in stdout or 'option' in stdout or '/dev/null' in stdout:
			options.debug_print(stdout)
			return ''

		# checking is run after we have already successfully generated an executable with clang
		# so if we can get an error, unlink the executable
		if process.returncode:
			try:
				os.unlink(options.object_pathname)
			except OSError as e:
				if options.debug:
					print(e)


	# avoid a confusing mess of linker errors
	if "undefined reference to `main" in stdout:
		options.die("error: your program does not contain a main function - a C program must contain a main function")

	# workaround for  https://github.com/android-ndk/ndk/issues/184
	# when not triggered earlier
	if "undefined reference to `__mul" in stdout and not checking_only:
		command = [c for c in command if not c in ['-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer']]
		options.debug_print("undefined reference to `__mulodi4'")
		options.debug_print("recompiling", " ".join(command))
		process = subprocess.run(command, input=input, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout = codecs.decode(process.stdout, 'utf8', errors='replace')

	# a user call to a renamed unistd.h function appears to be undefined
	# so recompile without renames

	if rename_functions and "undefined reference to `__renamed_" in stdout and not checking_only:
		options.debug_print("undefined reference to `__renamed_' recompiling without -D renames")
		return execute_compiler(base_command, compiler_stdin, options, rename_functions=False, print_stdout=print_stdout, debug_wrapper_file=debug_wrapper_file)

	if stdout and print_stdout:
		if options.explanations:
			explain_compiler_output(stdout, options)
		else:
			print(stdout, end='', file=sys.stderr)

	if process.returncode:
		sys.exit(process.returncode)

	return stdout

def get_wrapper_tar_source(options):
	wrapper_source = ''.join(pkgutil.get_data('src', f).decode('utf8') for f in ['dcc_main.c', 'dcc_dual_sanitizers.c', 'dcc_util.c', 'dcc_check_output.c'])

	wrapper_source = wrapper_source.replace('__PATH__', options.dcc_path)
	wrapper_source = wrapper_source.replace('__DCC_VERSION__', '"' + VERSION + '"')
	wrapper_source = wrapper_source.replace('__HOSTNAME__', '"' +  platform.node() + '"')
	wrapper_source = wrapper_source.replace('__CLANG_VERSION__', '"%s"' % options.clang_version)
	wrapper_source = wrapper_source.replace('__SUPRESSIONS_FILE__', options.suppressions_file)
	wrapper_source = wrapper_source.replace('__STACK_USE_AFTER_RETURN__', "1" if options.stack_use_after_return else "0")
	wrapper_source = wrapper_source.replace('__CHECK_OUTPUT__', "1" if options.check_output else "0")
	wrapper_source = wrapper_source.replace('__CLANG_VERSION_MAJOR__', str(options.clang_version_major))
	wrapper_source = wrapper_source.replace('__CLANG_VERSION_MINOR__', str(options.clang_version_minor))
	wrapper_source = wrapper_source.replace('__N_SANITIZERS__', str(len(options.sanitizers)))
	wrapper_source = wrapper_source.replace('__SANITIZER_1__', options.sanitizers[0].upper())

	if len(options.sanitizers) > 1:
		wrapper_source = wrapper_source.replace('__SANITIZER_2__', options.sanitizers[1].upper())

	if options.embed_source:
		tar_n_bytes, tar_source = source_for_embedded_tarfile(options)
		watcher = fr"python3 -E -c \"import io,os,sys,tarfile,tempfile\n\
with tempfile.TemporaryDirectory() as temp_dir:\n\
 buffer = io.BytesIO(sys.stdin.buffer.raw.read({tar_n_bytes}))\n\
 if len(buffer.getbuffer()) == {tar_n_bytes}:\n\
  tarfile.open(fileobj=buffer, bufsize={tar_n_bytes}, mode='r|xz').extractall(temp_dir)\n\
  os.chdir(temp_dir)\n\
  exec(open('watch_valgrind.py').read())\n\
\""
	else:
		# hopefully obsolete option to invoke Python in dcc rather than use Python embeded in binary
		tar_n_bytes, tar_source = 0, ''
		watcher = options.dcc_path +  "--watch-stdin-for-valgrind-errors"

	wrapper_source = wrapper_source.replace('__MONITOR_VALGRIND__', watcher)

	return wrapper_source, tar_source


class Options(object):
	def __init__(self):

		# OSX has clang renamed as gcc - but it doesn't take gcc options
		self.also_run_gcc = sys.platform != "darwin" and search_path('gcc')

		self.basename = os.path.basename(sys.argv[0])
		self.check_output = sys.platform != "darwin"

		self.c_compiler = "clang"
		self.clang_args = COMMON_COMPILER_ARGS + CLANG_ONLY_ARGS

		# needed for shared-libasan
		self.clang_lib_dir="/usr/lib/clang/{clang_version}/lib/linux"

		self.clang_version = ''
		self.clang_version_major = 0
		self.clang_version_minor = 0
		self.clang_version_float = 0.0

		# FIXME - check terminal actually supports ANSI
		self.colorize_output = sys.stderr.isatty() or os.environ.get('DCC_COLORIZE_OUTPUT', False)

		# used by hopefully obsolete code which use executes dcc from binary
		self.dcc_path = os.path.realpath(sys.argv[0])

		# list of system includes for standard lib function which will not
		# interfere with dual sanitizer synchronization
		self.dual_sanitizer_safe_system_includes = set(['assert.h', 'complex.h', 'ctype.h', 'errno.h', 'fenv.h', 'float.h', 'inttypes.h', 'iso646.h', 'limits.h', 'locale.h', 'math.h', 'setjmp.h', 'stdalign.h', 'stdarg.h', 'stdatomic.h', 'stdbool.h', 'stddef.h', 'stdint.h', 'stdio.h', 'stdlib.h', 'stdnoreturn.h', 'string.h', 'tgmath.h', 'time.h', 'uchar.h', 'wchar.h', 'wctype.h', 'sanitizer/asan_interface.h', 'malloc.h', 'strings.h', 'sysexits.h'])

		self.debug = int(os.environ.get('DCC_DEBUG', '0'))
		self.embed_source = True
		self.explanations = True

		# ld reportedly doesn't have wrap on OSX
		self.ifdef_instead_of_wrap = sys.platform == "darwin"

		self.incremental_compilation = False

		self.gcc_args = COMMON_COMPILER_ARGS + GCC_ONLY_ARGS

		self.leak_check = False
		self.libraries_being_linked = False
		self.max_explanations = 3
		self.maximum_source_file_embedded_bytes = 1000000
		self.object_files_being_linked = False
		self.object_pathname = "a.out"
		self.sanitizers = []
		self.shared_libasan = None
		self.source_files = set()
		self.stack_use_after_return = None
		self.suppressions_file = os.devnull
		self.system_includes_used = set()

		self.tar_buffer = io.BytesIO()
		self.tar = tarfile.open(fileobj=self.tar_buffer, mode='w|xz')

		self.threads_used = False
		self.treat_warnings_as_errors = False
		self.user_supplied_compiler_args = []

	def die(self, *args, **kwargs):
		self.warn(*args, **kwargs)
		sys.exit(1)

	def warn(self, *args, **kwargs):
		print(self.basename + ': ', end='', file=sys.stderr)
		kwargs['file'] = sys.stderr
		print(*args, **kwargs)

	def debug_print(self, *args, level=1, **kwargs):
		if self.debug >= level:
			kwargs['file'] = sys.stderr
			print(*args, **kwargs)

def get_options():
	options = parse_args(sys.argv[1:])

	if options.colorize_output:
		options.clang_args += ['-fcolor-diagnostics']
		options.clang_args += ['-fdiagnostics-color']
		options.gcc_args += ['-fdiagnostics-color=always']

	options.unsafe_system_includes = list(options.system_includes_used - options.dual_sanitizer_safe_system_includes)

	if not options.sanitizers or len(options.sanitizers) > 1:
		reason = ""
		if options.incremental_compilation:
			reason = "incremental compilation"
		elif options.object_files_being_linked:
			reason = "object files being linked"
		elif options.object_files_being_linked:
			reason = "library other than C standard library used"
		elif options.threads_used:
			reason = "threads used"
		elif options.unsafe_system_includes:
			reason = options.unsafe_system_includes[0]+ " used"
		elif sys.platform == "darwin":
			reason = "not supported on OSX"

		if reason:
			# if 2 sanitizer have been explicityl specified, give a warning
			if len(options.sanitizers) > 1:
				options.warn('warning: running 2 sanitizers will probably fail:', reason)
			else:
				options.sanitizers = ["address"]
		else:
			options.sanitizers = ["address", "valgrind"]

	if "memory" in options.sanitizers and platform.architecture()[0][0:2] == '32':
		options.die("MemorySanitizer not available on 32-bit architectures")

	get_clang_version(options)

	if "address" in options.sanitizers  and platform.architecture()[0][0:2] == '32':
		libc_version = get_libc_version(options)

		if  libc_version and options.clang_version_float < 6 and libc_version >= 2.27:
			options.warn("incompatible clang libc versions, disabling error detection by sanitizers")
			options.sanitizers = [a for a in options.sanitizers if a != "address"]

	# shared_libasan breaks easily ,e.g if there are libraries in  /etc/ld.so.preload
	# and we can't override with verify_asan_link_order=0 for clang version < 5
	# and with clang-6 on debian __asan_default_options not called with shared_libasan
	if options.shared_libasan is None and options.clang_version_float >= 7.0:
		options.shared_libasan = True

	if options.incremental_compilation and len(options.sanitizers) > 1:
		options.die("only a single sanitizer supported with incremental compilation")

	if options.object_files_being_linked and len(options.sanitizers) > 1:
		options.die("only a single sanitizer supported with linking of .o files")

	return options


def parse_args(commandline_args):
	options = Options()
	if not commandline_args:
		print(f"Usage: {sys.argv[0]} [-fsanitize=sanitizer1,sanitizer2] [--leak-check] [clang-arguments] <c-files>", file=sys.stderr)
		sys.exit(1)

	while commandline_args:
		arg = commandline_args.pop(0)
		parse_arg(arg, commandline_args, options)

	return options

# check for options which are for dcc and should not be passed to clang

def parse_arg(arg, remaining_args, options):
	if arg.startswith('-fsanitize='):
		options.sanitizers = []
		sanitizer_list = arg[len('-fsanitize='):].split(',')
		for sanitizer in sanitizer_list:
			if sanitizer in ['memory', 'address', 'valgrind']:
				options.sanitizers.append(sanitizer)
			elif sanitizer not in ['undefined']:
				options.die("unknown sanitizer", sanitizer)
		if len(options.sanitizers) not in [1,2]:
			options.die("only 1 or 2 sanitizers supported")
	elif arg in ['--memory']:	# for backwardscompatibility
		options.sanitizers = ["memory"]
	elif arg == '--valgrind':	# for backwardscompatibility
		options.sanitizers = ["valgrind"]
	elif arg == '--leak-check' or arg == '--leakcheck':
		options.leak_check = True
	elif arg.startswith('--suppressions='):
		options.suppressions_file = arg[len('--suppressions='):]
	elif arg == '--explanations' or arg == '--no_explanation': # backwards compatibility
		options.explanations = True
	elif arg == '--no-explanations':
		options.explanations = False
	elif arg == '--shared-libasan' or arg == '-shared-libasan':
		options.shared_libasan = True
	elif arg == '--use-after-return':
		options.stack_use_after_return = True
	elif arg == '--no-shared-libasan':
		options.shared_libasan = False
	elif arg == '--embed-source':
		options.embed_source = True
	elif arg == '--no-embed-source':
		options.embed_source = False
	elif arg == '--ifdef'  or arg == '--ifdef-main':
		options.ifdef_instead_of_wrap = True
	elif arg.startswith('--c-compiler='):
		options.c_compiler = arg[arg.index('=') + 1:]
	elif arg == '-fcolor-diagnostics':
		options.colorize_output = True
	elif arg == '-fno-color-diagnostics':
		options.colorize_output = False
	elif arg == '-v' or arg == '--version':
		print('dcc version', VERSION)
		sys.exit(0)
	elif arg == '--help':
		print("""
  --fsanitize=<sanitizer1,sanitizer2>    run two sanitizers (default -fsanitize=address,valgrind)
						   The second sanitizer is a separate process.
						   The synchronisation of the 2 processes should be effective for most
						   use of the standard C library and hence should work for novice programmers.
						   If synchronisation is lost the 2nd sanitizer terminates silently.
  --fsanitize=<sanitizer>  check for runtime errors using using a single sanitizer which can be one of
						   address   - AddressSanitizer, invalid memory operations
						   valgrind  - valgrind, primarily uninitialized variables
						   memory    - MemorySanitizer, primarily uninitialized variables
  --leak-check             check for memory leaks, requires --fsanitizer=valgrind to intercept errors
  --no-explanations        do not add explanations to compile-time error messages
  --no-embed-source        do not embed program source in binary
  --no-shared-libasan      do not use libasan
  --ifdef                  use ifdef instead of ld's -wrap option

""")
		sys.exit(0)
	elif arg.startswith('-o'):
		if arg == '-o':
			if remaining_args:
				options.object_pathname = remaining_args.pop(0)
		else:
			options.object_pathname = arg[2:]
		op = options.object_pathname
		if ((op.endswith('.c') or op.endswith('.h')) and os.path.exists(op)):
			options.die(f"will not overwrite {op} with machine code")
	else:
		parse_clang_arg(arg, remaining_args, options)

# check for options which are passed intact to clang
# but modify dcc behaviour

def parse_clang_arg(arg, remaining_args, options):
	options.user_supplied_compiler_args.append(arg)
	if arg == '-c':
		options.incremental_compilation = True
	elif arg.startswith('-l'):
		options.libraries_being_linked = True
	elif arg == '-Werror':
		options.treat_warnings_as_errors = True
	elif arg == '-pthreads':
		options.threads_used = True
	else:
		process_possible_source_file(arg, options)

# FIXME this is crude and brittle
def process_possible_source_file(pathname, options):
	extension = os.path.splitext(pathname)[1]
	if extension.lower() in ['.a', '.o', '.so']:
		options.object_files_being_linked = True
		return
	# don't try to handle paths with .. or with leading /
	# should we convert argument to normalized relative path if possible
	# before passing to to compiler?
	normalized_path = os.path.normpath(pathname)
	if pathname != normalized_path and os.path.join('.', normalized_path) != pathname:
		options.debug_print('not embedding source of', pathname, 'because normalized path differs:', normalized_path)
		return
	if normalized_path.startswith('..'):
		options.debug_print('not embedding source of', pathname, 'because it contains ..')
		return
	if os.path.isabs(pathname):
		options.debug_print('not embedding source of', pathname, 'because it has absolute path')
		return
	if pathname in options.source_files:
		return
	try:
		if os.path.getsize(pathname) > options.maximum_source_file_embedded_bytes:
			return
		options.tar.add(pathname)
		options.source_files.add(pathname)
		options.debug_print('adding', pathname, 'to tar file', level=2)
		with open(pathname, encoding='utf-8', errors='replace') as f:
			for line in f:
				m = re.match(r'^\s*#\s*include\s*"(.*?)"', line)
				if m:
					process_possible_source_file(m.group(1), options)
				m = re.match(r'^\s*#\s*include\s*<(.*?)>', line)
				if m:
					options.system_includes_used.add(m.group(1))
	except OSError as e:
		if options.debug:
			print('process_possible_source_file', pathname, e)
		return

def source_for_sanitizer2_executable(executable):
	source = "\nstatic unsigned char sanitizer2_executable[] = {";
	source += ','.join(map(str, executable)) + ',\n'
	source += "};\n";
	n_bytes = len(executable)
	return n_bytes, source

def source_for_embedded_tarfile(options):
	for file in FILES_EMBEDDED_IN_BINARY:
		contents = pkgutil.get_data('src', file)
		if file.endswith('.py'):
			contents = minify(contents)
		add_tar_file(options.tar, file, contents)
	options.tar.close()
	n_bytes = options.tar_buffer.tell()
	options.tar_buffer.seek(0)

	source = "\nstatic unsigned char tar_data[] = {";
	while True:
		bytes = options.tar_buffer.read(1024)
		if not bytes:
			break
		source += ','.join(map(str, bytes)) + ',\n'
	source += "};\n";
	return n_bytes, source

# Do some brittle shrinking of Python source  before embedding in binary.
# Very limited benefits as source is bzip2 compressed before embedded in binary

def minify(python_source_bytes):
	python_source = python_source_bytes.decode('utf-8')
	lines = python_source.splitlines()
	lines1 = []
	while lines:
		line = lines.pop(0)
		if is_doc_string_delimiter(line):
			line = lines.pop(0)
			while not is_doc_string_delimiter(line):
				line = lines.pop(0)
			line = lines.pop(0)
		if not is_comment(line):
			lines1.append(line)
	python_source = '\n'.join(lines1) + '\n'
	return python_source.encode('utf-8')

def is_doc_string_delimiter(line):
	return line == '    """'

def is_comment(line):
	return re.match(r'^\s*#.*$', line)

def add_tar_file(tar, pathname, bytes):
	file_buffer = io.BytesIO(bytes)
	file_info = tarfile.TarInfo(pathname)
	file_info.size = len(bytes)
	tar.addfile(file_info, file_buffer)

def search_path(program):
	for path in os.environ["PATH"].split(os.pathsep):
		full_path = os.path.join(path, program)
		if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
			return full_path

def get_my_path():
	dcc_path = os.path.realpath(sys.argv[0])
	# replace automount path with /home - otherwise breaks sometimes with ssh jobs
	dcc_path = re.sub(r'/tmp_amd/\w+/\w+ort/\w+/\d+/', '/home/', dcc_path)
	dcc_path = re.sub(r'^/tmp_amd/\w+/\w+ort/\d+/', '/home/', dcc_path)
	dcc_path = re.sub(r'^/(import|export)/\w+/\d+/', '/home/', dcc_path)
	return dcc_path

def get_clang_version(options):
	if options.clang_version:
		return
	# apple replaces clang version with xcode release
	# which might break the workarounds below for old clang version
	try:
		clang_version_string = subprocess.check_output([options.c_compiler, "--version"], universal_newlines=True)
		options.debug_print("clang version:", clang_version_string)
		# assume little about how version is printed, e.g. because Apple mangles it
		m = re.search("((\d+)\.(\d+)\.\d+)", clang_version_string, flags=re.I)
		if m:
			options.clang_version = m.group(1)
			options.clang_version_major = m.group(2)
			options.clang_version_minor = m.group(3)
			options.clang_version_float = float(m.group(2) + "." + m.group(3))
		else:
			options.die("can not parse clang version '{clang_version_string}'")

	except OSError as e:
		if options.debug:
			print(e)

	if not options.clang_version:
		options.die(f"can not get version information for '{options.c_compiler}'")
		sys.exit(1)

def get_libc_version(options):
	try:
		libc_version = subprocess.check_output(["ldd", "--version"]).decode("ascii")
		if options.debug:
			print("libc version:", libc_version)
		m = re.search("([0-9]\.[0-9]+)", libc_version)
		if m:
			return float(m.group(1))
	except Exception as e:
		if options.debug:
			print(e)
	return None
