import os, re, sys, signal, subprocess

def start_gdb(gdb_driver_file='drive_gdb.py'):
	signal.signal(signal.SIGINT, handler)
	debug = int(os.environ.get('DCC_DEBUG', '0'))
	if debug: print(sys.argv, 'DCC_RUN_INSIDE_GDB="%s" DCC_PID="%s"' % (os.environ.get('DCC_RUN_INSIDE_GDB', ''), os.environ.get('DCC_PID', '')))
	os.environ['DCC_RUN_INSIDE_GDB'] = 'true'
	os.environ['PATH'] = '/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:' + os.environ.get('PATH', '')
	os.environ['LC_ALL'] = 'C' # stop invalid utf-8  throwing Python exception with gdb - still needed?
	if os.path.exists(gdb_driver_file):
		command = ["gdb", "--nx", "--batch", "-ex", "python exec(open('%s', encoding='utf-8', errors='replace').read())" % gdb_driver_file, os.environ['DCC_BINARY']]
	else:
		from embedded_source import embedded_source_drive_gdb_py
		command = ["gdb", "--nx", "--batch", "-ex", "python exec(r\"\"\"" + embedded_source_drive_gdb_py + "\"\"\")", os.environ['DCC_BINARY']]
	if debug: print('running:', command)
	# gdb puts confusing messages on stderr & stdout  so send these to /dev/null
	# and use file descriptor 3 for our messages
	os.dup2(2, 3)
	try:
		if debug:
			p = subprocess.Popen(command, stdin=subprocess.DEVNULL, close_fds=False)
		else:
			p = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=False)
		p.communicate()
	except OSError:
		print('\ngdb not available to print variable values\n', file=sys.stderr)
	kill_program()

#
# ensure the program compiled with dcc terminates after error
#
def kill_program():
	if 'DCC_PID' in os.environ:
		try:
			os.kill(int(os.environ['DCC_PID']), signal.SIGPIPE)
			os.kill(int(os.environ['DCC_PID']), signal.SIGKILL)
		except ProcessLookupError:
			pass
	sys.exit(1)

def handler(signum, frame):
	kill_program()

	
# valgrind is being used - we have been invoked via the binary to watch for valgrind errors
# which have been directed to our stdin
def watch_stdin_for_valgrind_errors():
	colorize_output = sys.stderr.isatty() or os.environ.get('DCC_COLORIZE_OUTPUT', False)
	if colorize_output:
		color = colors.color
	else:
		color = lambda text, color_name: text
	debug = int(os.environ.get('DCC_DEBUG', '0'))
	while True:
		line = sys.stdin.readline()
		if not line:
			break
		if debug: print('valgrind: ', line, file=sys.stderr)
		if 'vgdb me' in line:
			error = 'Runtime error: ' + color('uninitialized variable accessed', 'red') + '.'
			os.environ['DCC_VALGRIND_ERROR'] = error
			print('\n'+error, file=sys.stderr)
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
	if sys.argv[1:] == ['--watch-stdin-for-valgrind-errors']:
		watch_stdin_for_valgrind_errors()
	else:
		start_gdb()
