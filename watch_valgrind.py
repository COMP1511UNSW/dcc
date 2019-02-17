import os, re, sys, signal, subprocess
from start_gdb import start_gdb
import colors

# valgrind is being used - we have been invoked via the binary to watch for valgrind errors
# which have been directed to our stdin
def watch_valgrind():
	colorize_output = sys.stderr.isatty() or os.environ.get('DCC_COLORIZE_OUTPUT', False)
	if colorize_output:
		color = colors.color
	else:
		color = lambda text, color_name: text

	debug = int(os.environ.get('DCC_DEBUG', '0'))
	if debug: print('watch_valgrind() running', file=sys.stderr)
	while True:
		line = sys.stdin.readline()
		if not line:
			break
		if debug: print('valgrind: ', line, file=sys.stderr)

		if 'vgdb me' in line:
			error = 'Runtime error: ' + color('uninitialized variable accessed.', 'red')
			os.environ['DCC_VALGRIND_ERROR'] = error
			print('\n' + error, file=sys.stderr)
			sys.stderr.flush()
			start_gdb()
			sys.exit(0)
		elif 'loss record' in line:
			line = sys.stdin.readline()
			if 'malloc' in line:
				line = sys.stdin.readline()
				m = re.search(r'(\S+)\s*\((.+):(\d+)', line)
				if m:
					print('Error: free not called for memory allocated with malloc in function {} in {} at line {}.'.format(m.group(1),m.group(2),m.group(3)), file=sys.stderr)
				else:
					print('Error: free not called for memory allocated with malloc.', file=sys.stderr)
			else:
				print('Error: memory allocated not de-allocated.', file=sys.stderr)
			sys.exit(0)
	
if __name__ == '__main__':
	watch_valgrind()
