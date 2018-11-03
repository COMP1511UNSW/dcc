import io, os, platform, re, subprocess, sys, tarfile,  traceback

EXTRA_C_COMPILER_ARGS = "-std=gnu11 -g -lm -Wno-unused	-Wunused-comparison	 -Wunused-value -fno-omit-frame-pointer -fno-common -funwind-tables -fno-optimize-sibling-calls -Qunused-arguments".split()
MAXIMUM_SOURCE_FILE_EMBEDDED_BYTES = 1000000

#
# Compile the user's program adding some C code
#
def compile():
	os.environ['PATH'] = os.path.dirname(os.path.realpath(sys.argv[0])) + ':/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:' + os.environ.get('PATH', '') 
	args = parse_args(sys.argv[1:])

	if args.which_sanitizer == "memory" and platform.architecture()[0][0:2] == '32':
		if search_path('valgrind'):
			# -fsanitize=memory requires 64-bits so we fallback to embedding valgrind
			args.which_sanitizer = "valgrind"
		else:
			print("%s: uninitialized value checking not supported on 32-bit architectures", file=sys.stderr)
			sys.exit(1)
			
	dcc_path = get_my_path()
	global colorize_output
	wrapper_source = embedded_source_main_wrapper_c
	wrapper_source = wrapper_source.replace('__DCC_PATH__', dcc_path)
	wrapper_source = wrapper_source.replace('__DCC_SANITIZER__', args.which_sanitizer)

	if args.which_sanitizer == "valgrind":
		# FIXME - make valgrind work with embedded source
		args.embed_source = False
		sanitizer_args = []
		wrapper_source = wrapper_source.replace('__DCC_SANITIZER_IS_VALGRIND__', '1')
		wrapper_source = wrapper_source.replace('__DCC_MONITOR_VALGRIND__', dcc_path+' --watch-stdin-for-valgrind-errors')
		wrapper_source = wrapper_source.replace('__DCC_LEAK_CHECK__', "yes" if args.leak_check else "no")
		wrapper_source = wrapper_source.replace('__DCC_SUPRESSIONS_FILE__', args.suppressions_file)
	elif args.which_sanitizer == "memory":
		sanitizer_args = ['-fsanitize=memory']
	else:
		# fixme add code to check version supports these
		sanitizer_args = ['-fsanitize=address', '-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer']
		args.which_sanitizer = "address"

	if args.embed_source:
		wrapper_source = wrapper_source.replace('__DCC_EMBED_SOURCE__', '1')
		wrapper_source = source_for_embedded_tarfile(args) + wrapper_source

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


	command = [args.c_compiler, '-w'] + sanitizer_args + EXTRA_C_COMPILER_ARGS + args.user_supplied_compiler_args
	if args.incremental_compilation:
		if args.debug:
			print(" ".join(command), file=sys.stderr)
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
		if args.print_explanations:
			explain_compiler_output(process.stdout, colorize_output=args.colorize_output)
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
	incremental_compilation = False
	leak_check = False
	suppressions_file = os.devnull
#	 linking_object_files = False
	user_supplied_compiler_args = []
	print_explanations = True
	embed_source = True	
	colorize_output = sys.stderr.isatty() or os.environ.get('DCC_COLORIZE_OUTPUT', False)
	debug = int(os.environ.get('DCC_DEBUG', '0'))
	source_files = set()
	tar_buffer = io.BytesIO()
	tar = tarfile.open(fileobj=tar_buffer, mode='w|xz')
	
def parse_args(commandline_args):
	args = Args()
	if not commandline_args:
		print("Usage: %s [--valgrind|--memory|'--leak-check'|--no_explanation] [clang-arguments] <c-files>" % sys.argv[0], file=sys.stderr)
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
	elif arg == '--explanation':
		args.print_explanations = True
	elif arg == '--no_explanation':
		args.print_explanations = False
	elif arg == '--embed_source':
		args.embed_source = True
	elif arg == '--no_embed_source':
		args.embed_source = False
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
		if args.debug: print('not embedding source of', pathname, 'becaused normalized path differs:', normalized_path, file=sys.stderr)
		return
	if normalized_path.startswith('..'):
		if args.debug: print('not embedding source of', pathname, 'because contains ..', file=sys.stderr)
		return
	if os.path.isabs(pathname):
		if args.debug: print('not embedding source of', pathname, 'becaused has absolute path', file=sys.stderr)
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
	except OSError:
		return
		
def source_for_embedded_tarfile(args):
	add_tar_file(args.tar, "start_gdb.py", embedded_source_start_gdb_py)
	add_tar_file(args.tar, "drive_gdb.py", embedded_source_drive_gdb_py)
	args.tar.close()
	args.tar_buffer.seek(0)

	source = "\nstatic unsigned char tar_data[] = {";
	while True:
		bytes = args.tar_buffer.read(1024)
		if not bytes:
			break
		source += ','.join(map(str, bytes)) + ',\n'
	source += "};\n";
	return source

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

embedded_source_main_wrapper_c = "this definition is for debugging - it will be over-written"

embedded_source_run_gdb_py = "this definition is for debugging - it will be over-written"
