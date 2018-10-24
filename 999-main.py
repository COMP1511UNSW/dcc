if __name__ == '__main__':
	signal.signal(signal.SIGINT, handler)
	if debug: print(sys.argv, 'DCC_RUN_INSIDE_GDB="%s" DCC_SANITIZER="%s"' % (os.environ.get('DCC_RUN_INSIDE_GDB', ''), os.environ.get('DCC_PID', '')))
	if not sys.argv[1:] and 'DCC_RUN_INSIDE_GDB' in os.environ:
		# we are invoked by gdb 
		import gdb
		explain_error()
		gdb_execute('call _exit()')
		gdb_execute('quit')
		kill_program()
	elif not sys.argv[1:] and 'DCC_PID' in os.environ:
		# we are invoked by the binary because an eror has occurred
		run_gdb()
	elif sys.argv[1:] == ['--watch-stdin-for-valgrind-errors']:
		# valgrind is being used - we have been invoked viq the binary to watch for valgrind errors
		# which have been directed to our stdin
		while True:
			line = sys.stdin.readline()
			if not line:
				break
			debug_print(1, 'valgrind: ', line)
			if 'vgdb me' in line:
				if colorize_output:
					os.environ['DCC_VALGRIND_ERROR'] = 'Runtime error: \033[31muninitialized variable accessed.\033[0m'
				else:
					os.environ['DCC_VALGRIND_ERROR'] = 'Runtime error: uninitialized variable accessed.'
				print('\n'+os.environ['DCC_VALGRIND_ERROR'], file=sys.stderr)
				sys.stderr.flush()
				run_gdb()
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
		# we are invoked by user to compile a program
		os.environ['PATH'] = os.path.dirname(os.path.realpath(sys.argv[0])) + ':/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:' + os.environ.get('PATH', '') 
		compile()
