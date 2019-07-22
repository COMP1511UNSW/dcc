#!/usr/bin/env python3

# andrewt@unsw.edu.au May 2013-2019

#
# Unless the --no_embed_source option is specified, a tar file is embedded in the binary
# containing the C source files for the user's program plus the files start_gdb.py and drive_gdb.py
#
# If a runtime error occurs the tar file is extracted into a temporary directory
# and start_gdb.py starts gdb controlled by drive_gdb.py to print details of the program state


import os, re, signal, sys
from start_gdb import start_gdb, watch_stdin_for_valgrind_errors
from drive_gdb import drive_gdb
from watch_valgrind import watch_valgrind
from compile import compile

def handler(signum, frame):
	sys.exit(1)

# This program can be executed in 4 ways
#
# 1) Invoked by the user from the command line to do the compilation
#
# 2) invoked from the C binary when a runtime error occurs - it then runs gdb (--no_embed_source only)
#
# 3) invoked via gdb to print details of the program state when the runtime error occurred (--no_embed_source only)
#
# 4) invoked from the C binary to watch for valgrind errors on stdin when using valgrind (--valgrind --no_embed_source only)

def main():
	signal.signal(signal.SIGINT, handler)
	debug = int(os.environ.get('DCC_DEBUG', '0'))
	colorize_output = sys.stderr.isatty() or os.environ.get('DCC_COLORIZE_OUTPUT', False)
	if debug > 1: print(sys.argv, 'DCC_RUN_INSIDE_GDB="%s" DCC_PID="%s"' % (os.environ.get('DCC_RUN_INSIDE_GDB', ''), os.environ.get('DCC_PID', '')), file=sys.stderr)
	if not sys.argv[1:] and 'DCC_RUN_INSIDE_GDB' in os.environ:
		drive_gdb()
	elif not sys.argv[1:] and 'DCC_PID' in os.environ:
		# we are invoked by the binary because an error has occurred
		start_gdb()
	elif sys.argv[1:] == ['--watch-stdin-for-valgrind-errors']:
		watch_valgrind()
	else:
		compile()

if __name__ == '__main__':
	main()
