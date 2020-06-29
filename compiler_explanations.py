#!/usr/bin/env python3

import copy, re, sys
import colors
from drive_gdb import explanation_url

def get_explanation(message, colorize_output):
	for e in explanations:
		text = e.get(message, colorize_output)
		if text:
			e = copy.deepcopy(e)
			e.text = text
			return e
	return None
	

#
# label - unique identifier, used as file name
#
# regex - if set, matched against text, if match fails no explanation is returned
#
# precondition - if callable, it is called with message and regex match results as arguments
#                if value returned is False, no explanation is returned
#                if value returned is non-empty string and explanation is not set
#                the value is returned as explanation 
# 
# explanation - if explanation is callable, it is called with message and regex match results as arguments
#               and value returned as explanation
#               if explanation is a string, it is evaluated as f-string with the fields from the message object
#               available as local variables,
#               Note, this includes the highlighted_word and underlined_word in the compiler message (if any)
#               The result of the evluation returned as the explanation
#
# show_note - print the note (if any)  on a clang warning
#
# no_following_explanations - if True, don't print explanations after this one
#                             use where confusing parasitic errors likely
#
# reproduce - C program which should yield explanation

class Explanation():

	def __init__(self, label=None, precondition=None, regex=None, explanation=None, no_following_explanations=False, show_note=True, reproduce='', long_explanation=False, long_explanation_url=''):
		self.label = label
		self.precondition = precondition
		self.regex = regex
		self.explanation = explanation
		self.no_following_explanations = no_following_explanations
		self.show_note = show_note
		self.reproduce = reproduce
		self.long_explanation = long_explanation
		self.long_explanation_url = long_explanation_url

	def get(self, message, colorize_output):
		explanation = self.get_short_explanation(message, colorize_output)
		if explanation and (self.long_explanation or self.long_explanation_url):
			url = self.long_explanation_url or explanation_url(self.label)
			explanation += "\n  See more information here: " + url
		return explanation

	def get_short_explanation(self, message, colorize_output):
		match = None
		if self.regex:
			match = re.search(self.regex, "\n".join(message.text_without_ansi_codes), flags=re.I|re.DOTALL)
			if not match:
				return None

		if hasattr(self.precondition, '__call__') :
			r = self.precondition(message, match)
			if not r:
				return None
			if isinstance(r, str) and not self.explanation:
				return r

		if hasattr(self.explanation, '__call__'):
			return self.explanation(message, match)
			
		if colorize_output:
			color = colors.color
		else:
			color = lambda text, *args, **kwargs: text

		parameters = dict((name, getattr(message, name)) for name in dir(message) if not name.startswith('__'))
		parameters['match'] = match
		parameters['color'] = color
		parameters['emphasize'] = lambda text: color(text, style='bold')
		parameters['danger'] = lambda text: color(text, color='red', style='bold')
		parameters['info'] = lambda text: color(text, 'cyan', style='bold')
		return eval('f"' + self.explanation.replace('\n', '\\n') +'"',  globals(), parameters)

