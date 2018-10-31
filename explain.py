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

#
# following code from
# https://github.com/cs50/help50/blob/master/helpers/clang.py
from collections import namedtuple

def help(lines):

	# $ clang foo.c
	# foo.c:13:25: error: adding 'int' to a string does not append to the string [-Werror,-Wstring-plus-int]
	matches = match(r"adding '(.+)' to a string does not append to the string", lines[0])
	if matches:
		response = ["Careful, you can't concatenate values and strings in C using the `+` operator, as you seem to be trying to do on line {} of `{}`.".format(matches.line, matches.file)]
		if len(lines) >= 2 and re.search(r"printf\s*\(", lines[1]):
			response.append("Odds are you want to provide `printf` with a format code for that value and pass that value to `printf` as an argument.")
			return (lines[0:2], response)
		return (lines[0:1], response)

	# caesar.c:9:18: error: array index 1 is past the end of the array (which contains 1 element) [-Werror,-Warray-bounds]
	#	 int k = atoi(argv[1]);
	#				  ^	   ~
	matches = match(r"array index (\d+) is past the end of the array", lines[0])
	if matches:
		array = caret_extract(lines[1:3])
		if array:
			response = ["Careful, on line {} of `{}`, it looks like you're trying to access location {} of `{}`, which doesn't exist; `{}` isn't that long.".format(matches.line, matches.file, matches.group[0], array, array)]
		else:
			response = ["Careful, on line {} of `{}`, it looks like you're trying to access location {} of an array, which doesn't exist; the array isn't that long.".format(matches.line, matches.file, matches.group[0])]
		response.append("Keep in mind that arrays are 0-indexed.")
		if array:
			return (lines[0:3], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# foo.c:6:21: error: array subscript is not an integer
	#	  printf("%i\n", x["28"]);
	#					  ^~~~~
	matches = match(r"array subscript is not an integer", lines[0])
	if matches:
		array = caret_extract(lines[1:3], left_aligned=False)
		index = tilde_extract(lines[1:3])
		if array and index:
			response = [
				"Looks like you're trying to access an element of the array `{}` on line {} of `{}`, but your index (`{}`) is not of type `int`.".format(array, matches.line, matches.file, index)
			]
			if index.startswith("\"") and index.endswith("\""):
				response.append("Right now, your index is of type `string` instead.")
		else:
			response = [
				"Looks like you're trying to access an element of an array on line {} of `{}`, but your index is not of type `int`.".format(matches.line, matches.file)
			]
		response.append("Make sure your index (the value between square brackets) is an `int`.")
		if len(lines) >= 2 and re.search(r"[.*]", lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# foo.c:1:3: error: assigning to 'float' from incompatible type 'float (void)'
	#		  f = get_float;
	#			^ ~~~~~~~~~
	matches = match(r"assigning to '(.+)' from incompatible type '.+ \(.+\)'", lines[0])
	if matches:
		function = tilde_extract(lines[1:3])
		if function:
			response = [
				"Looks like you're trying to call `{}` on line {} of `{}`, but did you forget parentheses after the function's name?".format(function, matches.line, matches.file)
			]
			return (lines[0:3], response);
		else:
			response = [
				"Looks like you're trying to call a function on line {} of `{}`, but did you forget parentheses after the function's name?".format(matches.line, matches.file)
			]
			return (lines[0:1], response);

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:3:12: error: conflicting types for 'round'
	# int round(int n);
	#	  ^
	matches = match(r"conflicting types for '(.*)'", lines[0])
	if matches:
		response = [
			"Looks like you're redeclaring the function `{}`, but with a different return type on line {} of `{}`.".format(matches.group[0], matches.line, matches.file)
		]
		if len(lines) >= 4:
			new_matches = re.search(r"^([^:]+):(\d+):\d+: note: previous declaration is here", lines[3])
			if new_matches:
				if matches.file == new_matches.group(1):
					response.append("You had already declared this function on line {}.".format(matches.line))
				else:
					response.append("The function `{}` is already declared in the library {}. Try renaming your function.".format(matches.group[0], new_matches.group(1).split('/')[-1]))
				return(lines[0:4], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# test.c:51:17: error: 'continue' statement not in loop statement
	#				  continue;
	#				  ^
	matches = match(r"'continue' statement not in loop statement", lines[0])
	if matches:
		response = [
			"Looks like you're trying to use `continue` on line {} of `{}`, which isn't inside of a loop, but that keyword can only be used inside of a loop.".format(matches.line, matches.file)
		]
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:6:1: error: control reaches end of non-void function [-Werror,-Wreturn-type]
	#
	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:7:1: error: control may reach end of non-void function [-Werror,-Wreturn-type]
	matches = match(r"control (may )?reach(es)? end of non-void function", lines[0])
	if matches:
		response = ["Ensure that your function will always return a value. If your function is not meant to return a value, try changing its return type to `void`."]
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:5:29: error: data argument not used by format string [-Werror,-Wformat-extra-args]
	#	 printf("%d %d", 27, 28, 29);
	#			~~~~~~~			 ^
	matches = match(r"data argument not used by format string", lines[0])
	if matches:
		response = [
			"You have more arguments in your formatted string on line {} of `{}` than you have format codes.".format(matches.line, matches.file),
			"Make sure that the number of format codes equals the number of additional arguments.",
			"Try either adding format code(s) or removing argument(s)."
		]
		if len(lines) >= 2 and re.search(r"%", lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:6:8: error: declaration shadows a local variable [-Werror,-Wshadow]
	#	 int x = 28;
	#		 ^
	# foo.c:5:13: note: previous declaration is here
	#				int x = 2;
	#					^
	#
	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:5:20: error: declaration shadows a local variable [-Werror,-Wshadow]
	#	 for (int i = 0, i < 28, i++)
	#					 ^
	matches = match(r"declaration shadows a local variable", lines[0])
	if matches:
		response = [
			"On line {} of `{}`, it looks like you're trying to declare a variable that's already been declared elsewhere.".format(matches.line, matches.file)
		]

		# check to see if declaration shadowing is due to for loop with commas instead of semicolons
		if len(lines) >= 2:
			for_loop = re.search(r"^\s*for\s*\(", lines[1])
			if for_loop:
				response.append("If you meant to create a `for` loop, be sure that each part of the `for` loop is separated with a semicolon rather than a comma.")
				if (len(lines) >= 3 and re.search(r"^\s*\^$", lines[2])):
					return (lines[0:3], response)
				return (lines[0:2], response)

		# see if we can get the line number of the previous declaration of the variable
		prev_declaration_file = None
		prev_declaration_line = None
		if len(lines) >= 4:
			prev = re.search(r"^([^:]+):(\d+):\d+: note: previous declaration is here", lines[3])
			if prev:
				prev_declaration_line = prev.group(2)
				prev_declaration_file = prev.group(1)

		omit_suggestion = "If you meant to use the variable you've already declared previously"
		if prev_declaration_line and prev_declaration_file:
			omit_suggestion += " (on line {} of `{}`)".format(prev_declaration_line, prev_declaration_file)
		omit_suggestion += ", try getting rid of the data type of the variable on line {} of `{}`. You only need to include the data type when you first declare a variable.".format(matches.line, matches.file)
		response.append(omit_suggestion)
		response.append("Otherwise, if you did mean to declare a new variable, try changing its name to a name that hasn't been used yet.")

		if len(lines) >= 4 and prev_declaration_line != None:
			return (lines[0:7], response) if len(lines) >= 6 and re.search(r"^\s*\^$", lines[5]) else (lines[0:4], response)
		if len(lines) >= 2:
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:5:16: error: division by zero is undefined [-Werror,-Wdivision-by-zero]
	# int x = 28 / 0;
	#			 ^ ~
	matches = match(r"division by zero is undefined", lines[0])
	if matches:
		response = [
			"Looks like you're trying to divide by `0` (which isn't defined mathematically) on line {} of `{}`.".format(matches.line, matches.file)
		]
		if len(lines) >= 2:
			return (lines[0:2], response)
		else:
			return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:9:2: error: expected '}'
	# }
	#  ^
	matches = match(r"expected '}'", lines[0])
	if matches:
		response = ["Make sure that all opening brace symbols `{` are matched with a closing brace `}`."]
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:6:8: error: expected '(' after 'if'
	#	  if x == 28
	#		 ^
	matches = match(r"expected '\(' after 'if'", lines[0])
	if matches:
		response = [
			"In your `if` statement on line {} of `{}`, be sure that you're enclosing the condition you're testing within parentheses.".format(matches.line, matches.file)
		]
		if len(lines) >= 2 and re.search(r"if\s*\(", lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:6:1: error: expected ')'
	# }
	# ^
	matches = match(r"expected '\)'", lines[0])
	if matches:
		# assume that the line number for the matching ')' is the line that generated the error
		match_line = matches.line
		n = 1

		# if there's a note on which '(' to match, use that line number instead
		if (len(lines) >= 4):
			parens_match = re.search(r"^([^:]+):(\d+):\d+: note: to match this '\('", lines[3])
			if parens_match:
				match_line = parens_match.group(2)
				n = 4

		response = [
			"Make sure that all opening parentheses `(` are matched with a closing parenthesis `)` in `{}`.".format(matches.file),
			"In particular, check to see if you are missing a closing parenthesis on line {} of `{}`.".format(match_line, matches.file)
		]
		return (lines[0:n], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:5:27: error: expected ';' after expression
	#	 printf("hello, world!")
	#							^
	#							;
	matches = match(r"expected ';' (?:after expression|at end of declaration|after do\/while statement)", lines[0])
	if matches:
		response = ["Try including a semicolon at the end of line {} of `{}`.".format(matches.line, matches.file)]
		if len(lines) >= 3 and re.search(r"^\s*\^$", lines[2]):
			if len(lines) >= 4 and re.search(r"^\s*;$", lines[3]):
				return (lines[0:4], response)
			return (lines[0:3], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:5:22: error: expected ';' in 'for' statement specifier
	#	 for (int i = 0, i < 28, i++)
	#					   ^
	matches = match(r"expected ';' in 'for' statement specifier", lines[0])
	if matches:
		response = ["Be sure to separate the three components of the 'for' loop on line {} with semicolons.".format(matches.file)]
		if len(lines) >= 2 and re.search(r"for\s*\(", lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:28:28: error: expected expression
	matches = match(r"expected expression", lines[0])
	if matches:
		response = [
			"Not quite sure how to help, but focus your attention on line {} of `{}`!".format(matches.line, matches.file)
		]
		return (lines[0:1], response)

	# mario.c:8:16: error: expected identifier
	# if (i<23)&&(i>0)
	#			 ^
	# 1 error generated.
	# make: *** [mario] Error 1
	matches = match(r"expected identifier", lines[0])
	if matches:
		response = [
			"Not quite sure how to help, but focus your attention on line {} of `{}`!".format(matches.line, matches.file)
		]
		if (len(lines) >= 3 and has_caret(lines[2])):
			return (lines[0:3], response)
		else:
			return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:5:1: error: expected identifier or '('
	# do
	# ^
	matches = match(r"expected identifier or '\('", lines[0])
	if matches:
		response = [
			"Looks like `clang` is having some trouble understanding where your functions start and end in your code.",
			"Are you defining a function (like `main` or some other function) somewhere just before line {} of `{}`?".format(matches.line, matches.file),
			"If so, make sure the function's first line doesn't end with a semicolon.",
			"Also make sure that all of the code for your function is inside of curly braces."
		]
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:3:12: error: expected parameter declarator
	# int square(28);
	#			 ^
	matches = match(r"expected parameter declarator", lines[0])
	if matches:
		response = [
			"If you're trying to call a function on line {} of `{}`, be sure that you're calling it inside of curly braces within a function. Also check that the function's header (the line introducing the function's name) doesn't end in a semicolon.".format(matches.line, matches.file),
			"Alternatively, if you're trying to declare a function or prototype on line {} of `{}`, be sure each argument to the function is formatted as a data type followed by a variable name.".format(matches.line, matches.file)
		]
		if len(lines) >= 3 and re.search(r"^\s*\^$", lines[2]):
			return (lines[0:3], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:9:1: error: expected 'while' in do/while loop
	# }
	# ^
	matches = match(r"expected 'while' in do/while loop", lines[0])
	if matches:
		response = [
			"Looks like you're trying to create a `do/while` loop, but you've left off the `while` statement.",
			"Try adding `while` followed by a condition just before line {} of `{}`.".format(matches.line, matches.file)
		]
		return (lines[0:1], response)

	# $ clang foo.c
	# foo.c:6:16: error: expression result unused [-Werror,-Wunused-value]
	# n*12;
	#  ^ 1 error generated.
	matches = match(r"expression result unused", lines[0])
	if matches:
		response = [
			"On line {} of `{}` you are performing an operation, but not saving the result.".format(matches.line, matches.file),
			"Did you mean to print or store the result in a variable?"
		]
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:1:19: error: extra tokens at end of #include directive [-Werror,-Wextra-tokens]
	# #include <stdio.h>;
	#					^
	matches = match(r"extra tokens at end of #include directive", lines[0])
	if matches:
		response = [
			"You seem to have an error in `{}` on line {}.".format(matches.file, matches.line),
			"By \"extra tokens\", `clang` means that you have one or more extra characters on that line that you shouldn't."
		]
		if len(lines) >= 3 and re.search(r"^\s*\^", lines[2]):
			token = lines[1][lines[2].index("^")]
			if token == ";":
				response.append("Try removing the semicolon at the end of that line.")
			else:
				response.append("Try removing the `{}` at the end of that line.".format(token))
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:1:19: error: extraneous ')' before ';' [-Werror]
	# digit = (number % (tracker)) / (tracker/10));
	#											 ^
	matches = match(r"extraneous '\)' before ';'", lines[0])
	if matches:
		response = [
			"You seem to have an extra parenthesis on line {} of `{}`, just before the semicolon.".format(matches.line, matches.file)
		]
		if len(lines) >= 3 and has_caret(lines[2]):
			return (lines[0:3], response)
		else:
			return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:21:1: error: extraneous closing brace ('}')
	# }
	# ^
	matches = match(r"extraneous closing brace \('}'\)", lines[0])
	if matches:
		response = [
			"You seem to have an unnecessary `}}` on line {} of `{}`.".format(matches.line, matches.file)
		]
		if len(lines) >= 3 and re.search(r"^\s*\^\s*$", lines[2]):
			return (lines[0:3], response)
		else:
			return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:1:10: fatal error: 'studio.h' file not found
	# #include <studio.h>
	#		   ^
	matches = match(r"'(.*)' file not found", lines[0])
	if matches:
		response = [
			"Looks like you're trying to `#include` a file (`{}`) on line {} of `{}` which does not exist.".format(matches.group[0], matches.line, matches.file)
		]
		if matches.group[0] in ["studio.h"]:
			response.append("Did you mean to `#include <stdio.h>` (without the `u`)?")
		else:
			response.append("Check to make sure you spelled the filename correctly.")

		if len(lines) >= 2 and re.search(r"#include", lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# foo.c:6:16: error: format string is not a string literal (potentially insecure) [-Werror,-Wformat-security]
	# printf(c);
	# ^ 1 error generated.
	matches = match(r"format string is not a string literal", lines[0])
	if matches and len(lines) >= 3 and re.search(r"^\s*\^", lines[2]):
		line = matches.line
		file = matches.file
		matches = re.search(r"^(.?printf|.?scanf)\s*\(", lines[1][lines[2].index("^"):])
		print(lines[1][lines[2].index("^"):])
		if matches:
			response = ["The first argument to `{}` on line {} of `{}` should be a double-quoted string.".format(matches.group(1), line, file)]
			return (lines[0:2], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:7:15: error: expression is not an integer constant expression
	#		  case (x > 28):
	#			   ~^~~~~~~
	matches = match(r"expression is not an integer constant expression", lines[0])
	if matches:
		response = [
			"Remember that each `case` in a `switch` statement needs to be an integer (or a `char`, which is really just an integer), not a Boolean expression or other type."
		]
		return (lines[0:2], response) if len(lines) >= 2 else (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:12:15: error: if statement has empty body [-Werror,-Wempty-body]
	#	if (n > 0);
	#			  ^
	matches = match(r"(if statement|while loop|for loop) has empty body", lines[0])
	if matches:
		response = [
			"Try removing the semicolon directly after the closing parentheses of the `{}` on line {} of `{}`.".format(matches.group[0],matches.line, matches.file)
		]
		if len(lines) >= 2 and re.search(r"if\s*\(", lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# round.c:17:5: error: ignoring return value of function declared with const attribute [-Werror,-Wunused-value]
	# round(cents);
	# ^~~~~ ~~~~~
	matches = match(r"ignoring return value of function declared with (.+) attribute", lines[0])
	if matches:
		function = caret_extract(lines[1:3])
		if function:
			response = [
				"You seem to be calling `{}` on line {} of `{}` but aren't using its return value.".format(function, matches.line, matches.file),
				"Did you mean to assign it to a variable?"
			]
			return (lines[0:3], response)
		else:
			response = [
				"You seem to be calling a function on line {} of `{}` but aren't using its return value.".format(matches.line, matches.file),
				"Did you mean to assign it to a variable?"
			]
			return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:5:12: error: implicit declaration of function 'get_int' is invalid in C99 [-Werror,-Wimplicit-function-declaration]
	#	 int x = get_int();
	#			 ^
	matches = match(r"implicit declaration of function '([^']+)' is invalid", lines[0])
	if matches:
		response = [
			"You seem to have an error in `{}` on line {}.".format(matches.file, matches.line),
			"By \"implicit declaration of function '{}'\", `clang` means that it doesn't recognize `{}`.".format(matches.group[0], matches.group[0])
		]
		if matches.group[0] in ["eprintf", "get_char", "get_double", "get_float", "get_int", "get_long", "get_long_long", "get_string", "GetChar", "GetDouble", "GetFloat", "GetInt", "GetLong", "GetLongLong", "GetString"]:
			response.append("Did you forget to `#include <cs50.h>` (in which `{}` is declared) atop your file?".format(matches.group[0]))
		elif matches.group[0] in ["crypt"]:
			response.append("Did you forget to `#include <unistd.h>` (in which `{}` is declared) atop your file?".format(matches.group[0]))
		else:
			response.append("Did you forget to `#include` the header file in which `{}` is declared atop your file?".format(matches.group[0]))
			response.append("Did you forget to declare a prototype for `{}` atop `{}`?".format(matches.group[0], matches.file))

		if len(lines) >= 2 and re.search(matches.group[0], lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:3:4: error: implicitly declaring library function 'printf' with type 'int (const char *, ...)' [-Werror]
	#	 printf("hello, world!");
	#	 ^
	matches = match(r"implicitly declaring library function '([^']+)'", lines[0])
	if matches:
		if (matches.group[0] in ["printf"]):
			response = ["Did you forget to `#include <stdio.h>` (in which `printf` is declared) atop your file?"]
		elif (matches.group[0] in ["malloc"]):
			response = ["Did you forget to `#include <stdlib.h>` (in which `malloc` is declared) atop your file?"]
		else:
			response = ["Did you forget to `#include` the header file in which `{}` is declared atop your file?".format(matches.group[0])]
		if len(lines) >= 2 and re.search(r"printf\s*\(", lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:3:8: error: incompatible pointer to integer conversion initializing 'int' with an expression of type 'char [3]'
	#		[-Werror,-Wint-conversion]
	#	 int x = "28";
	#		 ^	 ~~~~
	matches = match(r"incompatible (.+) to (.+) conversion", lines[0])
	if matches:
		response = [
			"By \"incompatible conversion\", `clang` means that you are assigning a value to a variable of a different type on line {} of `{}`. Try ensuring that your value is of type `{}`.".format(matches.line, matches.file, matches.group[1])
		]
		if len(lines) >= 2 and re.search(r"=", lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ ./a.out
	# foo.c:7:5: runtime error: index 2 out of bounds for type 'int [2]'
	matches = match(r"index (-?\d+) out of bounds for type '.+'", lines[0])
	if matches:
		response = []
		if int(matches.group[0]) < 0:
			response.append("Looks like you're to access location {} of an array on line {} of `{}`, but that location is before the start of the array.".format(matches.group[0], matches.line, matches.file))
		else:
			response.append("Looks like you're to access location {} of an array on line {} of `{}`, but that location is past the end of the array.".format(matches.group[0], matches.line, matches.file, matches.group[0]))
		return (lines[0:1], response)

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
			"Be sure to use the correct format code (e.g., `%i` for integers, `%f` for floating-point values, `%s` for strings, etc.) in your format string on line {} of `{}`.".format(matches.line, matches.file)
		]
		if len(lines) >= 3 and re.search(r"\^", lines[2]):
			if len(lines) >= 4 and re.search(r"%", lines[3]):
				return (lines[0:4], response)
			return (lines[0:3], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# foo.c:8:19: error: invalid '==' at end of declaration; did you mean '='?
	#	 for(int i == 0; i < height; i++)
	#			   ^~
	#			   =
	matches = match(r"invalid '==' at end of declaration; did you mean '='?", lines[0])
	if matches:
		response = [
			"Looks like you may have used '==' (which is used for comparing two values for equality) instead of '=' (which is used to assign a value to a variable) on line {} of `{}`?".format(matches.line, matches.file)
		]
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:1:2: error: invalid preprocessing directive
	# #incalude <stdio.h>
	#  ^
	matches = match(r"invalid preprocessing directive", lines[0])
	if matches:
		response = [
			"By \"invalid preprocessing directive\", `clang` means that you've used a preprocessor command on line {} (a command beginning with #) that is not recognized.".format(matches.file)
		]
		if len(lines) >= 2:
			directive = re.search(r"^([^' ]+)", lines[1])
			if directive:
				response.append("Check to make sure that `{}` is a valid directive (like `#include`) and is spelled correctly.".format(directive.group(1)))
				return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:3:1: error: 'main' must return 'int'
	# void main(void)
	# ^~~~
	# int
	matches = match(r"'main' must return 'int'", lines[0])
	if matches:
		response = [
			"Your `main` function (declared on line {} of `{}`) must have a return type `int`.".format(matches.line, matches.file)
		]
		cur_type = caret_extract(lines[1:3])
		if len(lines) >= 3 and cur_type:
			response.append("Right now, it has a return type of `{}`.".format(cur_type))
			return (lines[0:3], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:5:16: error: more '%' conversions than data arguments [-Werror,-Wformat]
	#	 printf("%d %d\n", 28);
	#				~^
	matches = match(r"more '%' conversions than data arguments", lines[0])
	if matches:
		response = [
			"You have too many format codes in your format string on line {} of `{}`.".format(matches.line, matches.file),
			"Be sure that the number of format codes equals the number of additional arguments."
		]
		if len(lines) >= 2 and re.search(r"%", lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:1:10: error: multiple unsequenced modifications to 'space' [-Werror,-Wunsequenced]
	#  space = space--;
	#		 ~		^
	matches = match(r"multiple unsequenced modifications to '(.*)'", lines[0])
	if matches:
		variable = matches.group[0]
		response = [
			"Looks like you're changing the variable `{}` multiple times in a row on line {} of `{}`.".format(variable, matches.line, matches.file)
		]
		if len(lines) >= 2:
			file = matches.file
			line = matches.line
			matches = re.search(r"(--|\+\+)", lines[1])
			if matches:
				response.append("When using the `{}` operator, there is no need to assign the result to the variable. Try using just `{}{}` instead".format(matches.group(1), variable, matches.group(1)))
				return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# foo.c:6:5: error: only one parameter on 'main' declaration [-Werror,-Wmain]
	# int main(int x)
	#	  ^
	matches = match(r"only one parameter on 'main' declaration", lines[0])
	if matches:
		response = [
		"Looks like your declaration of `main` on line {} of `{}` isn't quite right. The declaration of `main` should be `int main(void)` or `int main(int argc, char *argv[])` or some equivalent.".format(matches.line, matches.file)
	]
		return (lines[0:1], response)

	# clang -ggdb3 -O0 -std=c11 -Wall -Werror -Wshadow	  mario.c  -lcs50 -lm -o mario
	# mario.c:12:19: error: relational comparison result unused [-Werror,-Wunused-comparison]
	#	  while (height < 0, height < 23);
	#			 ~~~~~~~^~~
	# 1 error generated.
	# make: *** [mario] Error 1
	matches = match(r"relational comparison result unused", lines[0])
	if matches:
		response = [
			"Looks like you're comparing two values on line {} of `{}` but not using the result?".format(matches.line, matches.file)
		]
		if len(lines) >= 3 and has_caret(lines[2]):
			return (lines[0:3], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:6:14: error: result of comparison against a string literal is unspecified (use strncmp instead) [-Werror,-Wstring-compare]
	#	  if (word < "twenty-eight")
	#			   ^ ~~~~~~~~~~~~~~
	matches = match(r"result of comparison against a string literal is unspecified", lines[0])
	if matches:
		response = [
			"You seem to be trying to compare two strings on line {} of `{}`".format(matches.line, matches.file),
			"You can't compare two strings the same way you would compare two numbers (with `<`, `>`, etc.).",
			"Did you mean to compare two characters instead? If so, try using single quotation marks around characters instead of double quotation marks.",
			"If you need to compare two strings, try using the `strcmp` function declared in `string.h`."
		]
		if len(lines) >= 3 and has_caret(lines[2]):
			return (lines[0:3], response)
		return (lines[0:1], response)

	# $ make caesar.c
	# clang -ggdb3 -O0 -std=c11 -Wall -Werror -Wshadow	  caesar.c	-lcs50 -lm -o caesar
	# caesar.c:5:5: error: second parameter of 'main' (argument array) must be of type 'char **'
	# int main(int argc, int argv[])
	#	  ^
	matches = match(r"second parameter of 'main' \(argument array\) must be of type 'char \*\*'", lines[0])
	if matches:
		response = [
			"Looks like your declaration of `main` isn't quite right.",
			"Be sure its second parameter is `char *argv[]` or some equivalent!"
		]
		return (lines[0:1], response)

	# fifteen.c:179:21: error: subscripted value is not an array, pointer, or vector
	# temp = board[d - 1][d - 2];
	#		 ~~~~~^~~~~~
	# TODO: extract symbol
	matches = match(r"subscripted value is not an array, pointer, or vector", lines[0])
	if matches:
		response = [
			"Looks like you're trying to index into a variable as though it's an array, even though it isn't, on line {} of `{}`?".format(matches.line, matches.file)
		]
		return (lines[0:1], response)

	# $ clang mario.c
	# mario.c:18:17: error: too many arguments to function call, expected 0, have 1
	#		  hashtag(x);
	#		  ~~~~~~~ ^
	matches = match(r"too many arguments to function call, expected (\d+), have (\d+)", lines[0])
	if matches:
		function = tilde_extract(lines[1:3]) if len(lines) >= 3 else None
		response = [
			"You seem to be passing in too many arguments to a function on line {} of `{}`.".format(matches.line, matches.file)
		]
		if function:
			response.append("The function `{}`".format(function))
		else:
			response.append("The function")
		response[1] += " is supposed to take {} argument(s), but you're passing it {}.".format(matches.group[0], matches.group[1])
		response.append("Try providing {} fewer argument(s) to the function.".format(str(int(matches.group[1]) - int(matches.group[0]))))
		if function:
			return (lines[0:3], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:3:1: error: type specifier missing, defaults to 'int' [-Werror,-Wimplicit-int]
	# square (int x) {
	# ^
	matches = match(r"type specifier missing, defaults to 'int'", lines[0])
	if matches:
		response = [
			"Looks like you're trying to declare a function on line {} of `{}`.".format(matches.line, matches.file),
			"Be sure, when declaring a function, to specify its return type just before its name."
		]
		if len(lines) >= 3 and re.search(r"^\s*\^$", lines[2]):
			return (lines[0:3], response)
		return (lines[0:1], response)

	# water.c:9:21: error: unknown escape sequence '\ ' [-Werror,-Wunknown-escape-sequence]
	# printf("bottles: %i \ n", shower);
	#					  ^~
	matches = match(r"unknown escape sequence '\\ '", lines[0])
	if matches:
		response = [
			"Looks like you have a space immediately after a backslash on line {} of `{}` but shouldn't.".format(matches.line, matches.file),
		]
		if len(lines) >= 3 and has_caret(lines[2]):
			response.append("Did you mean to escape some character?")
			return (lines[0:3], response)
		else:
			response.append("Did you mean to escape some character?")
			return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:6:10: error: using the result of an assignment as a condition without parentheses [-Werror,-Wparentheses]
	#	 if (x = 28)
	#		 ~~^~~~
	matches = match(r"using the result of an assignment as a condition without parentheses", lines[0])
	if matches:
		response = [
			"When checking for equality in the condition on line {} of `{}`, try using a double equals sign (`==`) instead of a single equals sign (`=`).".format(matches.line, matches.file)
		]
		if len(lines) >= 2 and re.search(r"if\s*\(", lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:5:4: error: use of undeclared identifier 'x'
	#	 x = 28;
	#	 ^
	matches = match(r"use of undeclared identifier '([^']+)'", lines[0])
	if matches:
		response = [
			"By \"undeclared identifier,\" `clang` means you've used a name `{}` on line {} of `{}` which hasn't been defined.".format(matches.group[0], matches.line, matches.file)
		]
		if matches.group[0] in ["true", "false", "bool", "string"]:
			response.append("Did you forget to `#include <cs50.h>` (in which `{}` is defined) atop your file?".format(matches.group[0]))
		else:
			response.append("If you mean to use `{}` as a variable, make sure to declare it by specifying its type, and check that the variable name is spelled correctly.".format(matches.group[0]))
		if len(lines) >= 2 and re.search(matches.file, lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:(.text+0x9): undefined reference to `get_int'
	matches = match(r"undefined reference to `([^']+)'", lines[0], raw=True)
	if matches:
		if matches.group[0] == "main":
			response = ["Did you try to compile a file that doesn't contain a `main` function?"]
		else:
			response = [
				"By \"undefined reference,\" `clang` means that you've called a function, `{}`, that doesn't seem to be implemented.".format(matches.group[0]),
				"If that function has, in fact, been implemented, odds are you've forgotten to tell `clang` to \"link\" against the file that implements `{}`.".format(matches.group[0])
			]
			if matches.group[0] in ["eprintf", "get_char", "get_double", "get_float", "get_int", "get_long", "get_long_long", "get_string"]:
				response.append("Did you forget to compile with `-lcs50` in order to link against against the CS50 Library, which implements `{}`?".format(matches.group[0]))
			elif matches.group[0] in ["GetChar", "GetDouble", "GetFloat", "GetInt", "GetLong", "GetLongLong", "GetString"]:
				response.append("Did you forget to compile with `-lcs50` in order to link against against the CS50 Library, which implements `{}`?".format(matches.group[0]))
			elif matches.group[0] == "crypt":
				response.append("Did you forget to compile with -lcrypt in order to link against the crypto library, which implements `crypt`?")
			else:
				response.append("Did you forget to compile with `-lfoo`, where `foo` is the library that defines `{}`?".format(matches.group[0]))
		return (lines[0:1], response)

	# $ clang foo.c
	# foo.c:18:1: error: unknown type name 'define'
	# define _XOPEN_SOURCE 500
	# ^
	matches = match(r"unknown type name 'define'", lines[0])
	if matches:
		response = [
			"If trying to define a constant on line {} of `{}`, be sure to use `#define` rather than just `define`.".format(matches.line, matches.file)
		]
		return (lines[0:3], response) if len(lines) >= 3 else (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:1:1: error: unknown type name 'include'
	# include <stdio.h>
	# ^
	matches = match(r"unknown type name 'include'", lines[0])
	if matches:
		response = [
			"If trying to include a header file on line {} of `{}`, be sure to use `#include` rather than just `include`.".format(matches.line, matches.file)
		]
		return (lines[0:3], response) if len(lines) >= 3 else (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:1:1: error: unknown type name 'bar'
	# bar baz
	# ^
	# TODO: check if baz has () after it so as to distinguish attempted variable declaration from function declaration
	matches = match(r"unknown type name '(.+)'", lines[0])
	if matches:
		response = [
			"You seem to be using `{}` on line {} of `{}` as though it's a type, even though it's not been defined as one.".format(matches.group[0], matches.line, matches.file),
		]
		if (matches.group[0] == "bool"):
			response.append("Did you forget `#include <cs50.h>` or `#include <stdbool.h>` atop `{}`?".format(matches.file))
		elif (matches.group[0] == "size_t"):
			response.append("Did you forget `#include <string.h>` atop `{}`?".format(matches.file))
		elif (matches.group[0] == "string"):
			response.append("Did you forget `#include <cs50.h>` atop `{}`?".format(matches.file))
		else:
			response.append("Did you perhaps misspell `{}` or forget to `typedef` it?".format(matches.group[0]))
		return (lines[0:3], response) if len(lines) >= 3 else (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:6:9: error: unused variable 'x' [-Werror,-Wunused-variable]
	#	  int x = 28;
	#		  ^
	matches = match(r"unused variable '([^']+)'", lines[0])
	if matches:
		response = [
			"It seems that the variable `{}` (declared on line {} of `{}`) is never used in your program. Try either removing it altogether or using it.".format(matches.group[0], matches.line, matches.file)
		]
		return (lines[0:1], response)

	# $ clang foo.c
	# /tmp/foo-1ce1b9.o: In function `main':
	# foo.c:6:20: error: variable 'x' is uninitialized when used here [-Werror,-Wuninitialized]
	#	  printf("%d\n", x);
	#					 ^
	matches = match(r"variable '(.*)' is uninitialized when used here", lines[0])
	if matches:
		response = [
			"It looks like you're trying to use the variable `{}` on line {} of `{}`.".format(matches.group[0], matches.line, matches.file),
			"However, on that line, the variable `{}` doesn't have a value yet.".format(matches.group[0]),
			"Be sure to assign a value to `{}` before trying to access its value.".format(matches.group[0])
		]
		if len(lines) >= 2 and re.search(matches.group[0], lines[1]):
			return (lines[0:2], response)
		return (lines[0:1], response)

	# $ clang -ggdb3 -O0 -std=c11 -Wall -Werror -Wshadow	water.c	 -lcs50 -lm -o water
	# water.c:8:15: error: variable 'x' is uninitialized when used within its own initialization [-Werror,-Wuninitialized]
	# int x= 12*x;
	#	  ~		^
	matches = match(r"variable '(.+)' is uninitialized when used within its own initialization", lines[0])
	if matches:
		response = [
			"Looks like you have `{}` on both the left- and right-hand side of the `=` on line {} of `{}`, but `{}` doesn't yet have a value.".format(matches.group[0], matches.line, matches.file, matches.group[0]),
			"Be sure not to initialize `{}` with itself.".format(matches.group[0])
		]
		if len(lines) >= 3 and re.search(r"^\s*~\s*\^\s*$", lines[2]):
			return (lines[0:3], response)
		return (lines[0:1], response)

	# $ clang foo.c
	# foo.c:6:10: error: void function 'f' should not return a value [-Wreturn-type]
	#		   return 0;
	#		   ^	  ~
	matches = match(r"void function '(.+)' should not return a value", lines[0])
	if matches:
		value = tilde_extract(lines[1:3])
		if len(lines) >= 3 and value:
			response = [
				"It looks like your function, `{}`, is returning `{}` on line {} of `{}`, but its return type is `void`.".format(matches.group[0], value, matches.line, matches.file),
				"Are you sure you want to return a value?"
			]
			return (lines[0:3], response)
		else:
			response = [
				"It looks like your function, `{}`, is returning a value on line {} of `{}`, but its return type is `void`.".format(matches.group[0], matches.line, matches.file),
				"Are you sure you want to return a value?"
			]
			return (lines[0:1], response)

# Performs a regular-expression match on a particular clang error or warning message.
# The first capture group is the filename associated with the message.
# The second capture group is the line number associated with the message.
# set raw=True to search for a message that doesn't follow clang's typical error output format.
def match(expression, line, raw=False):
	query = r"^([^:\s]+):(\d+):\d+: (?:warning|(?:fatal |runtime )?error): " + expression
	if raw:
		query = expression
	matches = re.search(query, line)
	if matches:
		Match = namedtuple('Match', ['file', 'line', 'group'])
		if raw:
			return Match(file=None, line=None, group=matches.groups())
		else:
			return Match(file=matches.group(1), line=matches.group(2), group=matches.groups()[2:])

# extract the name of a variable above the ^
# by default, assumes that ^ is under the first character of the variable
# if left_aligned is set to False, ^ is under the next character after the variable
# if char is set to True, will extract just a single character
def caret_extract(lines, left_aligned=True, char=False):
	if len(lines) < 2 or not has_caret(lines[1]):
		return
	index = lines[1].index("^")

	if char and len(lines[0]) >= index + 1:
		return lines[0][index]

	if left_aligned:
		matches = re.match(r"^([A-Za-z0-9_]+)", lines[0][index:])
	else:
		matches = re.match(r"^.*?([A-Za-z0-9_]+)$", lines[0][:index])
	return matches.group(1) if matches else None

# returns true if line contains a caret diagnostic
def has_caret(line):
	return True if (re.search(r"^[ ~]*\^[ ~]*$", line)) else False

# extracts all characters above the first sequence of ~
def tilde_extract(lines):
	if len(lines) < 2 or not re.search(r"~", lines[1]):
		return
	start = lines[1].index("~")
	length = 1
	while len(lines[1]) > start + length and lines[1][start + length] == "~":
		length += 1
	if len(lines[0]) < start + length:
		return
	return lines[0][start:start+length]

# end help50 code
