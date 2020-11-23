import os, re, sys, signal
from start_gdb import start_gdb, kill_sanitizer2
from util import explanation_url
import colors

# valgrind is being used - we have been invoked via the binary to watch for valgrind errors
# which have been directed to our stdin
def watch_valgrind():
	colorize_output = sys.stderr.isatty() or os.environ.get('DCC_COLORIZE_OUTPUT', False)
	if colorize_output:
		color = colors.color
	else:
		color = lambda text, color_name: text

	debug_level = int(os.environ.get('DCC_DEBUG', '0'))
	if debug_level > 1: print('watch_valgrind() running', file=sys.stderr)
	while True:
		line = sys.stdin.readline()
		if not line:
			break
		if debug_level > 1: print('valgrind: ', line, file=sys.stderr, end='')

		if 'vgdb me' in line:
			error = 'Runtime error: ' + color('uninitialized variable accessed.', 'red')
			os.environ['DCC_VALGRIND_ERROR'] = error
			print('\n' + error, file=sys.stderr)
			sys.stderr.flush()
			start_gdb()
			break
		elif 'exit_group(status)' in line:
			error = f"""Runtime error: {color('exit value is uninitialized', 'red')}

Main is returning an uninitialized value or exit has been passed an uninitialized value.
"""
			print('\n' + error, file=sys.stderr)
			# too late to start gdb as the program is exiting
			# we kill sanitizer2 as it is waiting for gdb
			kill_sanitizer2()
			sys.exit(1)
		elif 'below stack pointer' in line:
			error = f"""Runtime error: {color('access to function variables after function has returned', 'red')}
You have used a pointer to a local variable that no longer exists.
When a function returns its local variables are destroyed.

For more information see: {explanation_url("stack_use_after_return")}'
"""
			os.environ['DCC_VALGRIND_ERROR'] = error
			print('\n' + error, file=sys.stderr)
			sys.stderr.flush()
			start_gdb()
			break
		elif 'Invalid write of size' in line:
			error = f"""Runtime error: invalid assignment.
A huge local array can produce this error.
"""
			os.environ['DCC_VALGRIND_ERROR'] = error
			print('\n' + error, file=sys.stderr)
			sys.stderr.flush()
			start_gdb()
			break
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
			break
	if debug_level > 1: print('watch_valgrind() - exiting', file=sys.stderr)
	sys.exit(0)
	
if __name__ == '__main__':
	signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(1))
	watch_valgrind()
