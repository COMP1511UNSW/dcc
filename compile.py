import codecs,io, os, pkgutil, platform, re, subprocess, sys, tarfile, tempfile

from version import VERSION 
from explain_compiler_output import explain_compiler_output 

# on some platforms -Wno-unused-result is needed to avoid warnings about scanf's return value being ignored -
# novice programmers will often be told to ignore scanf's return value
# when writing their first programs 

COMMON_WARNING_ARGS = "-Wall -Wno-unused -Wunused-variable -Wunused-value -Wno-unused-result".split()
COMMON_COMPILER_ARGS = COMMON_WARNING_ARGS + "-std=gnu11 -g -lm".split()

CLANG_ONLY_ARGS = "-Wunused-comparison -fno-omit-frame-pointer -fno-common -funwind-tables -fno-optimize-sibling-calls -Qunused-arguments".split()

GCC_ARGS = COMMON_COMPILER_ARGS + "-Wunused-but-set-variable -O  -o /dev/null".split()

MAXIMUM_SOURCE_FILE_EMBEDDED_BYTES = 1000000

CLANG_LIB_DIR="/usr/lib/clang/{clang_version}/lib/linux"

FILES_EMBEDDED_IN_BINARY = ["start_gdb.py", "drive_gdb.py", "watch_valgrind.py", "colors.py"]

# list of system includes for standard lib fucntion which will not
# interfer with dual sanitizer synchronization

DUAL_SANITIZER_SAFE_SYSTEM_INCLUDES = set(['assert.h', 'complex.h', 'ctype.h', 'errno.h', 'fenv.h', 'float.h', 'inttypes.h', 'iso646.h', 'limits.h', 'locale.h', 'math.h', 'setjmp.h', 'stdalign.h', 'stdarg.h', 'stdatomic.h', 'stdbool.h', 'stddef.h', 'stdint.h', 'stdio.h', 'stdlib.h', 'stdnoreturn.h', 'string.h', 'tgmath.h', 'time.h', 'uchar.h', 'wchar.h', 'wctype.h', 'sanitizer/asan_interface.h', 'malloc.h', 'strings.h', 'sysexits.h']) 

