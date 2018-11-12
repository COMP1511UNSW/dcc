import re, sys

ANSI_DEFAULT = "\033[0m"
ANSI_BLUE = ANSI_DEFAULT + "\033[34m"

def explain_compiler_output(output, args):
	lines = output.splitlines()
	explanations_made = set()
	errors_explained = 0
	last_message = None
	
	while lines and (not errors_explained or len(explanations_made) < args.max_explanations):
		message, lines = get_next_message(lines)
		if not message:
			print(lines.pop(0), file=sys.stderr)
			continue
			
		if message.is_same_line(last_message):
			# skip if there are two errors for one line
			# often the second message is unhelpful
			continue

		if message.type == "warning" and len(explanations_made) >= args.max_explanations:
			# skip warnings if we have made max_explanations
			# we don't exit because we want to print the first error if there is on3
			continue


		last_message = message

		if args.debug:
			print('message for explanation:', message.text_without_ansi_codes, file=sys.stderr)

		explanation = None
		for explanation in explanations:
			explanation_text  = explanation.get(message)
			if explanation_text:
				break
		
		# FIXME - replace all cs50 explanations
			
		if not explanation_text:
			explanation_text = help_cs50(message.text_without_ansi_codes)
			explanation = None
			
		if args.debug:
			print('explanation_text:', explanation_text, file=sys.stderr)

		message_lines = message.text
		if not explanation or explanation.show_note:
			message_lines += message.note
		text = '\n'.join(message_lines)
		if message.has_ansi_codes():
			text += ANSI_DEFAULT
		print(text, file=sys.stderr)
		
		if not explanation_text:
			continue # should we give up when we get a message for which we don't have an explanation?

		# remove any reference to specific line and check if we've already made this explanation
		e = re.sub('line.*', '', explanation_text, flags=re.I)
		if e in explanations_made:
			continue
		explanations_made.add(e)

		if message.type == 'error':
			errors_explained += 1

		prefix = ANSI_BLUE + "dcc explanation:" + ANSI_DEFAULT if args.colorize_output else "dcc explanation:"
		print(prefix, explanation_text, file=sys.stderr)
			
		if  explanation and explanation.no_following_explanations:
			break
			
	if lines and lines[-1].endswith(' generated.'):
		lines[-1] = re.sub(r'\d .*', '', lines[-1])

	# if we explained 1 or more errors, don't output any remaining compiler output
	# often its confusing parasitic errors
	#
	# if we didn't explain any messages, just pass through all compiler output
	#
	if not errors_explained:
		print('\n'.join(lines), file=sys.stderr)

class Message():
	file = ""
	line_number = ""
	column = ""
	type = ""
	text = []
	text_without_ansi_codes = []
	note = []
	note_without_ansi_codes = []
	highlighted_word = ''
	
	def is_same_line(self, message):
		return message and (message.file, message.line_number) == (self.file, self.line_number)

	def has_ansi_codes(self):
		return self.text != self.text_without_ansi_codes or self.note != self.note_without_ansi_codes


def get_next_message(lines):
	if not lines:
		return (None, lines)
	line = lines[0]
	colorless_line = remove_ansi_codes(line)
	m = re.match(r'^(\S.*?):(\d+):', colorless_line)
	if not m:
		return (None, lines)
	lines.pop(0)
	e = Message()
	e.file, e.line_number = m.groups()
	m = re.match(r'^\S.*?:\d+:(\d+):\s*(.*?):', colorless_line)
	if m:
		e.column, e.type = m.groups()

	e.text = [line]
	e.text_without_ansi_codes = [colorless_line]
	parsing_note = False

	while lines:
		next_line = lines[0]
		if not next_line:
			break
		colorless_next_line = remove_ansi_codes(lines[0])
		m = re.match(r'^\S.*:\d+:', colorless_next_line)
		if m:
			if re.match(r'^\S.*?:\d+:\d+:\s*note:', colorless_next_line):
				parsing_note = True
			else:
				break

		lines.pop(0)
		
		if colorless_next_line.endswith(' generated.'):
			break
			
		if parsing_note:
			e.note.append(next_line)
			e.note_without_ansi_codes.append(colorless_next_line)
			continue
		
		if re.match(r"^[ ~]*\^[ ~]*$", colorless_next_line):
			index = colorless_next_line.index("^")
			previous_line = e.text_without_ansi_codes[-1]
			m = re.match(r"^\w*", previous_line[index:])
			e.highlighted_word = m.group(0)
			
		e.text.append(next_line)
		e.text_without_ansi_codes.append(colorless_next_line)


	return (e, lines)

def remove_ansi_codes(string):
	return re.sub(r'\x1b[^m]*m', '', string)


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

	def __init__(self, label=None, precondition=None, regex=None, explanation=None, no_following_explanations=False, show_note=True, reproduce=''):
		self.label = label
		self.precondition = precondition
		self.regex = regex
		self.explanation = explanation
		self.no_following_explanations = no_following_explanations
		self.show_note = show_note
		self.reproduce = reproduce
		
	def get(self, message):
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
			
		parameters = dict((name, getattr(message, name)) for name in dir(message) if not name.startswith('__'))
		parameters['match'] = match
		return eval('f"' + self.explanation +'"',  globals(), parameters)


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
			
		explanation = "Perhaps you have forgotten an '&' before {highlighted_word} on line {line_number}.",
		
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
]


if __name__ == '__main__':
	if sys.argv[1:] and sys.argv[1] == "--create_test_files":
		for explanation in explanations:
			if explanation.label and explanation.reproduce:
				with open(explanation.label + ".c", "w") as f:
					f.write(explanation.reproduce)
