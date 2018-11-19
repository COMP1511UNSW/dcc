#!/usr/bin/env python3

# andrewt@unsw.edu.au May 2013-
# compile a C program with runtime checking enabled
# run-time errors are intercepted and an explanation
# printed in a form comprehensible to beginner programmers
# using	 information obtained from	gdb
# clang errors are explained using matcher from https://github.com/cs50/help50

# This program can be executed in 4 ways
#
# 1) Invoked by the user from the command line to do the compilation
#	 the binary produced has code added which intercepts runtime errors and runs this program
#
# 2) invoked from the C binary when a runtime error occurs - it then runs gdb (--no_embed_source only)
#
# 3) invoked via gdb to print details of the program state when the runtime error occurred (--no_embed_source only)
#
# 4) invoked from the C binary to watch for valgrind errors on stdin when using valgrind
#
# The above 4 execution modes have been bundled into one file to simplify installation 
#
# Unless the --no_embed_source option is specified, a tar file is embedded in the binary
# containing the C source files for the user's program plus the files start_gdb.py and drive_gdb.py
#
# If a runtime error occurs the tar file is extracted into a temporary directory
# and start_gdb.py starts gdb controlled by drive_gdb.py to print details of the program state
#
# --valgrind currently implies --no_embed_source option


import os, re, signal, sys
from start_gdb import start_gdb
from drive_gdb import drive_gdb
from compile import compile

def handler(signum, frame):
	sys.exit(1)

def main():
	signal.signal(signal.SIGINT, handler)
	debug = int(os.environ.get('DCC_DEBUG', '0'))
	colorize_output = sys.stderr.isatty() or os.environ.get('DCC_COLORIZE_OUTPUT', False)
	if debug: print(sys.argv, 'DCC_RUN_INSIDE_GDB="%s" DCC_PID="%s"' % (os.environ.get('DCC_RUN_INSIDE_GDB', ''), os.environ.get('DCC_PID', '')))
	if not sys.argv[1:] and 'DCC_RUN_INSIDE_GDB' in os.environ:
		drive_gdb()
	elif not sys.argv[1:] and 'DCC_PID' in os.environ:
		# we are invoked by the binary because an error has occurred
		start_gdb()
	elif sys.argv[1:] == ['--watch-stdin-for-valgrind-errors']:
		# valgrind is being used - we have been invoked via the binary to watch for valgrind errors
		# which have been directed to our stdin
		while True:
			line = sys.stdin.readline()
			if not line:
				break
			if debug: print('valgrind: ', line, file=sys.stderr)
			if 'vgdb me' in line:
				if colorize_output:
					os.environ['DCC_VALGRIND_ERROR'] = 'Runtime error: \033[31muninitialized variable accessed.\033[0m'
				else:
					os.environ['DCC_VALGRIND_ERROR'] = 'Runtime error: uninitialized variable accessed.'
				print('\n'+os.environ['DCC_VALGRIND_ERROR'], file=sys.stderr)
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
	else:
		compile()

if __name__ == '__main__':
	main()