#
# Compile the user's program adding some C code
#
def compile():
	os.environ['PATH'] = os.path.dirname(os.path.realpath(sys.argv[0])) + ':/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:' + os.environ.get('PATH', '') 
	args = parse_args(sys.argv[1:])
	# we have to set these explicitly because 
	clang_args = COMMON_COMPILER_ARGS + CLANG_ONLY_ARGS
	if args.colorize_output:
		clang_args += ['-fcolor-diagnostics']
		clang_args += ['-fdiagnostics-color']
		
	args.unsafe_system_includes = list(args.system_includes_used - DUAL_SANITIZER_SAFE_SYSTEM_INCLUDES)
	
	if not args.sanitizers:
		reason = ""
		if args.incremental_compilation:
			reason = "incremental compilation"
		elif args.object_files_being_linked:
			reason = "object files being linked"
		elif args.object_files_being_linked:
			reason = "library other than C standard library used"
		elif args.threads_used:
			reason = "threads used"
		elif args.unsafe_system_includes:
			reason = args.unsafe_system_includes[0]+ " used"
		if reason:
			print('warning uninititialized variable checking disabled:', reason, file=sys.stderr)
			args.sanitizers = ["address"]
		else:
			args.sanitizers = ["address", "valgrind"]
		
	if "memory" in args.sanitizers and platform.architecture()[0][0:2] == '32':
		print("MemorySanitizer not available on 32-bit architectures", file=sys.stderr)
		sys.exit(1)
			

	# apple replaces clang version with xcode release
	# which might break the workarounds below for old clang version
	clang_version = None
	try:
		clang_version = subprocess.check_output([args.c_compiler, "--version"], universal_newlines=True)
		if args.debug:
			print("clang version:", clang_version)
		# assume little about how version is printed, e.g. because Apple mangles it
		m = re.search("((\d+)\.(\d+)\.\d+)", clang_version, flags=re.I)
		if m:
			clang_version = m.group(1)
			clang_version_major = m.group(2)
			clang_version_minor = m.group(3)
			clang_version_float = float(m.group(2) + "." + m.group(3))
		else:
			print("Can not parse clang version '%s'" % clang_version, file=sys.stderr)
			sys.exit(1)
			
	except OSError as e:
		if args.debug:
			print(e)

	if not clang_version:
		print("Can not get version information for '%s'" % args.c_compiler, file=sys.stderr)
		sys.exit(1)

	if "address" in args.sanitizers  and platform.architecture()[0][0:2] == '32':
		libc_version = None
		try:
			libc_version = subprocess.check_output(["ldd", "--version"]).decode("ascii")
			if args.debug:
				print("libc version:", libc_version)
			m = re.search("([0-9]\.[0-9]+)", libc_version)
			if m is not None:
				libc_version = float(m.group(1))
			else:
				libc_version = None
		except Exception as e:
			if args.debug:
				print(e)

		if  libc_version and clang_version_float < 6 and libc_version >= 2.27:
			print("incompatible clang libc versions, disabling error detection by sanitizers", file=sys.stderr)
			args.sanitizers = [a for a in args.sanitizers if a != "address"]

	# shared_libasan breaks easily ,e.g if there are libraries in  /etc/ld.so.preload
	# and we can't override with verify_asan_link_order=0 for clang version < 5
	# and with clang-6 on debian __asan_default_options not called with shared_libasan
	if args.shared_libasan is None and clang_version_float >= 7.0:
		args.shared_libasan = True

	if args.incremental_compilation and len(args.sanitizers) > 1:
		print("only a single sanitizer supported with incremental compilation", file=sys.stderr)
		sys.exit(1)
		
	if args.object_files_being_linked and len(args.sanitizers) > 1:
		print("only a single sanitizer supported with linking of .o files", file=sys.stderr)
		sys.exit(1)
			
	dcc_path = get_my_path()

	wrapper_source = ''.join(pkgutil.get_data('src', f).decode('utf8') for f in ['dcc_main.c', 'dcc_dual_sanitizers.c', 'dcc_util.c'])
	
	wrapper_source = wrapper_source.replace('__PATH__', dcc_path)
	wrapper_source = wrapper_source.replace('__SUPRESSIONS_FILE__', args.suppressions_file)
	wrapper_source = wrapper_source.replace('__STACK_USE_AFTER_RETURN__', "1" if args.stack_use_after_return else "0")
	wrapper_source = wrapper_source.replace('__CLANG_VERSION_MAJOR__', clang_version_major)
	wrapper_source = wrapper_source.replace('__CLANG_VERSION_MINOR__', clang_version_minor)
	wrapper_source = wrapper_source.replace('__N_SANITIZERS__', str(len(args.sanitizers)))
	wrapper_source = wrapper_source.replace('__SANITIZER_1__', args.sanitizers[0].upper())
	if len(args.sanitizers) > 1:
		wrapper_source = wrapper_source.replace('__SANITIZER_2__', args.sanitizers[1].upper())
	
	if args.embed_source:
		tar_n_bytes, tar_source = source_for_embedded_tarfile(args) 
		watcher = fr"python3 -E -c \"import io,os,sys,tarfile,tempfile\n\
with tempfile.TemporaryDirectory() as temp_dir:\n\
 buffer = io.BytesIO(sys.stdin.buffer.raw.read({tar_n_bytes}))\n\
 if len(buffer.getbuffer()) == {tar_n_bytes}:\n\
  tarfile.open(fileobj=buffer, bufsize={tar_n_bytes}, mode='r|xz').extractall(temp_dir)\n\
  os.chdir(temp_dir)\n\
  exec(open('watch_valgrind.py').read())\n\
\""
	else:
		tar_n_bytes, tar_source = 0, ''
		watcher = dcc_path +  "--watch-stdin-for-valgrind-errors"
	wrapper_source = wrapper_source.replace('__MONITOR_VALGRIND__', watcher)
	
	# -x - must come after any filenames but before ld options
	
	#
	# if we have two sanitizers we need to do first compile a binary with appropriate
	# options for sanitizers 2 and embed the binary as C data inside the bianry for sanitizer 1
	#
	base_compile_command = [args.c_compiler] + args.user_supplied_compiler_args + ['-x', 'c', '-', ] +  clang_args
	compiler_stdout = ''
	executable_source = ''
	if len(args.sanitizers) == 2:
		sanitizer2_wrapper_source, sanitizer2_sanitizer_args = update_source(args.sanitizers[1], 2, wrapper_source, tar_source, args, clang_version, clang_version_float)
		try:
			# can't use tempfile.NamedTemporaryFile becaus emay be multiple opens
			executable = tempfile.mkstemp(prefix='dcc_sanitizer2')[1]
			command = base_compile_command + sanitizer2_sanitizer_args + ['-o', executable]
			compiler_stdout = execute_compiler(command, sanitizer2_wrapper_source, args, debug_wrapper_file="tmp_dcc_sanitizer2.c")
			with open(executable, "rb") as f:
				executable_n_bytes, executable_source = source_for_sanitizer2_executable(f.read())
			os.unlink(executable)
		except OSError:
			# compiler may unlink temporary file resulting in this exception
			sys.exit(1)	

	# leave leak checking to valgrind if it is running
	# because it currently gives better errors
	wrapper_source, sanitizer_args = update_source(args.sanitizers[0], 1, wrapper_source, tar_source, args, clang_version, clang_version_float)

	if args.incremental_compilation:
		incremental_compilation_args = sanitizer_args + clang_args + args.user_supplied_compiler_args
		command = [args.c_compiler] + incremental_compilation_args
		if args.debug:
			print('incremental compilation, running: ', " ".join(command), file=sys.stderr)
		sys.exit(subprocess.call(command))
		
	if executable_source:
		wrapper_source = wrapper_source.replace('__EXECUTABLE_N_BYTES__', str(executable_n_bytes))
		wrapper_source = executable_source + wrapper_source
	
	command = base_compile_command + sanitizer_args 
	compiler_stdout = execute_compiler(command, wrapper_source, args, print_stdout=not compiler_stdout)
	
	# gcc picks up some errors at compile-time that clang doesn't, e.g 
	# int main(void) {int a[1]; return a[0];}
	# so run gcc as well if available

	if not compiler_stdout and search_path('gcc') and 'gcc' not in args.c_compiler and not args.object_files_being_linked:
		command = ['gcc'] + args.user_supplied_compiler_args + GCC_ARGS
		if args.debug:
			print("compiling with gcc for extra checking", file=sys.stderr)
		execute_compiler(command, '', args, rename_functions=False)	

	sys.exit(0)


