#
# code in this file will be be eventually removed
# if explanation here is incorrect, it should be moved
# to explain_compile_time_error.py
#

import re

def help_cs50(lines):
	r = help(lines)
	if not r:
		return None
	explanation = r[1]
	modified_explanation = []
	for e in explanation:
		if 'cs50' in e or 'not quite sure' in e.lower():
			continue
		me = e.replace("`clang`", 'the compiler')
		modified_explanation.append(me)
	if modified_explanation:
		return "\n ".join(modified_explanation)
	return None

# following code from
# https://github.com/cs50/help50-server/blob/master/helpers/clang.py

from collections import namedtuple

def help(lines):



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