explanations = [

	Explanation(
		label = 'two_main_functions',	
		
		regex = r'multiple definition of \W*main\b',
			
		explanation = "Your program contains more than one main function - a C program can only contain one main function.",
		
		reproduce = """
// hack to get 2 main functions compiled in separate files
//dcc_flags=$src_file
int main(void) {
}
"""
	),
	

	Explanation(
		label = 'no_main_function',	
		
		regex = r'undefined reference to \W*main\b',
			
		explanation = "Your program does not contain a main function - a C program must contain a main function.",
		
		no_following_explanations = True,

		reproduce = """
"""
	),
	

	Explanation(
		label = 'scanf_missing_ampersand',	
		
		regex = r"format specifies type '(?P<type>int|double) \*' but the argument has type '(?P=type)'",
			
		explanation = "Perhaps you have forgotten an '&' before '{emphasize(highlighted_word)}' on line {line_number}.",
		
		reproduce = """
#include <stdio.h>

int main(void) {
	int i;
	scanf("%d", i);
}
"""
	),

	
	Explanation(
		label = 'format_type_mismatch',	
		
		regex = r"format specifies type '[^:]+' but the argument has type '[^:]+'",
			
		explanation = "make sure you are using the correct format code (e.g., `%d` for integers, `%lf` for floating-point values) in your format string on line {line_number}",
		
		reproduce = """
#include <stdio.h>

int main(void) {
	printf("%d\n", "hello!");
}
"""
	),

	
	Explanation(
		label = 'missing_semicolon_line_before_assert',	
		
		regex = r"called object type 'int' is not a function or function pointer",
		
		explanation = "there is probably a syntax error such as missing semi-colon on line {int(line_number) - 1} of {file} or an earlier line",
		
		precondition = lambda message, match: message.highlighted_word == 'assert',
		
		reproduce = """
#include <assert.h>

int main(void) {
	int i = 10
	assert(i == 10);
}
"""
	),
	
	Explanation(
		label = 'assert_without_closing_parenthesis',	
		
		regex = r"unterminated function-like macro invocation",
		
		explanation = "it looks like there is a missing closing bracket on the assert on line {line_number} of {file}",
		
		precondition = lambda message, match: message.highlighted_word == 'assert',
		
		no_following_explanations = True,

		show_note = False,

		reproduce = """
#include <assert.h>

int main(int argc, char *argv[]) {
	assert(argc == 1;
}
"""
	),
	
	Explanation(
		label = 'double_int_literal_conversion',	
		
		regex = r"implicit conversion from 'double' to 'int'",
		
		explanation = "you are assigning the floating point number {emphasize(highlighted_word)} to the int variable {emphasize(underlined_word)} , if this is what you want, change {emphasize(highlighted_word)} to {emphasize(truncate_number(highlighted_word))}",
		

		reproduce = """
int main(int argc, char *argv[]) {
	int i = 6.7;
}
"""
	),
	
	Explanation(
		label = 'assign_to_multidimensional_array',
		
		regex = r"array type .*?\]\[.* is not assignable",
		
		explanation = """you are trying to assign to '{emphasize(underlined_word)}' which is an array.
  You can not assign to a whole array.
  You can use a nested loop to assign to each array element individually.""",
		
		reproduce = """
int main(int argc, char *argv[]) {
	int a[3][1], b[3][1] = {0};
	a = b;
}
"""
	),
	
	Explanation(
		label = 'assign_to_array',
		
		regex = r"array type .*?[^\]]\[(\d+)\]' is not assignable",
		
		explanation = """you are trying to assign to '{emphasize(underlined_word)}' which is an array with {match.group(1)} element{'s' if match.group(1) != '1' else ''}.
  You can not assign to a whole array.
  You can use a loop to assign to each array element individually.""",
		
		long_explanation = True,
		
		reproduce = """
int main(void) {
	int a[1], b[1] = {0};
	a = b;
}
""",
	),
	
	Explanation(
		label = 'stack_use_after_return',
		
		regex = r"address of stack memory associated with local variable '(.*?)' returned",
		
		explanation = """you are trying to return a pointer to the local variable '{emphasize(highlighted_word)}'.
  You can not do this because {emphasize(highlighted_word)} will not exist after the function returns.""",
		
		long_explanation = True,
		
		reproduce = """
int main(void) {
	int i;
	return (int)&i;
}
""",
	),
	
	Explanation(
		label = 'assign_function_to_int',
		
		regex = r"incompatible pointer to integer conversion (assigning to|initializing) '(\w+)'.*\(",
		
		explanation = """you are attempting to assign {emphasize(underlined_word)} which is a function to an {emphasize(match.group(2))} variable.
Perhaps you are trying to call the function and have forgotten the round brackets and any parameter values.""",
		
		long_explanation = True,
		
		reproduce = """
int main(int argc, char *argv[]) {
	int a = main;
}
""",
	),
	
	Explanation(
		label = 'assign_array_to_int',
		
		regex = r"incompatible pointer to integer conversion (assigning to|initializing) '(\w+)'.*]'",
		
		explanation = """you are attempting to assign {emphasize(underlined_word)} which is an array to an {emphasize(match.group(2))} variable.""",
		
		reproduce = """
int main(void) {
	int a[3][3] = {0};
	a[0][0] = a[1];
}
""",
	),
	
	Explanation(
		label = 'assign_pointer_to_int',
		
		regex = r"incompatible pointer to integer conversion (assigning to|initializing) '(\w+)'",
		
		explanation = """you are attempting to assign {emphasize(underlined_word)} which is not an {emphasize(match.group(2))} to an {emphasize(match.group(2))} variable.""",
		
		reproduce = """
int main(int argc, char *argv[]) {
	int a;
	a = &a;
}
""",
	),
	Explanation(
		label = 'missing_library_include',
		
		regex = r"implicitly declaring library function '(\w+)'",
		
		explanation = """You are calling the function {emphasize(match.group(1))} on line {line_number} of {file} but dcc does not recognize {emphasize(match.group(1))} as a function
because you have forgotten to {emphasize('#include <' + extract_system_include_file(note) + '>')}
""",
		show_note = False,
		
		reproduce = """
int main(int argc, char *argv[]) {
	printf("hello");
}
""",
	),
	
	Explanation(
		label = 'misspelt_printf',
		
		regex = r"implicit declaration of function '(print.?.?)' is invalid in C99",
		
		explanation = """you are calling a function named {emphasize(match.group(1))} on line {line_number} of {file} but dcc does not recognize {emphasize(match.group(1))} as a function.
Maybe you meant {emphasize('printf')}?
""",
		no_following_explanations = True,
		
		reproduce = """
#include <stdio.h>
int main(int argc, char *argv[]) {
	print("hello");
}
""",
	),
	
	Explanation(
		label = 'implicit_function_declaration',
		
		regex = r"implicit declaration of function '(\w+)' is invalid in C99",
		
		explanation = """you are calling a function named {emphasize(match.group(1))} line {line_number} of {file} but dcc does not recognize {emphasize(match.group(1))} as a function.
There are several possible causes:
  a) You might have misspelt the function name.
  b) You might need to add a #include line at the top of {file}.
  c) You might need to add a prototype for {emphasize(match.group(1))}.
""",
		no_following_explanations = True,
		
		reproduce = """
int main(int argc, char *argv[]) {
	f();
}
""",
	),
	
	Explanation(
		label = 'expression_not_assignable',
		
		regex = r"expression is not assignable",
		
		explanation = """You are using {emphasize('=')} incorrectly perhaps you meant {emphasize('==')}.
Reminder: you use {emphasize('=')} to assign to a variable.
You use {emphasize('==')} to compare values.		
		""",
		
		reproduce = """
int main(int argc, char *argv[]) {
	if (argc = 1 || argc = 2) {
		return 1;
	}
}
""",
	),
	
	Explanation(
		label = 'uninitialized-local-variable',
		
		regex = r"'(.*)' is used uninitialized in this function",
		
		explanation = """You are using the value of the variable {emphasize(match.group(1))} before assigning a value to {emphasize(match.group(1))}.""",
		
		reproduce = """
int main(void) {
	int a[1];
	return a[0];
}
""",
	),
	
	Explanation(
		label = 'function-variable-clash',
		
		regex = r"called object type .* is not a function or function pointer",
		
		precondition = lambda message, match: re.match(r'^\w+$', message.underlined_word),
		
		long_explanation = True,
		
		explanation = """'{emphasize(underlined_word)}' is the name of a variable but you are trying to call it as a function.
  If '{emphasize(underlined_word)}' is also the name of a function, you can avoid the clash,
  by changing the name of the variable '{emphasize(underlined_word)}' to something else.""",
		
		reproduce = """
int main(void) { 
	int main;
	return main();
}
""",
	),
	
	
	Explanation(
		label = 'function-definition-not-allowed-here',
		
		regex = r"function definition is not allowed here",
		
		precondition = lambda message, match: message.line_number and int(message.line_number) > 1,
		
		long_explanation = True,
		
		explanation = """There is likely a closing brace (curly bracket) missing before line {line_number}.
Is a {emphasize('} missing')} in the previous function?""",
		
		no_following_explanations = True,

		reproduce = """
int f(int a) {
	return a;
	
int main(void) { 
	return f(0);
}
""",
	),
	
	Explanation(
		label = 'indirection-requires-pointer-operand',
		
		regex = r"indirection requires pointer operand \('(.*)' invalid\)",
		
		explanation = """You are trying to use '{emphasize(underlined_word)}' as a pointer.
  You can not do this because '{emphasize(underlined_word)}' is of type {emphasize(match.group(1))}.
""",
		
		reproduce = """
int main(int argc, char *argv[]) {
	return *argc;
}
""",
	),
	
	Explanation(
		label = 'duplicated-cond',
		
		regex = r"duplicated .*\bif\b.* condition",
		
		explanation = """You have repeated the same condition in a chain of if statements.
Only the first if statement using the condition can be executed.
The others can never be executed.

""",
		
		reproduce = """
int main(int argc, char *argv[]) {
	if (argc == 1)
		return 42;
	else if (argc == 1)
		return 43;
	else
		return 44;
}
""",
	),
	
	Explanation(
		label = 'duplicated-branches',
		
		regex = r"condition has identical branches",
		
		explanation = """Your if statement has identical then and else parts.
It is pointless to have an if statement which executes the same code
when its condition is true and also when its condition is false.

""",
		
		reproduce = """
int main(int argc, char *argv[]) {
	if (argc == 1)
		return 42;
	else 
		return 42;
}
""",
	),
	
	Explanation(
		label = 'logical-or-always-true',
		
		regex = r"logical .?\bor\b.* is always true|logical.*or.*of collectively exhaustive tests is always true",
		
		explanation = """Your '{emphasize('||')}' expression is always true, no matter what value variables have.
Perhaps you meant to use '{emphasize('&&')}' ?

""",
		
		reproduce = """
int main(int argc, char *argv[]) {
	if (argc > 1 || argc < 3)
		return 42;
	else 
		return 43;
}
""",
	),
	
	Explanation(
		label = 'logical-and-always-false',
		
		regex = r"logical .?\band\b.* is always false|overlapping comparisons always evaluate to false",
		
		explanation = """Your '{emphasize('&&')}' expression is always false, no matter what value variables have.
Perhaps you meant to use '{emphasize('||')}' ?

""",
		
		reproduce = """
int main(int argc, char *argv[]) {
	if (argc > 1 && argc < 1)
		return 42;
	else 
		return 43;
}
""",
	),
	
	Explanation(
		label = 'logical-equal-expressions',
		
		regex = r"logical .?((and|or)).? of equal expressions",
		
		explanation = """Your have used '{emphasize(highlighted_word)}' with same lefthand and righthand operands.
If this what you meant, it can be simplified: {emphasize('x ' + highlighted_word + ' x')} can be replaced with just {emphasize('x')}.

""",
		
		reproduce = """
int main(int argc, char *argv[]) {
	if (argc > 1 ||argc > 1)
		return 42;
	else 
		return 43;
}
""",
	),
	
	Explanation(
		label = 'shadow-local-variable',
		
		regex = r"declaration shadows a local variable",
		
		explanation = """Your already have a variable named '{emphasize(highlighted_word)}'.
It is confusing to have a second overlapping declaration of the same variable name.

""",
		
		reproduce = """
int main(int argc, char *argv[]) {
	{
		int argc = 42;
		return argc;
	}
}
""",
	),
	
	Explanation(
		label = 'nonnull',
		
		regex = r"argument (\d+) null where non-null expected",
		
		explanation = """You are passing {extract_argument_variable(highlighted_word, match.group(1), emphasize)} which always contains NULL as {emphasize('argument ' + match.group(1))} to '{emphasize(extract_function_name(highlighted_word))}'.
{emphasize('Argument ' + match.group(1))} to '{emphasize(extract_function_name(highlighted_word))}' should never be NULL.

""",
		
		reproduce = """
#include <unistd.h>

int main(void) {
	char *pathname = NULL;
	faccessat(0, pathname, 0, 0);
}
""",
	),
]

def extract_function_name(string):
	return re.sub(r'\(.*', '', string)

def extract_argument_variable(string, argument_number, emphasize):
	string = re.sub(r'.*?\(', '', string)
	string = re.sub(r'\)$', '', string)
	string = string.strip()
	variable_name = ''
	if not re.match('\(.*,.*\)', string):
		try:
			n = int(argument_number)
			variable_name = string.split(',')[n - 1].strip()
		except (ValueError,IndexError):
			pass
	if re.match('^[_a-z]\w*$', variable_name):
		return 'the variable ' + emphasize(variable_name)
	else:
		return 'a variable ' + emphasize(variable_name)
		
def extract_system_include_file(string):
	m = re.search(r'<(.*?)>', str(string))
	return m.group(1) if m else ''

import math
def truncate_number(num):
	try:
		return str(math.trunc(float(num)))
	except ValueError:
		return str(num)
		
if __name__ == '__main__':
	if sys.argv[1:] and sys.argv[1] == "--create_test_files":
		for explanation in explanations:
			if explanation.label and explanation.reproduce:
				with open(explanation.label + ".c", "w") as f:
					f.write(explanation.reproduce)