def update_source(sanitizer, sanitizer_n, wrapper_source, tar_source,  args, clang_version, clang_version_float):
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
		if clang_version_float >= 3.6:
			sanitizer_args += ['-fno-sanitize-recover=undefined,integer']

	if args.shared_libasan and  sanitizer == "address":
		lib_dir = CLANG_LIB_DIR.replace('{clang_version}', clang_version)
		if os.path.exists(lib_dir):
			sanitizer_args += ['-shared-libasan', '-Wl,-rpath,' + lib_dir]

	wrapper_source = wrapper_source.replace('__LEAK_CHECK_YES_NO__', "yes" if args.leak_check else "no")
	leak_check = args.leak_check
	if leak_check and args.sanitizers[1:] == ["valgrind"]:
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

	
def execute_compiler(base_command, compiler_stdin, args, rename_functions=True, print_stdout=True, debug_wrapper_file="tmp_dcc_sanitizer1.c"):
	command = list(base_command)
	if compiler_stdin:
		if rename_functions and not args.unsafe_system_includes:
			# unistd functions used by single-sanitizer dcc
			rename_function_names = ['_exit', 'close', 'execvp', 'getpid']
			# unistd functions used by dual-sanitizer dcc
			if len(args.sanitizers) > 1:
				rename_function_names += ['lseek', 'pipe', 'read', 'sleep', 'unlink', 'write']
			command +=  ['-D{}=__renamed_{}'.format(f, f) for f in rename_function_names]

		wrapped_functions = ['main']

		override_functions = []
		if len(args.sanitizers) > 1:
			override_functions  = ['clock', 'fdopen', 'fopen', 'freopen', 'system', 'time']

		if args.ifdef_instead_of_wrap:
			command +=  ['-D{}=__real_{}'.format(f, f) for f in wrapped_functions]
			command +=  ['-D{}=__wrap_{}'.format(f, f) for f in override_functions]
			for f in wrapped_functions:
				compiler_stdin = compiler_stdin.replace('__wrap_' + f, f)
			for f in override_functions:
				compiler_stdin = compiler_stdin.replace('__real_' + f, f)
		else:
			command += ['-Wl' + ''.join(',-wrap,' + f for f in wrapped_functions + override_functions)]

	if args.debug:
		print(" ".join(command), file=sys.stderr)

	if args.debug > 1 and compiler_stdin:
		print("Leaving dcc code in", debug_wrapper_file, "compile with this command:", file=sys.stderr)
		print(" ".join(command).replace('-x c -', debug_wrapper_file), file=sys.stderr)
		try:
			with open(debug_wrapper_file,"w") as f:
				f.write(compiler_stdin)
		except OSError as e:
			print(e)
	input = codecs.encode(compiler_stdin, 'utf8')
	process = subprocess.run(command, input=input, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	stdout = codecs.decode(process.stdout, 'utf8', errors='replace')

	# avoid a confusing mess of linker errors
	if "undefined reference to `main" in stdout:
		print("Error: your program does not contain a main function - a C program must contain a main function", file=sys.stderr)
		sys.exit(1)

	# workaround for  https://github.com/android-ndk/ndk/issues/184
	# when not triggered earlier    
	if "undefined reference to `__mul" in stdout:
		command = [c for c in command if not c in ['-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer']]
		if args.debug:
			print("undefined reference to `__mulodi4'", file=sys.stderr)
			print("recompiling", " ".join(command), file=sys.stderr)
		process = subprocess.run(command, input=input, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		stdout = codecs.decode(process.stdout, 'utf8', errors='replace')

	# a user call to a renamed unistd.h function appears to be undefined
	# so recompile without renames
	
	if rename_functions and "undefined reference to `__renamed_" in stdout:
		if args.debug:
			print("undefined reference to `__renamed_' recompiling without -D renames", file=sys.stderr)
		return execute_compiler(base_command, compiler_stdin, args, rename_functions=False, print_stdout=print_stdout, debug_wrapper_file=debug_wrapper_file)
	
	if process.stdout and print_stdout:
		if args.explanations:
			explain_compiler_output(stdout, args)
		else:
			print(stdout, end='', file=sys.stderr)
			
	if process.returncode:
		sys.exit(process.returncode)
		
	return stdout	
	
class Args(object): 
	c_compiler = "clang"
#   for c_compiler in ["clang-3.9", "clang-3.8", "clang"]:
#       if search_path(c_compiler):  # shutil.which not available in Python 2
#           break
	sanitizers = []
	shared_libasan = None
	stack_use_after_return = None
	incremental_compilation = False
	leak_check = False
	suppressions_file = os.devnull
	user_supplied_compiler_args = []
	explanations = True
	max_explanations = 3
	embed_source = True
	# FIXME - check terminal actually support ANSI
	colorize_output = sys.stderr.isatty() or os.environ.get('DCC_COLORIZE_OUTPUT', False)
	debug = int(os.environ.get('DCC_DEBUG', '0'))
	source_files = set()
	tar_buffer = io.BytesIO()
	tar = tarfile.open(fileobj=tar_buffer, mode='w|xz')
	object_files_being_linked = False
	libraries_being_linked = False
	threads_used = False
	system_includes_used = set()
	ifdef_instead_of_wrap = sys.platform == "darwin" # ld reportedly doesn't have wrap on Darwin
	
def parse_args(commandline_args):
	args = Args()
	if not commandline_args:
		print("Usage: %s [-fsanitize=sanitizer1,sanitizer2] [--leak-check] [clang-arguments] <c-files>" % sys.argv[0], file=sys.stderr)
		sys.exit(1)

	while commandline_args:
		arg = commandline_args.pop(0)
		next_arg = commandline_args[0] if commandline_args else None
		parse_arg(arg, next_arg, args)
		
	return args

def get_my_path():
	dcc_path = os.path.realpath(sys.argv[0])
	# replace CSE mount path with /home - otherwise breaks sometimes with ssh jobs
	dcc_path = re.sub(r'/tmp_amd/\w+/\w+ort/\w+/\d+/', '/home/', dcc_path)
	dcc_path = re.sub(r'^/tmp_amd/\w+/\w+ort/\d+/', '/home/', dcc_path) 
	dcc_path = re.sub(r'^/(import|export)/\w+/\d+/', '/home/', dcc_path)    
	return dcc_path

KNOWN_SANITIZERS = set()
DEFAULT_SANITIZERS = set(['undefined'])

def parse_arg(arg, next_arg, args):
			#
	if arg.startswith('-fsanitize='):
		args.sanitizers = []
		sanitizer_list = arg[len('-fsanitize='):].split(',')
		for sanitizer in sanitizer_list:
			if sanitizer in ['memory', 'address', 'valgrind']:
				args.sanitizers.append(sanitizer)
			elif sanitizer not in ['undefined']:
				print("unknown sanitizer '%s'" % sanitizer, file=sys.stderr)
				sys.exit(1)	
		if len(args.sanitizers) not in [1,2]:
			print("only 1 or sanitizers supported", file=sys.stderr)
			sys.exit(1)	
	elif arg in ['--memory']:	# for backwardscompatibility
		args.sanitizers = ["memory"]
	elif arg == '--valgrind':	# for backwardscompatibility
		args.sanitizers = ["valgrind"]
	elif arg == '--leak-check' or arg == '--leakcheck':
		args.leak_check = True
	elif arg.startswith('--suppressions='):
		args.suppressions_file = arg[len('--suppressions='):]
	elif arg == '--explanations' or arg == '--no_explanation': # backwards compatibility
		args.explanations = True
	elif arg == '--no-explanations':
		args.explanations = False
	elif arg == '--shared-libasan' or arg == '-shared-libasan':
		args.shared_libasan = True
	elif arg == '--use-after-return':
		args.stack_use_after_return = True
	elif arg == '--no-shared-libasan':
		args.shared_libasan = False
	elif arg == '--embed-source':
		args.embed_source = True
	elif arg == '--no-embed-source':
		args.embed_source = False
	elif arg == '--ifdef'  or arg == '--ifdef-main':
		args.ifdef_instead_of_wrap = True
	elif arg.startswith('--c-compiler='):
		args.c_compiler = arg[arg.index('=') + 1:]
	elif arg == '-fcolor-diagnostics':
		args.colorize_output = True
	elif arg == '-fno-color-diagnostics':
		args.colorize_output = False
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
	else:
		parse_clang_arg(arg, next_arg, args)
		
def parse_clang_arg(arg, next_arg, args):
	args.user_supplied_compiler_args.append(arg)
	if arg == '-c':
		args.incremental_compilation = True
	elif arg.startswith('-l'):
		args.libraries_being_linked = True
	elif arg == '-pthreads':
		args.threads_used = True
	elif arg == '-o' and next_arg:
		object_filename = next_arg
		if object_filename.endswith('.c') and os.path.exists(object_filename):
			print("%s: will not overwrite %s with machine code" % (os.path.basename(sys.argv[0]), object_filename), file=sys.stderr)
			sys.exit(1)
	else:
		process_possible_source_file(arg, args)

# FIXME this is crude and brittle 
def process_possible_source_file(pathname, args):
	extension = os.path.splitext(pathname)[1]
	if extension.lower() in ['.a', '.o', '.so']:
		args.object_files_being_linked = True
		return
	# don't try to handle paths with .. or with leading /
	# should we convert argument to normalized relative path if possible
	# before passing to to compiler?
	normalized_path = os.path.normpath(pathname)
	if pathname != normalized_path and os.path.join('.', normalized_path) != pathname:
		if args.debug: print('not embedding source of', pathname, 'because normalized path differs:', normalized_path, file=sys.stderr)
		return
	if normalized_path.startswith('..'):
		if args.debug: print('not embedding source of', pathname, 'because it contains ..', file=sys.stderr)
		return
	if os.path.isabs(pathname):
		if args.debug: print('not embedding source of', pathname, 'because it has absolute path', file=sys.stderr)
		return
	if pathname in args.source_files:
		return
	try:
		if os.path.getsize(pathname) > MAXIMUM_SOURCE_FILE_EMBEDDED_BYTES:
			return
		args.tar.add(pathname)
		args.source_files.add(pathname)
		if args.debug > 1: print('adding', pathname, 'to tar file', file=sys.stderr)
		with open(pathname, encoding='utf-8', errors='replace') as f:
			for line in f:
				m = re.match(r'^\s*#\s*include\s*"(.*?)"', line)
				if m:
					process_possible_source_file(m.group(1), args)
				m = re.match(r'^\s*#\s*include\s*<(.*?)>', line)
				if m:
					args.system_includes_used.add(m.group(1))
	except OSError as e:
		if args.debug:
			print('process_possible_source_file', pathname, e)
		return

def source_for_sanitizer2_executable(executable):
	source = "\nstatic unsigned char sanitizer2_executable[] = {";
	source += ','.join(map(str, executable)) + ',\n'
	source += "};\n";
	n_bytes = len(executable)
	return n_bytes, source

def source_for_embedded_tarfile(args):
	for file in FILES_EMBEDDED_IN_BINARY:
		contents = pkgutil.get_data('src', file)
		if file.endswith('.py'):
			contents = minify(contents)
		add_tar_file(args.tar, file, contents)
	args.tar.close()
	n_bytes = args.tar_buffer.tell()
	args.tar_buffer.seek(0)

	source = "\nstatic unsigned char tar_data[] = {";
	while True:
		bytes = args.tar_buffer.read(1024)
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
