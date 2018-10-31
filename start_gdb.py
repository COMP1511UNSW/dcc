import os, sys, signal, subprocess

def start_gdb(gdb_driver_file=sys.argv[0]):
	signal.signal(signal.SIGINT, handler)
	debug = int(os.environ.get('DCC_DEBUG', '0'))
	if debug: print(sys.argv, 'DCC_RUN_INSIDE_GDB="%s" DCC_PID="%s"' % (os.environ.get('DCC_RUN_INSIDE_GDB', ''), os.environ.get('DCC_PID', '')))
	os.environ['DCC_RUN_INSIDE_GDB'] = 'true'
	os.environ['PATH'] = '/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:' + os.environ.get('PATH', '')
	os.environ['LC_ALL'] = 'C' # stop invalid utf-8 from gdb throwing Python exception
	
	command = ["gdb", "--nx", "--batch", "-ex", "python exec(open('%s').read())" % gdb_driver_file, os.environ['DCC_BINARY']]
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
#	if debug: print >>sys.stderr, 'signal caught'
	kill_program()
	
if __name__ == '__main__':
	start_gdb(gdb_driver_file='drive_gdb.py')
