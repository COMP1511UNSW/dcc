def explain_compiler_output(output, colorize_output=False):
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
		while i < len(lines):
			matching_error_messages = help_dcc(colourless_lines[i:]) or help_cs50(colourless_lines[i:])

			if not matching_error_messages: 
				break

			matched_error_messages, explanation = matching_error_messages

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
				if args.colorize_output:
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


#
# some extra helpers 

def help_dcc(lines):
	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:5:19: warning: format specifies type 'int *' but the argument has type 'int' [-Wformat]
	#	 printf("%d\n", "hello!");
	#			 ~~		^~~~~~~~
	#			 %s
	# TODO: pattern match on argument's type
	matches = match(r"format specifies type '(?P<type>int|double) \*' but the argument has type '(?P=type)'", lines[0])
	if matches:
		argument = caret_extract(lines[1:3])
		if argument and re.match(r'^[a-zA-Z]', argument):
			response = [
				"Perhaps you have forgotten an `&` before the argument `{}` on line {} of `{}`.".format(argument, matches.line, matches.file)
			]
			if len(lines) >= 4 and re.search(r"%", lines[3]):
				return (lines[0:4], response)
			return (lines[0:3], response)
	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:5:19: error: format specifies type 'int' but the argument has type 'char *' [-Werror,-Wformat]
	#	 printf("%d\n", "hello!");
	#			 ~~		^~~~~~~~
	#			 %s
	# TODO: pattern match on argument's type
	matches = match(r"format specifies type '[^:]+' but the argument has type '[^:]+'", lines[0])
	if matches:
		response = [
			"Be sure to use the correct format code (e.g., `%d` for integers, `%lf` for floating-point values) in your format string on line {} of `{}`.".format(matches.line, matches.file)
		]
		if len(lines) >= 3 and re.search(r"\^", lines[2]):
			if len(lines) >= 4 and re.search(r"%", lines[3]):
				return (lines[0:4], response)
			return (lines[0:3], response)
		return (lines[0:1], response)
	# $ clang foo.c
	# /usr/bin/../lib/gcc/x86_64-linux-gnu/6.3.0/../../../x86_64-linux-gnu/crt1.o: In function `_start':
	# (.text+0x20): undefined reference to `main'
	# clang: error: linker command failed with exit code 1 (use -v to see invocation)
	if lines[1:] and re.search(r"undefined reference to `main'", lines[1]):
		response = [
			"Your program does not contain a main function - a C program must contain a main function."
		]
		return (lines, response)
	# $ clang a.c b.c
	# /tmp/b-9a488a.o: In function `main':
	# /home/andrewt/b.c:1: multiple definition of `main'
	# /tmp/a-583396.o:/home/andrewt/a.c:1: first defined here
	# clang: error: linker command failed with exit code 1 (use -v to see invocation)
	if lines[1:] and re.search(r"multiple definition of `main'", lines[1]):
		response = [
			"Your program contains more than one main function - a C program can only contain one main function."
		]
		return (lines, response)

