import os, platform, re, signal, subprocess, sys, traceback

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
	wrapper_source = dcc_wrapper_source
	wrapper_source = wrapper_source.replace('__DCC_PATH__', '"'+dcc_path+'"')
	wrapper_source = wrapper_source.replace('__DCC_SANITIZER__', '"'+which_sanitizer+'"')
	if which_sanitizer == "memory" and platform.architecture()[0][0:2] == '32':
		if search_path('valgrind'):
			# -fsanitize=memory requires 64-bits so we fallback to embedding valgrind
			which_sanitizer = "valgrind"
		else:
			print("%s: uninitialized value checking not support on 32-bit architectures", file=sys.stderr)
			sys.exit(1)
	if which_sanitizer == "valgrind":
		sanitizer_args = []
		wrapper_source = wrapper_source.replace('__DCC_SANITIZER_IS_VALGRIND__', '1')
		wrapper_source = wrapper_source.replace('__DCC_MONITOR_VALGRIND__', '"'+dcc_path+' --watch-stdin-for-valgrind-errors"')
		wrapper_source = wrapper_source.replace('__DCC_LEAK_CHECK__', "yes" if leak_check else "no")
		wrapper_source = wrapper_source.replace('__DCC_SUPRESSIONS_FILE__', suppressions_file)
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
		print(wrapper_source)
		print("eof")
	process = subprocess.run(command, input=wrapper_source, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
	# workaround for  https://github.com/android-ndk/ndk/issues/184
	# can  be triggered	 not earlier
	if "undefined reference to `__" in process.stdout:
		command = [c for c in command if not c in ['-fsanitize=undefined', '-fno-sanitize-recover=undefined,integer']]
		if debug:
			print("undefined reference to `__mulodi4'", file=sys.stderr)
			print("recompiling", " ".join(command), file=sys.stderr)
		process = subprocess.run(command, input=wrapper_source, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
	print(process.stdout, end='', file=sys.stderr)
	sys.exit(process.returncode)

def search_path(program):
	for path in os.environ["PATH"].split(os.pathsep):
		full_path = os.path.join(path, program)
		if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
			return full_path

dcc_wrapper_source = "this definition is for debugging  will be over-written"