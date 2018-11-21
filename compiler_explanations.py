#!/usr/bin/env python3

import copy, re, sys
import colors

DEFAULT_EXPLANATION_URL = "https://comp1511unsw.github.io/dcc/"

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
#               available as local variables, and the result return as the explanation
#
# show_note - print any note on clang warning
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
			url = self.long_explanation_url or DEFAULT_EXPLANATION_URL + self.label + '.html'
			explanation += "\n  See more information here: " + url
		return explanation

	def get_short_explanation(self, message, colorize_output):
		match = None
		if self.regex:
			match = re.search(self.regex, "\n".join(message.text), flags=re.I|re.DOTALL)
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
			color = lambda text, color_name: text

		parameters = dict((name, getattr(message, name)) for name in dir(message) if not name.startswith('__'))
		parameters['match'] = match
		parameters['color'] = color
		parameters['emphasize'] = lambda text: color(text, 'red')
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
		
		explanation = "there is probably a missing closing bracket on the assert on {line_number} of {file}",
		
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
]


if __name__ == '__main__':
	if sys.argv[1:] and sys.argv[1] == "--create_test_files":
		for explanation in explanations:
			if explanation.label and explanation.reproduce:
				with open(explanation.label + ".c", "w") as f:
					f.write(explanation.reproduce)
