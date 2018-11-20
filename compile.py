import io, os, platform, re, subprocess, sys, tarfile

from version import VERSION 
from explain_compiler_output import explain_compiler_output 
from embedded_source import embedded_source_main_wrapper_c, embedded_source_start_gdb_py, embedded_source_drive_gdb_py, embedded_source_watch_valgrind_py

EXTRA_C_COMPILER_ARGS = " -fcolor-diagnostics -Wall -std=gnu11 -g -lm -Wno-unused	-Wunused-comparison	 -Wunused-value -fno-omit-frame-pointer -fno-common -funwind-tables -fno-optimize-sibling-calls -Qunused-arguments".split()
MAXIMUM_SOURCE_FILE_EMBEDDED_BYTES = 1000000
CLANG_LIB_DIR="/usr/lib/clang/{clang_version}/lib/linux"


#
# Compile the user's program adding some C code
#
def compile(debug=False):
	os.environ['PATH'] = os.path.dirname(os.path.realpath(sys.argv[0])) + ':/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:' + os.environ.get('PATH', '') 
	args = parse_args(sys.argv[1:])

	if args.which_sanitizer == "memory" and platform.architecture()[0][0:2] == '32':
		if search_path('valgrind'):
			# -fsanitize=memory requires 64-bits so we fallback to embedding valgrind
			args.which_sanitizer = "valgrind"
		else:
			print("%s: uninitialized value checking not supported on 32-bit architectures", file=sys.stderr)
			sys.exit(1)
			

	clang_version = None
	try:
		clang_version = subprocess.check_output(["clang", "--version"], universal_newlines=True)
		if debug:
			print("clang version:", clang_version)
		m = re.search("clang version (\d+\.\d+\.\d+)", clang_version, flags=re.I)
		if m is not None:
			clang_version = m.group(1)
	except OSError as e:
		if debug:
			print(e)

	if not clang_version:
		print("Can not get clang version", file=sys.stderr)
		sys.exit(1)

	if args.which_sanitizer == "address" and platform.architecture()[0][0:2] == '32':
		libc_version = None
		try:
			libc_version = subprocess.check_output(["ldd", "--version"]).decode("ascii")
			if debug:
				print("libc version:", libc_version)
			m = re.search("([0-9]\.[0-9]+)", libc_version)
			if m is not None:
				libc_version = float(m.group(1))
			else:
				libc_version = None
		except Exception as e:
			if debug:
				print(e)

		if clang_version and libc_version and clang_version[0] in "345" and libc_version >= 2.27:
			print("incompatible clang libc versions, disabling error detection by sanitiziers", file=sys.stderr)
			sanitizer_args = []
			
	dcc_path = get_my_path()
	wrapper_source = embedded_source_main_wrapper_c
	wrapper_source = wrapper_source.replace('__DCC_PATH__', dcc_path)
	wrapper_source = wrapper_source.replace('__DCC_SANITIZER__', args.which_sanitizer)

	if args.embed_source:
		tar_n_bytes, tar_source = source_for_embedded_tarfile(args) 

	if args.which_sanitizer == "valgrind":
		# FIXME - make valgrind work with embedded source
#		args.embed_source = False
		sanitizer_args = []
		wrapper_source = wrapper_source.replace('__DCC_SANITIZER_IS_VALGRIND__', '1')
		if args.embed_source:
			watcher = fr"python3 -E -c \"import os,sys,tarfile,tempfile\n\
with tempfile.TemporaryDirectory() as temp_dir:\n\
	tarfile.open(fileobj=sys.stdin.buffer, bufsize={tar_n_bytes}, mode='r|xz').extractall(temp_dir)\n\
	os.chdir(temp_dir)\n\
	exec(open('watch_valgrind.py').read())\n\
\""
		else:
			watcher = dcc_path +  "--watch-stdin-for-valgrind-errors"
		wrapper_source = wrapper_source.replace('__DCC_MONITOR_VALGRIND__', watcher)
		wrapper_source = wrapper_source.replace('__DCC_LEAK_CHECK__', "yes" if args.leak_check else "no")
		wrapper_source = wrapper_source.replace('__DCC_SUPRESSIONS_FILE__', args.suppressions_file)
	elif args.which_sanitizer == "memory":
		sanitizer_args = ['-fsanitize=memory']
	else:
		# fixme add code to check version supports these
		sanitizer_args = ['-fsanitize=address', '-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer']
		args.which_sanitizer = "address"

	if args.shared_libasan and args.which_sanitizer != "valgrind":
		lib_dir = CLANG_LIB_DIR.replace('{clang_version}', clang_version)
		if os.path.exists(lib_dir):
			sanitizer_args += ['-shared-libasan', '-Wl,-rpath,' + lib_dir]
			
	if args.embed_source:
		wrapper_source = wrapper_source.replace('__DCC_EMBED_SOURCE__', '1')
		wrapper_source = tar_source + wrapper_source

