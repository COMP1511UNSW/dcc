#!/usr/bin/env python3

import re, sys
from help_cs50 import help_cs50
from compiler_explanations import get_explanation

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

		explanation = get_explanation(message, args.colorize_output)
		if explanation:
			explanation_text = explanation.text
		else:
			# FIXME - replace all cs50 explanations
			explanation_text = help_cs50(message.text_without_ansi_codes)
			
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

		prefix = ansi_colorize("dcc explanation:", BLUE, args.colorize_output)
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

			caret_index = colorless_next_line.index('^')
			previous_line = e.text_without_ansi_codes[-1]
			m = re.match(r"^\w*", previous_line[caret_index:])
			e.highlighted_word = m.group(0)

			# can multiple words be underlined?
			e.underlined_word = ''
			m = re.match(r"^(.*?)~+", colorless_next_line)
			if m:
				e.underlined_word = previous_line[len(m.group(1)):len(m.group(0))]

		e.text.append(next_line)
		e.text_without_ansi_codes.append(colorless_next_line)


	return (e, lines)

def remove_ansi_codes(string):
	return re.sub(r'\x1b[^m]*m', '', string)



def ansi_colorize(string, color, colorize=True):
	if colorize:
		return color + string + ANSI_DEFAULT
	else:
		return string
	
ANSI_DEFAULT = "\033[0m"
BLUE = ANSI_DEFAULT + "\033[34m"
RED = ANSI_DEFAULT + "\033[31m"