# are there still cases where clang produces better warnings for -O??
#	# First run	 with -O enabled for better compile-time warnings 
#	command = [args.c_compiler, '-O', '-Wall']  + sanitizer_args + EXTRA_C_COMPILER_ARGS + args.user_supplied_compiler_args
#	if args.colorize_output:
#		command += ['-fcolor-diagnostics']
#	if args.debug:
#		print(" ".join(command), file=sys.stderr)
#	process = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
#
#	# workaround for  https://github.com/android-ndk/ndk/issues/184
#	if "undefined reference to `__" in process.stdout:
#			sanitizer_args = [c for c in sanitizer_args if not c in ['-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer']]
#			command = [args.c_compiler, '-O', '-Wall']  + sanitizer_args + EXTRA_C_COMPILER_ARGS + args.user_supplied_compiler_args
#			if args.debug:
#				print("undefined reference to `__mulodi4'", file=sys.stderr)
#				print("recompiling", " ".join(command), file=sys.stderr)
#			process = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

	command = [args.c_compiler] + sanitizer_args + EXTRA_C_COMPILER_ARGS + args.user_supplied_compiler_args
	if args.incremental_compilation:
		if args.debug:
			print('incremental compilation, running: ', " ".join(command), file=sys.stderr)
		sys.exit(subprocess.call(command))

	command +=	['-Wl,-wrap,main', '-x', 'c', '-']
	if args.debug:
		print(" ".join(command), file=sys.stderr)
	if args.debug > 1:
		print(" ".join(command), '<<eof', file=sys.stderr)
		print(wrapper_source)
		print("eof")
	process = subprocess.run(command, input=wrapper_source, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

	# workaround for  https://github.com/android-ndk/ndk/issues/184
	# when not triggered earlier	
	if "undefined reference to `__" in process.stdout:
		command = [c for c in command if not c in ['-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer']]
		if args.debug:
			print("undefined reference to `__mulodi4'", file=sys.stderr)
			print("recompiling", " ".join(command), file=sys.stderr)
		process = subprocess.run(command, input=wrapper_source, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

	if process.stdout:
		if args.explanations:
			explain_compiler_output(process.stdout, args)
		else:
			print(process.stdout, end='', file=sys.stderr)
			
	if process.returncode:
		sys.exit(process.returncode)
		
	sys.exit(process.returncode)
	
class Args(object):	
	c_compiler = "clang"
#	for c_compiler in ["clang-3.9", "clang-3.8", "clang"]:
#		if search_path(c_compiler):	 # shutil.which not available in Python 2
#			break
	which_sanitizer = "address"
	shared_libasan = True
	incremental_compilation = False
	leak_check = False
	suppressions_file = os.devnull
#	 linking_object_files = False
	user_supplied_compiler_args = []
	explanations = True
	max_explanations = 3
	embed_source = True	
	colorize_output = sys.stderr.isatty() or os.environ.get('DCC_COLORIZE_OUTPUT', False)
	debug = int(os.environ.get('DCC_DEBUG', '0'))
	source_files = set()
	tar_buffer = io.BytesIO()
	tar = tarfile.open(fileobj=tar_buffer, mode='w|xz')
	
def parse_args(commandline_args):
	args = Args()
	if not commandline_args:
		print("Usage: %s [--valgrind|--memory|--leak-check|--no-explanations|--no-shared-libasan|--no-embed-source] [clang-arguments] <c-files>" % sys.argv[0], file=sys.stderr)
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
	
def parse_arg(arg, next_arg, args):
	if arg in ['-u', '--undefined', '--uninitialized', '--uninitialised', '-fsanitize=memory', '--memory']:
		args.which_sanitizer = "memory"
	elif arg == '--valgrind':
		args.which_sanitizer = "valgrind"
	elif arg == '--leak-check':
		args.which_sanitizer = "valgrind"
		args.leak_check = True
	elif arg.startswith('--suppressions='):
		args.suppressions_file = arg[len('--suppressions='):]
	elif arg == '--explanations' or arg == '--no_explanation': # backwards compatibility
		args.explanations = True
	elif arg == '--no-explanations':
		args.explanations = False
	elif arg == '--shared-libasan' or arg == '-shared-libasan':
		args.shared_libasan = True
	elif arg == '--no-shared-libasan':
		args.shared_libasan = False
	elif arg == '--embed-source':
		args.embed_source = True
	elif arg == '--no-embed-source':
		args.embed_source = False
	elif arg == '-v':
		print('dcc version', VERSION)
		sys.exit(0)
	else:
		parse_clang_arg(arg, next_arg, args)
		
def parse_clang_arg(arg, next_arg, args):
	args.user_supplied_compiler_args.append(arg)
	if arg	== '-c':
		args.incremental_compilation = True
#		 elif arg.endswith('.o'):
#			 linking_object_files = True
	elif arg == '-fcolor-diagnostics':
		args.colorize_output = True
	elif arg == '-fno-color-diagnostics':
		args.colorize_output = False
	elif arg == '-o' and next_arg:
		object_filename = next_arg
		if object_filename.endswith('.c') and os.path.exists(object_filename):
			print("%s: will not overwrite %s with machine code" % (os.path.basename(sys.argv[0]), object_filename), file=sys.stderr)
			sys.exit(1)
	else:
		process_possible_source_file(arg, args)
	
def process_possible_source_file(pathname, args):
	extension = os.path.splitext(pathname)[1]
	if extension.lower() not in ['.c', '.h']:
		return
	# don't try to handle paths with .. or with leading /
	# should we convert argument to normalized relative path if possible
	# before passing to to compiler?
	normalized_path = os.path.normpath(pathname)
	if pathname != normalized_path:
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
	except OSError as e:
		if args.debug:
			print('process_possible_source_file', pathname, e)
		return
		
def source_for_embedded_tarfile(args):
	add_tar_file(args.tar, "start_gdb.py", embedded_source_start_gdb_py)
	add_tar_file(args.tar, "drive_gdb.py", embedded_source_drive_gdb_py)
	add_tar_file(args.tar, "watch_valgrind.py", embedded_source_watch_valgrind_py)
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

def add_tar_file(tar, pathname, contents):
	bytes = contents.encode('utf8')
	file_buffer = io.BytesIO(bytes)
	file_info = tarfile.TarInfo(pathname)
	file_info.size = len(bytes)
	tar.addfile(file_info, file_buffer)
	
def search_path(program):
	for path in os.environ["PATH"].split(os.pathsep):
		full_path = os.path.join(path, program)
		if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
			return full_path
